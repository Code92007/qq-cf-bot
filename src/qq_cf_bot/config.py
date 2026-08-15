from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional

from .llm import infer_wire_api, normalize_wire_api


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _groups_env(name: str) -> FrozenSet[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return frozenset()
    groups = set()
    for item in raw.replace(";", ",").split(","):
        item = item.strip()
        if item:
            groups.add(int(item))
    return frozenset(groups)


def _optional_int_env(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _wire_api_env(name: str, default: str) -> str:
    raw = os.getenv(name, "").strip()
    return normalize_wire_api(raw or default)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    onebot_http_url: str
    onebot_access_token: str
    onebot_image_mode: str
    onebot_self_id: Optional[int]
    allowed_groups: FrozenSet[int]
    db_path: Path
    cache_path: Path
    asset_dir: Path
    min_rating: int
    max_rating: int
    dedup_scope: str
    cf_cache_ttl_seconds: int
    max_selection_attempts: int
    render_width: int
    render_viewport_height: int
    render_max_slice_height: int
    initial_rating: float
    rating_k_factor: float
    judge_api_url: str
    judge_api_key: str
    judge_model: str
    judge_wire_api: str
    judge_enabled: bool
    judge_timeout_seconds: int
    judge_statement_max_chars: int
    judge_solution_context_max_chars: int
    solution_bank_enabled: bool
    solution_bank_min_refs: int
    solution_bank_max_refs: int
    solution_bank_max_ref_chars: int
    solution_bank_fetch_luogu: bool
    solution_bank_fetch_cf_editorial: bool
    solution_bank_fetch_cf_ac_code: bool
    solution_bank_generate_llm: bool
    fallback_statement_source: str
    translate_enabled: bool
    translate_api_url: str
    translate_api_key: str
    translate_model: str
    translate_wire_api: str
    translate_timeout_seconds: int
    translate_max_chars: int
    cf_submit_enabled: bool
    cf_username: str
    cf_password: str
    cf_handle: str
    cf_submit_default_language: str
    cf_submit_language_id: str
    cf_submit_min_interval_seconds: int
    cf_submit_poll_interval_seconds: int
    cf_submit_poll_timeout_seconds: int
    cf_submit_http_timeout_seconds: int
    cf_auto_submit_direct_code: bool

    @classmethod
    def from_env(cls) -> "Config":
        root = Path(os.getenv("BOT_DATA_DIR", "data"))
        judge_api_url = os.getenv("JUDGE_API_URL", "https://api.openai.com/v1/chat/completions").rstrip("/")
        judge_api_key = os.getenv("JUDGE_API_KEY", "")
        judge_model = os.getenv("JUDGE_MODEL", "")
        judge_wire_api = _wire_api_env("JUDGE_WIRE_API", infer_wire_api(judge_api_url))
        dedup_scope = os.getenv("BOT_DEDUP_SCOPE", "group").strip().lower()
        if dedup_scope not in {"group", "global"}:
            raise ValueError("BOT_DEDUP_SCOPE must be either 'group' or 'global'")
        min_rating = _int_env("CF_MIN_RATING", 1900)
        max_rating = _int_env("CF_MAX_RATING", 2600)
        if min_rating > max_rating:
            raise ValueError("CF_MIN_RATING must be <= CF_MAX_RATING")

        onebot_image_mode = os.getenv("ONEBOT_IMAGE_MODE", "base64").strip().lower()
        if onebot_image_mode not in {"base64", "file_uri"}:
            raise ValueError("ONEBOT_IMAGE_MODE must be either 'base64' or 'file_uri'")
        fallback_statement_source = os.getenv("FALLBACK_STATEMENT_SOURCE", "codeforces").strip().lower()
        if fallback_statement_source not in {"codeforces", "none"}:
            raise ValueError("FALLBACK_STATEMENT_SOURCE must be either 'codeforces' or 'none'")

        return cls(
            host=os.getenv("BOT_HOST", "127.0.0.1"),
            port=_int_env("BOT_PORT", 8088),
            onebot_http_url=os.getenv("ONEBOT_HTTP_URL", "http://127.0.0.1:3000").rstrip("/"),
            onebot_access_token=os.getenv("ONEBOT_ACCESS_TOKEN", ""),
            onebot_image_mode=onebot_image_mode,
            onebot_self_id=_optional_int_env("ONEBOT_SELF_ID"),
            allowed_groups=_groups_env("BOT_ALLOWED_GROUPS"),
            db_path=Path(os.getenv("BOT_DB_PATH", str(root / "bot.sqlite3"))),
            cache_path=Path(os.getenv("CF_CACHE_PATH", str(root / "codeforces_problems.json"))),
            asset_dir=Path(os.getenv("BOT_ASSET_DIR", str(root / "assets"))),
            min_rating=min_rating,
            max_rating=max_rating,
            dedup_scope=dedup_scope,
            cf_cache_ttl_seconds=_int_env("CF_CACHE_TTL_SECONDS", 6 * 60 * 60),
            max_selection_attempts=_int_env("BOT_MAX_SELECTION_ATTEMPTS", 30),
            render_width=_int_env("RENDER_WIDTH", 760),
            render_viewport_height=_int_env("RENDER_VIEWPORT_HEIGHT", 1100),
            render_max_slice_height=_int_env("RENDER_MAX_SLICE_HEIGHT", 2400),
            initial_rating=float(os.getenv("RANK_INITIAL_RATING", "1500")),
            rating_k_factor=float(os.getenv("RANK_K_FACTOR", "64")),
            judge_api_url=judge_api_url,
            judge_api_key=judge_api_key,
            judge_model=judge_model,
            judge_wire_api=judge_wire_api,
            judge_enabled=_bool_env("JUDGE_ENABLED", True),
            judge_timeout_seconds=_int_env("JUDGE_TIMEOUT_SECONDS", 60),
            judge_statement_max_chars=_int_env("JUDGE_STATEMENT_MAX_CHARS", 12_000),
            judge_solution_context_max_chars=_int_env("JUDGE_SOLUTION_CONTEXT_MAX_CHARS", 10_000),
            solution_bank_enabled=_bool_env("SOLUTION_BANK_ENABLED", True),
            solution_bank_min_refs=_int_env("SOLUTION_BANK_MIN_REFS", 1),
            solution_bank_max_refs=_int_env("SOLUTION_BANK_MAX_REFS", 4),
            solution_bank_max_ref_chars=_int_env("SOLUTION_BANK_MAX_REF_CHARS", 5_000),
            solution_bank_fetch_luogu=_bool_env("SOLUTION_BANK_FETCH_LUOGU", True),
            solution_bank_fetch_cf_editorial=_bool_env("SOLUTION_BANK_FETCH_CF_EDITORIAL", True),
            solution_bank_fetch_cf_ac_code=_bool_env("SOLUTION_BANK_FETCH_CF_AC_CODE", False),
            solution_bank_generate_llm=_bool_env("SOLUTION_BANK_GENERATE_LLM", True),
            fallback_statement_source=fallback_statement_source,
            translate_enabled=_bool_env("TRANSLATE_ENABLED", True),
            translate_api_url=(os.getenv("TRANSLATE_API_URL") or judge_api_url).rstrip("/"),
            translate_api_key=os.getenv("TRANSLATE_API_KEY") or judge_api_key,
            translate_model=os.getenv("TRANSLATE_MODEL") or judge_model,
            translate_wire_api=_wire_api_env("TRANSLATE_WIRE_API", judge_wire_api),
            translate_timeout_seconds=_int_env("TRANSLATE_TIMEOUT_SECONDS", 60),
            translate_max_chars=_int_env("TRANSLATE_MAX_CHARS", 24_000),
            cf_submit_enabled=_bool_env("CF_SUBMIT_ENABLED", False),
            cf_username=os.getenv("CF_USERNAME", ""),
            cf_password=os.getenv("CF_PASSWORD", ""),
            cf_handle=os.getenv("CF_HANDLE") or os.getenv("CF_USERNAME", ""),
            cf_submit_default_language=os.getenv("CF_SUBMIT_DEFAULT_LANGUAGE", "cpp").strip().lower(),
            cf_submit_language_id=os.getenv("CF_SUBMIT_LANGUAGE_ID", "").strip(),
            cf_submit_min_interval_seconds=_int_env("CF_SUBMIT_MIN_INTERVAL_SECONDS", 180),
            cf_submit_poll_interval_seconds=_int_env("CF_SUBMIT_POLL_INTERVAL_SECONDS", 8),
            cf_submit_poll_timeout_seconds=_int_env("CF_SUBMIT_POLL_TIMEOUT_SECONDS", 180),
            cf_submit_http_timeout_seconds=_int_env("CF_SUBMIT_HTTP_TIMEOUT_SECONDS", 30),
            cf_auto_submit_direct_code=_bool_env("CF_AUTO_SUBMIT_DIRECT_CODE", False),
        )
