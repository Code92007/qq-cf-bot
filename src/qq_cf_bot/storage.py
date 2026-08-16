from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import (
    ActiveProblem,
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

    def _init(self) -> None:
        with self._connect() as conn:
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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(ddl)


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
    }


def _problem_from_json(raw_json: str) -> CFProblem:
    raw = json.loads(raw_json)
    return CFProblem(
        contest_id=int(raw["contest_id"]),
        index=str(raw["index"]),
        name=str(raw["name"]),
        rating=int(raw["rating"]),
        tags=tuple(str(tag) for tag in raw.get("tags") or ()),
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
