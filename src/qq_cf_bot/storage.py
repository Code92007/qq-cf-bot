from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import (
    ActiveProblem,
    CFContest,
    CFProblem,
    PreparedProblem,
    ProblemStatement,
    RatingRange,
    RemoteJudgeResult,
    SolutionReference,
    UserStat,
)
from .rating import leaderboard_rating


class SentProblemStore:
    def __init__(self, db_path: Path, dedup_scope: str = "group") -> None:
        self.db_path = db_path
        self.dedup_scope = dedup_scope
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def sent_ids(self, group_id: int) -> Set[str]:
        with self._connect() as conn:
            if self.dedup_scope == "global":
                rows = conn.execute("select distinct cf_id from sent_problems").fetchall()
            else:
                rows = conn.execute(
                    "select cf_id from sent_problems where group_id = ?",
                    (str(group_id),),
                ).fetchall()
        return {str(row[0]) for row in rows}

    def mark_sent(self, group_id: int, problem: CFProblem) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert or ignore into sent_problems
                    (group_id, cf_id, contest_id, problem_index, name, rating, tags_json, sent_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(group_id),
                    problem.cf_id,
                    problem.contest_id,
                    problem.index,
                    problem.name,
                    problem.rating,
                    json.dumps(problem.tags, ensure_ascii=False),
                    now,
                ),
            )

    def get_active_problem(self, group_id: int) -> Optional[ActiveProblem]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select problem_json, statement_json, image_paths_json, created_at, ranked
                from active_problems
                where group_id = ?
                """,
                (str(group_id),),
            ).fetchone()
        if row is None:
            return None
        return ActiveProblem(
            problem=_problem_from_json(row[0]),
            statement=_statement_from_json(row[1]),
            images=[Path(path) for path in json.loads(row[2])],
            created_at=str(row[3]),
            ranked=bool(row[4]),
        )

    def set_active_problem(
        self,
        group_id: int,
        problem: CFProblem,
        statement: ProblemStatement,
        image_paths: Iterable[Path],
        ranked: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into active_problems
                    (group_id, cf_id, problem_json, statement_json, image_paths_json, created_at, ranked)
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(group_id) do update set
                    cf_id = excluded.cf_id,
                    problem_json = excluded.problem_json,
                    statement_json = excluded.statement_json,
                    image_paths_json = excluded.image_paths_json,
                    created_at = excluded.created_at,
                    ranked = excluded.ranked
                """,
                (
                    str(group_id),
                    problem.cf_id,
                    json.dumps(_problem_to_json(problem), ensure_ascii=False),
                    json.dumps(_statement_to_json(statement), ensure_ascii=False),
                    json.dumps([str(path) for path in image_paths], ensure_ascii=False),
                    now,
                    1 if ranked else 0,
                ),
            )

    def update_active_problem_assets(
        self,
        group_id: int,
        problem: CFProblem,
        statement: ProblemStatement,
        image_paths: Iterable[Path],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update active_problems
                set problem_json = ?, statement_json = ?, image_paths_json = ?
                where group_id = ? and cf_id = ?
                """,
                (
                    json.dumps(_problem_to_json(problem), ensure_ascii=False),
                    json.dumps(_statement_to_json(statement), ensure_ascii=False),
                    json.dumps([str(path) for path in image_paths], ensure_ascii=False),
                    str(group_id),
                    problem.cf_id,
                ),
            )

    def get_prefetched_problem(self, group_id: int, rating_range: RatingRange) -> Optional[PreparedProblem]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select problem_json, statement_json, image_paths_json, min_rating, max_rating, created_at
                from prefetched_problems
                where group_id = ? and min_rating = ? and max_rating = ?
                """,
                (str(group_id), rating_range.min_rating, rating_range.max_rating),
            ).fetchone()
        if row is None:
            return None
        return PreparedProblem(
            problem=_problem_from_json(row[0]),
            statement=_statement_from_json(row[1]),
            images=[Path(path) for path in json.loads(row[2])],
            rating_range=RatingRange(int(row[3]), int(row[4])),
            created_at=str(row[5]),
        )

    def set_prefetched_problem(
        self,
        group_id: int,
        prepared: PreparedProblem,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into prefetched_problems
                    (group_id, min_rating, max_rating, cf_id, problem_json, statement_json, image_paths_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(group_id, min_rating, max_rating) do update set
                    cf_id = excluded.cf_id,
                    problem_json = excluded.problem_json,
                    statement_json = excluded.statement_json,
                    image_paths_json = excluded.image_paths_json,
                    created_at = excluded.created_at
                """,
                (
                    str(group_id),
                    prepared.rating_range.min_rating,
                    prepared.rating_range.max_rating,
                    prepared.problem.cf_id,
                    json.dumps(_problem_to_json(prepared.problem), ensure_ascii=False),
                    json.dumps(_statement_to_json(prepared.statement), ensure_ascii=False),
                    json.dumps([str(path) for path in prepared.images], ensure_ascii=False),
                    prepared.created_at,
                ),
            )

    def clear_prefetched_problem(self, group_id: int, rating_range: RatingRange) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                delete from prefetched_problems
                where group_id = ? and min_rating = ? and max_rating = ?
                """,
                (str(group_id), rating_range.min_rating, rating_range.max_rating),
            )

    def get_cached_statement(self, cf_id: str, require_translated: bool = False) -> Optional[ProblemStatement]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select statement_json
                from statement_cache
                where cf_id = ? and (? = 0 or translated = 1)
                """,
                (cf_id, 1 if require_translated else 0),
            ).fetchone()
        if row is None:
            return None
        return _statement_from_json(row[0])

    def cache_statement(
        self,
        problem: CFProblem,
        statement: ProblemStatement,
        source: str,
        translated: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into statement_cache
                    (cf_id, problem_json, statement_json, source, translated, cached_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(cf_id) do update set
                    problem_json = excluded.problem_json,
                    statement_json = excluded.statement_json,
                    source = excluded.source,
                    translated = excluded.translated,
                    cached_at = excluded.cached_at
                """,
                (
                    problem.cf_id,
                    json.dumps(_problem_to_json(problem), ensure_ascii=False),
                    json.dumps(_statement_to_json(statement), ensure_ascii=False),
                    source,
                    1 if translated else 0,
                    now,
                ),
            )

    def clear_active_problem(self, group_id: int) -> None:
        with self._connect() as conn:
            conn.execute("delete from active_problems where group_id = ?", (str(group_id),))

    def record_submission(
        self,
        group_id: int,
        user_id: int,
        display_name: str,
        problem: CFProblem,
        raw_text: str,
        accepted: bool,
        reason: str,
        ranked: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into submissions
                    (group_id, user_id, display_name, cf_id, raw_text, accepted, reason, created_at, ranked)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(group_id),
                    str(user_id),
                    display_name,
                    problem.cf_id,
                    raw_text,
                    1 if accepted else 0,
                    reason,
                    now,
                    1 if ranked else 0,
                ),
            )

    def list_submission_history(self, group_id: int, cf_id: str, limit: int = 12) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select display_name, raw_text, accepted, reason, created_at
                from submissions
                where group_id = ? and cf_id = ?
                order by id desc
                limit ?
                """,
                (str(group_id), cf_id, max(1, limit)),
            ).fetchall()
        return [
            {
                "display_name": str(row[0]),
                "text": str(row[1]),
                "accepted": bool(row[2]),
                "reason": str(row[3]),
                "created_at": str(row[4]),
            }
            for row in reversed(rows)
        ]

    def record_code_submission(
        self,
        group_id: int,
        user_id: int,
        display_name: str,
        problem: CFProblem,
        language: str,
        source_hash: str,
        source_chars: int,
        result: RemoteJudgeResult,
        ranked: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into code_submissions
                    (
                        group_id, user_id, display_name, cf_id, language, source_hash,
                        source_chars, accepted, verdict, submission_id, passed_tests,
                        time_ms, memory_bytes, url, message, created_at, ranked
                    )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(group_id),
                    str(user_id),
                    display_name,
                    problem.cf_id,
                    language,
                    source_hash,
                    source_chars,
                    1 if result.accepted else 0,
                    result.verdict,
                    result.submission_id,
                    result.passed_tests,
                    result.time_ms,
                    result.memory_bytes,
                    result.url,
                    result.message,
                    now,
                    1 if ranked else 0,
                ),
            )

    def list_user_accepted_problems(self, group_id: int, user_id: int) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    attempts.cf_id,
                    attempts.accepted_at,
                    attempts.method,
                    attempts.verdict,
                    attempts.submission_url,
                    attempts.source_order,
                    attempts.submission_order,
                    sp.contest_id,
                    sp.problem_index,
                    sp.name,
                    sp.rating,
                    sc.statement_json
                from (
                    select
                        id as submission_order,
                        group_id,
                        user_id,
                        cf_id,
                        created_at as accepted_at,
                        'oral' as method,
                        'ACCEPTED' as verdict,
                        '' as submission_url,
                        0 as source_order
                    from submissions
                    where group_id = ? and user_id = ? and accepted = 1 and ranked = 1
                    union all
                    select
                        id as submission_order,
                        group_id,
                        user_id,
                        cf_id,
                        created_at as accepted_at,
                        'code' as method,
                        verdict,
                        url as submission_url,
                        1 as source_order
                    from code_submissions
                    where group_id = ? and user_id = ? and accepted = 1 and ranked = 1
                ) attempts
                join sent_problems sp
                    on sp.group_id = attempts.group_id and sp.cf_id = attempts.cf_id
                left join statement_cache sc on sc.cf_id = attempts.cf_id
                order by
                    attempts.accepted_at asc,
                    attempts.source_order asc,
                    attempts.submission_order asc
                """,
                (str(group_id), str(user_id), str(group_id), str(user_id)),
            ).fetchall()

        accepted_by_problem: Dict[str, dict] = {}
        for row in rows:
            cf_id = str(row[0])
            if cf_id in accepted_by_problem:
                continue
            contest_id = int(row[7])
            problem_index = str(row[8])
            accepted_by_problem[cf_id] = {
                "cf_id": cf_id,
                "title": _cached_statement_title(row[11], str(row[9])),
                "rating": int(row[10]),
                "accepted_at": str(row[1]),
                "method": str(row[2]),
                "verdict": str(row[3]),
                "submission_url": str(row[4]),
                "codeforces_url": f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}",
                "solution_url": f"https://www.luogu.com.cn/problem/solution/CF{cf_id}",
            }
        return sorted(
            accepted_by_problem.values(),
            key=lambda item: (item["accepted_at"], item["cf_id"]),
            reverse=True,
        )

    def get_rating_range(self, group_id: int, default_min: int, default_max: int) -> RatingRange:
        with self._connect() as conn:
            row = conn.execute(
                """
                select min_rating, max_rating
                from group_settings
                where group_id = ?
                """,
                (str(group_id),),
            ).fetchone()
        if row is None:
            return RatingRange(default_min, default_max)
        return RatingRange(int(row[0]), int(row[1]))

    def set_rating_range(self, group_id: int, min_rating: int, max_rating: int) -> RatingRange:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into group_settings
                    (group_id, min_rating, max_rating, updated_at)
                values (?, ?, ?, ?)
                on conflict(group_id) do update set
                    min_rating = excluded.min_rating,
                    max_rating = excluded.max_rating,
                    updated_at = excluded.updated_at
                """,
                (str(group_id), min_rating, max_rating, now),
            )
        return RatingRange(min_rating, max_rating)

    def get_meta_float(self, key: str, default: float = 0.0) -> float:
        with self._connect() as conn:
            row = conn.execute("select value from bot_meta where key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return float(row[0])
        except (TypeError, ValueError):
            return default

    def set_meta_float(self, key: str, value: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into bot_meta (key, value)
                values (?, ?)
                on conflict(key) do update set value = excluded.value
                """,
                (key, repr(value)),
            )

    def list_solution_references(self, cf_id: str) -> List[SolutionReference]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select cf_id, source, title, author, url, content, content_hash, fetched_at
                from solution_references
                where cf_id = ?
                order by
                    case source
                        when 'luogu' then 0
                        when 'codeforces_editorial' then 1
                        when 'codeforces_ac_code' then 2
                        else 3
                    end,
                    id asc
                """,
                (cf_id,),
            ).fetchall()
        return [
            SolutionReference(
                cf_id=str(row[0]),
                source=str(row[1]),
                title=str(row[2]),
                author=str(row[3]),
                url=str(row[4]),
                content=str(row[5]),
                content_hash=str(row[6]),
                fetched_at=str(row[7]),
            )
            for row in rows
        ]

    def add_solution_references(self, references: Iterable[SolutionReference]) -> int:
        inserted = 0
        with self._connect() as conn:
            for reference in references:
                cursor = conn.execute(
                    """
                    insert or ignore into solution_references
                        (cf_id, source, title, author, url, content, content_hash, fetched_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reference.cf_id,
                        reference.source,
                        reference.title,
                        reference.author,
                        reference.url,
                        reference.content,
                        reference.content_hash,
                        reference.fetched_at or datetime.now(timezone.utc).isoformat(),
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def get_solution_fetch_attempt(self, cf_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "select attempted_at from solution_fetch_attempts where cf_id = ?",
                (cf_id,),
            ).fetchone()
        return str(row[0]) if row else ""

    def mark_solution_fetch_attempt(self, cf_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into solution_fetch_attempts (cf_id, attempted_at)
                values (?, ?)
                on conflict(cf_id) do update set attempted_at = excluded.attempted_at
                """,
                (cf_id, now),
            )

    def get_user_stat(self, group_id: int, user_id: int, display_name: str, initial_rating: float) -> UserStat:
        with self._connect() as conn:
            row = conn.execute(
                """
                select display_name, solved_count, rating
                from user_stats
                where group_id = ? and user_id = ?
                """,
                (str(group_id), str(user_id)),
            ).fetchone()
        if row is None:
            return UserStat(user_id=user_id, display_name=display_name, solved_count=0, rating=initial_rating)
        with self._connect() as conn:
            solved_ratings = _solved_ratings_for_user(conn, group_id, user_id)
        return UserStat(
            user_id=user_id,
            display_name=str(row[0]),
            solved_count=int(row[1]),
            rating=float(row[2]),
            solved_ratings=solved_ratings,
        )

    def update_user_display_name(self, group_id: int, user_id: int, display_name: str) -> bool:
        if not display_name:
            return False
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update user_stats
                set display_name = ?
                where group_id = ? and user_id = ? and display_name <> ?
                """,
                (display_name, str(group_id), str(user_id), display_name),
            )
            return cursor.rowcount > 0

    def mark_solved(
        self,
        group_id: int,
        user_id: int,
        display_name: str,
        new_rating: float,
        initial_rating: float,
    ) -> UserStat:
        now = datetime.now(timezone.utc).isoformat()
        solved_ratings: Tuple[int, ...]
        with self._connect() as conn:
            row = conn.execute(
                """
                select solved_count
                from user_stats
                where group_id = ? and user_id = ?
                """,
                (str(group_id), str(user_id)),
            ).fetchone()
            solved_count = int(row[0]) + 1 if row else 1
            conn.execute(
                """
                insert into user_stats
                    (group_id, user_id, display_name, solved_count, rating, last_solved_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(group_id, user_id) do update set
                    display_name = excluded.display_name,
                    solved_count = excluded.solved_count,
                    rating = excluded.rating,
                    last_solved_at = excluded.last_solved_at
                """,
                (
                    str(group_id),
                    str(user_id),
                    display_name,
                    solved_count,
                    new_rating if row else max(new_rating, initial_rating),
                    now,
                ),
            )
            solved_ratings = _solved_ratings_for_user(conn, group_id, user_id)
        return UserStat(
            user_id=user_id,
            display_name=display_name,
            solved_count=solved_count,
            rating=new_rating,
            solved_ratings=solved_ratings,
        )

    def list_group_stats(self, group_id: int) -> List[UserStat]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select user_id, display_name, solved_count, rating
                from user_stats
                where group_id = ?
                order by rating desc, solved_count desc, display_name asc
                """,
                (str(group_id),),
            ).fetchall()
            solved_ratings = _solved_ratings_by_user(conn, group_id)
        stats = [
            UserStat(
                user_id=int(row[0]),
                display_name=str(row[1]),
                solved_count=int(row[2]),
                rating=float(row[3]),
                solved_ratings=solved_ratings.get(str(row[0]), ()),
            )
            for row in rows
        ]
        stats.sort(
            key=lambda stat: (
                -leaderboard_rating(stat.solved_ratings, stat.rating),
                -(stat.solved_ratings[0] if stat.solved_ratings else 0),
                -stat.solved_count,
                stat.display_name,
            )
        )
        return stats

    def create_web_user(self, username: str, display_name: str, password_hash: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    insert into web_users (username, display_name, password_hash, created_at)
                    values (?, ?, ?, ?)
                    """,
                    (username, display_name, password_hash, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("username already exists") from exc
            user_id = int(cursor.lastrowid)
        return {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "password_hash": password_hash,
            "created_at": now,
        }

    def get_web_user_by_username(self, username: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "select id, username, display_name, password_hash, created_at from web_users where username = ?",
                (username,),
            ).fetchone()
        return _web_user_row(row)

    def get_web_user(self, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "select id, username, display_name, password_hash, created_at from web_users where id = ?",
                (user_id,),
            ).fetchone()
        return _web_user_row(row)

    def create_web_session(self, token_hash: str, user_id: int, csrf_token: str, expires_at: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "delete from web_sessions where user_id = ? or expires_at <= ?",
                (user_id, now),
            )
            conn.execute(
                """
                insert into web_sessions (token_hash, user_id, csrf_token, created_at, expires_at)
                values (?, ?, ?, ?, ?)
                """,
                (token_hash, user_id, csrf_token, now, expires_at),
            )

    def get_web_session(self, token_hash: str) -> Optional[dict]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                select s.user_id, s.csrf_token, s.expires_at, u.username, u.display_name
                from web_sessions s
                join web_users u on u.id = s.user_id
                where s.token_hash = ? and s.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        if row is None:
            return None
        return {
            "user_id": int(row[0]),
            "csrf_token": str(row[1]),
            "expires_at": str(row[2]),
            "username": str(row[3]),
            "display_name": str(row[4]),
        }

    def delete_web_session(self, token_hash: str) -> None:
        with self._connect() as conn:
            conn.execute("delete from web_sessions where token_hash = ?", (token_hash,))

    def create_web_contest_session(
        self,
        user_id: int,
        contest: CFContest,
        category: str,
        problems: Iterable[CFProblem],
    ) -> dict:
        problem_list = list(problems)
        if not problem_list:
            raise ValueError("contest session requires at least one problem")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into web_contest_sessions (
                    user_id, contest_id, contest_name, category, duration_seconds,
                    started_at, ended_at, status, current_cf_id, current_selected_at
                ) values (?, ?, ?, ?, ?, ?, '', 'active', ?, ?)
                """,
                (
                    user_id,
                    contest.contest_id,
                    contest.name,
                    category,
                    contest.duration_seconds,
                    now,
                    problem_list[0].cf_id,
                    now,
                ),
            )
            session_id = int(cursor.lastrowid)
            conn.executemany(
                """
                insert into web_contest_session_problems (
                    session_id, position, cf_id, problem_json, opened_at,
                    oral_accepted_at, code_accepted_at, oral_attempts, code_attempts,
                    thinking_seconds, coding_seconds
                ) values (?, ?, ?, ?, ?, '', '', 0, 0, 0, 0)
                """,
                [
                    (
                        session_id,
                        position,
                        problem.cf_id,
                        json.dumps(_problem_to_json(problem), ensure_ascii=False),
                        now if position == 0 else "",
                    )
                    for position, problem in enumerate(problem_list)
                ],
            )
        session = self.get_web_contest_session(session_id, user_id)
        if session is None:
            raise RuntimeError("failed to persist contest session")
        return session

    def get_active_web_contest_session(self, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id
                from web_contest_sessions
                where user_id = ? and status = 'active'
                order by id desc
                limit 1
                """,
                (user_id,),
            ).fetchone()
        return self.get_web_contest_session(int(row[0]), user_id) if row else None

    def get_latest_ended_web_contest_session(self, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id
                from web_contest_sessions
                where user_id = ? and status = 'ended'
                order by id desc
                limit 1
                """,
                (user_id,),
            ).fetchone()
        return self.get_web_contest_session(int(row[0]), user_id) if row else None

    def get_web_contest_session(self, session_id: int, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id, contest_id, contest_name, category, duration_seconds,
                       started_at, ended_at, status, current_cf_id, current_selected_at
                from web_contest_sessions
                where id = ? and user_id = ?
                """,
                (session_id, user_id),
            ).fetchone()
            if row is None:
                return None
            problem_rows = conn.execute(
                """
                select position, cf_id, problem_json, opened_at, oral_accepted_at,
                       code_accepted_at, oral_attempts, code_attempts,
                       thinking_seconds, coding_seconds
                from web_contest_session_problems
                where session_id = ?
                order by position asc
                """,
                (session_id,),
            ).fetchall()
        return {
            "id": int(row[0]),
            "contest_id": int(row[1]),
            "contest_name": str(row[2]),
            "category": str(row[3]),
            "duration_seconds": int(row[4]),
            "started_at": str(row[5]),
            "ended_at": str(row[6]),
            "status": str(row[7]),
            "current_cf_id": str(row[8]),
            "current_selected_at": str(row[9]),
            "problems": [
                {
                    "position": int(item[0]),
                    "cf_id": str(item[1]),
                    "problem": _problem_from_json(item[2]),
                    "opened_at": str(item[3]),
                    "oral_accepted_at": str(item[4]),
                    "code_accepted_at": str(item[5]),
                    "oral_attempts": int(item[6]),
                    "code_attempts": int(item[7]),
                    "thinking_seconds": int(item[8]),
                    "coding_seconds": int(item[9]),
                }
                for item in problem_rows
            ],
        }

    def select_web_contest_problem(self, session_id: int, user_id: int, cf_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            active = conn.execute(
                """
                select current_cf_id, current_selected_at
                from web_contest_sessions
                where id = ? and user_id = ? and status = 'active'
                """,
                (session_id, user_id),
            ).fetchone()
            if active is None:
                raise ValueError("contest session is no longer active")
            selected = conn.execute(
                """
                update web_contest_session_problems
                set opened_at = case when opened_at = '' then ? else opened_at end
                where session_id = ? and cf_id = ?
                """,
                (now, session_id, cf_id),
            )
            if selected.rowcount != 1:
                raise ValueError("problem is not part of this contest session")
            _accrue_web_contest_focus(conn, session_id, str(active[0]), str(active[1]), now)
            updated = conn.execute(
                """
                update web_contest_sessions
                set current_cf_id = ?, current_selected_at = ?
                where id = ? and user_id = ? and status = 'active'
                """,
                (cf_id, now, session_id, user_id),
            )
            if updated.rowcount != 1:
                raise ValueError("contest session is no longer active")
        session = self.get_web_contest_session(session_id, user_id)
        if session is None:
            raise RuntimeError("contest session disappeared")
        return session

    def record_web_contest_attempt(
        self,
        session_id: int,
        user_id: int,
        cf_id: str,
        method: str,
        accepted: bool,
    ) -> dict:
        if method not in {"oral", "code"}:
            raise ValueError("unknown contest attempt method")
        accepted_column = "oral_accepted_at" if method == "oral" else "code_accepted_at"
        attempts_column = "oral_attempts" if method == "oral" else "code_attempts"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            active = conn.execute(
                """
                select current_cf_id, current_selected_at
                from web_contest_sessions
                where id = ? and user_id = ? and status = 'active'
                """,
                (session_id, user_id),
            ).fetchone()
            if active is None:
                raise ValueError("contest session is no longer active")
            if str(active[0]) != cf_id:
                raise ValueError("only the current contest problem can receive an attempt")
            problem_state = conn.execute(
                """
                select oral_accepted_at, code_accepted_at
                from web_contest_session_problems
                where session_id = ? and cf_id = ?
                """,
                (session_id, cf_id),
            ).fetchone()
            if problem_state is None:
                raise ValueError("problem is not part of this contest session")
            first_accept = accepted and not str(problem_state[0 if method == "oral" else 1])
            if first_accept:
                elapsed = _seconds_between(str(active[1]), now)
                focus_column = None
                if method == "oral" and not problem_state[0] and not problem_state[1]:
                    focus_column = "thinking_seconds"
                elif method == "code" and problem_state[0] and not problem_state[1]:
                    focus_column = "coding_seconds"
                if focus_column is not None:
                    conn.execute(
                        f"""
                        update web_contest_session_problems
                        set {focus_column} = {focus_column} + ?
                        where session_id = ? and cf_id = ?
                        """,
                        (elapsed, session_id, cf_id),
                    )
                conn.execute(
                    "update web_contest_sessions set current_selected_at = ? where id = ?",
                    (now, session_id),
                )
            updated = conn.execute(
                f"""
                update web_contest_session_problems
                set {attempts_column} = {attempts_column} + 1,
                    {accepted_column} = case
                        when ? = 1 and {accepted_column} = '' then ?
                        else {accepted_column}
                    end
                where session_id = ? and cf_id = ?
                """,
                (1 if accepted else 0, now, session_id, cf_id),
            )
            if updated.rowcount != 1:
                raise ValueError("problem is not part of this contest session")
        session = self.get_web_contest_session(session_id, user_id)
        if session is None:
            raise RuntimeError("contest session disappeared")
        return session

    def end_web_contest_session(self, session_id: int, user_id: int) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            active = conn.execute(
                """
                select current_cf_id, current_selected_at
                from web_contest_sessions
                where id = ? and user_id = ? and status = 'active'
                """,
                (session_id, user_id),
            ).fetchone()
            if active is None:
                raise ValueError("contest session is no longer active")
            _accrue_web_contest_focus(conn, session_id, str(active[0]), str(active[1]), now)
            updated = conn.execute(
                """
                update web_contest_sessions
                set status = 'ended', ended_at = ?
                where id = ? and user_id = ? and status = 'active'
                """,
                (now, session_id, user_id),
            )
            if updated.rowcount != 1:
                raise ValueError("contest session is no longer active")
        session = self.get_web_contest_session(session_id, user_id)
        if session is None:
            raise RuntimeError("contest session disappeared")
        return session

    def delete_web_contest_session(self, session_id: int, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "delete from web_contest_sessions where id = ? and user_id = ?",
                (session_id, user_id),
            )

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("pragma journal_mode = wal")
            conn.execute(
                """
                create table if not exists sent_problems (
                    group_id text not null,
                    cf_id text not null,
                    contest_id integer not null,
                    problem_index text not null,
                    name text not null,
                    rating integer not null,
                    tags_json text not null,
                    sent_at text not null,
                    primary key (group_id, cf_id)
                )
                """
            )
            conn.execute("create index if not exists idx_sent_cf_id on sent_problems(cf_id)")
            conn.execute(
                """
                create table if not exists active_problems (
                    group_id text primary key,
                    cf_id text not null,
                    problem_json text not null,
                    statement_json text not null,
                    image_paths_json text not null,
                    created_at text not null,
                    ranked integer not null default 1
                )
                """
            )
            _ensure_column(
                conn,
                "active_problems",
                "ranked",
                "alter table active_problems add column ranked integer not null default 1",
            )
            conn.execute(
                """
                create table if not exists prefetched_problems (
                    group_id text not null,
                    min_rating integer not null,
                    max_rating integer not null,
                    cf_id text not null,
                    problem_json text not null,
                    statement_json text not null,
                    image_paths_json text not null,
                    created_at text not null,
                    primary key (group_id, min_rating, max_rating)
                )
                """
            )
            conn.execute(
                """
                create table if not exists statement_cache (
                    cf_id text primary key,
                    problem_json text not null,
                    statement_json text not null,
                    source text not null,
                    translated integer not null,
                    cached_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists user_stats (
                    group_id text not null,
                    user_id text not null,
                    display_name text not null,
                    solved_count integer not null,
                    rating real not null,
                    last_solved_at text not null,
                    primary key (group_id, user_id)
                )
                """
            )
            conn.execute(
                """
                create table if not exists submissions (
                    id integer primary key autoincrement,
                    group_id text not null,
                    user_id text not null,
                    display_name text not null,
                    cf_id text not null,
                    raw_text text not null,
                    accepted integer not null,
                    reason text not null,
                    created_at text not null,
                    ranked integer not null default 1
                )
                """
            )
            _ensure_column(
                conn,
                "submissions",
                "ranked",
                "alter table submissions add column ranked integer not null default 1",
            )
            conn.execute("create index if not exists idx_submissions_group on submissions(group_id, cf_id)")
            conn.execute(
                """
                create index if not exists idx_submissions_user_accepted
                on submissions(group_id, user_id, accepted, ranked, created_at)
                """
            )
            conn.execute(
                """
                create table if not exists group_settings (
                    group_id text primary key,
                    min_rating integer not null,
                    max_rating integer not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists code_submissions (
                    id integer primary key autoincrement,
                    group_id text not null,
                    user_id text not null,
                    display_name text not null,
                    cf_id text not null,
                    language text not null,
                    source_hash text not null,
                    source_chars integer not null,
                    accepted integer not null,
                    verdict text not null,
                    submission_id integer,
                    passed_tests integer,
                    time_ms integer,
                    memory_bytes integer,
                    url text not null,
                    message text not null,
                    created_at text not null,
                    ranked integer not null default 1
                )
                """
            )
            _ensure_column(
                conn,
                "code_submissions",
                "ranked",
                "alter table code_submissions add column ranked integer not null default 1",
            )
            conn.execute("create index if not exists idx_code_submissions_group on code_submissions(group_id, cf_id)")
            conn.execute(
                """
                create index if not exists idx_code_submissions_user_accepted
                on code_submissions(group_id, user_id, accepted, ranked, created_at)
                """
            )
            conn.execute(
                """
                create table if not exists bot_meta (
                    key text primary key,
                    value text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists solution_references (
                    id integer primary key autoincrement,
                    cf_id text not null,
                    source text not null,
                    title text not null,
                    author text not null,
                    url text not null,
                    content text not null,
                    content_hash text not null,
                    fetched_at text not null,
                    unique (cf_id, source, content_hash)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_solution_references_cf_id on solution_references(cf_id)"
            )
            conn.execute(
                """
                create table if not exists solution_fetch_attempts (
                    cf_id text primary key,
                    attempted_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists web_users (
                    id integer primary key autoincrement,
                    username text not null unique collate nocase,
                    display_name text not null,
                    password_hash text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists web_sessions (
                    token_hash text primary key,
                    user_id integer not null,
                    csrf_token text not null,
                    created_at text not null,
                    expires_at text not null,
                    foreign key (user_id) references web_users(id) on delete cascade
                )
                """
            )
            conn.execute("create index if not exists idx_web_sessions_user on web_sessions(user_id)")
            conn.execute(
                """
                create table if not exists web_contest_sessions (
                    id integer primary key autoincrement,
                    user_id integer not null,
                    contest_id integer not null,
                    contest_name text not null,
                    category text not null,
                    duration_seconds integer not null,
                    started_at text not null,
                    ended_at text not null,
                    status text not null,
                    current_cf_id text not null,
                    current_selected_at text not null,
                    foreign key (user_id) references web_users(id) on delete cascade
                )
                """
            )
            _ensure_column(
                conn,
                "web_contest_sessions",
                "current_selected_at",
                "alter table web_contest_sessions add column current_selected_at text not null default ''",
            )
            conn.execute(
                """
                create unique index if not exists idx_web_contest_sessions_active_user
                on web_contest_sessions(user_id)
                where status = 'active'
                """
            )
            conn.execute(
                """
                create table if not exists web_contest_session_problems (
                    session_id integer not null,
                    position integer not null,
                    cf_id text not null,
                    problem_json text not null,
                    opened_at text not null,
                    oral_accepted_at text not null,
                    code_accepted_at text not null,
                    oral_attempts integer not null,
                    code_attempts integer not null,
                    thinking_seconds integer not null,
                    coding_seconds integer not null,
                    primary key (session_id, cf_id),
                    unique (session_id, position),
                    foreign key (session_id) references web_contest_sessions(id) on delete cascade
                )
                """
            )
            _ensure_column(
                conn,
                "web_contest_session_problems",
                "thinking_seconds",
                "alter table web_contest_session_problems add column thinking_seconds integer not null default 0",
            )
            _ensure_column(
                conn,
                "web_contest_session_problems",
                "coding_seconds",
                "alter table web_contest_session_problems add column coding_seconds integer not null default 0",
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("pragma busy_timeout = 30000")
        conn.execute("pragma foreign_keys = on")
        return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(ddl)


def _seconds_between(start_value: str, end_value: str) -> int:
    if not start_value or not end_value:
        return 0
    try:
        start = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_value.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds()))


def _accrue_web_contest_focus(
    conn: sqlite3.Connection,
    session_id: int,
    cf_id: str,
    selected_at: str,
    now: str,
) -> None:
    row = conn.execute(
        """
        select oral_accepted_at, code_accepted_at
        from web_contest_session_problems
        where session_id = ? and cf_id = ?
        """,
        (session_id, cf_id),
    ).fetchone()
    if row is None:
        return
    column = None
    if not row[0] and not row[1]:
        column = "thinking_seconds"
    elif row[0] and not row[1]:
        column = "coding_seconds"
    if column is None:
        return
    conn.execute(
        f"""
        update web_contest_session_problems
        set {column} = {column} + ?
        where session_id = ? and cf_id = ?
        """,
        (_seconds_between(selected_at, now), session_id, cf_id),
    )


def _web_user_row(row) -> Optional[dict]:
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "username": str(row[1]),
        "display_name": str(row[2]),
        "password_hash": str(row[3]),
        "created_at": str(row[4]),
    }


def _cached_statement_title(raw_json: object, fallback: str) -> str:
    if not raw_json:
        return fallback
    try:
        title = str(json.loads(str(raw_json)).get("title") or "").strip()
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return title or fallback


def _solved_ratings_for_user(conn: sqlite3.Connection, group_id: int, user_id: int) -> Tuple[int, ...]:
    return _solved_ratings_by_user(conn, group_id).get(str(user_id), ())


def _solved_ratings_by_user(conn: sqlite3.Connection, group_id: int) -> Dict[str, Tuple[int, ...]]:
    solved: Dict[str, Dict[str, int]] = {}
    rows = conn.execute(
        """
        select user_id, cf_id, rating
        from (
            select s.user_id as user_id, s.cf_id as cf_id, sp.rating as rating
            from submissions s
            join sent_problems sp on sp.group_id = s.group_id and sp.cf_id = s.cf_id
            where s.group_id = ? and s.accepted = 1 and s.ranked = 1
            union all
            select c.user_id as user_id, c.cf_id as cf_id, sp.rating as rating
            from code_submissions c
            join sent_problems sp on sp.group_id = c.group_id and sp.cf_id = c.cf_id
            where c.group_id = ? and c.accepted = 1 and c.ranked = 1
        )
        """,
        (str(group_id), str(group_id)),
    ).fetchall()
    for user_id, cf_id, rating in rows:
        by_problem = solved.setdefault(str(user_id), {})
        by_problem[str(cf_id)] = max(int(rating), by_problem.get(str(cf_id), 0))
    return {
        user_id: tuple(sorted(problem_ratings.values(), reverse=True))
        for user_id, problem_ratings in solved.items()
    }


def _problem_to_json(problem: CFProblem) -> dict:
    return {
        "contest_id": problem.contest_id,
        "index": problem.index,
        "name": problem.name,
        "rating": problem.rating,
        "tags": list(problem.tags),
        "is_gym": problem.is_gym,
    }


def _problem_from_json(raw_json: str) -> CFProblem:
    raw = json.loads(raw_json)
    return CFProblem(
        contest_id=int(raw["contest_id"]),
        index=str(raw["index"]),
        name=str(raw["name"]),
        rating=int(raw["rating"]),
        tags=tuple(str(tag) for tag in raw.get("tags") or ()),
        is_gym=bool(raw.get("is_gym", False)),
    )


def _statement_to_json(statement: ProblemStatement) -> dict:
    return {
        "pid": statement.pid,
        "title": statement.title,
        "description": statement.description,
        "input_format": statement.input_format,
        "output_format": statement.output_format,
        "samples": [list(sample) for sample in statement.samples],
        "hint": statement.hint,
        "background": statement.background,
        "source_url": statement.source_url,
    }


def _statement_from_json(raw_json: str) -> ProblemStatement:
    raw = json.loads(raw_json)
    return ProblemStatement(
        pid=str(raw.get("pid") or ""),
        title=str(raw.get("title") or ""),
        description=str(raw.get("description") or ""),
        input_format=str(raw.get("input_format") or ""),
        output_format=str(raw.get("output_format") or ""),
        samples=[(str(sample[0]), str(sample[1])) for sample in raw.get("samples") or []],
        hint=str(raw.get("hint") or ""),
        background=str(raw.get("background") or ""),
        source_url=str(raw.get("source_url") or ""),
    )
