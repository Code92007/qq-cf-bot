"""Shared recommendations with private, persistent fishing and completion records."""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from .core import ChallengeError
from .storage import _ensure_column


PLATFORMS = {"codeforces": "CF / Gym", "luogu": "洛谷", "qoj": "QOJ",
             "atcoder": "AtCoder", "nowcoder": "牛客", "vjudge": "VJudge"}
STATUSES = {"new", "picked", "skipped", "ac"}


def normalize_problem(value: str, platform: str = "auto") -> dict:
    """Only store canonical, supported problem URLs; never fetch arbitrary input."""
    value = str(value or "").strip()
    platform = str(platform or "auto").strip().lower()
    platform = {"cf": "codeforces", "gym": "codeforces", "lg": "luogu", "nc": "nowcoder"}.get(platform, platform)
    if not value or len(value) > 500:
        raise ValueError("请输入题号或题目链接（最多 500 字符）。")
    if platform not in {*PLATFORMS, "auto"}:
        raise ValueError("请选择支持的 OJ 平台。")
    atcoder_url = None
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port:
            raise ValueError("请输入支持平台的题目链接。")
        host, path = (parsed.hostname or "").lower(), parsed.path.rstrip("/")
        match = None
        if host in {"codeforces.com", "www.codeforces.com"}:
            match = re.fullmatch(r"/(?:contest|gym)/(\d+)/problem/([A-Za-z][A-Za-z0-9]*)", path)
            match = match or re.fullmatch(r"/problemset/problem/(\d+)/([A-Za-z][A-Za-z0-9]*)", path)
            if match:
                platform, value = "codeforces", "".join(match.groups())
        elif host in {"luogu.com.cn", "www.luogu.com.cn", "luogu.org", "www.luogu.org"}:
            match = re.fullmatch(r"/problem/([A-Za-z0-9_]+)", path)
            if match:
                platform, value = "luogu", match[1]
        elif host in {"qoj.ac", "www.qoj.ac"}:
            match = re.fullmatch(r"/problem/(\d+)", path)
            if match:
                platform, value = "qoj", match[1]
        elif host in {"atcoder.jp", "www.atcoder.jp"}:
            match = re.fullmatch(r"/contests/([A-Za-z0-9_-]+)/tasks/([A-Za-z0-9_]+)", path)
            if match:
                platform, value = "atcoder", match[2]
                atcoder_url = f"https://atcoder.jp/contests/{match[1].lower()}/tasks/{value.lower()}"
            else:
                match = None
        elif host in {"ac.nowcoder.com", "www.nowcoder.com", "nowcoder.com"}:
            match = re.fullmatch(r"/acm/problem/(\d+)|/acm/contest/(\d+)/([A-Za-z0-9]+)|/practice/([a-fA-F0-9]{32})", path)
            if match:
                platform, value = "nowcoder", ":".join(x for x in match.groups() if x)
        elif host in {"vjudge.net", "www.vjudge.net"}:
            match = re.fullmatch(r"/problem/([A-Za-z0-9_]+-[A-Za-z0-9_:-]+)", path)
            if match:
                platform, value = "vjudge", match[1]
        if not match:
            raise ValueError("无法识别题目链接，请使用 CF/Gym、洛谷、QOJ、AtCoder、牛客或 VJudge 的题目页链接。")
    elif platform == "auto":
        prefix = re.fullmatch(r"(cf|codeforces|gym|luogu|lg|qoj|atcoder|nowcoder|nc|vjudge)\s*[:：]\s*(.+)", value, re.I)
        if prefix:
            return normalize_problem(prefix[2], prefix[1])
        if re.fullmatch(r"(?:CF)?[1-9]\d{0,6}[A-Za-z][A-Za-z0-9]*", value, re.I):
            platform = "codeforces"
        elif re.fullmatch(r"(?:P|B|U|AT|SP)\d+|AT_[A-Za-z0-9_]+", value, re.I):
            platform = "luogu"
        elif re.fullmatch(r"[A-Za-z0-9_]+_[A-Za-z0-9]+", value):
            platform = "atcoder"
        elif re.fullmatch(r"[A-Za-z0-9_]+-[A-Za-z0-9_:-]+", value):
            platform = "vjudge"
        else:
            raise ValueError("纯数字题号请选择 OJ 平台，或直接粘贴题目链接。")

    if platform == "vjudge":
        match = re.fullmatch(r"([A-Za-z0-9_]+)-([A-Za-z0-9_:-]+)", value)
        if not match:
            raise ValueError("VJudge 题号格式如 HDU-1000。")
        upstream = {"codeforces": "codeforces", "gym": "codeforces", "luogu": "luogu",
                    "qoj": "qoj", "atcoder": "atcoder", "nowcoder": "nowcoder"}.get(match[1].lower())
        if upstream:
            return normalize_problem(match[2], upstream)
        # VJudge OJ names are case sensitive in problem links.
        oj = {"hdu": "HDU", "poj": "POJ", "zoj": "ZOJ", "uva": "UVA", "uvalive": "UVALive",
              "spoj": "SPOJ", "ural": "URAL", "kattis": "Kattis", "hysbz": "HYSBZ"}.get(match[1].lower(), match[1])
        value = oj + "-" + match[2].upper()
        url = "https://vjudge.net/problem/" + value
        identity = value.upper()
    elif platform == "codeforces":
        value = re.sub(r"^CF", "", value, flags=re.I).upper()
        match = re.fullmatch(r"([1-9]\d{0,6})([A-Z][A-Z0-9]*)", value)
        if not match:
            raise ValueError("CF / Gym 题号格式如 1704F 或 105789A。")
        url = (f"https://codeforces.com/gym/{match[1]}/problem/{match[2]}" if int(match[1]) >= 100000
               else f"https://codeforces.com/problemset/problem/{match[1]}/{match[2]}")
        identity = value
    elif platform == "luogu":
        value = value.upper()
        if re.fullmatch(r"CF[1-9]\d{0,6}[A-Z][A-Z0-9]*", value):
            return normalize_problem(value, "codeforces")
        if not re.fullmatch(r"(?:P|B|U|AT|SP)[1-9]\d*|AT_[A-Z0-9_]+", value):
            raise ValueError("洛谷题号格式如 P1001。")
        url, identity = "https://www.luogu.com.cn/problem/" + ("AT_" + value[3:].lower() if value.startswith("AT_") else value), value
    elif platform == "qoj":
        if not re.fullmatch(r"[0-9]{1,9}", value) or int(value) < 1:
            raise ValueError("QOJ 题号需为正整数。")
        value = str(int(value))
        url, identity = "https://qoj.ac/problem/" + value, value
    elif platform == "atcoder":
        value = value.lower()
        match = re.fullmatch(r"([a-z0-9_]+)_([a-z0-9]+)", value)
        if not match:
            raise ValueError("AtCoder 题号格式如 abc350_f。")
        contest = match[1].replace("_", "-")
        url, identity = atcoder_url or f"https://atcoder.jp/contests/{contest}/tasks/{value}", value.upper()
    else:
        value = value.upper()
        if re.fullmatch(r"[1-9]\d{0,9}", value):
            url = "https://ac.nowcoder.com/acm/problem/" + value
        elif re.fullmatch(r"[1-9]\d{0,9}:[A-Z0-9]{1,8}", value):
            url = "https://ac.nowcoder.com/acm/contest/" + value.replace(":", "/")
        elif re.fullmatch(r"[A-F0-9]{32}", value):
            url = "https://www.nowcoder.com/practice/" + value.lower()
        else:
            raise ValueError("牛客题号需为练习题数字编号、比赛编号:A，或题目链接。")
        identity = value
    return {"key": f"{platform}:{identity}", "platform": platform, "problemId": value, "url": url}


