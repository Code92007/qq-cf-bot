from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from .config import Config
from .core import ChallengeActor, ChallengeError, ChallengeService, SubmissionOutcome
from .models import ActiveProblem, CodeSubmission, ProblemStatement, UserStat
from .rating import leaderboard_rating
from .renderer import _markdown_to_html
from .security import redact_sensitive_text


LOGGER = logging.getLogger(__name__)

_SESSION_COOKIE = "cf_session"
_WEB_LEADERBOARD_ID = -1
_WEB_SCOPE_OFFSET = 1_000_000_000_000
_USERNAME_RE = re.compile(r"[A-Za-z0-9_-]{3,24}")
_LANGUAGES = {"cpp", "c", "java", "py", "python"}
_DUMMY_PASSWORD_HASH = "pbkdf2_sha256$310000$00000000000000000000000000000000$" + ("00" * 32)


class WebApplication:
    def __init__(self, config: Config, service: ChallengeService) -> None:
        self.config = config
        self.service = service
        self.static_dir = Path(__file__).with_name("web")
        self._locks: Dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def handle_get(self, handler, path: str) -> bool:
        if not self.config.web_enabled:
            return False
        try:
            if path == "/api/state":
                session = self._require_session(handler)
                self._json(handler, self._state(session))
                return True
            if path == "/api/leaderboard":
                self._json(handler, {"leaderboard": self._leaderboard()})
                return True
            if path in {"/", "/index.html"}:
                self._static(handler, "index.html", "text/html; charset=utf-8", no_cache=True)
                return True
            static_files = {
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            }
            target = static_files.get(path)
            if target:
                self._static(handler, target[0], target[1])
                return True
            return False
        except ChallengeError as exc:
            self._json(handler, {"error": exc.code, "message": exc.message}, status=exc.status)
            return True

    def handle_post(self, handler, path: str) -> bool:
        if not self.config.web_enabled or not path.startswith("/api/"):
            return False
        try:
            payload = self._read_json(handler)
            if path == "/api/auth/register":
                self._register(handler, payload)
                return True
            if path == "/api/auth/login":
                self._login(handler, payload)
                return True

            session = self._require_session(handler)
            self._require_csrf(handler, session)
            if path == "/api/auth/logout":
                self._logout(handler)
                return True

            lock = self._user_lock(session["user_id"])
            if not lock.acquire(blocking=False):
                raise ChallengeError("operation_in_progress", "上一个操作还在处理中。", 409)
            try:
                if path == "/api/challenges":
                    self._new_challenge(handler, session, payload)
                elif path == "/api/challenges/giveup":
                    self._give_up(handler, session)
                elif path == "/api/challenges/oral":
                    self._oral_submit(handler, session, payload)
                elif path == "/api/challenges/code":
                    self._code_submit(handler, session, payload)
                else:
                    return False
            finally:
                lock.release()
            return True
        except ChallengeError as exc:
            self._json(handler, {"error": exc.code, "message": exc.message}, status=exc.status)
            return True
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(handler, {"error": "invalid_request", "message": str(exc) or "请求格式不正确。"}, status=400)
            return True
        except Exception as exc:
            LOGGER.exception("web request failed path=%s", path)
            safe = redact_sensitive_text(str(exc))
            LOGGER.warning("web request error summary path=%s error=%s", path, safe[:200])
            self._json(handler, {"error": "service_unavailable", "message": "服务暂时不可用，请稍后重试。"}, status=503)
            return True

    def _register(self, handler, payload: dict) -> None:
        if not self.config.web_registration_enabled:
            raise ChallengeError("registration_disabled", "当前已关闭新用户注册。", 403)
        username = str(payload.get("username") or "").strip().lower()
        display_name = str(payload.get("displayName") or "").strip()
        password = str(payload.get("password") or "")
        if not _USERNAME_RE.fullmatch(username):
            raise ValueError("用户名需为 3-24 位字母、数字、下划线或短横线。")
        if not display_name or len(display_name) > 32 or any(ord(char) < 32 for char in display_name):
            raise ValueError("显示名需为 1-32 个可见字符。")
        _validate_password(password)
        try:
            user = self.service.store.create_web_user(username, display_name, _hash_password(password))
        except ValueError as exc:
            raise ChallengeError("username_taken", "这个用户名已经被使用。", 409) from exc
        self._create_session_response(handler, user, status=201)

    def _login(self, handler, payload: dict) -> None:
        username = str(payload.get("username") or "").strip().lower()
        password = str(payload.get("password") or "")
        user = self.service.store.get_web_user_by_username(username)
        encoded = user["password_hash"] if user is not None else _DUMMY_PASSWORD_HASH
        password_ok = _verify_password(password, encoded)
        if user is None or not password_ok:
            raise ChallengeError("invalid_credentials", "用户名或密码不正确。", 401)
        self._create_session_response(handler, user)

    def _logout(self, handler) -> None:
        token = self._cookie_token(handler)
        if token:
            self.service.store.delete_web_session(_token_hash(token))
        self._json(
            handler,
            {"ok": True},
            extra_headers={"Set-Cookie": self._expired_cookie()},
        )

    def _new_challenge(self, handler, session: dict, payload: dict) -> None:
        min_rating = _rating_value(payload.get("minRating"))
        max_rating = _rating_value(payload.get("maxRating"))
        if min_rating > max_rating:
            min_rating, max_rating = max_rating, min_rating
        actor = self._actor(session)
        rating_range = self.service.set_rating_range(actor.scope_id, min_rating, max_rating)
        self.service.issue_problem(actor.scope_id, rating_range)
        self._json(handler, {"ok": True, "state": self._state(session)})

    def _give_up(self, handler, session: dict) -> None:
        active = self.service.give_up(self._actor(session).scope_id)
        self._json(
            handler,
            {"ok": True, "resolved": _revealed_problem(active), "state": self._state(session)},
        )

    def _oral_submit(self, handler, session: dict, payload: dict) -> None:
        submission = str(payload.get("solution") or "").strip()
        if len(submission) > 20_000:
            raise ValueError("做法说明不能超过 20000 个字符。")
        outcome = self.service.submit_solution(self._actor(session), submission)
        self._json(handler, self._outcome_payload(session, outcome))

    def _code_submit(self, handler, session: dict, payload: dict) -> None:
        language = str(payload.get("language") or self.config.cf_submit_default_language).strip().lower()
        if language not in _LANGUAGES:
            raise ValueError("当前仅支持 C++、C、Java 和 Python。")
        source = str(payload.get("source") or "")
        if len(source) > 128_000:
            raise ValueError("代码不能超过 128000 个字符。")
        outcome = self.service.submit_code(
            self._actor(session),
            CodeSubmission(language=language, source=source),
        )
        self._json(handler, self._outcome_payload(session, outcome))

    def _outcome_payload(self, session: dict, outcome: SubmissionOutcome) -> dict:
        payload: dict = {
            "ok": True,
            "accepted": outcome.accepted,
            "message": outcome.reason,
            "state": self._state(session),
        }
        if outcome.accepted:
            payload["resolved"] = _revealed_problem(outcome.active)
        if outcome.stat is not None:
            payload["rating"] = round(outcome.leaderboard_rating or outcome.stat.rating, 2)
            payload["solvedCount"] = outcome.stat.solved_count
        if outcome.remote_result is not None:
            result = outcome.remote_result
            payload["verdict"] = {
                "code": result.verdict,
                "message": result.message,
                "submissionId": result.submission_id,
                "passedTests": result.passed_tests,
                "timeMs": result.time_ms,
                "memoryKb": result.memory_bytes // 1024 if result.memory_bytes is not None else None,
                "url": result.url if outcome.accepted else "",
            }
        return payload

    def _state(self, session: dict) -> dict:
        actor = self._actor(session)
        active = self.service.get_active_problem(actor.scope_id)
        rating_range = self.service.get_rating_range(actor.scope_id)
        stat = self.service.get_user_stat(actor)
        return {
            "authenticated": True,
            "csrfToken": session["csrf_token"],
            "user": {
                "id": session["user_id"],
                "username": session["username"],
                "displayName": session["display_name"],
            },
            "ratingRange": {"min": rating_range.min_rating, "max": rating_range.max_rating},
            "me": _stat_json(stat),
            "active": _active_json(active, self.service.giveup_wait_seconds(active)) if active else None,
            "leaderboard": self._leaderboard(),
            "capabilities": {
                "oralJudge": self.service.judge.configured,
                "codeJudge": self.config.cf_submit_enabled and self.service.remote_judge.configured,
                "registration": self.config.web_registration_enabled,
            },
        }

    def _leaderboard(self) -> list:
        return [
            {**_stat_json(stat), "rank": index}
            for index, stat in enumerate(self.service.list_leaderboard(_WEB_LEADERBOARD_ID)[:50], start=1)
        ]

    def _actor(self, session: dict) -> ChallengeActor:
        user_id = int(session["user_id"])
        return ChallengeActor(
            scope_id=-(_WEB_SCOPE_OFFSET + user_id),
            leaderboard_id=_WEB_LEADERBOARD_ID,
            user_id=user_id,
            display_name=str(session["display_name"]),
        )

    def _create_session_response(self, handler, user: dict, status: int = 200) -> None:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(hours=max(1, self.config.web_session_hours))
        self.service.store.create_web_session(_token_hash(token), int(user["id"]), csrf_token, expires.isoformat())
        session = {
            "user_id": int(user["id"]),
            "username": str(user["username"]),
            "display_name": str(user["display_name"]),
            "csrf_token": csrf_token,
        }
        self._json(
            handler,
            {"ok": True, "state": self._state(session)},
            status=status,
            extra_headers={"Set-Cookie": self._session_cookie(token)},
        )

    def _require_session(self, handler) -> dict:
        token = self._cookie_token(handler)
        session = self.service.store.get_web_session(_token_hash(token)) if token else None
        if session is None:
            raise ChallengeError("authentication_required", "请先登录。", 401)
        return session

    def _require_csrf(self, handler, session: dict) -> None:
        supplied = str(handler.headers.get("X-CSRF-Token") or "")
        if not supplied or not hmac.compare_digest(supplied, session["csrf_token"]):
            raise ChallengeError("invalid_csrf", "页面会话已失效，请刷新后重试。", 403)

    def _cookie_token(self, handler) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(handler.headers.get("Cookie") or "")
        except Exception:
            return ""
        morsel = cookie.get(_SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _read_json(self, handler) -> dict:
        raw_length = handler.headers.get("Content-Length") or "0"
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("无效的请求长度。") from exc
        if length < 0 or length > self.config.web_max_body_bytes:
            raise ChallengeError("request_too_large", "请求内容过大。", 413)
        if length == 0:
            return {}
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("请求内容必须是 JSON 对象。")
        return payload

    def _user_lock(self, user_id: int) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(user_id, threading.Lock())

    def _session_cookie(self, token: str) -> str:
        parts = [
            f"{_SESSION_COOKIE}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={max(1, self.config.web_session_hours) * 3600}",
        ]
        if self.config.web_cookie_secure:
            parts.append("Secure")
        return "; ".join(parts)

    def _expired_cookie(self) -> str:
        parts = [f"{_SESSION_COOKIE}=", "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"]
        if self.config.web_cookie_secure:
            parts.append("Secure")
        return "; ".join(parts)

    def _static(self, handler, filename: str, content_type: str, no_cache: bool = False) -> None:
        data = (self.static_dir / filename).read_bytes()
        handler.send_response(200)
        self._security_headers(handler)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", "no-store" if no_cache else "public, max-age=300")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _json(self, handler, payload: dict, status: int = 200, extra_headers: Optional[dict] = None) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        handler.send_response(status)
        self._security_headers(handler)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            handler.send_header(name, value)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    @staticmethod
    def _security_headers(handler) -> None:
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("X-Frame-Options", "DENY")
        handler.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https: http:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )


def _rating_value(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("难度必须是整数。")
    try:
        rating = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("难度必须是整数。") from exc
    if rating < 800 or rating > 4000 or rating % 100:
        raise ValueError("难度需为 800-4000 之间的整百数。")
    return rating


def _validate_password(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("密码长度需为 8-128 个字符。")


def _hash_password(password: str) -> str:
    iterations = 310_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(raw_salt),
            int(raw_iterations),
        )
        return hmac.compare_digest(digest, bytes.fromhex(raw_digest))
    except (TypeError, ValueError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _stat_json(stat: UserStat) -> dict:
    return {
        "userId": stat.user_id,
        "displayName": stat.display_name,
        "solvedCount": stat.solved_count,
        "rating": round(leaderboard_rating(stat.solved_ratings, stat.rating), 2),
        "highestSolved": stat.solved_ratings[0] if stat.solved_ratings else None,
    }


def _active_json(active: ActiveProblem, giveup_wait: int) -> dict:
    statement = active.statement
    return {
        "createdAt": active.created_at,
        "giveupWaitSeconds": giveup_wait,
        "statement": {
            "description": _safe_statement_html(statement.description, statement.source_url),
            "input": _safe_statement_html(statement.input_format, statement.source_url),
            "output": _safe_statement_html(statement.output_format, statement.source_url),
            "hint": _safe_statement_html(statement.hint, statement.source_url),
            "samples": [{"input": sample[0], "output": sample[1]} for sample in statement.samples],
        },
    }


def _revealed_problem(active: ActiveProblem) -> dict:
    problem = active.problem
    return {
        "cfId": problem.cf_id,
        "title": active.statement.title or problem.name,
        "rating": problem.rating or None,
        "tags": list(problem.tags),
        "codeforcesUrl": problem.cf_url,
        "luoguUrl": problem.luogu_url,
        "solutionUrl": problem.luogu_solution_url,
        "ranked": active.ranked,
    }


def _safe_statement_html(value: str, source_url: str) -> str:
    if not value.strip():
        return ""
    try:
        rendered = _markdown_to_html(value, source_url)
    except RuntimeError as exc:
        if "markdown is required" not in str(exc):
            raise
        rendered = value
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(rendered)
    sanitizer.close()
    return sanitizer.result


class _HTMLSanitizer(HTMLParser):
    allowed_tags = {
        "a", "b", "blockquote", "br", "code", "div", "em", "i", "img", "li", "ol", "p",
        "pre", "span", "strong", "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "ul",
    }
    void_tags = {"br", "img"}
    suppressed_tags = {"script", "style", "iframe", "object", "embed", "form", "input", "button"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed_depth = 0

    @property
    def result(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.suppressed_tags:
            self.suppressed_depth += 1
            return
        if self.suppressed_depth or tag not in self.allowed_tags:
            return
        clean_attrs = []
        for name, value in attrs:
            name = name.lower()
            value = value or ""
            if tag == "a" and name == "href" and _safe_url(value):
                clean_attrs.append(("href", value))
                clean_attrs.extend((("target", "_blank"), ("rel", "noopener noreferrer")))
            elif tag == "img" and name in {"src", "alt"}:
                if name == "alt" or _safe_url(value):
                    clean_attrs.append((name, value))
            elif tag == "span" and name == "class":
                classes = " ".join(part for part in value.split() if part in {"math", "math-display"})
                if classes:
                    clean_attrs.append(("class", classes))
            elif tag in {"td", "th"} and name in {"colspan", "rowspan"} and value.isdigit():
                clean_attrs.append((name, value))
        attributes = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in clean_attrs)
        self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.suppressed_tags:
            self.suppressed_depth = max(0, self.suppressed_depth - 1)
            return
        if not self.suppressed_depth and tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.suppressed_depth:
            self.parts.append(html.escape(data))


def _safe_url(value: str) -> bool:
    return urlsplit(value).scheme.lower() in {"http", "https"}
