from __future__ import annotations

import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import Cookie, CookieJar, LoadError, MozillaCookieJar
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import CFProblem, CodeSubmission, RemoteJudgeResult
from .submitter import RemoteSubmissionError, _language_aliases, _normalize_language_name


LOGGER = logging.getLogger(__name__)
VJUDGE_BASE_URL = "https://vjudge.net"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class VJudgeSubmissionError(RemoteSubmissionError):
    """VJudge rejected or could not complete a submission workflow."""


class VJudgeRemoteJudge:
    def __init__(
        self,
        username: str = "",
        password: str = "",
        cookie_header: str = "",
        forced_language_id: str = "",
        http_timeout_seconds: int = 30,
        poll_interval_seconds: int = 8,
        poll_timeout_seconds: int = 180,
        base_url: str = VJUDGE_BASE_URL,
        session_dir: Optional[Path] = None,
    ) -> None:
        self.username = username.strip()
        self.password = password
        self.cookie_header = cookie_header.strip()
        self.forced_language_id = forced_language_id.strip()
        self.http_timeout_seconds = http_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.base_url = _normalize_base_url(base_url)
        self.session_dir = Path(session_dir) if session_dir is not None else None
        self._cookie_path = self.session_dir / "http-cookies.txt" if self.session_dir is not None else None
        self._cookie_jar = self._new_cookie_jar(load=True)
        self._seed_cookie_header(self.cookie_header)
        self._cookie_loaded_mtime = self._cookie_mtime()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._logged_in = False
        self._last_error = ""
        self._last_success_at = 0.0
        self._last_submit_at = 0.0

    @property
    def provider(self) -> str:
        return "vjudge"

    @property
    def configured(self) -> bool:
        has_saved_session = bool(self._cookie_path is not None and self._cookie_path.exists())
        return bool((self.username and self.password) or self.cookie_header or has_saved_session)

    @property
    def availability(self) -> dict:
        if not self.configured:
            return {"state": "disabled", "message": "VJudge 提交账号或 Cookie 未配置"}
        account = self.username or "缓存会话"
        if self._last_error:
            return {"state": "degraded", "message": f"VJudge 最近一次提交失败：{self._last_error}"}
        if self._last_success_at:
            return {"state": "ready", "message": f"VJudge 账号 {account} 已验证"}
        return {"state": "configured", "message": f"VJudge 账号 {account} 已配置，提交时验证登录"}

    @property
    def last_submit_at(self) -> float:
        return self._last_submit_at

    def verify_login(self) -> str:
        if not self.configured:
            raise VJudgeSubmissionError("VJudge 提交账号未配置。")
        try:
            self._ensure_logged_in()
        except VJudgeSubmissionError as exc:
            self._last_error = _friendly_vjudge_error(str(exc))
            raise
        except Exception as exc:
            self._last_error = _friendly_vjudge_error(str(exc))
            raise VJudgeSubmissionError(self._last_error) from exc
        self._last_error = ""
        self._last_success_at = time.time()
        return str(self.availability["message"])

    def judge(self, problem: CFProblem, submission: CodeSubmission) -> RemoteJudgeResult:
        if not self.configured:
            raise VJudgeSubmissionError("VJudge 提交账号未配置。")
        if not submission.source.strip():
            return RemoteJudgeResult(False, "EMPTY_SOURCE", "代码为空。")

        LOGGER.info(
            "VJudge submit start cf_id=%s language=%s source_chars=%s",
            problem.cf_id,
            submission.language,
            len(submission.source),
        )
        try:
            self._ensure_logged_in()
            language_id = self.forced_language_id or self._resolve_language_id(problem, submission.language)
            run_id = self._submit(problem, submission, language_id)
            self._last_submit_at = time.time()
            result = self._poll_result(run_id)
        except VJudgeSubmissionError as exc:
            self._last_error = _friendly_vjudge_error(str(exc))
            raise
        except Exception as exc:
            self._last_error = _friendly_vjudge_error(str(exc))
            raise VJudgeSubmissionError(self._last_error) from exc
        self._last_error = ""
        self._last_success_at = time.time()
        return result

    def _ensure_logged_in(self) -> None:
        if self._logged_in:
            return
        self._reload_http_cookies_if_changed()
        if self._check_logged_in():
            self._logged_in = True
            return
        if not self.username or not self.password:
            raise VJudgeSubmissionError(
                "VJudge Cookie 已失效；请重新登录 vjudge.net 后更新服务器 VJUDGE_COOKIE。"
            )

        response = self._post(
            "/user/login",
            {"username": self.username, "password": self.password, "token": ""},
            referer="/",
        )
        if not self._check_logged_in():
            detail = _extract_vjudge_error(response)
            if detail:
                raise VJudgeSubmissionError(f"VJudge 登录失败：{detail}")
            raise VJudgeSubmissionError(
                "VJudge 登录失败，可能要求 Turnstile 人机验证；请在浏览器登录后配置 VJUDGE_COOKIE。"
            )
        self._logged_in = True

    def _check_logged_in(self) -> bool:
        response = self._post("/user/checkLogInStatus", {}, referer="/")
        value = response.strip().lower()
        if value in {"true", "1"}:
            return True
        try:
            return json.loads(value) is True
        except (json.JSONDecodeError, TypeError):
            return False

    def _resolve_language_id(self, problem: CFProblem, language: str) -> str:
        page = self._get(f"/problem/CodeForces-{problem.cf_id}")
        languages, submit_methods = _extract_problem_submit_context(page)
        if submit_methods and not bool(submit_methods[0]):
            raise VJudgeSubmissionError("VJudge 当前未开放默认账号提交 Codeforces 题目。")
        language_id = _choose_vjudge_language_id(languages, language)
        if language_id:
            return language_id
        available = "、".join(list(languages.values())[:8])
        suffix = f"；当前可用语言：{available}" if available else ""
        raise VJudgeSubmissionError(
            "无法从 VJudge 题目页识别提交语言，可设置 VJUDGE_LANGUAGE_ID 强制指定" + suffix
        )

    def _submit(self, problem: CFProblem, submission: CodeSubmission, language_id: str) -> int:
        path = f"/problem/submit/CodeForces-{problem.cf_id}"
        response = self._post(
            path,
            {
                "method": "0",
                "language": language_id,
                "open": "0",
                "source": submission.source,
                "token": "",
            },
            referer=f"/problem/CodeForces-{problem.cf_id}",
        )
        payload = _decode_json(response, "VJudge 提交接口")
        run_id = _as_int(payload.get("runId")) if isinstance(payload, dict) else None
        if run_id is None:
            detail = _extract_vjudge_error(payload)
            if isinstance(payload, dict) and payload.get("challenge"):
                detail = detail or "VJudge 要求人机验证"
            raise VJudgeSubmissionError(f"VJudge 拒绝提交：{detail or '没有返回 runId'}")
        LOGGER.info(
            "VJudge submit accepted cf_id=%s run_id=%s language_id=%s",
            problem.cf_id,
            run_id,
            language_id,
        )
        return run_id

    def _poll_result(self, run_id: int) -> RemoteJudgeResult:
        deadline = time.time() + self.poll_timeout_seconds
        last_payload: Optional[dict] = None
        last_error = ""
        while time.time() < deadline:
            try:
                response = self._post(
                    f"/solution/data/{run_id}",
                    {"showCode": "false"},
                    referer=f"/solution/{run_id}",
                )
                payload = _decode_json(response, "VJudge 判题状态接口")
                if not isinstance(payload, dict):
                    raise VJudgeSubmissionError("VJudge 判题状态接口返回格式异常。")
                if payload.get("error"):
                    raise VJudgeSubmissionError(_extract_vjudge_error(payload) or "VJudge 无法读取判题状态。")
                last_payload = payload
                if not _vjudge_result_is_pending(payload):
                    result = _result_from_vjudge(payload, run_id, self.base_url)
                    LOGGER.info("VJudge verdict run_id=%s verdict=%s", run_id, result.verdict)
                    return result
            except Exception as exc:
                last_error = _friendly_vjudge_error(str(exc))
                LOGGER.warning("VJudge verdict poll failed run_id=%s error=%s", run_id, last_error)
            time.sleep(self.poll_interval_seconds)

        status = _status_text(last_payload or {})
        detail = f"，最后状态为 {status}" if status else ""
        if last_error and last_payload is None:
            detail = f"，状态接口最近错误：{last_error}"
        return RemoteJudgeResult(
            False,
            "PENDING",
            f"代码已提交到 VJudge，但轮询超时{detail}；请打开提交记录确认最终结果。",
            submission_id=run_id,
            url=f"{self.base_url}/solution/{run_id}",
        )

    def _get(self, path_or_url: str) -> str:
        request = urllib.request.Request(self._absolute_url(path_or_url), headers=self._headers())
        return self._open_text(request)

    def _post(self, path_or_url: str, fields: Dict[str, str], referer: str) -> str:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(
            self._absolute_url(path_or_url),
            data=data,
            headers=self._headers(referer=referer, form=True),
            method="POST",
        )
        return self._open_text(request)

    def _absolute_url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return urllib.parse.urljoin(self.base_url + "/", path_or_url.lstrip("/"))

    def _headers(self, referer: str = "/", form: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Referer": self._absolute_url(referer),
            "X-Requested-With": "XMLHttpRequest",
        }
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            headers["Origin"] = self.base_url
        return headers

    def _open_text(self, request: urllib.request.Request) -> str:
        try:
            with self._opener.open(request, timeout=self.http_timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
            self._save_http_cookies()
            return body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self._save_http_cookies()
            detail = _extract_vjudge_error(body)
            suffix = f"：{detail}" if detail else ""
            raise VJudgeSubmissionError(f"VJudge HTTP {exc.code}{suffix}") from exc
        except urllib.error.URLError as exc:
            raise VJudgeSubmissionError(f"VJudge 网络请求失败：{exc.reason}") from exc

    def _new_cookie_jar(self, *, load: bool) -> CookieJar:
        if self._cookie_path is None:
            return CookieJar()
        self._cookie_path.parent.mkdir(parents=True, exist_ok=True)
        jar = MozillaCookieJar(str(self._cookie_path))
        if load and self._cookie_path.exists():
            try:
                jar.load(ignore_discard=True, ignore_expires=True)
            except (LoadError, OSError) as exc:
                LOGGER.warning("VJudge saved cookies could not be loaded: %s", exc)
        return jar

    def _seed_cookie_header(self, raw_header: str) -> None:
        if not raw_header:
            return
        parsed = _parse_cookie_header(raw_header)
        host = urllib.parse.urlparse(self.base_url).hostname or "vjudge.net"
        secure = self.base_url.startswith("https://")
        for name, value in parsed.items():
            self._cookie_jar.set_cookie(
                Cookie(
                    version=0,
                    name=name,
                    value=value,
                    port=None,
                    port_specified=False,
                    domain=host,
                    domain_specified=True,
                    domain_initial_dot=False,
                    path="/",
                    path_specified=True,
                    secure=secure,
                    expires=None,
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={"HttpOnly": None},
                    rfc2109=False,
                )
            )
        self._save_http_cookies()

    def _save_http_cookies(self) -> None:
        if self._cookie_path is None or not isinstance(self._cookie_jar, MozillaCookieJar):
            return
        try:
            self._cookie_jar.save(ignore_discard=True, ignore_expires=True)
            self._cookie_path.chmod(0o600)
            self._cookie_loaded_mtime = self._cookie_mtime()
        except OSError as exc:
            LOGGER.warning("VJudge cookies could not be saved: %s", exc)

    def _reload_http_cookies_if_changed(self) -> None:
        modified_at = self._cookie_mtime()
        if not modified_at or modified_at <= self._cookie_loaded_mtime:
            return
        self._cookie_jar = self._new_cookie_jar(load=True)
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._cookie_loaded_mtime = modified_at
        LOGGER.info("VJudge session reloaded from persistent storage")

    def _cookie_mtime(self) -> float:
        if self._cookie_path is None:
            return 0.0
        try:
            return self._cookie_path.stat().st_mtime
        except OSError:
            return 0.0


def _normalize_base_url(value: str) -> str:
    raw = (value or VJUDGE_BASE_URL).strip().rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("VJUDGE_BASE_URL must be an absolute HTTP(S) URL")
    return raw


def _parse_cookie_header(raw_header: str) -> Dict[str, str]:
    value = raw_header.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    cookie = SimpleCookie()
    try:
        cookie.load(value)
    except Exception:
        cookie = SimpleCookie()
    parsed = {name: morsel.value for name, morsel in cookie.items()}
    if parsed:
        return parsed
    ignored = {"path", "domain", "expires", "secure", "httponly", "samesite", "max-age"}
    for item in value.split(";"):
        if "=" not in item:
            continue
        name, item_value = item.split("=", 1)
        name = name.strip()
        if name and name.lower() not in ignored:
            parsed[name] = item_value.strip()
    return parsed


def _extract_problem_submit_context(page_html: str) -> Tuple[Dict[str, str], List[Any]]:
    for raw in re.findall(r"<textarea\b[^>]*>(.*?)</textarea>", page_html, flags=re.IGNORECASE | re.DOTALL):
        text = html.unescape(raw).strip()
        if not text.startswith(("{", "[")):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        context = _find_submit_context(payload)
        if context is not None:
            languages = {
                str(key): str(label)
                for key, label in (context.get("languages") or {}).items()
                if key is not None and label is not None
            }
            methods = context.get("submitMethods") or []
            return languages, methods if isinstance(methods, list) else []
    raise VJudgeSubmissionError(
        "VJudge 题目页没有返回提交配置，登录态可能已失效，或该 Codeforces 题目暂不可提交。"
    )


def _find_submit_context(value: Any) -> Optional[dict]:
    if isinstance(value, dict):
        if isinstance(value.get("languages"), dict) and (
            "submitMethods" in value or "problemId" in value or "allowSubmit" in value
        ):
            return value
        for child in value.values():
            found = _find_submit_context(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_submit_context(child)
            if found is not None:
                return found
    return None


def _choose_vjudge_language_id(languages: Dict[str, str], language: str) -> str:
    options = [(value, _normalize_language_name(label)) for value, label in languages.items()]
    for alias in _language_aliases(language):
        normalized_alias = _normalize_language_name(alias)
        for value, normalized_label in options:
            if normalized_alias and normalized_alias in normalized_label:
                return value
    return ""


def _decode_json(value: str, endpoint_name: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        if "login=1" in value or "id=\"loginModal\"" in value:
            raise VJudgeSubmissionError("VJudge 登录态已失效。") from exc
        if "cloudflare" in value.lower() or "cf-chl" in value.lower():
            raise VJudgeSubmissionError("VJudge 返回 Cloudflare 访问保护页。") from exc
        raise VJudgeSubmissionError(f"{endpoint_name}没有返回 JSON。") from exc


def _extract_vjudge_error(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _extract_vjudge_error(json.loads(stripped))
            except json.JSONDecodeError:
                pass
        return _clean_text(stripped)
    if isinstance(value, dict):
        error = value.get("error") or value.get("message") or value.get("text") or value.get("i18nKey")
        if isinstance(error, dict):
            error = error.get("text") or error.get("message") or error.get("i18nKey")
        error_code = str(value.get("errorCode") or "")
        if "human_verification" in str(error) or value.get("challenge"):
            return "VJudge 要求人机验证，请更新 VJUDGE_COOKIE"
        if error_code.startswith("bind_account"):
            return "VJudge 远端账号不可用；本项目应使用默认账号提交方式 method=0"
        return _clean_text(str(error or error_code))
    return _clean_text(str(value or ""))


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", text).strip()[:300]


def _friendly_vjudge_error(message: str) -> str:
    text = _clean_text(message)
    lower = text.lower()
    if "human_verification" in lower or "turnstile" in lower or "人机验证" in text:
        return "VJudge 要求人机验证；请在浏览器登录后更新服务器 VJUDGE_COOKIE。"
    if "cloudflare" in lower:
        return "VJudge 返回 Cloudflare 访问保护页。"
    if not text:
        return "VJudge 没有返回可读错误。"
    return text


def _vjudge_result_is_pending(payload: dict) -> bool:
    if bool(payload.get("processing")):
        return True
    status = _status_text(payload).lower()
    canonical = str(payload.get("statusCanonical") or "").strip().upper()
    return canonical in {"", "PENDING", "RUNNING", "SUBMITTED", "QUEUE", "QUEUING"} or any(
        token in status for token in ("pending", "running", "judging", "submitted", "queue", "compiling")
    )


def _result_from_vjudge(payload: dict, run_id: int, base_url: str) -> RemoteJudgeResult:
    status = _status_text(payload) or "Unknown"
    verdict = _normalize_vjudge_verdict(str(payload.get("statusCanonical") or status))
    additional = _extract_vjudge_error(payload.get("additionalInfo"))
    message = f"VJudge 判题：{status}"
    if additional and additional.lower() != status.lower():
        message += f"（{additional}）"
    return RemoteJudgeResult(
        accepted=verdict == "OK",
        verdict=verdict,
        message=message,
        submission_id=run_id,
        time_ms=_as_int(payload.get("runtime")),
        url=f"{base_url}/solution/{run_id}",
    )


def _status_text(payload: dict) -> str:
    return _clean_text(str(payload.get("status") or payload.get("statusCanonical") or ""))


def _normalize_vjudge_verdict(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    aliases = {
        "AC": "OK",
        "ACCEPTED": "OK",
        "WA": "WRONG_ANSWER",
        "WRONG_ANSWER": "WRONG_ANSWER",
        "TLE": "TIME_LIMIT_EXCEEDED",
        "TIME_LIMIT_EXCEEDED": "TIME_LIMIT_EXCEEDED",
        "MLE": "MEMORY_LIMIT_EXCEEDED",
        "MEMORY_LIMIT_EXCEEDED": "MEMORY_LIMIT_EXCEEDED",
        "RE": "RUNTIME_ERROR",
        "RUNTIME_ERROR": "RUNTIME_ERROR",
        "CE": "COMPILATION_ERROR",
        "COMPILATION_ERROR": "COMPILATION_ERROR",
        "PE": "PRESENTATION_ERROR",
        "PRESENTATION_ERROR": "PRESENTATION_ERROR",
        "OLE": "OUTPUT_LIMIT_EXCEEDED",
        "OUTPUT_LIMIT_EXCEEDED": "OUTPUT_LIMIT_EXCEEDED",
    }
    return aliases.get(normalized, normalized or "UNKNOWN")


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
