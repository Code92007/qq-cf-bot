from __future__ import annotations

import html
import hashlib
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar, LoadError, MozillaCookieJar
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .cf_mirrors import normalize_codeforces_base_urls
from .codeforces import CodeforcesStatusClient
from .models import CFProblem, CodeSubmission, RemoteJudgeResult, SolutionReference


CODEFORCES_BASE_URL = "https://codeforces.com"
LOGGER = logging.getLogger(__name__)
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


_VERDICT_ZH = {
    "OK": "Accepted",
    "WRONG_ANSWER": "Wrong Answer",
    "TIME_LIMIT_EXCEEDED": "Time Limit Exceeded",
    "MEMORY_LIMIT_EXCEEDED": "Memory Limit Exceeded",
    "RUNTIME_ERROR": "Runtime Error",
    "COMPILATION_ERROR": "Compilation Error",
    "PRESENTATION_ERROR": "Presentation Error",
    "IDLENESS_LIMIT_EXCEEDED": "Idleness Limit Exceeded",
    "SECURITY_VIOLATED": "Security Violated",
    "CRASHED": "Crashed",
    "INPUT_PREPARATION_CRASHED": "Input Preparation Crashed",
    "CHALLENGED": "Challenged",
    "SKIPPED": "Skipped",
    "TESTING": "Testing",
    "REJECTED": "Rejected",
}


