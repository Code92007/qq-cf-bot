from __future__ import annotations

import logging
import queue
import hashlib
import html
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .cf_statement import CodeforcesStatementClient
from .codeforces import CodeforcesClient
from .config import Config
from .judge import SolutionJudge
from .luogu import LuoguClient
from .message import extract_plain_text, looks_like_code_submission, parse_code_submission, parse_command
from .models import CFProblem, CodeSubmission, GroupMessage, ProblemStatement, RatingRange, RemoteJudgeResult
from .onebot import OneBotClient
from .rank_renderer import RanklistRenderer
from .rating import accepted_rating_update, leaderboard_rating
from .renderer import StatementRenderer
from .selector import ProblemSelector
from .security import redact_sensitive_text
from .solution_bank import SolutionBank
from .solution_generator import LLMSolutionGenerator
from .storage import SentProblemStore
from .submitter import CodeforcesRemoteJudge
from .translator import OpenAIStatementTranslator


LOGGER = logging.getLogger(__name__)

_HELP_TEXT = """可用命令：
/help：查看帮助；只 @ 我也会显示本帮助
/new：出一道默认难度题
/new 2100 2400：临时指定难度出题
/rating：查看本群默认难度
/cfset rating 1900 2600：设置本群默认难度
/cur：重发当前题
/giveup：放弃当前题
/ranklist：查看群内榜单
/submit 做法：提交口头做法审核（需配置模型）
/solutions：题目结束前不公开题解来源
/submitcode cpp + 代码：提交代码到 CF（需开启远端提交）"""


@dataclass
class PushResult:
    problem: CFProblem
    image_count: int


@dataclass(frozen=True)
class _QueuedCodeSubmission:
    group_id: int
    user_id: int
    sender_name: str
    problem: CFProblem
    submission: CodeSubmission


class CodeforcesPushBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.cf = CodeforcesClient(config.cache_path, config.cf_cache_ttl_seconds)
        self.luogu = LuoguClient()
        self.cf_statement = CodeforcesStatementClient()
        self.store = SentProblemStore(config.db_path, config.dedup_scope)
        self.selector = ProblemSelector(config.min_rating, config.max_rating)
        self.renderer = StatementRenderer(
            config.asset_dir,
            width=config.render_width,
            viewport_height=config.render_viewport_height,
            max_slice_height=config.render_max_slice_height,
        )
        self.rank_renderer = RanklistRenderer(config.asset_dir, width=config.render_width)
        self.judge = SolutionJudge(
            api_url=config.judge_api_url,
            api_key=config.judge_api_key,
            model=config.judge_model,
            wire_api=config.judge_wire_api,
            timeout_seconds=config.judge_timeout_seconds,
            max_statement_chars=config.judge_statement_max_chars,
            max_solution_context_chars=config.judge_solution_context_max_chars,
            enabled=config.judge_enabled,
        )
        self.onebot = OneBotClient(
            config.onebot_http_url,
            config.onebot_access_token,
            config.onebot_image_mode,
            config.onebot_self_id,
        )
        self.remote_judge = CodeforcesRemoteJudge(
            username=config.cf_username,
            password=config.cf_password,
            handle=config.cf_handle,
            forced_language_id=config.cf_submit_language_id,
            http_timeout_seconds=config.cf_submit_http_timeout_seconds,
            poll_interval_seconds=config.cf_submit_poll_interval_seconds,
            poll_timeout_seconds=config.cf_submit_poll_timeout_seconds,
        )
        self.solution_generator = LLMSolutionGenerator(
            api_url=config.judge_api_url,
            api_key=config.judge_api_key,
            model=config.judge_model,
            wire_api=config.judge_wire_api,
            timeout_seconds=config.judge_timeout_seconds,
            enabled=config.solution_bank_generate_llm and config.judge_enabled,
            max_statement_chars=config.judge_statement_max_chars,
        )
        self.solution_bank = SolutionBank(
            store=self.store,
            luogu=self.luogu,
            remote_judge=self.remote_judge,
            solution_generator=self.solution_generator,
            enabled=config.solution_bank_enabled,
            min_refs=config.solution_bank_min_refs,
            max_refs=config.solution_bank_max_refs,
            max_ref_chars=config.solution_bank_max_ref_chars,
            fetch_luogu=config.solution_bank_fetch_luogu,
            fetch_cf_editorial=config.solution_bank_fetch_cf_editorial,
            fetch_cf_ac_code=config.solution_bank_fetch_cf_ac_code,
        )
        self.translator = OpenAIStatementTranslator(
            api_url=config.translate_api_url,
            api_key=config.translate_api_key,
            model=config.translate_model,
            wire_api=config.translate_wire_api,
            timeout_seconds=config.translate_timeout_seconds,
            max_chars=config.translate_max_chars,
            enabled=config.translate_enabled,
        )
        self._code_queue: "queue.Queue[_QueuedCodeSubmission]" = queue.Queue()
        self._code_worker_started = False
        if config.cf_submit_enabled:
            self._start_code_worker()
        self._locks: Dict[int, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def handle_group_message(self, event: GroupMessage) -> None:
        if self.config.allowed_groups and event.group_id not in self.config.allowed_groups:
            LOGGER.info("ignore command from disallowed group %s", event.group_id)
            return

        command = parse_command(event.message)
        direct_code = False
        if command is None:
            if not (self.config.cf_auto_submit_direct_code and looks_like_code_submission(event.message)):
                return
            direct_code = True
        elif command.name not in {
            "help",
            "new",
            "cur",
            "giveup",
            "ranklist",
            "submit",
            "submitcode",
            "cfset",
            "rating",
            "solutions",
            "solution",
        }:
            return

        if command.name == "help":
            self.handle_help(event)
            return

        lock = self._group_lock(event.group_id)
        if not lock.acquire(blocking=False):
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} 上一个操作还在处理中，稍等一下。")
            return

        try:
            if direct_code:
                self.handle_submitcode(event, extract_plain_text(event.message))
            elif command is None:
                return
            elif command.name == "new":
                self.handle_new(event, command.arg)
            elif command.name == "cur":
                self.handle_cur(event)
            elif command.name == "giveup":
                self.handle_giveup(event)
            elif command.name == "ranklist":
                self.handle_ranklist(event)
            elif command.name in {"solutions", "solution"}:
                self.handle_solutions(event)
            elif command.name == "submit":
                self.handle_submit(event, command.arg)
            elif command.name == "submitcode":
                self.handle_submitcode(event, command.arg)
            elif command.name == "cfset":
                self.handle_cfset(event, command.arg)
            elif command.name == "rating":
                self.handle_rating(event)
        except Exception:
            LOGGER.exception(
                "failed to handle command %s in group %s",
                "direct-code" if direct_code or command is None else command.name,
                event.group_id,
            )
            self.onebot.send_group_text(event.group_id, "操作失败了：题库、中文题面、图片渲染或判题服务暂时不可用。")
        finally:
            lock.release()

    def handle_new(self, event: GroupMessage, arg: str = "") -> None:
        if self.store.get_active_problem(event.group_id) is not None:
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} 上一道题还没做完哦~")
            return

        rating_range = self._rating_range_for_new(event.group_id, arg)
        result = self.push_new_problem(event.group_id, rating_range)
        LOGGER.info(
            "pushed %s to group %s as %s image(s)",
            result.problem.cf_id,
            event.group_id,
            result.image_count,
        )

    def handle_help(self, event: GroupMessage) -> None:
        self.onebot.send_group_text(event.group_id, _HELP_TEXT)

    def handle_cur(self, event: GroupMessage) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        self.onebot.send_group_text(event.group_id, "当前题面在这里。")
        self._send_statement_images(event.group_id, active.images)

    def handle_giveup(self, event: GroupMessage) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目可以放弃。")
            return
        self.store.clear_active_problem(event.group_id)
        self.onebot.send_group_text(
            event.group_id,
            "已放弃当前题：\n" + self._problem_summary(active.problem, active.statement),
        )

    def handle_ranklist(self, event: GroupMessage) -> None:
        stats = self.store.list_group_stats(event.group_id)
        if not stats:
            self.onebot.send_group_text(event.group_id, "当前还没有通过记录。")
            return
        image = self.rank_renderer.render(event.group_id, stats)
        self.onebot.send_group_image(event.group_id, image)

    def handle_submit(self, event: GroupMessage, submission: str) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        if not submission.strip():
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} 请在 /submit 后面写你的做法。")
            return
        if not self.judge.configured:
            self.onebot.send_group_text(event.group_id, _JUDGE_SETUP_HINT)
            return

        solution_references = self.solution_bank.ensure(active.problem, active.statement)
        solution_context = self.solution_bank.context_for_prompt(
            solution_references,
            self.config.judge_solution_context_max_chars,
        )
        result = self.judge.judge(
            active.problem,
            active.statement,
            submission,
            solution_references=solution_references,
            solution_context=solution_context,
        )
        self.store.record_submission(
            event.group_id,
            event.user_id,
            event.sender_name,
            active.problem,
            submission,
            result.accepted,
            result.reason,
        )

        if not result.accepted:
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} {result.reason}")
            return

        old_stat = self.store.get_user_stat(
            event.group_id,
            event.user_id,
            event.sender_name,
            self.config.initial_rating,
        )
        new_rating = accepted_rating_update(
            old_stat.rating,
            active.problem.rating,
            self.config.rating_k_factor,
        )
        new_stat = self.store.mark_solved(
            event.group_id,
            event.user_id,
            event.sender_name,
            new_rating,
            self.config.initial_rating,
        )
        self.store.clear_active_problem(event.group_id)
        self.onebot.send_group_text(
            event.group_id,
            (
                f"恭喜@{event.sender_name} 拿下本题 first blood! "
                f"本题信息：\n{self._problem_summary(active.problem, active.statement)}\n"
                f"通过数：{new_stat.solved_count}，榜单 Rating："
                f"{leaderboard_rating(new_stat.solved_ratings, new_stat.rating):.2f}"
            ),
        )

    def handle_solutions(self, event: GroupMessage) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        self.onebot.send_group_text(event.group_id, "当前题还未结束，不能提前公开题解来源。")

    def handle_submitcode(self, event: GroupMessage, raw_submission: str) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        if not self.remote_judge.configured:
            self.onebot.send_group_text(event.group_id, "CF 提交账号未配置完整，至少需要 CF_USERNAME 和 CF_PASSWORD。")
            return
        if not self.config.cf_submit_enabled:
            self.onebot.send_group_text(
                event.group_id,
                "CF 远端提交被 CF_SUBMIT_ENABLED=false 关闭，改成 true 或 auto 后可用。",
            )
            return

        parsed = parse_code_submission(raw_submission, default_language=self.config.cf_submit_default_language)
        if parsed is None or not parsed.source.strip():
            self.onebot.send_group_text(
                event.group_id,
                f"@{event.sender_name} 请在 /submitcode 后粘贴代码，或使用 ```cpp 代码块。",
            )
            return

        job = _QueuedCodeSubmission(
            group_id=event.group_id,
            user_id=event.user_id,
            sender_name=event.sender_name,
            problem=active.problem,
            submission=CodeSubmission(language=parsed.language, source=parsed.source),
        )
        self._code_queue.put(job)
        position = self._code_queue.qsize()
        self.onebot.send_group_text(
            event.group_id,
            (
                f"@{event.sender_name} 已加入 CF 远端提交队列。"
                f"语言 {parsed.language}，当前队列约 {position} 个。"
            ),
        )

    def handle_cfset(self, event: GroupMessage, arg: str) -> None:
        parsed = _parse_rating_range(arg)
        if parsed is None:
            self.onebot.send_group_text(event.group_id, "用法：/cfset rating 1900 2600")
            return
        min_rating, max_rating = parsed
        self.store.set_rating_range(event.group_id, min_rating, max_rating)
        self.onebot.send_group_text(event.group_id, f"本群默认 Codeforces 难度已设置为 {min_rating}-{max_rating}。")

    def handle_rating(self, event: GroupMessage) -> None:
        rating_range = self.store.get_rating_range(event.group_id, self.config.min_rating, self.config.max_rating)
        self.onebot.send_group_text(event.group_id, f"本群当前默认 Codeforces 难度：{rating_range.min_rating}-{rating_range.max_rating}")

    def push_new_problem(self, group_id: int, rating_range: Optional[RatingRange] = None) -> PushResult:
        if rating_range is None:
            rating_range = self.store.get_rating_range(group_id, self.config.min_rating, self.config.max_rating)
        sent_ids = self.store.sent_ids(group_id)
        problems = self.cf.fetch_problems()
        attempted = 0
        last_error: Optional[Exception] = None

        for problem in self.selector.shuffled_candidates(
            problems,
            sent_ids,
            rating_range.min_rating,
            rating_range.max_rating,
        ):
            if attempted >= self.config.max_selection_attempts:
                break
            attempted += 1
            try:
                statement = self._fetch_renderable_statement(problem)
                images = self.renderer.render(problem, statement, reveal_metadata=False)
            except Exception as exc:
                last_error = exc
                LOGGER.warning("skip %s because statement rendering failed: %s", problem.cf_id, exc)
                continue

            self.onebot.send_group_text(group_id, "刷新了一道新题目~")
            self._send_statement_images(group_id, images)
            self.store.mark_sent(group_id, problem)
            self.store.set_active_problem(group_id, problem, statement, images)
            return PushResult(problem=problem, image_count=len(images))

        if last_error is not None:
            raise RuntimeError(f"no renderable unsent problem found after {attempted} attempts") from last_error
        raise RuntimeError(
            f"no unsent Codeforces problem remains in rating range {rating_range.min_rating}-{rating_range.max_rating}"
        )

    def _fetch_renderable_statement(self, problem: CFProblem) -> ProblemStatement:
        cached = self.store.get_cached_statement(problem.cf_id, require_translated=self.translator.configured)
        if cached is not None:
            if self.translator.configured and _needs_statement_translation(cached):
                try:
                    return self._translate_and_cache_if_needed(problem, cached, source="cached")
                except Exception as exc:
                    LOGGER.warning("cached statement translation failed for %s: %s", problem.cf_id, exc)
            return cached
        cached_untranslated = self.store.get_cached_statement(problem.cf_id) if self.translator.configured else None

        try:
            statement = self.luogu.fetch_statement(problem)
            return self._translate_and_cache_if_needed(problem, statement, source="luogu")
        except Exception as luogu_error:
            if self.config.fallback_statement_source != "codeforces":
                raise
            LOGGER.warning("Luogu statement failed for %s, falling back to Codeforces: %s", problem.cf_id, luogu_error)

        statement = cached_untranslated or self.cf_statement.fetch_statement(problem)
        return self._translate_and_cache_if_needed(problem, statement, source="codeforces")

    def _translate_and_cache_if_needed(self, problem: CFProblem, statement: ProblemStatement, source: str) -> ProblemStatement:
        from dataclasses import replace

        if not self.translator.configured:
            self.store.cache_statement(problem, statement, source=source, translated=not _needs_statement_translation(statement))
            return statement

        try:
            if _needs_body_translation(statement):
                translated = self.translator.translate_statement(statement)
                self.store.cache_statement(problem, translated, source=f"{source}_llm_translate", translated=True)
                return translated
            if _needs_title_translation(statement.title):
                translated = replace(statement, title=self.translator.translate_title(statement.title or problem.name))
                self.store.cache_statement(problem, translated, source=f"{source}_llm_title_translate", translated=True)
                return translated
        except Exception as exc:
            LOGGER.warning("statement translation failed for %s from %s: %s", problem.cf_id, source, exc)

        self.store.cache_statement(problem, statement, source=source, translated=not _needs_statement_translation(statement))
        return statement

    def _group_lock(self, group_id: int) -> threading.Lock:
        with self._locks_lock:
            lock = self._locks.get(group_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[group_id] = lock
            return lock

    def _problem_summary(self, problem: CFProblem, statement: Optional[ProblemStatement] = None) -> str:
        tags = ", ".join(problem.tags[:8]) if problem.tags else "无"
        title = statement.title if statement and statement.title else problem.name
        return (
            f"{problem.luogu_pid} {title}\n"
            f"难度：{problem.rating}\n"
            f"标签：{tags}\n"
            f"题目：{problem.cf_url}\n"
            f"中文题面：{problem.luogu_url}"
        )

    def _current_problem_text(self, problem: CFProblem) -> str:
        return "题目在这里~"

    def _send_statement_images(self, group_id: int, images: Iterable[Path]) -> None:
        image_list = list(images)
        try:
            self.onebot.send_group_forward_images(group_id, image_list)
        except Exception:
            LOGGER.exception("failed to send merged forward, falling back to regular image messages")
            self.onebot.send_group_problem(group_id, "题面", image_list)

    def _rating_range_for_new(self, group_id: int, arg: str) -> RatingRange:
        parsed = _parse_rating_range(arg)
        if parsed is not None:
            return RatingRange(*parsed)
        return self.store.get_rating_range(group_id, self.config.min_rating, self.config.max_rating)

    def _start_code_worker(self) -> None:
        if self._code_worker_started:
            return
        thread = threading.Thread(target=self._code_worker, name="cf-code-submit-worker", daemon=True)
        thread.start()
        self._code_worker_started = True

    def _code_worker(self) -> None:
        while True:
            job = self._code_queue.get()
            try:
                self._process_code_submission(job)
            except Exception as exc:
                LOGGER.exception("failed to process remote code submission")
                safe_error = redact_sensitive_text(str(exc))
                if len(safe_error) > 160:
                    safe_error = safe_error[:160].rstrip() + "..."
                self.onebot.send_group_text(job.group_id, f"@{job.sender_name} CF 远端提交失败：{safe_error or '服务暂时不可用。'}")
            finally:
                self._code_queue.task_done()

    def _process_code_submission(self, job: _QueuedCodeSubmission) -> None:
        active = self.store.get_active_problem(job.group_id)
        if active is None or active.problem.cf_id != job.problem.cf_id:
            self.onebot.send_group_text(job.group_id, f"@{job.sender_name} 当前题目已变化，本次提交取消。")
            return

        self._wait_for_submit_interval(job.group_id)
        self.store.set_meta_float("cf_last_submit_at", time.time())
        self.onebot.send_group_text(
            job.group_id,
            f"@{job.sender_name} 开始提交到 Codeforces，语言 {job.submission.language}。",
        )
        result = self.remote_judge.judge(job.problem, job.submission)
        self._record_remote_result(job, result)
        if result.accepted:
            self._settle_accepted_code(job, result)
            return
        self.onebot.send_group_text(job.group_id, self._remote_result_text(job.sender_name, result))

    def _wait_for_submit_interval(self, group_id: int) -> None:
        interval = max(0, self.config.cf_submit_min_interval_seconds)
        if interval <= 0:
            return
        last_submit_at = self.store.get_meta_float("cf_last_submit_at", 0.0)
        wait_seconds = int(max(0.0, last_submit_at + interval - time.time()))
        if wait_seconds <= 0:
            return
        self.onebot.send_group_text(group_id, f"为保护 CF 账号，距离上次提交过近，将等待约 {wait_seconds} 秒后提交。")
        time.sleep(wait_seconds)

    def _record_remote_result(self, job: _QueuedCodeSubmission, result: RemoteJudgeResult) -> None:
        source_hash = hashlib.sha256(job.submission.source.encode("utf-8")).hexdigest()
        self.store.record_code_submission(
            job.group_id,
            job.user_id,
            job.sender_name,
            job.problem,
            job.submission.language,
            source_hash,
            len(job.submission.source),
            result,
        )

    def _settle_accepted_code(self, job: _QueuedCodeSubmission, result: RemoteJudgeResult) -> None:
        active = self.store.get_active_problem(job.group_id)
        if active is None or active.problem.cf_id != job.problem.cf_id:
            self.onebot.send_group_text(
                job.group_id,
                self._remote_result_text(job.sender_name, result) + "\n题目已变化，不结算榜单。",
            )
            return

        old_stat = self.store.get_user_stat(
            job.group_id,
            job.user_id,
            job.sender_name,
            self.config.initial_rating,
        )
        new_rating = accepted_rating_update(
            old_stat.rating,
            job.problem.rating,
            self.config.rating_k_factor,
        )
        new_stat = self.store.mark_solved(
            job.group_id,
            job.user_id,
            job.sender_name,
            new_rating,
            self.config.initial_rating,
        )
        self.store.clear_active_problem(job.group_id)
        self.onebot.send_group_text(
            job.group_id,
            (
                self._remote_result_text(job.sender_name, result, reveal_details=True)
                + "\n"
                + f"恭喜@{job.sender_name} 拿下本题 first blood! "
                + f"本题信息：\n{self._problem_summary(job.problem, active.statement)}\n"
                + f"通过数：{new_stat.solved_count}，榜单 Rating："
                + f"{leaderboard_rating(new_stat.solved_ratings, new_stat.rating):.2f}"
            ),
        )

    def _remote_result_text(self, sender_name: str, result: RemoteJudgeResult, reveal_details: bool = False) -> str:
        parts = [f"@{sender_name} CF verdict：{result.message}"]
        if reveal_details and result.submission_id:
            parts.append(f"提交 ID：{result.submission_id}")
        if result.time_ms is not None:
            parts.append(f"耗时：{result.time_ms} ms")
        if result.memory_bytes is not None:
            parts.append(f"内存：{result.memory_bytes // 1024} KB")
        if reveal_details and result.url:
            parts.append(result.url)
        return "\n".join(parts)


def _parse_rating_range(arg: str) -> Optional[Tuple[int, int]]:
    text = arg.strip().lower()
    if text.startswith("rating"):
        text = text[len("rating") :].strip()
    if not text:
        return None
    parts = text.replace(",", " ").replace("-", " ").split()
    if len(parts) < 2:
        return None
    try:
        min_rating = int(parts[0])
        max_rating = int(parts[1])
    except ValueError:
        return None
    if min_rating > max_rating:
        min_rating, max_rating = max_rating, min_rating
    if min_rating < 800 or max_rating > 4000:
        return None
    return min_rating, max_rating


_JUDGE_SETUP_HINT = """还没有配置判题模型，无法审核 /submit。
服务器 .env 至少需要：
JUDGE_ENABLED=true
JUDGE_API_URL=<模型服务地址>
JUDGE_API_KEY=<密钥>
JUDGE_MODEL=<模型名>
如果复用 Codex 的 responses 配置，再加 JUDGE_WIRE_API=responses；
如果服务端要求 WebSocket upgrade，改成 JUDGE_WIRE_API=responses_stream。"""


def _needs_title_translation(title: str) -> bool:
    text = title.strip()
    if not text:
        return False
    if re.search(r"[\u4e00-\u9fff]", text):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def _needs_statement_translation(statement: ProblemStatement) -> bool:
    return _needs_title_translation(statement.title) or _needs_body_translation(statement)


def _needs_body_translation(statement: ProblemStatement) -> bool:
    text = _visible_statement_text(
        " ".join(
            [
                statement.description,
                statement.input_format,
                statement.output_format,
                statement.hint,
            ]
        )
    )
    if not text:
        return False

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = re.findall(r"[A-Za-z][A-Za-z']{2,}", text)
    if len(english_words) < 8:
        return False
    if cjk_chars == 0:
        return True
    return len(english_words) >= 20 and len(english_words) > cjk_chars / 2


def _visible_statement_text(value: str) -> str:
    text = re.sub(r"\${1,3}.*?\${1,3}", " ", value, flags=re.DOTALL)
    text = re.sub(r"\\\(.+?\\\)|\\\[.+?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
