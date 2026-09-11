from __future__ import annotations

import logging
import queue
import html
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

from .config import Config
from .core import ChallengeActor, ChallengeService
from .message import extract_plain_text, looks_like_code_submission, parse_code_submission, parse_command
from .models import ActiveProblem, CFProblem, CodeSubmission, GroupMessage, PreparedProblem, ProblemStatement, RatingRange, RemoteJudgeResult
from .onebot import OneBotClient
from .rank_renderer import RanklistRenderer
from .renderer import StatementRenderer
from .security import redact_sensitive_text


LOGGER = logging.getLogger(__name__)

_REMOTE_SUBMIT_QUEUE_NOTICE_THRESHOLD = 3

_HELP_TEXT = """可用命令：
/help：查看帮助；只 @ 我也会显示本帮助
/new：出一道默认难度题
/new 2100 2400：临时指定难度出题
/share 1704F：分享指定 CF 题，不计入榜单
/rating：查看本群默认难度
/cfset rating 1900 2600：设置本群默认难度
/cur：重发当前题
/giveup：放弃当前题
/ranklist：查看群内榜单
/submit 做法：提交口头做法审核（需配置模型）
/submitcode + 代码：自动识别语言并提交到 CF（需开启远端提交）"""


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
    ranked: bool


class CodeforcesPushBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.challenge_service = ChallengeService(config)
        # These aliases preserve the existing adapter surface while the shared
        # service owns all domain dependencies.
        self.cf = self.challenge_service.cf
        self.luogu = self.challenge_service.luogu
        self.cf_statement = self.challenge_service.cf_statement
        self.store = self.challenge_service.store
        self.selector = self.challenge_service.selector
        self.judge = self.challenge_service.judge
        self.remote_judge = self.challenge_service.remote_judge
        self.solution_bank = self.challenge_service.solution_bank
        self.translator = self.challenge_service.translator
        self.renderer = StatementRenderer(
            config.asset_dir,
            width=config.render_width,
            viewport_height=config.render_viewport_height,
            max_slice_height=config.render_max_slice_height,
        )
        self.rank_renderer = RanklistRenderer(config.asset_dir, width=config.render_width)
        self.onebot = OneBotClient(
            config.onebot_http_url,
            config.onebot_access_token,
            config.onebot_image_mode,
            config.onebot_self_id,
        )
        self._code_queue: "queue.Queue[_QueuedCodeSubmission]" = queue.Queue()
        self._code_worker_started = False
        if config.code_submit_enabled:
            self._start_code_worker()
        self._locks: Dict[int, threading.Lock] = {}
        self._locks_lock = threading.Lock()
        self._prefetch_inflight: Set[Tuple[int, int, int]] = set()
        self._prefetch_lock = threading.Lock()

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
            "share",
            "cur",
            "giveup",
            "ranklist",
            "submit",
            "submitcode",
            "cfset",
            "rating",
        }:
            return

        command_name = "direct-code" if direct_code or command is None else command.name
        LOGGER.info(
            "bot command accepted group=%s user=%s message_id=%s command=%s",
            event.group_id,
            event.user_id,
            event.message_id,
            command_name,
        )
        if self.store.update_user_display_name(event.group_id, event.user_id, event.sender_name):
            LOGGER.info(
                "updated ranklist display name group=%s user=%s display_name=%s",
                event.group_id,
                event.user_id,
                event.sender_name,
            )

        started_at = time.monotonic()
        if command is not None and command.name == "help":
            try:
                self.handle_help(event)
            except Exception:
                LOGGER.exception(
                    "failed to handle command %s in group %s",
                    command_name,
                    event.group_id,
                )
            finally:
                LOGGER.info(
                    "bot command finished group=%s user=%s message_id=%s command=%s elapsed=%.2fs",
                    event.group_id,
                    event.user_id,
                    event.message_id,
                    command_name,
                    time.monotonic() - started_at,
                )
            return

        lock = self._group_lock(event.group_id)
        if not lock.acquire(blocking=False):
            LOGGER.info(
                "bot command blocked by group lock group=%s user=%s message_id=%s command=%s",
                event.group_id,
                event.user_id,
                event.message_id,
                command_name,
            )
            self._send_group_text_best_effort(event.group_id, f"@{event.sender_name} 上一个操作还在处理中，稍等一下。")
            return

        try:
            if direct_code:
                self.handle_submitcode(event, extract_plain_text(event.message))
            elif command is None:
                return
            elif command.name == "new":
                self.handle_new(event, command.arg)
            elif command.name == "share":
                self.handle_share(event, command.arg)
            elif command.name == "cur":
                self.handle_cur(event)
            elif command.name == "giveup":
                self.handle_giveup(event)
            elif command.name == "ranklist":
                self.handle_ranklist(event)
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
                command_name,
                event.group_id,
            )
            self._send_group_text_best_effort(event.group_id, "操作失败了：题库、中文题面、图片渲染或判题服务暂时不可用。")
        finally:
            LOGGER.info(
                "bot command finished group=%s user=%s message_id=%s command=%s elapsed=%.2fs",
                event.group_id,
                event.user_id,
                event.message_id,
                command_name,
                time.monotonic() - started_at,
            )
            lock.release()

    def _send_group_text_best_effort(self, group_id: int, text: str) -> None:
        try:
            self.onebot.send_group_text(group_id, text)
        except Exception:
            LOGGER.exception("failed to send group text group=%s", group_id)

    def _challenge_core(self) -> ChallengeService:
        service = getattr(self, "challenge_service", None)
        if service is not None:
            return service
        # A few adapter-level tests construct the bot without its network
        # dependencies. Build the same service facade from their fakes.
        service = ChallengeService.__new__(ChallengeService)
        service.config = self.config
        service.store = self.store
        service.judge = self.judge
        service.solution_bank = self.solution_bank
        service.remote_judge = getattr(self, "remote_judge", None)
        service._submit_lock = threading.Lock()
        self.challenge_service = service
        return service

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

    def handle_share(self, event: GroupMessage, arg: str) -> None:
        if self.store.get_active_problem(event.group_id) is not None:
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} 上一道题还没做完哦~")
            return
        parsed = _parse_problem_id(arg)
        if parsed is None:
            self.onebot.send_group_text(event.group_id, "用法：/share 1704F 或 /share https://codeforces.com/contest/1704/problem/F")
            return

        contest_id, index = parsed
        problem = self._find_problem_by_id(contest_id, index)
        prepared = self._prepare_specific_problem(problem)
        self._publish_prepared_problem(event.group_id, prepared, intro_text="分享了一道题目~", ranked=False)
        LOGGER.info("shared %s to group %s as %s image(s)", problem.cf_id, event.group_id, len(prepared.images))

    def handle_help(self, event: GroupMessage) -> None:
        self.onebot.send_group_text(event.group_id, _HELP_TEXT)

    def handle_cur(self, event: GroupMessage) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        active = self._refresh_active_statement_if_needed(event.group_id, active)
        self._send_statement_images(event.group_id, active.images, intro_text="当前题面在这里。")

    def handle_giveup(self, event: GroupMessage) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目可以放弃。")
            return
        wait_seconds = self._giveup_wait_seconds(active)
        if wait_seconds > 0:
            self.onebot.send_group_text(event.group_id, f"这题刚刷出来，还要等约 {wait_seconds} 秒才能 /giveup。")
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

        started_at = time.monotonic()
        LOGGER.info(
            "oral submit judge start group=%s user=%s cf_id=%s ranked=%s chars=%s",
            event.group_id,
            event.user_id,
            active.problem.cf_id,
            active.ranked,
            len(submission),
        )

        outcome = self._challenge_core().submit_solution(
            ChallengeActor(
                scope_id=event.group_id,
                leaderboard_id=event.group_id,
                user_id=event.user_id,
                display_name=event.sender_name,
            ),
            submission,
        )
        LOGGER.info(
            "oral submit judged group=%s cf_id=%s accepted=%s elapsed=%.2fs",
            event.group_id,
            active.problem.cf_id,
            outcome.accepted,
            time.monotonic() - started_at,
        )

        if not outcome.accepted:
            self.onebot.send_group_text(event.group_id, f"@{event.sender_name} {outcome.reason}")
            return

        if not active.ranked:
            self.onebot.send_group_text(
                event.group_id,
                (
                    f"恭喜@{event.sender_name} 通过这道分享题！本题不计入榜单。\n"
                    f"本题信息：\n{self._problem_summary(active.problem, active.statement)}"
                ),
            )
            return

        new_stat = outcome.stat
        if new_stat is None:
            raise RuntimeError("accepted ranked submission was not settled")
        self.onebot.send_group_text(
            event.group_id,
            (
                f"恭喜@{event.sender_name} 拿下本题 first blood! "
                f"本题信息：\n{self._problem_summary(active.problem, active.statement)}\n"
                f"通过数：{new_stat.solved_count}，榜单 Rating："
                f"{outcome.leaderboard_rating:.2f}"
            ),
        )

    def handle_submitcode(self, event: GroupMessage, raw_submission: str) -> None:
        active = self.store.get_active_problem(event.group_id)
        if active is None:
            self.onebot.send_group_text(event.group_id, "当前没有题目，用 /new 刷一道。")
            return
        if not self.remote_judge.configured:
            self.onebot.send_group_text(event.group_id, "远端代码判题账号未配置完整，请检查当前提交载具的账号或 Cookie。")
            return
        if not self.config.code_submit_enabled:
            self.onebot.send_group_text(
                event.group_id,
                "远端代码提交被 CODE_SUBMIT_ENABLED=false 关闭，改成 true 或 auto 后可用。",
            )
            return

        parsed = parse_code_submission(raw_submission, default_language=self.config.cf_submit_default_language)
        if parsed is None or not parsed.source.strip():
            self.onebot.send_group_text(
                event.group_id,
                f"@{event.sender_name} 请在 /submitcode 后直接粘贴代码，语言我会自动识别。",
            )
            return

        job = _QueuedCodeSubmission(
            group_id=event.group_id,
            user_id=event.user_id,
            sender_name=event.sender_name,
            problem=active.problem,
            submission=CodeSubmission(language=parsed.language, source=parsed.source),
            ranked=active.ranked,
        )
        self._code_queue.put(job)
        position = self._code_queue.qsize()
        if position >= _REMOTE_SUBMIT_QUEUE_NOTICE_THRESHOLD:
            self.onebot.send_group_text(
                event.group_id,
                (
                    f"@{event.sender_name} CF 远端提交队列较忙。"
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
        prepared = self._claim_prefetched_problem(group_id, rating_range)
        if prepared is None:
            prepared = self._prepare_problem_bundle(group_id, rating_range)
        self._publish_prepared_problem(group_id, prepared, intro_text="刷新了一道新题目~", ranked=True)
        self._start_prefetch(group_id, rating_range)
        return PushResult(problem=prepared.problem, image_count=len(prepared.images))

    def _prepare_problem_bundle(self, group_id: int, rating_range: RatingRange) -> PreparedProblem:
        return self.challenge_service.prepare_problem(
            group_id,
            rating_range,
            asset_builder=lambda problem, statement: self.renderer.render(
                problem,
                statement,
                reveal_metadata=False,
            ),
        )

    def _prepare_specific_problem(self, problem: CFProblem) -> PreparedProblem:
        return self.challenge_service.prepare_specific_problem(
            problem,
            asset_builder=lambda selected, statement: self.renderer.render(
                selected,
                statement,
                reveal_metadata=False,
            ),
        )

    def _publish_prepared_problem(self, group_id: int, prepared: PreparedProblem, intro_text: str, ranked: bool) -> None:
        self._send_statement_images(group_id, prepared.images, intro_text=intro_text)
        self.challenge_service.activate_problem(group_id, prepared, ranked=ranked)

    def _claim_prefetched_problem(self, group_id: int, rating_range: RatingRange) -> Optional[PreparedProblem]:
        if not self.config.prefetch_enabled:
            return None
        prepared = self.store.get_prefetched_problem(group_id, rating_range)
        if prepared is None:
            return None
        self.store.clear_prefetched_problem(group_id, rating_range)
        if not _images_exist(prepared.images):
            LOGGER.warning("discard stale prefetched problem %s because images are missing", prepared.problem.cf_id)
            return None
        return prepared

    def _start_prefetch(self, group_id: int, rating_range: RatingRange) -> None:
        if not self.config.prefetch_enabled:
            return
        key = (group_id, rating_range.min_rating, rating_range.max_rating)
        with self._prefetch_lock:
            if key in self._prefetch_inflight:
                return
            if self.store.get_prefetched_problem(group_id, rating_range) is not None:
                return
            self._prefetch_inflight.add(key)
        thread = threading.Thread(
            target=self._prefetch_worker,
            args=(group_id, rating_range, key),
            name=f"cf-prefetch-{group_id}-{rating_range.min_rating}-{rating_range.max_rating}",
            daemon=True,
        )
        thread.start()

    def _prefetch_worker(self, group_id: int, rating_range: RatingRange, key: Tuple[int, int, int]) -> None:
        try:
            prepared = self._prepare_problem_bundle(group_id, rating_range)
            self.store.set_prefetched_problem(group_id, prepared)
            self.solution_bank.ensure(prepared.problem, prepared.statement)
            LOGGER.info("prefetched %s for group %s", prepared.problem.cf_id, group_id)
        except Exception as exc:
            LOGGER.warning("problem prefetch failed for group %s: %s", group_id, exc)
        finally:
            with self._prefetch_lock:
                self._prefetch_inflight.discard(key)

    def _fetch_renderable_statement(self, problem: CFProblem) -> ProblemStatement:
        return self.challenge_service.fetch_statement(problem)

    def _find_problem_by_id(self, contest_id: int, index: str) -> CFProblem:
        return self.challenge_service.find_problem(contest_id, index)

    def _translate_and_cache_if_needed(self, problem: CFProblem, statement: ProblemStatement, source: str) -> ProblemStatement:
        return self.challenge_service._translate_and_cache_if_needed(problem, statement, source)

    def _refresh_active_statement_if_needed(self, group_id: int, active: ActiveProblem) -> ActiveProblem:
        if not (self.translator.configured and _needs_statement_translation(active.statement)):
            return active
        try:
            statement = self._translate_and_cache_if_needed(active.problem, active.statement, source="active")
            if _needs_statement_translation(statement):
                return active
            images = self.renderer.render(active.problem, statement, reveal_metadata=False)
            self.store.update_active_problem_assets(group_id, active.problem, statement, images)
            return ActiveProblem(
                problem=active.problem,
                statement=statement,
                images=images,
                created_at=active.created_at,
                ranked=active.ranked,
            )
        except Exception as exc:
            LOGGER.warning("active statement refresh failed for %s: %s", active.problem.cf_id, exc)
            return active

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
        rating = str(problem.rating) if problem.rating > 0 else "未知"
        return (
            f"{problem.luogu_pid} {title}\n"
            f"难度：{rating}\n"
            f"标签：{tags}\n"
            f"题目：{problem.cf_url}\n"
            f"中文题面：{problem.luogu_url}\n"
            f"洛谷题解：{problem.luogu_solution_url}"
        )

    def _current_problem_text(self, problem: CFProblem) -> str:
        return "题目在这里~"

    def _send_statement_images(self, group_id: int, images: Iterable[Path], intro_text: str = "") -> None:
        image_list = list(images)
        try:
            self.onebot.send_group_forward_images(group_id, image_list, intro_text=intro_text)
        except Exception:
            LOGGER.exception("failed to send merged forward, falling back to regular image messages")
            self.onebot.send_group_problem(group_id, intro_text or "当前题面在这里。", image_list)

    def _giveup_wait_seconds(self, active: ActiveProblem) -> int:
        minimum = max(0, self.config.giveup_min_seconds)
        if minimum <= 0:
            return 0
        try:
            created_at = datetime.fromisoformat(active.created_at.replace("Z", "+00:00"))
        except ValueError:
            return 0
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
        return int(max(0, minimum - elapsed))

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
                LOGGER.exception(
                    "failed to process remote code submission group=%s user=%s cf_id=%s language=%s",
                    job.group_id,
                    job.user_id,
                    job.problem.cf_id,
                    job.submission.language,
                )
                safe_error = redact_sensitive_text(str(exc))
                if len(safe_error) > 160:
                    safe_error = safe_error[:160].rstrip() + "..."
                self.onebot.send_group_text(job.group_id, f"@{job.sender_name} CF 远端提交失败：{safe_error or '服务暂时不可用。'}")
            finally:
                self._code_queue.task_done()

    def _process_code_submission(self, job: _QueuedCodeSubmission) -> None:
        LOGGER.info(
            "remote code submit worker start group=%s user=%s cf_id=%s language=%s ranked=%s source_chars=%s",
            job.group_id,
            job.user_id,
            job.problem.cf_id,
            job.submission.language,
            job.ranked,
            len(job.submission.source),
        )
        outcome = self.challenge_service.submit_code(
            ChallengeActor(
                scope_id=job.group_id,
                leaderboard_id=job.group_id,
                user_id=job.user_id,
                display_name=job.sender_name,
            ),
            job.submission,
            expected_cf_id=job.problem.cf_id,
        )
        result = outcome.remote_result
        if result is None:
            raise RuntimeError("remote judge returned no result")
        LOGGER.info(
            "remote code submit worker result group=%s user=%s cf_id=%s verdict=%s accepted=%s submission_id=%s",
            job.group_id,
            job.user_id,
            job.problem.cf_id,
            result.verdict,
            result.accepted,
            result.submission_id,
        )
        if not outcome.accepted:
            self.onebot.send_group_text(job.group_id, self._remote_result_text(job.sender_name, result))
            return

        if not outcome.settled:
            self.onebot.send_group_text(
                job.group_id,
                self._remote_result_text(job.sender_name, result, reveal_details=True)
                + "\n题目已变化，不结算榜单。",
            )
            return

        if not outcome.active.ranked:
            self.onebot.send_group_text(
                job.group_id,
                (
                    self._remote_result_text(job.sender_name, result, reveal_details=True)
                    + "\n"
                    + f"恭喜@{job.sender_name} 通过这道分享题！本题不计入榜单。\n"
                    + f"本题信息：\n{self._problem_summary(job.problem, outcome.active.statement)}"
                ),
            )
            return

        if outcome.stat is None or outcome.leaderboard_rating is None:
            raise RuntimeError("accepted ranked code submission was not settled")
        self.onebot.send_group_text(
            job.group_id,
            (
                self._remote_result_text(job.sender_name, result, reveal_details=True)
                + "\n"
                + f"恭喜@{job.sender_name} 拿下本题 first blood! "
                + f"本题信息：\n{self._problem_summary(job.problem, outcome.active.statement)}\n"
                + f"通过数：{outcome.stat.solved_count}，榜单 Rating：{outcome.leaderboard_rating:.2f}"
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
    if re.fullmatch(r"\d+", text):
        rating = _round_rating_to_nearest_hundred(int(text))
        if rating < 800 or rating > 4000:
            return None
        return rating, rating

    match = re.fullmatch(r"(\d+)\s*(?:,|-|\s)\s*(\d+)", text)
    if match is None:
        return None

    min_rating = int(match.group(1))
    max_rating = int(match.group(2))
    if min_rating > max_rating:
        min_rating, max_rating = max_rating, min_rating
    if min_rating < 800 or max_rating > 4000:
        return None
    min_rating = _floor_rating_to_hundred(min_rating)
    max_rating = _ceil_rating_to_hundred(max_rating)
    if min_rating > max_rating:
        return None
    return min_rating, max_rating


def _floor_rating_to_hundred(value: int) -> int:
    return (value // 100) * 100


def _ceil_rating_to_hundred(value: int) -> int:
    return ((value + 99) // 100) * 100


def _round_rating_to_nearest_hundred(value: int) -> int:
    return ((value + 50) // 100) * 100


def _parse_problem_id(arg: str) -> Optional[Tuple[int, str]]:
    text = arg.strip()
    if not text:
        return None

    contest_id, index = _parse_problem_url_path(text)
    if contest_id is not None and index:
        return contest_id, index.upper()

    compact = re.sub(r"\s+", "", text)
    id_match = re.fullmatch(r"(?i)(?:CF)?(\d{1,7})([A-Za-z][A-Za-z0-9]*)", compact)
    if id_match is None:
        return None
    contest_id = int(id_match.group(1))
    index = id_match.group(2).upper()
    if contest_id <= 0:
        return None
    return contest_id, index


def _parse_problem_url_path(text: str) -> Tuple[Optional[int], str]:
    problemset_match = re.search(
        r"codeforces\.com/problemset/problem/(\d+)/([A-Za-z][A-Za-z0-9]*)",
        text,
        re.IGNORECASE,
    )
    if problemset_match:
        return int(problemset_match.group(1)), problemset_match.group(2)

    contest_match = re.search(
        r"codeforces\.com/(?:contest|gym)/(\d+)/problem/([A-Za-z][A-Za-z0-9]*)",
        text,
        re.IGNORECASE,
    )
    if contest_match:
        return int(contest_match.group(1)), contest_match.group(2)

    return None, ""


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


def _images_exist(images: Iterable[Path]) -> bool:
    return all(Path(image).exists() for image in images)