@dataclass
class _ParsedForm:
    action: str = ""
    method: str = "post"
    attrs: Dict[str, str] = field(default_factory=dict)
    inputs: Dict[str, str] = field(default_factory=dict)
    selects: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: List[_ParsedForm] = []
        self._current: Optional[_ParsedForm] = None
        self._current_select: Optional[str] = None
        self._current_option: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "form":
            self._current = _ParsedForm(
                action=attr_map.get("action", ""),
                method=(attr_map.get("method") or "post").lower(),
                attrs=attr_map,
            )
            return
        if self._current is None:
            return
        if tag == "input":
            name = attr_map.get("name")
            if name:
                self._current.inputs[name] = attr_map.get("value", "")
        elif tag == "textarea":
            name = attr_map.get("name")
            if name and name not in self._current.inputs:
                self._current.inputs[name] = ""
        elif tag == "select":
            name = attr_map.get("name")
            if name:
                self._current_select = name
                self._current.selects.setdefault(name, [])
        elif tag == "option" and self._current_select:
            self._current_option = [attr_map.get("value", ""), ""]

    def handle_data(self, data: str) -> None:
        if self._current_option is not None:
            self._current_option[1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._current is not None and self._current_select and self._current_option:
            value, label = self._current_option
            self._current.selects.setdefault(self._current_select, []).append((value, label.strip()))
            self._current_option = None
        elif tag == "select":
            self._current_select = None
        elif tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


class CodeforcesForbiddenError(RuntimeError):
    """Codeforces rejected the request before normal form handling."""


class CodeforcesSubmissionError(RuntimeError):
    """All configured Codeforces submission transports failed."""


class CodeforcesRemoteJudge:
    def __init__(
        self,
        username: str,
        password: str,
        handle: str,
        forced_language_id: str = "",
        http_timeout_seconds: int = 30,
        poll_interval_seconds: int = 8,
        poll_timeout_seconds: int = 180,
        base_urls: Iterable[str] | str | None = None,
        session_dir: Optional[Path] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.handle = handle or username
        self.forced_language_id = forced_language_id
        self.http_timeout_seconds = http_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.session_dir = Path(session_dir) if session_dir is not None else None
        self._cookie_path = self.session_dir / "http-cookies.txt" if self.session_dir is not None else None
        self._browser_profile_dir = self.session_dir / "browser-profile" if self.session_dir is not None else None
        self._browser_ready_path = self.session_dir / "browser-session-ready" if self.session_dir is not None else None
        self._cookie_jar = self._new_cookie_jar(load=True)
        self._cookie_loaded_mtime = self._cookie_mtime()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._logged_in = False
        self._last_error = ""
        self._last_success_at = 0.0
        self._last_submit_at = 0.0
        self.base_urls = normalize_codeforces_base_urls(base_urls)
        self._status = CodeforcesStatusClient(
            self.handle,
            timeout_seconds=http_timeout_seconds,
            base_urls=self.base_urls,
        )

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password and self.handle)

    @property
    def availability(self) -> dict:
        if not self.configured:
            return {"state": "disabled", "message": "Codeforces 提交账号未配置"}
        if self._last_error:
            return {"state": "degraded", "message": f"最近一次提交失败：{self._last_error}"}
        if self._last_success_at:
            return {"state": "ready", "message": f"Codeforces 账号 {self.handle} 已验证"}
        if self._has_browser_session():
            return {"state": "configured", "message": f"Codeforces 账号 {self.handle} 已缓存登录会话"}
        return {"state": "configured", "message": f"Codeforces 账号 {self.handle} 已配置，提交时验证登录"}

    @property
    def last_submit_at(self) -> float:
        return self._last_submit_at

    def verify_login(self) -> str:
        if not self.configured:
            raise CodeforcesSubmissionError("Codeforces 提交账号未配置。")
        try:
            if self._has_browser_session():
                self._verify_browser_login()
            else:
                try:
                    self._ensure_logged_in()
                except Exception as http_exc:
                    LOGGER.warning(
                        "Codeforces HTTP login verification failed, trying persistent browser: %s",
                        _friendly_cf_error(str(http_exc)),
                    )
                    self._reset_session()
                    try:
                        self._verify_browser_login()
                    except Exception as browser_exc:
                        raise CodeforcesSubmissionError(
                            "HTTP 登录验证失败："
                            f"{_friendly_cf_error(str(http_exc))}；持久浏览器登录验证失败："
                            f"{_friendly_cf_error(str(browser_exc))}"
                        ) from browser_exc
        except CodeforcesSubmissionError as exc:
            self._last_error = _friendly_cf_error(str(exc))
            raise
        except Exception as exc:
            self._last_error = _friendly_cf_error(str(exc))
            raise CodeforcesSubmissionError(self._last_error) from exc
        self._last_error = ""
        self._last_success_at = time.time()
        return str(self.availability["message"])

    def judge(self, problem: CFProblem, submission: CodeSubmission) -> RemoteJudgeResult:
        if not self.configured:
            raise RuntimeError("Codeforces submit account is not configured")
        if not submission.source.strip():
            return RemoteJudgeResult(False, "EMPTY_SOURCE", "代码为空。")

        LOGGER.info(
            "Codeforces submit start cf_id=%s language=%s source_chars=%s",
            problem.cf_id,
            submission.language,
            len(submission.source),
        )
        try:
            before_id = self._latest_matching_submission_id(problem)
            submitted_after = max(0, int(time.time()) - 5)
            LOGGER.info(
                "Codeforces latest matching submission before submit cf_id=%s before_id=%s",
                problem.cf_id,
                before_id,
            )
            self._submit_with_retry(problem, submission)
            self._last_submit_at = time.time()
            result = self._poll_result(problem, before_id, submitted_after=submitted_after)
        except CodeforcesSubmissionError as exc:
            self._last_error = _friendly_cf_error(str(exc))
            raise
        except Exception as exc:
            self._last_error = _friendly_cf_error(str(exc))
            raise CodeforcesSubmissionError(self._last_error) from exc
        self._last_error = ""
        self._last_success_at = time.time()
        return result

    def fetch_accepted_code_references(
        self,
        problem: CFProblem,
        max_items: int = 1,
        max_chars: int = 5000,
    ) -> List[SolutionReference]:
        if max_items <= 0:
            return []
        self._ensure_logged_in()
        status_path = (
            f"/problemset/status/{problem.contest_id}/problem/{urllib.parse.quote(problem.index)}"
            "?order=BY_PROGRAM_LENGTH_ASC&verdictName=OK"
        )
        status_html = self._get(status_path)
        submission_ids = _extract_submission_ids(status_html, problem.contest_id)
        references: List[SolutionReference] = []
        for submission_id in submission_ids[: max_items * 3]:
            if len(references) >= max_items:
                break
            url = f"{CODEFORCES_BASE_URL}/contest/{problem.contest_id}/submission/{submission_id}"
            page_html = self._get(url)
            source = _extract_program_source(page_html)
            if len(source.strip()) < 40:
                continue
            content = source.strip()
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[AC 代码过长，后续内容已截断]"
            references.append(
                SolutionReference(
                    cf_id=problem.cf_id,
                    source="codeforces_ac_code",
                    title=f"Accepted submission {submission_id}",
                    author="Codeforces",
                    url=url,
                    content=f"```text\n{content}\n```",
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        return references

    def _submit_with_retry(self, problem: CFProblem, submission: CodeSubmission) -> None:
        if self._has_browser_session():
            try:
                self._submit_via_browser(problem, submission)
                LOGGER.info("Codeforces persistent browser session submitted %s", problem.cf_id)
                return
            except Exception as browser_exc:
                LOGGER.warning(
                    "Codeforces persistent browser submit failed for %s, trying HTTP: %s",
                    problem.cf_id,
                    _friendly_cf_error(str(browser_exc)),
                )
                self._set_browser_session_ready(False)
                self._reset_session()
                try:
                    self._submit(problem, submission)
                    return
                except Exception as http_exc:
                    raise CodeforcesSubmissionError(
                        "持久浏览器通道失败："
                        f"{_friendly_cf_error(str(browser_exc))}；HTTP 通道失败："
                        f"{_friendly_cf_error(str(http_exc))}"
                    ) from http_exc

        try:
            self._submit(problem, submission)
            return
        except Exception as exc:
            LOGGER.warning(
                "Codeforces HTTP submit failed for %s, trying persistent browser fallback: %s",
                problem.cf_id,
                _friendly_cf_error(str(exc)),
            )
            self._reset_session()
            try:
                self._submit_via_browser(problem, submission)
                LOGGER.info("Codeforces persistent browser fallback submitted %s", problem.cf_id)
                return
            except Exception as browser_exc:
                raise CodeforcesSubmissionError(
                    "HTTP 通道失败："
                    f"{_friendly_cf_error(str(exc))}；持久浏览器通道失败："
                    f"{_friendly_cf_error(str(browser_exc))}"
                ) from browser_exc

    def _submit(self, problem: CFProblem, submission: CodeSubmission) -> None:
        self._ensure_logged_in()
        submit_path = f"/problemset/submit/{problem.contest_id}/{problem.index}"
        page = self._get(submit_path)
        form = _find_submit_form(_parse_forms(page))
        language_id = self.forced_language_id or _choose_language_id(form, submission.language)
        if not language_id:
            raise RuntimeError(
                "无法从 Codeforces 提交表单识别语言，请设置 CF_SUBMIT_LANGUAGE_ID 后重试。"
            )

        fields = dict(form.inputs)
        fields.update(
            {
                "action": "submitSolutionFormSubmitted",
                "submittedProblemIndex": problem.index,
                "submittedProblemCode": problem.cf_id,
                "programTypeId": language_id,
                "source": submission.source,
                "tabSize": fields.get("tabSize") or "4",
            }
        )
        action = form.action or submit_path
        response_text = self._post(action, fields, referer=submit_path)
        error = _extract_cf_error(response_text)
        if error:
            raise RuntimeError(f"Codeforces 拒绝提交：{error}")
        LOGGER.info("Codeforces HTTP submit form posted cf_id=%s language_id=%s", problem.cf_id, language_id)

    def _submit_via_browser(self, problem: CFProblem, submission: CodeSubmission) -> None:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright 未安装，无法使用浏览器兜底提交。") from exc

        submit_path = f"/problemset/submit/{problem.contest_id}/{problem.index}"
        login_url = _absolute_url("/enter?back=%2F")
        submit_url = _absolute_url(submit_path)

        with sync_playwright() as playwright:
            context, browser = self._launch_browser_context(playwright)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(login_url, wait_until="domcontentloaded", timeout=self.http_timeout_seconds * 1000)
                _wait_quiet(page, PlaywrightTimeoutError)
                if not _looks_logged_in(page.content(), self.handle):
                    _browser_login(page, self.username, self.password, self.handle, PlaywrightTimeoutError)
                self._set_browser_session_ready(True)

                page.goto(submit_url, wait_until="domcontentloaded", timeout=self.http_timeout_seconds * 1000)
                _wait_quiet(page, PlaywrightTimeoutError)
                page_html = page.content()
                block_reason = _diagnose_cf_block(page_html)
                if block_reason:
                    raise RuntimeError(block_reason)

                form = _find_submit_form(_parse_forms(page_html))
                language_id = self.forced_language_id or _choose_language_id(form, submission.language)
                if not language_id:
                    raise RuntimeError(
                        "无法从 Codeforces 提交表单识别语言，请设置 CF_SUBMIT_LANGUAGE_ID 后重试。"
                    )

                _set_if_present(page, 'input[name="submittedProblemIndex"]', problem.index)
                _set_if_present(page, 'input[name="submittedProblemCode"]', problem.cf_id)
                _select_if_present(page, 'select[name="programTypeId"]', language_id)
                if not _set_if_present(page, 'textarea[name="source"]', submission.source):
                    if not _set_if_present(page, 'textarea#sourceCodeTextarea', submission.source):
                        raise RuntimeError("提交页没有找到源码输入框。")

                clicked = _click_submit(page, PlaywrightTimeoutError)
                if not clicked:
                    raise RuntimeError("提交页没有找到提交按钮。")

                _wait_quiet(page, PlaywrightTimeoutError)
                submitted_html = page.content()
                error = _extract_cf_error(submitted_html) or _diagnose_cf_block(submitted_html)
                if error:
                    raise RuntimeError(f"Codeforces 拒绝提交：{error}")
                LOGGER.info(
                    "Codeforces browser submit clicked cf_id=%s language_id=%s current_url=%s",
                    problem.cf_id,
                    language_id,
                    page.url,
                )
            finally:
                self._close_browser_context(context, browser)

    def _verify_browser_login(self) -> None:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright 未安装，无法验证浏览器登录。") from exc

        login_url = _absolute_url("/enter?back=%2F")
        with sync_playwright() as playwright:
            context, browser = self._launch_browser_context(playwright)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(login_url, wait_until="domcontentloaded", timeout=self.http_timeout_seconds * 1000)
                _wait_quiet(page, PlaywrightTimeoutError)
                if not _looks_logged_in(page.content(), self.handle):
                    _browser_login(page, self.username, self.password, self.handle, PlaywrightTimeoutError)
                self._set_browser_session_ready(True)
            finally:
                self._close_browser_context(context, browser)

    def _launch_browser_context(self, playwright):
        options = {
            "user_agent": _BROWSER_USER_AGENT,
            "locale": "en-US",
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            },
        }
        if self._browser_profile_dir is not None:
            self._browser_profile_dir.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                str(self._browser_profile_dir),
                headless=True,
                **options,
            )
            return context, None
        browser = playwright.chromium.launch(headless=True)
        return browser.new_context(**options), browser

    @staticmethod
    def _close_browser_context(context, browser) -> None:
        context.close()
        if browser is not None:
            browser.close()

    def _ensure_logged_in(self) -> None:
        if self._logged_in:
            return
        self._reload_http_cookies_if_changed()
        login_page = self._get("/enter?back=%2F")
        if _looks_logged_in(login_page, self.handle):
            self._logged_in = True
            return

        form = _find_login_form(_parse_forms(login_page))
        fields = dict(form.inputs)
        fields.update(
            {
                "action": "enter",
                "handleOrEmail": self.username,
                "password": self.password,
                "remember": "on",
            }
        )
        action = form.action or "/enter?back=%2F"
        response_text = self._post(action, fields, referer="/enter?back=%2F")
        if not _looks_logged_in(response_text, self.handle):
            home = self._get("/")
            if not _looks_logged_in(home, self.handle):
                error = _extract_cf_error(response_text)
                suffix = f"：{error}" if error else "。可能需要验证码、二次验证或账号安全确认。"
                raise RuntimeError("Codeforces 登录失败" + suffix)
        self._logged_in = True

    def _reset_session(self) -> None:
        self._cookie_jar = self._new_cookie_jar(load=False)
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._logged_in = False
        if self._cookie_path is not None:
            self._cookie_path.unlink(missing_ok=True)
        self._cookie_loaded_mtime = 0.0

    def _new_cookie_jar(self, *, load: bool) -> CookieJar:
        if self._cookie_path is None:
            return CookieJar()
        self._cookie_path.parent.mkdir(parents=True, exist_ok=True)
        jar = MozillaCookieJar(str(self._cookie_path))
        if load and self._cookie_path.exists():
            try:
                jar.load(ignore_discard=True, ignore_expires=True)
            except (LoadError, OSError) as exc:
                LOGGER.warning("Codeforces saved HTTP cookies could not be loaded: %s", exc)
        return jar

    def _save_http_cookies(self) -> None:
        if self._cookie_path is None or not isinstance(self._cookie_jar, MozillaCookieJar):
            return
        try:
            self._cookie_jar.save(ignore_discard=True, ignore_expires=True)
            self._cookie_path.chmod(0o600)
            self._cookie_loaded_mtime = self._cookie_mtime()
        except OSError as exc:
            LOGGER.warning("Codeforces HTTP cookies could not be saved: %s", exc)

    def _reload_http_cookies_if_changed(self) -> None:
        modified_at = self._cookie_mtime()
        if not modified_at or modified_at <= self._cookie_loaded_mtime:
            return
        self._cookie_jar = self._new_cookie_jar(load=True)
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._cookie_loaded_mtime = modified_at
        LOGGER.info("Codeforces HTTP session reloaded from persistent storage")

    def _cookie_mtime(self) -> float:
        if self._cookie_path is None:
            return 0.0
        try:
            return self._cookie_path.stat().st_mtime
        except OSError:
            return 0.0

    def _has_browser_session(self) -> bool:
        return bool(self._browser_ready_path is not None and self._browser_ready_path.exists())

    def _set_browser_session_ready(self, ready: bool) -> None:
        if self._browser_ready_path is None:
            return
        if not ready:
            self._browser_ready_path.unlink(missing_ok=True)
            return
        self._browser_ready_path.parent.mkdir(parents=True, exist_ok=True)
        self._browser_ready_path.write_text("ready\n", encoding="ascii")
        self._browser_ready_path.chmod(0o600)

    def _latest_matching_submission_id(self, problem: CFProblem) -> int:
        try:
            submissions = self._status.fetch_recent(count=20)
        except (OSError, urllib.error.URLError, RuntimeError) as exc:
            LOGGER.warning("Codeforces latest submission probe failed before submit cf_id=%s: %s", problem.cf_id, exc)
            return 0
        ids = [
            int(submission.get("id") or 0)
            for submission in submissions
            if _same_problem(submission, problem)
        ]
        return max(ids, default=0)

    def _poll_result(self, problem: CFProblem, before_id: int, *, submitted_after: int = 0) -> RemoteJudgeResult:
        deadline = time.time() + self.poll_timeout_seconds
        last_seen: Optional[dict] = None
        last_poll_error = ""
        while time.time() < deadline:
            try:
                submissions = self._status.fetch_recent(count=50)
            except Exception as exc:
                last_poll_error = _friendly_cf_error(str(exc))
                LOGGER.warning("Codeforces verdict poll failed cf_id=%s error=%s", problem.cf_id, last_poll_error)
                time.sleep(self.poll_interval_seconds)
                continue
            match = _find_new_matching_submission(
                submissions,
                problem,
                before_id,
                submitted_after=submitted_after,
            )
            if match is not None:
                last_seen = match
                verdict = str(match.get("verdict") or "")
                if verdict and verdict != "TESTING":
                    result = _result_from_submission(match)
                    LOGGER.info(
                        "Codeforces submit verdict cf_id=%s submission_id=%s verdict=%s",
                        problem.cf_id,
                        result.submission_id,
                        result.verdict,
                    )
                    return result
            time.sleep(self.poll_interval_seconds)

        if last_seen is not None:
            LOGGER.warning("Codeforces submit poll timeout cf_id=%s last_seen=%s", problem.cf_id, last_seen.get("id"))
            return _pending_result(last_seen, "提交已发出，但轮询超时，暂未拿到最终结果。")
        if last_poll_error:
            LOGGER.warning("Codeforces submit poll timeout cf_id=%s api_error=%s", problem.cf_id, last_poll_error)
            return RemoteJudgeResult(
                False,
                "PENDING",
                "提交已发出，但 Codeforces 状态接口暂时不可用，请稍后在提交记录中确认。",
            )
        LOGGER.warning("Codeforces submit poll timeout cf_id=%s no matching submission found", problem.cf_id)
        return RemoteJudgeResult(False, "PENDING", "提交已发出，但轮询超时，未在最近提交中找到记录。")

    def _get(self, path_or_url: str) -> str:
        request = urllib.request.Request(
            _absolute_url(path_or_url),
            headers=_browser_headers(),
        )
        return self._open_text(request)

    def _post(self, path_or_url: str, fields: Dict[str, str], referer: str) -> str:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(
            _absolute_url(path_or_url),
            data=data,
            headers=_browser_headers(referer=referer, form=True),
            method="POST",
        )
        return self._open_text(request)

    def _open_text(self, request: urllib.request.Request) -> str:
        try:
            with self._opener.open(request, timeout=self.http_timeout_seconds) as response:
                text = response.read().decode("utf-8", errors="replace")
            self._save_http_cookies()
            return text
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self._save_http_cookies()
            error = _extract_cf_error(body)
            if exc.code == 403:
                detail = f"：{error}" if error else ""
                raise CodeforcesForbiddenError(f"Codeforces 返回 403 Forbidden{detail}") from exc
            detail = f"：{error}" if error else ""
            raise RuntimeError(f"Codeforces HTTP {exc.code}{detail}") from exc


def _parse_forms(page_html: str) -> List[_ParsedForm]:
    parser = _FormParser()
    parser.feed(page_html)
    return parser.forms


def _find_login_form(forms: Iterable[_ParsedForm]) -> _ParsedForm:
    for form in forms:
        if "handleOrEmail" in form.inputs or "password" in form.inputs:
            return form
    raise RuntimeError("Codeforces 登录页没有找到登录表单。")


def _find_submit_form(forms: Iterable[_ParsedForm]) -> _ParsedForm:
    fallback: Optional[_ParsedForm] = None
    for form in forms:
        input_names = set(form.inputs)
        if "source" in input_names and "programTypeId" in form.selects:
            return form
        if "submitSolutionFormSubmitted" in " ".join(form.inputs.values()):
            fallback = form
    if fallback is not None:
        return fallback
    raise RuntimeError("Codeforces 提交页没有找到提交表单。")


def _choose_language_id(form: _ParsedForm, language: str) -> str:
    options = form.selects.get("programTypeId") or []
    if not options:
        return form.inputs.get("programTypeId", "")

    aliases = _language_aliases(language)
    normalized_aliases = [_normalize_language_name(alias) for alias in aliases]
    normalized_options = [(value, _normalize_language_name(label)) for value, label in options]
    for alias in normalized_aliases:
        for value, normalized_label in normalized_options:
            if alias in normalized_label:
                return value
    return ""


def _language_aliases(language: str) -> List[str]:
    normalized = language.strip().lower()
    if normalized in {"cpp", "c++", "gnu++17", "gnu++20", "gnu++23"}:
        return ["gnu g++20", "gnu g++23", "gnu g++17", "c++20", "c++17", "g++"]
    if normalized in {"py", "python", "python3", "pypy"}:
        return ["pypy 3", "python 3"]
    if normalized == "java":
        return ["java 21", "java 17", "java 11", "java 8"]
    if normalized in {"kt", "kotlin"}:
        return ["kotlin"]
    if normalized in {"rs", "rust"}:
        return ["rust"]
    if normalized == "go":
        return ["go"]
    if normalized == "c":
        return ["gcc", "c11"]
    return [normalized]


def _normalize_language_name(value: str) -> str:
    return re.sub(r"[^a-z0-9+]+", "", value.lower())


def _looks_logged_in(page_html: str, handle: str) -> bool:
    lower = page_html.lower()
    if "/logout" in lower or "logout" in lower:
        return True
    return bool(handle and re.search(rf"\b{re.escape(handle.lower())}\b", lower) and "enter" not in lower)


def _extract_cf_error(page_html: str) -> str:
    candidates = re.findall(
        r"<(?:div|span)[^>]*(?:class|style)=[\"'][^\"']*(?:error|notice)[^\"']*[\"'][^>]*>(.*?)</(?:div|span)>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for candidate in candidates:
        text = _strip_tags(candidate)
        if text:
            return text
    return ""


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _friendly_cf_error(message: str) -> str:
    text = _strip_tags(message) if "<" in message else re.sub(r"\s+", " ", message).strip()
    lower = text.lower()
    if any(token in lower for token in ("captcha", "recaptcha", "enter the characters", "verify you are human")):
        return "Codeforces 要求验证码/人机验证，需要手动登录账号处理。"
    if any(token in lower for token in ("cloudflare", "attention required", "checking your browser")):
        return "Codeforces 返回访问保护页，可能触发了 Cloudflare/风控。"
    if any(token in lower for token in ("technical maintenance", "temporarily unavailable", "can't be reached")):
        return "Codeforces 正在维护或暂时不可用。"
    if any(token in lower for token in ("access denied", "forbidden", "403")):
        return "Codeforces 仍然拒绝提交，可能是风控、验证码、维护或账号安全确认。"
    if not text:
        return "Codeforces 页面没有返回可读错误。"
    return text[:220]


def _diagnose_cf_block(page_html: str) -> str:
    lower = page_html.lower()
    if "cf-error" in lower or "cloudflare" in lower or "attention required" in lower:
        return "Codeforces 返回访问保护页，可能触发了 Cloudflare/风控。"
    if "captcha" in lower or "recaptcha" in lower or "enter the characters" in lower:
        return "Codeforces 要求验证码/人机验证。"
    if "technical maintenance" in lower or "temporarily unavailable" in lower or "can't be reached" in lower:
        return "Codeforces 正在维护或暂时不可用。"
    if "access denied" in lower or "403 forbidden" in lower:
        return "Codeforces 返回 403 Forbidden。"
    if "security" in lower and ("verification" in lower or "confirm" in lower):
        return "Codeforces 要求账号安全确认。"
    return ""


def _wait_quiet(page, timeout_error_class) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except timeout_error_class:
        return


def _browser_login(page, username: str, password: str, handle: str, timeout_error_class) -> None:
    content = page.content()
    block_reason = _diagnose_cf_block(content)
    if block_reason:
        raise RuntimeError(block_reason)

    if page.locator('input[name="handleOrEmail"]').count() <= 0:
        raise RuntimeError("Codeforces 登录页没有找到账号输入框。")
    if page.locator('input[name="password"]').count() <= 0:
        raise RuntimeError("Codeforces 登录页没有找到密码输入框。")

    page.fill('input[name="handleOrEmail"]', username)
    page.fill('input[name="password"]', password)
    remember = page.locator('input[name="remember"]').first
    if remember.count() > 0:
        try:
            remember.check()
        except Exception:
            pass

    submit = page.locator('input[type="submit"], button[type="submit"]').first
    if submit.count() <= 0:
        raise RuntimeError("Codeforces 登录页没有找到登录按钮。")
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
            submit.click()
    except timeout_error_class:
        pass
    _wait_quiet(page, timeout_error_class)

    content = page.content()
    if _looks_logged_in(content, handle):
        return
    error = _extract_cf_error(content) or _diagnose_cf_block(content)
    suffix = f"：{error}" if error else "，可能需要验证码、二次验证或账号安全确认。"
    raise RuntimeError("Codeforces 浏览器登录失败" + suffix)


def _set_if_present(page, selector: str, value: str) -> bool:
    if page.locator(selector).count() <= 0:
        return False
    page.eval_on_selector(
        selector,
        """
        (el, value) => {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """,
        value,
    )
    return True


def _select_if_present(page, selector: str, value: str) -> bool:
    if page.locator(selector).count() <= 0:
        return False
    page.select_option(selector, value)
    return True


def _click_submit(page, timeout_error_class) -> bool:
    if page.locator('textarea[name="source"]').count() > 0:
        clicked = False
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                clicked = bool(page.eval_on_selector(
                    'textarea[name="source"]',
                    """
                    (el) => {
                        const form = el.form;
                        if (!form) return false;
                        const button = form.querySelector('input[type="submit"], button[type="submit"], input.submit');
                        if (button) {
                            button.click();
                        } else if (form.requestSubmit) {
                            form.requestSubmit();
                        } else {
                            form.submit();
                        }
                        return true;
                    }
                    """,
                ))
        except timeout_error_class:
            clicked = True
        if clicked:
            return True

    selectors = [
        'form input[type="submit"]',
        'form button[type="submit"]',
        'input.submit',
        'button:has-text("Submit")',
        'input[value="Submit"]',
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() <= 0:
            continue
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                locator.click()
        except timeout_error_class:
            pass
        return True
    return False


def _same_problem(submission: dict, problem: CFProblem) -> bool:
    raw_problem = submission.get("problem") or {}
    return int(raw_problem.get("contestId") or 0) == problem.contest_id and str(raw_problem.get("index") or "") == problem.index


def _find_new_matching_submission(
    submissions: Iterable[dict],
    problem: CFProblem,
    before_id: int,
    *,
    submitted_after: int = 0,
) -> Optional[dict]:
    matches = [
        submission
        for submission in submissions
        if int(submission.get("id") or 0) > before_id
        and int(submission.get("creationTimeSeconds") or 0) >= submitted_after
        and _same_problem(submission, problem)
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: int(item.get("id") or 0))


def _result_from_submission(submission: dict) -> RemoteJudgeResult:
    verdict = str(submission.get("verdict") or "UNKNOWN")
    submission_id = int(submission.get("id") or 0) or None
    passed_tests = submission.get("passedTestCount")
    time_ms = submission.get("timeConsumedMillis")
    memory_bytes = submission.get("memoryConsumedBytes")
    readable = _VERDICT_ZH.get(verdict, verdict.replace("_", " ").title())
    if passed_tests is not None and verdict != "OK":
        message = f"{readable}，已通过 {passed_tests} 个测试点。"
    elif passed_tests is not None:
        message = f"{readable}，通过 {passed_tests} 个测试点。"
    else:
        message = readable
    return RemoteJudgeResult(
        accepted=verdict == "OK",
        verdict=verdict,
        message=message,
        submission_id=submission_id,
        passed_tests=int(passed_tests) if passed_tests is not None else None,
        time_ms=int(time_ms) if time_ms is not None else None,
        memory_bytes=int(memory_bytes) if memory_bytes is not None else None,
        url=_submission_url(submission),
    )


def _pending_result(submission: dict, message: str) -> RemoteJudgeResult:
    return RemoteJudgeResult(
        accepted=False,
        verdict=str(submission.get("verdict") or "PENDING"),
        message=message,
        submission_id=int(submission.get("id") or 0) or None,
        passed_tests=submission.get("passedTestCount"),
        time_ms=submission.get("timeConsumedMillis"),
        memory_bytes=submission.get("memoryConsumedBytes"),
        url=_submission_url(submission),
    )


def _submission_url(submission: dict) -> str:
    submission_id = submission.get("id")
    contest_id = submission.get("contestId") or (submission.get("problem") or {}).get("contestId")
    if not submission_id or not contest_id:
        return ""
    return f"{CODEFORCES_BASE_URL}/contest/{contest_id}/submission/{submission_id}"


def _absolute_url(path_or_url: str) -> str:
    return urllib.parse.urljoin(CODEFORCES_BASE_URL, path_or_url)


def _browser_headers(referer: str = "", form: bool = False) -> Dict[str, str]:
    headers = {
        "User-Agent": _BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if form:
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": CODEFORCES_BASE_URL,
                "Referer": _absolute_url(referer),
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
    else:
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none" if not referer else "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        if referer:
            headers["Referer"] = _absolute_url(referer)
    return headers


def _extract_submission_ids(page_html: str, contest_id: int) -> List[int]:
    ids: List[int] = []
    seen = set()
    patterns = [
        rf"/contest/{contest_id}/submission/(\d+)",
        rf"/problemset/submission/{contest_id}/(\d+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, page_html):
            submission_id = int(match.group(1))
            if submission_id not in seen:
                seen.add(submission_id)
                ids.append(submission_id)
    return ids


def _extract_program_source(page_html: str) -> str:
    match = re.search(
        r"<pre[^>]*id=[\"']program-source-text[\"'][^>]*>(.*?)</pre>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
