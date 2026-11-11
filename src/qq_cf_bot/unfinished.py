"""Private, resumable problem drafts with optimistic concurrency control."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .core import ChallengeError
from .problem_pool import normalize_problem


LANGUAGES = {"cpp", "c", "java", "py", "rust", "other"}
FIELDS = {"title": 120, "problemRef": 500, "idea": 20000, "code": 128000, "nextStep": 2000}
PAGE_SIZE = 30


def _invalid(message):
    raise ChallengeError("invalid_request", message, 400)


def _number(value, label):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9]\d{0,12}", str(value)):
        _invalid(f"{label}不正确。")
    return int(value)


def _text(value, maximum, label):
    if not isinstance(value, str) or len(value) > maximum or any(
        ord(c) < 32 and c not in "\n\r\t" for c in value
    ):
        _invalid(f"{label}需为文本，且不超过 {maximum} 字符。")
    return value


def _url(reference):
    try:
        parsed = urlsplit(reference)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not (parsed.username or parsed.password):
            return reference
        return normalize_problem(reference)["url"]
    except ValueError:
        return ""


class UnfinishedPool:
    def __init__(self, web):
        self.web = web
        with self.connect() as db:
            db.executescript("""
                create table if not exists unfinished_entries (
                    id integer primary key,
                    user_id integer not null references web_users(id) on delete cascade,
                    client_id text not null,
                    title text not null, problem_ref text not null,
                    idea text not null, code text not null, language text not null,
                    next_step text not null,
                    status text not null default 'open' check(status in ('open','done')),
                    revision integer not null default 1,
                    created_at text not null, updated_at text not null,
                    completed_at text not null default '',
                    unique(user_id, client_id));
                create index if not exists unfinished_user_updated
                    on unfinished_entries(user_id, updated_at desc, id desc);
            """)

    def connect(self):
        db = self.web.service.store._connect()
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _item(row):
        return {"id": row["id"], "title": row["title"], "problemRef": row["problem_ref"],
                "url": _url(row["problem_ref"]), "idea": row["idea"], "code": row["code"],
                "language": row["language"], "nextStep": row["next_step"],
                "status": row["status"], "revision": row["revision"],
                "createdAt": row["created_at"], "updatedAt": row["updated_at"],
                "completedAt": row["completed_at"]}

    @staticmethod
    def _find(db, user, entry_id):
        row = db.execute("select * from unfinished_entries where user_id=? and id=?", (user, entry_id)).fetchone()
        if row is None:
            raise ChallengeError("unfinished_not_found", "这条记录不存在。", 404)
        return row

    def entry(self, user, entry_id):
        with self.connect() as db:
            return {"item": self._item(self._find(db, user, _number(entry_id, "记录编号")))}

    def listing(self, session, query):
        user = int(session["user_id"])
        status = query.get("status", "open")
        if status not in {"open", "done", "all"}:
            _invalid("筛选状态不正确。")
        q = _text(query.get("q", ""), 100, "搜索词").strip().lower()
        page = _number(query.get("page", 1), "页码")
        where, args = "user_id=?", [user]
        if status != "all":
            where += " and status=?"
            args.append(status)
        if q:
            where += " and instr(lower(title || char(10) || problem_ref || char(10) || idea || char(10) || code || char(10) || next_step), ?) > 0"
            args.append(q)
        with self.connect() as db:
            counts = {"open": 0, "done": 0}
            counts.update({r["status"]: r["n"] for r in db.execute(
                "select status,count(*) n from unfinished_entries where user_id=? group by status", (user,))})
            counts["all"] = counts["open"] + counts["done"]
            total = db.execute(f"select count(*) from unfinished_entries where {where}", args).fetchone()[0]
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(page, pages)
            rows = db.execute(f"""select id,title,problem_ref,next_step,status,revision,updated_at,
                substr(idea,1,140) preview, length(trim(idea)) has_idea, length(trim(code)) has_code
                from unfinished_entries where {where} order by updated_at desc,id desc limit ? offset ?""",
                [*args, PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
        return {"items": [{"id": r["id"], "title": r["title"], "problemRef": r["problem_ref"],
                           "nextStep": r["next_step"], "preview": r["preview"], "status": r["status"],
                           "revision": r["revision"], "updatedAt": r["updated_at"],
                           "hasIdea": bool(r["has_idea"]), "hasCode": bool(r["has_code"])} for r in rows],
                "counts": counts, "total": total, "page": page, "pages": pages,
                "csrfToken": session["csrf_token"],
                "user": {"id": user, "displayName": session["display_name"]}}

    def post(self, session, action, payload):
        if action not in {"save", "status"}:
            raise ChallengeError("not_found", "操作不存在。", 404)
        user = int(session["user_id"])
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("begin immediate")
            entry_id = payload.get("id")
            row = self._find(db, user, _number(entry_id, "记录编号")) if entry_id is not None else None
            if row is not None and _number(payload.get("revision"), "草稿版本") != row["revision"]:
                raise ChallengeError("draft_conflict", "另一处已更新这道题。当前草稿已保留，请加载最新版本或另存一份。", 409)
            if action == "status":
                if row is None or payload.get("status") not in {"open", "done"}:
                    _invalid("请选择要更新的记录和完成状态。")
                status = payload["status"]
                if row["status"] != status:
                    db.execute("""update unfinished_entries set status=?,completed_at=?,updated_at=?,revision=revision+1
                        where id=? and user_id=?""", (status, now if status == "done" else "", now, row["id"], user))
            else:
                fields = {name: _text(payload.get(name, ""), maximum, name) for name, maximum in FIELDS.items()}
                language = payload.get("language", "cpp")
                if not isinstance(language, str) or language not in LANGUAGES:
                    _invalid("请选择支持的代码语言。")
                if not any(value.strip() for value in fields.values()):
                    _invalid("先留下一点题目、思路或代码吧。")
                fields["title"] = fields["title"].strip() or fields["problemRef"].strip()[:120] or "未命名的题目"
                values = [fields["title"], fields["problemRef"].strip(), fields["idea"], fields["code"], language, fields["nextStep"]]
                if row is not None:
                    db.execute("""update unfinished_entries set title=?,problem_ref=?,idea=?,code=?,language=?,
                        next_step=?,updated_at=?,revision=revision+1 where id=? and user_id=?""", [*values, now, row["id"], user])
                else:
                    client_id = payload.get("clientId")
                    if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", client_id):
                        _invalid("草稿标识不正确，请刷新页面。")
                    # A lost response can be retried without creating a second draft.
                    row = db.execute("select * from unfinished_entries where user_id=? and client_id=?", (user, client_id)).fetchone()
                    if row is None:
                        entry_id = db.execute("""insert into unfinished_entries
                            (user_id,client_id,title,problem_ref,idea,code,language,next_step,created_at,updated_at)
                            values (?,?,?,?,?,?,?,?,?,?)""", [user, client_id, *values, now, now]).lastrowid
                    else:
                        entry_id = row["id"]
            if row is not None:
                entry_id = row["id"]
            return {"item": self._item(self._find(db, user, entry_id))}
