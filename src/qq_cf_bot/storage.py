from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Set

from .models import (
    ActiveProblem,
    CFProblem,
    ProblemStatement,
    RatingRange,
    RemoteJudgeResult,
    SolutionReference,
    UserStat,
)


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
                select problem_json, statement_json, image_paths_json, created_at
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
        )

    def set_active_problem(
        self,
        group_id: int,
        problem: CFProblem,
        statement: ProblemStatement,
        image_paths: Iterable[Path],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into active_problems
                    (group_id, cf_id, problem_json, statement_json, image_paths_json, created_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(group_id) do update set
                    cf_id = excluded.cf_id,
                    problem_json = excluded.problem_json,
                    statement_json = excluded.statement_json,
                    image_paths_json = excluded.image_paths_json,
                    created_at = excluded.created_at
                """,
                (
                    str(group_id),
                    problem.cf_id,
                    json.dumps(_problem_to_json(problem), ensure_ascii=False),
                    json.dumps(_statement_to_json(statement), ensure_ascii=False),
                    json.dumps([str(path) for path in image_paths], ensure_ascii=False),
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
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into submissions
                    (group_id, user_id, display_name, cf_id, raw_text, accepted, reason, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

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
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into code_submissions
                    (
                        group_id, user_id, display_name, cf_id, language, source_hash,
                        source_chars, accepted, verdict, submission_id, passed_tests,
                        time_ms, memory_bytes, url, message, created_at
                    )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return UserStat(user_id=user_id, display_name=str(row[0]), solved_count=int(row[1]), rating=float(row[2]))

    def mark_solved(
        self,
        group_id: int,
        user_id: int,
        display_name: str,
        new_rating: float,
        initial_rating: float,
    ) -> UserStat:
        now = datetime.now(timezone.utc).isoformat()
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
        return UserStat(user_id=user_id, display_name=display_name, solved_count=solved_count, rating=new_rating)

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
        return [
            UserStat(
                user_id=int(row[0]),
                display_name=str(row[1]),
                solved_count=int(row[2]),
                rating=float(row[3]),
            )
            for row in rows
        ]

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
                    created_at text not null
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
                    created_at text not null
                )
                """
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
                    created_at text not null
                )
                """
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
