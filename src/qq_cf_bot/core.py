from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .cf_statement import CodeforcesStatementClient
from .codeforces import CodeforcesClient
from .config import Config
from .judge import SolutionJudge
from .luogu import LuoguClient
from .models import (
    ActiveProblem,
    CFProblem,
    CodeSubmission,
    JudgeResult,
    PreparedProblem,
    ProblemStatement,
    RatingRange,
    RemoteJudgeResult,
    UserStat,
)
from .rating import accepted_rating_update, leaderboard_rating
from .selector import ProblemSelector
from .solution_bank import SolutionBank
from .solution_generator import LLMSolutionGenerator
from .storage import SentProblemStore
from .submitter import CodeforcesRemoteJudge, RemoteSubmissionError
from .translator import OpenAIStatementTranslator
from .vjudge_submitter import VJudgeRemoteJudge


LOGGER = logging.getLogger(__name__)


class ChallengeError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class ChallengeActor:
    scope_id: int
    leaderboard_id: int
    user_id: int
    display_name: str


@dataclass(frozen=True)
class SubmissionOutcome:
    active: ActiveProblem
    accepted: bool
    reason: str
    stat: Optional[UserStat] = None
    leaderboard_rating: Optional[float] = None
    remote_result: Optional[RemoteJudgeResult] = None
    settled: bool = True