def _text(value, maximum, label):
    value = str(value or "").strip()
    if len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError(f"{label}最多 {maximum} 字符，请勿包含控制字符。")
    return value


def _integer(value, minimum, maximum, label):
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError(f"{label}必须是 {minimum}–{maximum} 之间的整数。")
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{label}必须是 {minimum}–{maximum} 之间的整数。")
    return number


class ProblemPool:
    def __init__(self, web):
        self.web = web
        with self.connect() as db:
            db.executescript("""
                create table if not exists pool_problems(
                    id integer primary key, problem_key text not null unique,
                    platform text not null, problem_id text not null, url text not null,
                    title text not null, rating integer, tags_json text not null,
                    note text not null, author_id integer not null, created_at text not null,
                    foreign key(author_id) references web_users(id));
                create table if not exists pool_records(
                    user_id integer not null, problem_id integer not null,
                    status text not null check(status in ('new','picked','skipped','ac')),
                    drawn_at text not null default '', ac_at text not null default '',
                    updated_at text not null, draw_count integer not null default 0,
                    primary key(user_id,problem_id),
                    foreign key(user_id) references web_users(id) on delete cascade,
                    foreign key(problem_id) references pool_problems(id) on delete cascade);
                create index if not exists pool_author on pool_problems(author_id);
            """)
            _ensure_column(db, "pool_records", "training_cf_id",
                           "alter table pool_records add column training_cf_id text not null default ''")

    def connect(self):
        db = self.web.service.store._connect()
        db.row_factory = sqlite3.Row
        return db

    def _accepted(self, db, user):
        accepted = {}
        for table in ("submissions", "code_submissions"):
            for row in db.execute(f"select cf_id,created_at from {table} where group_id='-1' and user_id=? and accepted=1", (str(user),)):
                accepted["codeforces:" + row[0]] = ("站内通过", row[1])
        for row in db.execute("""select p.problem_key,r.training_cf_id from pool_records r
                join pool_problems p on p.id=r.problem_id where r.user_id=? and r.training_cf_id!=''""", (user,)):
            if "codeforces:" + row[1] in accepted:
                accepted[row[0]] = accepted["codeforces:" + row[1]]
        for row in db.execute("select problem_key,submitted_at from regional_evidence where user_id=? and verdict='AC'", (user,)):
            at = datetime.fromtimestamp(row[1], timezone.utc).isoformat() if row[1] else ""
            accepted[row[0]] = ("平台 AC", at)
        regional = self.web.regionals.store
        completed = {regional.aliases[key] for key in accepted if key in regional.aliases}
        for row in db.execute("select problem_id,created_at from regional_attempts where user_id=? and accepted=1", (user,)):
            problem = regional.problems.get(row[0], {})
            for key in problem.get("aliases", []):
                accepted.setdefault(key, ("区域赛通过", row[1]))
        for pid in completed:
            for key in regional.problems[pid].get("aliases", []):
                accepted.setdefault(key, ("区域赛通过", ""))
        return accepted

    def _items(self, db, user):
        accepted = self._accepted(db, user)
        rows = db.execute("""
            select p.*, u.display_name as author, r.status, r.drawn_at, r.ac_at, r.updated_at, r.draw_count
            from pool_problems p join web_users u on u.id=p.author_id
            left join pool_records r on r.problem_id=p.id and r.user_id=?
            order by p.id desc
        """, (user,))
        result = []
        for r in rows:
            imported = accepted.get(r["problem_key"])
            status = "ac" if imported else r["status"] or "new"
            result.append({"id": r["id"], "key": r["problem_key"], "platform": r["platform"],
                           "problemId": r["problem_id"], "url": r["url"], "title": r["title"],
                           "rating": r["rating"], "tags": json.loads(r["tags_json"]), "note": r["note"],
                           "author": r["author"], "authorId": r["author_id"], "createdAt": r["created_at"],
                           "status": status, "drawnAt": r["drawn_at"] or "", "drawCount": r["draw_count"] or 0,
                           "updatedAt": r["updated_at"] or "", "acAt": (r["ac_at"] or "") if not imported else imported[1],
                           "acSource": imported[0] if imported else "手动 AC" if status == "ac" else "",
                           "importedAc": bool(imported)})
        return result

    def _filter(self, items, user, filters):
        status, platform = str(filters.get("status") or "all"), str(filters.get("platform") or "all")
        if status not in {*STATUSES, "all"} or platform not in {*PLATFORMS, "all"}:
            raise ValueError("筛选项不正确。")
        query = _text(filters.get("q"), 100, "搜索词").casefold()
        tag = _text(filters.get("tag"), 40, "标签").casefold()
        minimum = _integer(filters["minRating"], 0, 4000, "最低难度") if filters.get("minRating") not in (None, "") else None
        maximum = _integer(filters["maxRating"], 0, 4000, "最高难度") if filters.get("maxRating") not in (None, "") else None
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("最低难度不能大于最高难度。")
        mine = filters.get("mine") in (True, "true", "1")
        return [p for p in items
                if (status == "all" or p["status"] == status)
                and (platform == "all" or p["platform"] == platform)
                and (not mine or p["authorId"] == user)
                and (not tag or tag in [t.casefold() for t in p["tags"]])
                and (not query or query in " ".join([p["problemId"], p["title"], p["note"], p["author"], *p["tags"]]).casefold())
                and (minimum is None or p["rating"] is not None and p["rating"] >= minimum)
                and (maximum is None or p["rating"] is not None and p["rating"] <= maximum)]

    def listing(self, user, filters):
        with self.connect() as db:
            items = self._items(db, user)
        page = _integer(filters.get("page", 1), 1, 1000000, "页码")
        selected = self._filter(items, user, filters)
        sort = str(filters.get("sort") or "newest")
        if sort not in {"newest", "oldest", "rating", "updated"}:
            raise ValueError("排序项不正确。")
        if sort == "oldest":
            selected.reverse()
        elif sort == "rating":
            selected.sort(key=lambda p: (p["rating"] is None, p["rating"] or 0, -p["id"]))
        elif sort == "updated":
            selected.sort(key=lambda p: (p["updatedAt"] or p["acAt"] or p["createdAt"], p["id"]), reverse=True)
        pages = max(1, (len(selected) + 23) // 24)
        page = min(page, pages)
        counts = Counter(p["status"] for p in items)
        available = len(self._filter(items, user, {**filters, "status": "new"}))
        return {"items": selected[(page - 1) * 24:page * 24], "total": len(selected), "page": page, "pages": pages, "available": available,
                "counts": {"all": len(items), **{s: counts[s] for s in STATUSES}},
                "tags": sorted({t for p in items for t in p["tags"]}), "platforms": PLATFORMS}

    def get(self, handler, session):
        filters = {k: values[0] for k, values in parse_qs(urlsplit(getattr(handler, "path", "")).query).items()}
        try:
            return {**self.listing(int(session["user_id"]), filters), "csrfToken": session["csrf_token"],
                    "user": {"id": session["user_id"], "displayName": session["display_name"]}}
        except ValueError as exc:
            raise ChallengeError("invalid_request", str(exc), 400) from exc

    def _metadata(self, problem):
        """Best effort local enrichment keeps tossing a bottle independent of OJ uptime."""
        regional = self.web.regionals.store
        pid = regional.aliases.get(problem["key"])
        if pid:
            item = regional.problems[pid]
            difficulty = regional.difficulties().get(pid, {})
            return item.get("name", ""), difficulty.get("rating"), []
        if problem["platform"] == "codeforces":
            try:
                cache = self.web.service.cf._load_any_cache() or {}
                for item in cache.get("result", {}).get("problems", []):
                    if str(item.get("contestId")) + str(item.get("index")) == problem["problemId"]:
                        return item.get("name", ""), item.get("rating"), item.get("tags", [])
            except (OSError, ValueError, TypeError):
                pass
        return "", None, []

    def post(self, session, action, payload):
        user = int(session["user_id"])
        if action == "problems":
            problem = normalize_problem(payload.get("problemId"), payload.get("platform", "auto"))
            title = _text(payload.get("title"), 160, "标题")
            note = _text(payload.get("note"), 500, "推荐语")
            raw_tags = payload.get("tags") or []
            if isinstance(raw_tags, str):
                raw_tags = re.split(r"[,，、\n]", raw_tags)
            if not isinstance(raw_tags, list) or len(raw_tags) > 10:
                raise ValueError("最多填写 10 个标签，用逗号分隔。")
            tags = list(dict.fromkeys(_text(t, 40, "标签") for t in raw_tags if str(t).strip()))
            rating = _integer(payload["rating"], 0, 4000, "参考难度") if payload.get("rating") not in (None, "") else None
            cached_title, cached_rating, cached_tags = self._metadata(problem)
            at = datetime.now(timezone.utc).isoformat()
            with self.connect() as db:
                db.execute("begin immediate")
                cursor = db.execute("""insert or ignore into pool_problems
                    (problem_key,platform,problem_id,url,title,rating,tags_json,note,author_id,created_at)
                    values (?,?,?,?,?,?,?,?,?,?)""", (problem["key"], problem["platform"], problem["problemId"], problem["url"],
                        title or cached_title or problem["problemId"], rating if rating is not None else cached_rating,
                        json.dumps(tags or cached_tags, ensure_ascii=False), note, user, at))
                created = cursor.rowcount == 1
                item = next(p for p in self._items(db, user) if p["key"] == problem["key"])
            return {"ok": True, "created": created, "item": item,
                    "message": "瓶子已漂进池子。" if created else "这道题已经在池子里了，已为你找到原瓶子。"}
        if action not in {"draw", "record", "practice"}:
            raise ChallengeError("not_found", "没有这个口胡池操作。", 404)
        if action == "practice":
            problem_id = _integer(payload.get("id"), 1, 2**63 - 1, "题目编号")
            with self.connect() as db:
                item = next((p for p in self._items(db, user) if p["id"] == problem_id), None)
            if item is None:
                raise ChallengeError("problem_not_found", "池子里没有这道题。", 404)
            if item["platform"] != "codeforces":
                raise ValueError("这道题请在原 OJ 练习，完成后可标记 AC。")
            from .webapp import _assistance_settings, _giveup_minutes
            _giveup_minutes(payload.get("giveupMinutes"))
            _assistance_settings(payload)
            match = re.fullmatch(r"(\d+)([A-Z][A-Z0-9]*)", item["problemId"])
            actor = self.web._actor(session)
            self.web.service.issue_specific_problem(actor.scope_id, int(match[1]), match[2])
            active = self.web.service.get_active_problem(actor.scope_id)
            self.web._set_single_challenge_control(session, active, payload)
            if item["status"] == "new":
                self.post(session, "record", {"id": item["id"], "status": "picked"})
            with self.connect() as db:
                db.execute("update pool_records set training_cf_id=? where user_id=? and problem_id=?",
                           (active.problem.cf_id, user, item["id"]))
            return {"ok": True, "item": item, "message": "题目已放到单题训练台。"}
        with self.connect() as db:
            # Selection and recording are atomic, including simultaneous requests from two tabs.
            db.execute("begin immediate")
            items = self._items(db, user)
            if action == "draw":
                filters = payload.get("filters") or {}
                if not isinstance(filters, dict):
                    raise ValueError("筛选条件格式不正确。")
                candidates = self._filter(items, user, {**filters, "status": "new"})
                if not candidates:
                    raise ChallengeError("pool_empty", "当前条件下没有新瓶子了。试试放宽筛选，或去「已捞待做」继续之前的题。", 409)
                item, status = secrets.choice(candidates), "picked"
            else:
                problem_id = _integer(payload.get("id"), 1, 2**63 - 1, "题目编号")
                status = str(payload.get("status") or "")
                if status not in STATUSES:
                    raise ValueError("题目状态不正确。")
                item = next((p for p in items if p["id"] == problem_id), None)
                if item is None:
                    raise ChallengeError("problem_not_found", "池子里没有这道题。", 404)
                if item["importedAc"]:
                    raise ChallengeError("already_accepted", "这道题已有站内通过或平台 AC 记录，会自动排除。", 409)
            at = datetime.now(timezone.utc).isoformat()
            drawn = status == "picked"
            first_draw = drawn and item["status"] != "picked"
            db.execute("""insert into pool_records(user_id,problem_id,status,drawn_at,ac_at,updated_at,draw_count)
                values (?,?,?,?,?,?,?) on conflict(user_id,problem_id) do update set
                status=excluded.status, drawn_at=case when excluded.drawn_at!='' then excluded.drawn_at else pool_records.drawn_at end,
                ac_at=case when pool_records.status='ac' and excluded.status='ac' then pool_records.ac_at else excluded.ac_at end,
                updated_at=excluded.updated_at, draw_count=pool_records.draw_count+excluded.draw_count""",
                (user, item["id"], status, at if first_draw else "", at if status == "ac" else "", at, int(first_draw)))
            item = next(p for p in self._items(db, user) if p["id"] == item["id"])
        return {"ok": True, "item": item}

    def record_giveup(self, session, cf_id):
        with self.connect() as db:
            db.execute("""update pool_records set status='skipped', updated_at=?
                where user_id=? and status='picked' and (problem_id in
                (select id from pool_problems where problem_key=?) or training_cf_id=?)""",
                (datetime.now(timezone.utc).isoformat(), int(session["user_id"]), "codeforces:" + cf_id, cf_id))
