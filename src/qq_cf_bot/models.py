from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CFProblem:
    contest_id: int
    index: str
    name: str
    rating: int
    tags: Tuple[str, ...] = ()

    @property
    def cf_id(self) -> str:
        return f"{self.contest_id}{self.index}"

    @property
    def luogu_pid(self) -> str:
        return f"CF{self.cf_id}"

    @property
    def cf_url(self) -> str:
        return f"https://codeforces.com/problemset/problem/{self.contest_id}/{self.index}"

    @property
    def luogu_url(self) -> str:
        return f"https://www.luogu.com.cn/problem/{self.luogu_pid}"


@dataclass(frozen=True)
class ProblemStatement:
    pid: str
    title: str
    description: str
    input_format: str
    output_format: str
    samples: Sequence[Tuple[str, str]]
    hint: str = ""
    background: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class RenderedProblem:
    problem: CFProblem
    images: List[Path]


@dataclass(frozen=True)
class ActiveProblem:
    problem: CFProblem
    statement: ProblemStatement
    images: List[Path]
    created_at: str


@dataclass(frozen=True)
class GroupMessage:
    group_id: int
    user_id: int
    sender_name: str
    message_id: Optional[int]
    message: object


@dataclass(frozen=True)
class JudgeResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class UserStat:
    user_id: int
    display_name: str
    solved_count: int
    rating: float


@dataclass(frozen=True)
class RatingRange:
    min_rating: int
    max_rating: int


@dataclass(frozen=True)
class CodeSubmission:
    language: str
    source: str


@dataclass(frozen=True)
class RemoteJudgeResult:
    accepted: bool
    verdict: str
    message: str
    submission_id: Optional[int] = None
    passed_tests: Optional[int] = None
    time_ms: Optional[int] = None
    memory_bytes: Optional[int] = None
    url: str = ""


@dataclass(frozen=True)
class SolutionReference:
    cf_id: str
    source: str
    title: str
    author: str
    url: str
    content: str
    content_hash: str
    fetched_at: str = ""