class ChallengeService:
    """Transport-neutral application service used by QQ and the website."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cf = CodeforcesClient(config.cache_path, config.cf_cache_ttl_seconds, base_urls=config.cf_base_urls)
        self.luogu = LuoguClient()
        self.cf_statement = CodeforcesStatementClient(config.cf_base_urls)
        self.store = SentProblemStore(config.db_path, config.dedup_scope)
        self.selector = ProblemSelector(
            config.min_rating,
            config.max_rating,
            recent_pool_size=config.recent_selection_pool_size,
        )
        self.judge = SolutionJudge(
            api_url=config.judge_api_url,
            api_key=config.judge_api_key,
            model=config.judge_model,
            wire_api=config.judge_wire_api,
            timeout_seconds=config.judge_timeout_seconds,
            max_statement_chars=config.judge_statement_max_chars,
            max_solution_context_chars=config.judge_solution_context_max_chars,
            max_code_chars=config.judge_code_max_chars,
            enabled=config.judge_enabled,
            providers=config.judge_providers,
        )
        self.codeforces_remote_judge = CodeforcesRemoteJudge(
            username=config.cf_username,
            password=config.cf_password,
            handle=config.cf_handle,
            forced_language_id=config.cf_submit_language_id,
            http_timeout_seconds=config.cf_submit_http_timeout_seconds,
            poll_interval_seconds=config.cf_submit_poll_interval_seconds,
            poll_timeout_seconds=config.cf_submit_poll_timeout_seconds,
            base_urls=config.cf_base_urls,
            session_dir=config.db_path.parent / "codeforces-session",
        )
        self.vjudge_remote_judge = VJudgeRemoteJudge(
            username=config.vjudge_username,
            password=config.vjudge_password,
            cookie_header=config.vjudge_cookie,
            forced_language_id=config.vjudge_language_id,
            http_timeout_seconds=config.cf_submit_http_timeout_seconds,
            poll_interval_seconds=config.cf_submit_poll_interval_seconds,
            poll_timeout_seconds=config.cf_submit_poll_timeout_seconds,
            base_url=config.vjudge_base_url,
            session_dir=config.db_path.parent / "vjudge-session",
        )
        if config.code_submit_provider == "vjudge":
            self.remote_judge = self.vjudge_remote_judge
        elif config.code_submit_provider == "codeforces":
            self.remote_judge = self.codeforces_remote_judge
        else:
            self.remote_judge = (
                self.vjudge_remote_judge
                if self.vjudge_remote_judge.configured
                else self.codeforces_remote_judge
            )
        solution_generator = LLMSolutionGenerator(
            api_url=config.judge_api_url,
            api_key=config.judge_api_key,
            model=config.judge_model,
            wire_api=config.judge_wire_api,
            timeout_seconds=config.judge_timeout_seconds,
            enabled=config.solution_bank_generate_llm and config.judge_enabled,
            max_statement_chars=config.judge_statement_max_chars,
            providers=config.judge_providers,
        )
        self.solution_bank = SolutionBank(
            store=self.store,
            luogu=self.luogu,
            remote_judge=self.codeforces_remote_judge,
            solution_generator=solution_generator,
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
            providers=config.translate_providers,
        )
        self._submit_lock = threading.Lock()

    @property
    def code_llm_fallback_configured(self) -> bool:
        return bool(self.config.code_submit_llm_fallback and self.judge.configured)

    @property
    def code_judge_available(self) -> bool:
        return bool(
            self.config.code_submit_enabled
            and (self.remote_judge.configured or self.code_llm_fallback_configured)
        )

    @property
    def code_judge_availability(self) -> dict:
        if not self.config.code_submit_enabled:
            return {"state": "disabled", "message": "代码判定已被 CODE_SUBMIT_ENABLED 关闭"}
        if self.remote_judge.configured:
            status = dict(self.remote_judge.availability)
            if self.code_llm_fallback_configured:
                status["message"] = str(status.get("message") or "远端判题已配置") + "；异常时使用大模型静态审核兜底"
            return status
        if self.code_llm_fallback_configured:
            return {
                "state": "ready",
                "message": "远端判题未配置；当前使用大模型静态审核（非官方运行结果）",
            }
        return dict(self.remote_judge.availability)

    def get_active_problem(self, scope_id: int) -> Optional[ActiveProblem]:
        return self.store.get_active_problem(scope_id)

    def get_rating_range(self, scope_id: int) -> RatingRange:
        return self.store.get_rating_range(scope_id, self.config.min_rating, self.config.max_rating)

    def set_rating_range(self, scope_id: int, min_rating: int, max_rating: int) -> RatingRange:
        if min_rating < 800 or max_rating > 4000 or min_rating > max_rating:
            raise ChallengeError("invalid_rating", "难度范围必须在 800 到 4000 之间。")
        return self.store.set_rating_range(scope_id, min_rating, max_rating)

    def prepare_problem(
        self,
        scope_id: int,
        rating_range: Optional[RatingRange] = None,
        asset_builder: Optional[Callable[[CFProblem, ProblemStatement], List[Path]]] = None,
    ) -> PreparedProblem:
        rating_range = rating_range or self.get_rating_range(scope_id)
        sent_ids = self.store.sent_ids(scope_id)
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
                statement = self.fetch_statement(problem)
                images = asset_builder(problem, statement) if asset_builder else []
            except Exception as exc:
                last_error = exc
                LOGGER.warning("skip %s because challenge preparation failed: %s", problem.cf_id, exc)
                continue
            return PreparedProblem(
                problem=problem,
                statement=statement,
                images=images,
                rating_range=rating_range,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        if last_error is not None:
            raise ChallengeError("problem_unavailable", "题库或中文题面暂时不可用，请稍后重试。", 503) from last_error
        raise ChallengeError(
            "problem_exhausted",
            f"{rating_range.min_rating}-{rating_range.max_rating} 难度内已经没有未做过的题目。",
            409,
        )

    def prepare_specific_problem(
        self,
        problem: CFProblem,
        asset_builder: Optional[Callable[[CFProblem, ProblemStatement], List[Path]]] = None,
    ) -> PreparedProblem:
        statement = self.fetch_statement(problem)
        images = asset_builder(problem, statement) if asset_builder else []
        rating = max(0, problem.rating)
        return PreparedProblem(
            problem=problem,
            statement=statement,
            images=images,
            rating_range=RatingRange(rating, rating),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def activate_problem(self, scope_id: int, prepared: PreparedProblem, ranked: bool = True) -> ActiveProblem:
        if ranked:
            self.store.mark_sent(scope_id, prepared.problem)
        self.store.set_active_problem(
            scope_id,
            prepared.problem,
            prepared.statement,
            prepared.images,
            ranked=ranked,
        )
        active = self.store.get_active_problem(scope_id)
        if active is None:
            raise RuntimeError("failed to persist active problem")
        return active

    def issue_problem(self, scope_id: int, rating_range: Optional[RatingRange] = None) -> ActiveProblem:
        if self.store.get_active_problem(scope_id) is not None:
            raise ChallengeError("active_problem", "当前挑战还没有结束。", 409)
        prepared = self.prepare_problem(scope_id, rating_range)
        return self.activate_problem(scope_id, prepared, ranked=True)

    def issue_specific_problem(self, scope_id: int, contest_id: int, index: str) -> ActiveProblem:
        if self.store.get_active_problem(scope_id) is not None:
            raise ChallengeError("active_problem", "当前挑战还没有结束。", 409)
        problem = self.find_problem(contest_id, index)
        prepared = self.prepare_specific_problem(problem)
        return self.activate_problem(scope_id, prepared, ranked=False)

    def giveup_wait_seconds(self, active: ActiveProblem) -> int:
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

    def give_up(self, scope_id: int) -> ActiveProblem:
        active = self.store.get_active_problem(scope_id)
        if active is None:
            raise ChallengeError("no_active_problem", "当前没有可以放弃的题目。", 409)
        wait_seconds = self.giveup_wait_seconds(active)
        if wait_seconds > 0:
            raise ChallengeError("giveup_too_early", f"还要等待约 {wait_seconds} 秒才能放弃。", 409)
        self.store.clear_active_problem(scope_id)
        return active

    def submit_solution(self, actor: ChallengeActor, submission: str) -> SubmissionOutcome:
        active = self._require_active(actor.scope_id)
        submission = submission.strip()
        if not submission:
            raise ChallengeError("empty_submission", "请先写下你的做法。")
        if not self.judge.configured:
            raise ChallengeError("judge_unavailable", "做法判定服务尚未配置。", 503)

        references = self.solution_bank.ensure(active.problem, active.statement)
        solution_context = self.solution_bank.context_for_prompt(
            references,
            self.config.judge_solution_context_max_chars,
        )
        history = self.store.list_submission_history(actor.leaderboard_id, active.problem.cf_id)
        result = self.judge.judge(
            active.problem,
            active.statement,
            submission,
            solution_references=references,
            solution_context=solution_context,
            submission_history=history,
        )
        if result.accepted and references:
            try:
                result = self.judge.second_judge(
                    active.problem,
                    active.statement,
                    submission,
                    first_result=result,
                    solution_references=references,
                    solution_context=solution_context,
                    submission_history=history,
                )
            except Exception as exc:
                LOGGER.warning("second judge failed for %s, keeping first result: %s", active.problem.cf_id, exc)

        self._ensure_problem_for_leaderboard(actor, active)
        self.store.record_submission(
            actor.leaderboard_id,
            actor.user_id,
            actor.display_name,
            active.problem,
            submission,
            result.accepted,
            result.reason,
            ranked=active.ranked,
        )
        if not result.accepted:
            return SubmissionOutcome(active=active, accepted=False, reason=result.reason)
        return self._settle_accepted(actor, active, result.reason)

    def submit_code(
        self,
        actor: ChallengeActor,
        submission: CodeSubmission,
        expected_cf_id: str = "",
    ) -> SubmissionOutcome:
        active = self._require_active(actor.scope_id)
        if expected_cf_id and active.problem.cf_id != expected_cf_id:
            raise ChallengeError("problem_changed", "当前题目已经变化，本次提交已取消。", 409)
        if not submission.source.strip():
            raise ChallengeError("empty_code", "请先粘贴代码。")
        if not self.config.code_submit_enabled:
            raise ChallengeError("code_judge_unavailable", "代码判定服务已关闭。", 503)

        fallback_configured = self.code_llm_fallback_configured
        if not self.remote_judge.configured and not fallback_configured:
            raise ChallengeError("code_judge_unavailable", "远端代码判题和大模型兜底均未配置。", 503)

        result: Optional[RemoteJudgeResult] = None
        remote_error: Optional[RemoteSubmissionError] = None
        if self.remote_judge.configured:
            with self._submit_lock:
                active = self._require_same_active(actor.scope_id, active.problem.cf_id)
                interval = max(0, self.config.cf_submit_min_interval_seconds)
                last_submit_at = self.store.get_meta_float("cf_last_submit_at", 0.0)
                wait_seconds = max(0.0, last_submit_at + interval - time.time())
                if wait_seconds:
                    time.sleep(wait_seconds)
                active = self._require_same_active(actor.scope_id, active.problem.cf_id)
                try:
                    result = self.remote_judge.judge(active.problem, submission)
                except RemoteSubmissionError as exc:
                    remote_error = exc
                remote_submit_at = self.remote_judge.last_submit_at
                if remote_submit_at:
                    self.store.set_meta_float("cf_last_submit_at", remote_submit_at)

        needs_fallback = result is None or _remote_verdict_is_pending(result.verdict)
        if needs_fallback and fallback_configured:
            remote_context = str(remote_error) if remote_error is not None else (result.message if result else "远端载具未配置")
            try:
                result = self._judge_code_with_llm(active, submission, remote_context, result)
            except Exception as exc:
                LOGGER.warning("LLM code fallback failed for %s: %s", active.problem.cf_id, exc)
                if result is not None:
                    result = replace(result, message=result.message + "；大模型兜底也暂时不可用。")
                else:
                    message = str(remote_error) if remote_error is not None else "远端代码判题不可用。"
                    raise ChallengeError("code_submit_failed", message + "；大模型兜底也暂时不可用。", 502) from exc
        elif remote_error is not None:
            raise ChallengeError("code_submit_failed", str(remote_error), 502) from remote_error

        if result is None:
            raise ChallengeError("code_submit_failed", "代码判定未返回结果。", 502)

        self._ensure_problem_for_leaderboard(actor, active)
        source_hash = hashlib.sha256(submission.source.encode("utf-8")).hexdigest()
        self.store.record_code_submission(
            actor.leaderboard_id,
            actor.user_id,
            actor.display_name,
            active.problem,
            submission.language,
            source_hash,
            len(submission.source),
            result,
            ranked=active.ranked,
        )
        if not result.accepted:
            return SubmissionOutcome(
                active=active,
                accepted=False,
                reason=result.message,
                remote_result=result,
            )
        current = self.store.get_active_problem(actor.scope_id)
        if current is None or current.problem.cf_id != active.problem.cf_id:
            return SubmissionOutcome(
                active=active,
                accepted=True,
                reason=result.message,
                remote_result=result,
                settled=False,
            )
        return replace(self._settle_accepted(actor, active, result.message), remote_result=result)

    def _judge_code_with_llm(
        self,
        active: ActiveProblem,
        submission: CodeSubmission,
        remote_context: str,
        remote_result: Optional[RemoteJudgeResult],
    ) -> RemoteJudgeResult:
        references = self.solution_bank.ensure(active.problem, active.statement)
        solution_context = self.solution_bank.context_for_prompt(
            references,
            self.config.judge_solution_context_max_chars,
        )
        decision = self.judge.judge_code(
            active.problem,
            active.statement,
            submission,
            solution_references=references,
            solution_context=solution_context,
        )
        context = re.sub(r"\s+", " ", remote_context).strip()
        if len(context) > 240:
            context = context[:240].rstrip() + "..."
        if decision.accepted:
            message = "大模型静态审核通过（兜底判定，非 Codeforces/VJudge 运行结果）"
            verdict = "LLM_ACCEPTED"
        else:
            message = f"大模型静态审核未通过（兜底判定，非官方运行结果）：{decision.reason}"
            verdict = "LLM_REJECTED"
        if context:
            message += f"；远端状态：{context}"
        return RemoteJudgeResult(
            accepted=decision.accepted,
            verdict=verdict,
            message=message,
            submission_id=remote_result.submission_id if remote_result else None,
            passed_tests=remote_result.passed_tests if remote_result else None,
            time_ms=remote_result.time_ms if remote_result else None,
            memory_bytes=remote_result.memory_bytes if remote_result else None,
            url=remote_result.url if remote_result else "",
        )

    def get_user_stat(self, actor: ChallengeActor) -> UserStat:
        return self.store.get_user_stat(
            actor.leaderboard_id,
            actor.user_id,
            actor.display_name,
            self.config.initial_rating,
        )

    def list_leaderboard(self, leaderboard_id: int):
        return self.store.list_group_stats(leaderboard_id)

    def fetch_statement(self, problem: CFProblem) -> ProblemStatement:
        cached = self.store.get_cached_statement(problem.cf_id, require_translated=self.translator.configured)
        if cached is not None:
            if self.translator.configured and _needs_statement_translation(cached):
                return self._translate_and_cache_if_needed(problem, cached, source="cached")
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

    def find_problem(self, contest_id: int, index: str) -> CFProblem:
        normalized_index = index.upper()
        try:
            for problem in self.cf.fetch_problems():
                if problem.contest_id == contest_id and problem.index.upper() == normalized_index:
                    return problem
        except Exception as exc:
            LOGGER.warning("failed to load problemset while finding %s%s: %s", contest_id, index, exc)
        return CFProblem(contest_id=contest_id, index=normalized_index, name=f"{contest_id}{normalized_index}", rating=0)

    def _translate_and_cache_if_needed(
        self,
        problem: CFProblem,
        statement: ProblemStatement,
        source: str,
    ) -> ProblemStatement:
        if not self.translator.configured:
            self.store.cache_statement(problem, statement, source=source, translated=not _needs_statement_translation(statement))
            return statement

        try:
            if _needs_body_translation(statement):
                translated = self.translator.translate_statement(statement)
                translated_ok = not _needs_statement_translation(translated)
                self.store.cache_statement(problem, translated, source=f"{source}_llm_translate", translated=translated_ok)
                if not translated_ok:
                    raise RuntimeError(f"translated statement for {problem.cf_id} still contains English")
                return translated
            if _needs_title_translation(statement.title):
                translated = replace(statement, title=self.translator.translate_title(statement.title or problem.name))
                self.store.cache_statement(
                    problem,
                    translated,
                    source=f"{source}_llm_title_translate",
                    translated=not _needs_statement_translation(translated),
                )
                return translated
        except Exception:
            if _needs_body_translation(statement):
                self.store.cache_statement(problem, statement, source=source, translated=False)
            raise

        self.store.cache_statement(problem, statement, source=source, translated=not _needs_statement_translation(statement))
        return statement

    def _require_active(self, scope_id: int) -> ActiveProblem:
        active = self.store.get_active_problem(scope_id)
        if active is None:
            raise ChallengeError("no_active_problem", "当前没有题目，请先抽取一道。", 409)
        return active

    def _require_same_active(self, scope_id: int, cf_id: str) -> ActiveProblem:
        active = self._require_active(scope_id)
        if active.problem.cf_id != cf_id:
            raise ChallengeError("problem_changed", "当前题目已经变化，本次提交已取消。", 409)
        return active

    def _ensure_problem_for_leaderboard(self, actor: ChallengeActor, active: ActiveProblem) -> None:
        if active.ranked and actor.leaderboard_id != actor.scope_id:
            self.store.mark_sent(actor.leaderboard_id, active.problem)

    def _settle_accepted(self, actor: ChallengeActor, active: ActiveProblem, reason: str) -> SubmissionOutcome:
        if not active.ranked:
            self.store.clear_active_problem(actor.scope_id)
            return SubmissionOutcome(active=active, accepted=True, reason=reason)

        old_stat = self.get_user_stat(actor)
        new_rating = accepted_rating_update(
            old_stat.rating,
            active.problem.rating,
            self.config.rating_k_factor,
        )
        stat = self.store.mark_solved(
            actor.leaderboard_id,
            actor.user_id,
            actor.display_name,
            new_rating,
            self.config.initial_rating,
        )
        self.store.clear_active_problem(actor.scope_id)
        return SubmissionOutcome(
            active=active,
            accepted=True,
            reason=reason,
            stat=stat,
            leaderboard_rating=leaderboard_rating(stat.solved_ratings, stat.rating),
        )


def _remote_verdict_is_pending(verdict: str) -> bool:
    return verdict.strip().upper() in {"", "PENDING", "RUNNING", "SUBMITTED", "TESTING", "QUEUE", "QUEUING"}


def parse_problem_id(value: str) -> Optional[Tuple[int, str]]:
    text = value.strip()
    if not text:
        return None

    problemset_match = re.search(
        r"codeforces\.com/problemset/problem/(\d+)/([A-Za-z][A-Za-z0-9]*)",
        text,
        re.IGNORECASE,
    )
    if problemset_match:
        return int(problemset_match.group(1)), problemset_match.group(2).upper()

    contest_match = re.search(
        r"codeforces\.com/(?:contest|gym)/(\d+)/problem/([A-Za-z][A-Za-z0-9]*)",
        text,
        re.IGNORECASE,
    )
    if contest_match:
        return int(contest_match.group(1)), contest_match.group(2).upper()

    compact = re.sub(r"\s+", "", text)
    id_match = re.fullmatch(r"(?i)(?:CF)?(\d{1,7})([A-Za-z][A-Za-z0-9]*)", compact)
    if id_match is None:
        return None
    contest_id = int(id_match.group(1))
    if contest_id <= 0:
        return None
    return contest_id, id_match.group(2).upper()


def _needs_title_translation(title: str) -> bool:
    text = title.strip()
    if not text or re.search(r"[\u4e00-\u9fff]", text):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def _needs_statement_translation(statement: ProblemStatement) -> bool:
    return _needs_title_translation(statement.title) or _needs_body_translation(statement)


def _needs_body_translation(statement: ProblemStatement) -> bool:
    text = _visible_statement_text(
        " ".join((statement.description, statement.input_format, statement.output_format, statement.hint))
    )
    if not text:
        return False
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = re.findall(r"[A-Za-z][A-Za-z']{2,}", text)
    if len(english_words) < 8:
        return False
    return cjk_chars == 0 or (len(english_words) >= 20 and len(english_words) > cjk_chars / 2)


def _visible_statement_text(value: str) -> str:
    text = re.sub(r"\${1,3}.*?\${1,3}", " ", value, flags=re.DOTALL)
    text = re.sub(r"\\\(.+?\\\)|\\\[.+?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
