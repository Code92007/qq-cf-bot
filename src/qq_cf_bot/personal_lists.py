"""Private problem lists and untimed oral practice."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone

from .core import ChallengeError
from .models import CFProblem
from .problem_pool import normalize_problem


def _now():
    return datetime.now(timezone.utc).isoformat()


def _name(value, label, limit=80):
    value = str(value or "").strip()
    if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{label}需为 1-{limit} 个可见字符。")
    return value


def _id(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9]\d{0,9}", str(value)):
        raise ChallengeError("not_found", "题单或题目不存在。", 404)
    return int(value)


def parse_entries(raw, default_group="未分组"):
    if not isinstance(raw, str) or len(raw) > 50000:
        raise ValueError("每次最多导入 50000 字符。")
    group = _name(default_group, "分组", 40)
    entries = []
    seen = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            group = _name(line.lstrip("#").strip(), "分组", 40)
            continue
        for token in re.split(r"[\s,，;；]+", line):
            if not token:
                continue
            item = normalize_problem(token)
            if re.fullmatch(r"CF[1-9]\d+[A-Za-z][A-Za-z0-9]*", token, re.I):
                item["problemId"] = token.upper()
                item["url"] = "https://www.luogu.com.cn/problem/" + item["problemId"]
            if item["key"] in seen:
                continue
            seen.add(item["key"])
            entries.append((group, item))
            if len(entries) > 1000:
                raise ValueError("每次最多导入 1000 道题。")
    if not entries:
        raise ValueError("请输入至少一道题。")
    return entries


class PersonalLists:
    def __init__(self, web):
        self.web = web
        self.prepare_lock = threading.Lock()
        with self.connect() as db:
            db.executescript("""
                create table if not exists personal_lists(
                    id integer primary key, owner_id integer not null, name text not null,
                    created_at text not null, updated_at text not null,
                    foreign key(owner_id) references web_users(id) on delete cascade);
                create index if not exists personal_lists_owner on personal_lists(owner_id);
                create table if not exists personal_list_entries(
                    id integer primary key, list_id integer not null, position integer not null,
                    group_name text not null, problem_key text not null, platform text not null,
                    problem_id text not null, url text not null, title text not null default '',
                    status text not null default 'new' check(status in ('new','doing','done','skipped')),
                    draft text not null default '', draft_version integer not null default 0,
                    statement_json text not null default '', updated_at text not null,
                    unique(list_id,problem_key),
                    foreign key(list_id) references personal_lists(id) on delete cascade);
                create index if not exists personal_entries_list on personal_list_entries(list_id,position);
                create table if not exists personal_list_attempts(
                    id integer primary key, entry_id integer not null, request_id text not null,
                    body text not null, accepted integer not null, reason text not null,
                    created_at text not null, unique(entry_id,request_id),
                    foreign key(entry_id) references personal_list_entries(id) on delete cascade);
            """)

    def connect(self):
        db = self.web.service.store._connect()
        db.row_factory = sqlite3.Row
        db.execute("pragma foreign_keys=on")
        return db

    def _list(self, db, user, list_id):
        row = db.execute("select * from personal_lists where id=? and owner_id=?", (_id(list_id), user)).fetchone()
        if not row:
            raise ChallengeError("list_not_found", "题单不存在。", 404)
        return row

    def _entry(self, db, user, entry_id):
        row = db.execute("""select e.* from personal_list_entries e
            join personal_lists l on l.id=e.list_id where e.id=? and l.owner_id=?""",
            (_id(entry_id), user)).fetchone()
        if not row:
            raise ChallengeError("problem_not_found", "题目不存在。", 404)
        return row

    def state(self, user):
        with self.connect() as db:
            lists = [dict(r) for r in db.execute("""select l.id,l.name,l.created_at,l.updated_at,
                count(e.id) as total, sum(case when e.status='done' then 1 else 0 end) as done
                from personal_lists l left join personal_list_entries e on e.list_id=l.id
                where l.owner_id=? group by l.id order by l.updated_at desc,l.id desc""", (user,))]
        return {"lists": [{"id": r["id"], "name": r["name"], "total": r["total"],
                           "done": r["done"] or 0, "updatedAt": r["updated_at"]} for r in lists]}

    def listing(self, user, list_id):
        with self.connect() as db:
            item = self._list(db, user, list_id)
            rows = [dict(r) for r in db.execute("""select id,position,group_name,platform,problem_id,url,title,status,
                case when length(draft)>0 then 1 else 0 end as has_draft from personal_list_entries
                where list_id=? order by position,id""", (item["id"],))]
        return {"list": {"id": item["id"], "name": item["name"]},
                "entries": [{"id": r["id"], "group": r["group_name"], "platform": r["platform"],
                             "problemId": r["problem_id"], "url": r["url"], "title": r["title"],
                             "status": r["status"], "hasDraft": bool(r["has_draft"])} for r in rows]}

    def create(self, user, name, text=""):
        name = _name(name, "题单名称")
        entries = parse_entries(text) if str(text or "").strip() else []
        with self.connect() as db:
            db.execute("begin immediate")
            count = db.execute("select count(*) from personal_lists where owner_id=?", (user,)).fetchone()[0]
            if count >= 100:
                raise ValueError("每人最多创建 100 个题单。")
            stamp = _now()
            cur = db.execute("insert into personal_lists(owner_id,name,created_at,updated_at) values (?,?,?,?)",
                             (user, name, stamp, stamp))
            self._insert_entries(db, cur.lastrowid, entries)
        return {"id": cur.lastrowid, "added": len(entries)}

    def _insert_entries(self, db, list_id, entries):
        position = db.execute("select coalesce(max(position),0) from personal_list_entries where list_id=?", (list_id,)).fetchone()[0]
        added = 0
        for group, item in entries:
            position += 1
            cur = db.execute("""insert or ignore into personal_list_entries
                (list_id,position,group_name,problem_key,platform,problem_id,url,updated_at)
                values (?,?,?,?,?,?,?,?)""", (list_id, position, group, item["key"], item["platform"],
                                              item["problemId"], item["url"], _now()))
            added += cur.rowcount
        return added

    def add(self, user, list_id, text, group):
        entries = parse_entries(text, group)
        with self.connect() as db:
            db.execute("begin immediate")
            self._list(db, user, list_id)
            count = db.execute("select count(*) from personal_list_entries where list_id=?", (list_id,)).fetchone()[0]
            if count + len(entries) > 5000:
                raise ValueError("单个题单最多 5000 道题。")
            added = self._insert_entries(db, list_id, entries)
            db.execute("update personal_lists set updated_at=? where id=?", (_now(), list_id))
        return {"added": added, "duplicates": len(entries) - added}

    def rename(self, user, list_id, name):
        name = _name(name, "题单名称")
        with self.connect() as db:
            self._list(db, user, list_id)
            db.execute("update personal_lists set name=?,updated_at=? where id=?", (name, _now(), list_id))
        return {"ok": True}

    def delete(self, user, list_id):
        with self.connect() as db:
            db.execute("begin immediate")
            self._list(db, user, list_id)
            db.execute("delete from personal_list_attempts where entry_id in (select id from personal_list_entries where list_id=?)", (list_id,))
            db.execute("delete from personal_list_entries where list_id=?", (list_id,))
            db.execute("delete from personal_lists where id=?", (list_id,))
        return {"ok": True}

    def remove(self, user, entry_id):
        with self.connect() as db:
            db.execute("begin immediate")
            entry = self._entry(db, user, entry_id)
            db.execute("delete from personal_list_attempts where entry_id=?", (entry_id,))
            db.execute("delete from personal_list_entries where id=?", (entry_id,))
            db.execute("update personal_lists set updated_at=? where id=?", (_now(), entry["list_id"]))
        return {"ok": True}

    def detail(self, user, entry_id, prepare=False):
        with self.connect() as db:
            entry = self._entry(db, user, entry_id)
            attempts = [dict(r) for r in db.execute("""select id,body,accepted,reason,created_at
                from personal_list_attempts where entry_id=? order by id desc limit 20""", (entry_id,))]
        statement = json.loads(entry["statement_json"]) if entry["statement_json"] else None
        error = ""
        if prepare and not statement:
            try:
                statement = self._fetch_statement(entry)
                with self.connect() as db:
                    self._entry(db, user, entry_id)
                    db.execute("update personal_list_entries set statement_json=?,title=? where id=?",
                               (json.dumps(statement, ensure_ascii=False), statement["title"], entry_id))
            except Exception:
                error = "题面暂时无法加载，可粘贴原题题面后继续口胡。"
        return {"entry": {"id": entry["id"], "group": entry["group_name"], "problemId": entry["problem_id"],
                          "platform": entry["platform"], "url": entry["url"], "status": entry["status"],
                          "title": entry["title"]}, "draft": entry["draft"], "draftVersion": entry["draft_version"],
                "statement": statement, "statementError": error, "attempts": attempts}

    def _fetch_statement(self, entry):
        platform, pid = entry["platform"], entry["problem_id"]
        if platform == "luogu":
            statement = self.web.service.luogu.fetch_problem_id(pid)
        elif platform == "codeforces":
            match = re.fullmatch(r"(\d+)([A-Z][A-Z0-9]*)", pid.removeprefix("CF"))
            problem = CFProblem(int(match[1]), match[2], pid, 0, (), int(match[1]) >= 100000)
            statement = self.web.service.fetch_statement(problem)
        else:
            raise RuntimeError("No statement adapter for this platform")
        if not statement.description.strip():
            raise RuntimeError("Empty statement")
        return {"title": statement.title, "description": statement.description,
                "input": statement.input_format, "output": statement.output_format,
                "hint": statement.hint, "background": statement.background,
                "samples": list(statement.samples), "sourceUrl": entry["url"]}

    def save_statement(self, user, entry_id, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 30000:
            raise ValueError("题面需为 1-30000 字。")
        with self.connect() as db:
            entry = self._entry(db, user, entry_id)
            title = entry["title"] or entry["problem_id"]
            statement = {"title": title, "description": text.strip(), "input": "", "output": "",
                         "hint": "", "background": "", "samples": [], "sourceUrl": entry["url"]}
            db.execute("update personal_list_entries set statement_json=?,updated_at=? where id=?",
                       (json.dumps(statement, ensure_ascii=False), _now(), entry_id))
        return {"statement": statement}

    def save_draft(self, user, entry_id, text, version):
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("草稿最多 20000 字。")
        with self.connect() as db:
            db.execute("begin immediate")
            entry = self._entry(db, user, entry_id)
            if entry["draft_version"] != version or isinstance(version, bool):
                raise ChallengeError("draft_conflict", "草稿已在别处更新，请重新打开题目。", 409)
            db.execute("update personal_list_entries set draft=?,draft_version=draft_version+1,updated_at=? where id=?",
                       (text, _now(), entry_id))
        return {"draftVersion": version + 1}

    def set_status(self, user, entry_id, status):
        if status not in {"new", "doing", "done", "skipped"}:
            raise ValueError("进度状态不正确。")
        with self.connect() as db:
            self._entry(db, user, entry_id)
            db.execute("update personal_list_entries set status=?,updated_at=? where id=?", (status, _now(), entry_id))
        return {"status": status}

    def submit(self, user, entry_id, body, request_id):
        if not isinstance(body, str) or not body.strip() or len(body) > 20000:
            raise ValueError("口胡做法需为 1-20000 字。")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise ValueError("提交 ID 不正确。")
        with self.connect() as db:
            entry = self._entry(db, user, entry_id)
            old = db.execute("select * from personal_list_attempts where entry_id=? and request_id=?",
                             (entry_id, request_id)).fetchone()
            if old:
                if old["body"] != body:
                    raise ChallengeError("request_conflict", "提交 ID 已用于另一份做法。", 409)
                return {"accepted": bool(old["accepted"]), "reason": old["reason"]}
        if not self.web.service.judge.configured:
            raise ChallengeError("judge_unavailable", "口胡审核服务尚未配置。", 503)
        statement = json.loads(entry["statement_json"]) if entry["statement_json"] else None
        if not statement or not statement["description"].strip():
            raise ChallengeError("statement_required", "先准备题面，再提交口胡。", 409)
        problem = CFProblem(0, entry["problem_id"], statement["title"], 0)
        from .models import ProblemStatement
        item = ProblemStatement(entry["problem_id"], statement["title"], statement["description"],
                                statement["input"], statement["output"], statement["samples"], statement["hint"],
                                statement["background"], statement["sourceUrl"])
        with self.connect() as db:
            history = [dict(r) for r in db.execute("""select body,accepted,reason from personal_list_attempts
                where entry_id=? order by id desc limit 8""", (entry_id,))]
        outcome = self.web.service.judge.judge(problem, item, body, submission_history=[
            {"raw_text": r["body"], "accepted": bool(r["accepted"]), "reason": r["reason"]} for r in history])
        with self.connect() as db:
            db.execute("begin immediate")
            self._entry(db, user, entry_id)
            db.execute("""insert or ignore into personal_list_attempts
                (entry_id,request_id,body,accepted,reason,created_at) values (?,?,?,?,?,?)""",
                (entry_id, request_id, body, int(outcome.accepted), outcome.reason, _now()))
            db.execute("""update personal_list_entries set draft=?,draft_version=draft_version+1,
                status=case when status='done' then 'done' else ? end,updated_at=? where id=?""",
                       (body, "done" if outcome.accepted else "doing", _now(), entry_id))
        return {"accepted": outcome.accepted, "reason": outcome.reason}

    def post(self, user, action, payload):
        if action == "create":
            return self.create(user, payload.get("name"), payload.get("text", ""))
        if action == "add":
            return self.add(user, payload.get("listId"), payload.get("text"), payload.get("group") or "未分组")
        if action == "rename":
            return self.rename(user, payload.get("listId"), payload.get("name"))
        if action == "delete":
            return self.delete(user, payload.get("listId"))
        if action == "remove":
            return self.remove(user, payload.get("entryId"))
        if action == "open":
            return self.detail(user, payload.get("entryId"), payload.get("prepareStatement") is True)
        if action == "statement":
            return self.save_statement(user, payload.get("entryId"), payload.get("text"))
        if action == "draft":
            return self.save_draft(user, payload.get("entryId"), payload.get("text"), payload.get("version"))
        if action == "status":
            return self.set_status(user, payload.get("entryId"), payload.get("status"))
        if action == "oral":
            return self.submit(user, payload.get("entryId"), payload.get("body"), payload.get("requestId"))
        raise ChallengeError("not_found", "没有这个题单操作。", 404)
