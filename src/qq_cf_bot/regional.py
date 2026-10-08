"""Persistent, untimed regional practice. All remote work is outside wall reads."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .core import ChallengeActor, ChallengeError, _needs_statement_translation
from .models import CFProblem, CodeSubmission, ProblemStatement
from .storage import _statement_from_json, _statement_to_json

LOGGER = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


def problem_key(platform, value):
    platform = str(platform).strip().lower()
    platform = {"cf": "codeforces", "gym": "codeforces", "vj": "vjudge", "lg": "luogu", "nc": "nowcoder"}.get(platform, platform)
    value = str(value).strip()
    if value.startswith("https://") or value.startswith("http://"):
        parsed = urlsplit(value)
        host, path = parsed.hostname or "", parsed.path
        if host in {"codeforces.com", "www.codeforces.com"}:
            match = re.search(r"/(?:gym|contest)/(\d+)/problem/([A-Za-z0-9]+)|/problemset/problem/(\d+)/([A-Za-z0-9]+)", path)
            if match:
                value = ''.join(x for x in match.groups() if x)
                platform = "codeforces"
        elif host == "qoj.ac" and re.fullmatch(r"/problem/\d+/?", path):
            platform, value = "qoj", path.strip('/').split('/')[-1]
        elif host.endswith("luogu.com.cn") and path.startswith('/problem/'):
            platform, value = "luogu", path.split('/')[-1]
        elif host == "vjudge.net" and path.startswith('/problem/'):
            platform, value = "vjudge", path.split('/')[-1]
    if platform == "vjudge":
        if value.startswith('洛谷-'):
            return problem_key('luogu',value[len('洛谷-'):])
        match = re.fullmatch(r"(CodeForces|Gym|QOJ|Luogu|HDU|POJ|ZOJ|NowCoder)[-_:](.+)", value, re.I)
        if match:
            return problem_key(match[1], match[2])
    if platform == "luogu" and re.fullmatch(r"CF\d+[A-Za-z][A-Za-z0-9]*", value, re.I):
        return problem_key("codeforces", value[2:])
    if platform == "codeforces":
        value = re.sub(r"^(?:CF|Codeforces)[-_:]?", "", value, flags=re.I).replace('-', '').upper()
        if not re.fullmatch(r"[1-9]\d{0,6}[A-Z][A-Z0-9]*", value):
            raise ValueError("Codeforces 题号格式应为 105657A。")
    else:
        if not re.fullmatch(r"[A-Za-z0-9_:-]{1,100}", value):
            raise ValueError("题号格式不正确，请填写平台原题号或题目链接。")
        value = value.upper()
    if not re.fullmatch(r"[a-z][a-z0-9]{1,24}", platform):
        raise ValueError("平台名称不正确。")
    return f"{platform}:{value}"


def verdict(value):
    value = str(value or "UNKNOWN").strip().upper().replace(' ', '_')
    return {"OK": "AC", "ACCEPTED": "AC", "答案正确": "AC", "WRONG_ANSWER": "WA", "TIME_LIMIT_EXCEEDED": "TLE", "COMPILATION_ERROR": "CE", "RUNTIME_ERROR": "RE", "MEMORY_LIMIT_EXCEEDED": "MLE"}.get(value, value[:80])


class RegionalStore:
    def __init__(self, path, catalog_path=None):
        self.path = Path(path)
        catalog_path = catalog_path or Path(__file__).with_name('catalog') / 'regionals.json'
        self.catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
        self.contests = self.catalog['contests']
        self.problems = {p['id']: {**p, 'contest': c['id']} for c in self.contests for p in c['problems']}
        ratings_path = Path(__file__).with_name('catalog') / 'regional_ratings.json'
        self.rating_release = json.loads(ratings_path.read_text(encoding='utf-8'))
        self.aliases = {}
        for p in self.problems.values():
            for alias in p.get('aliases', []):
                if alias in self.aliases and self.aliases[alias] != p['id']:
                    raise ValueError(f"目录存在重复题号映射：{alias}")
                self.aliases[alias] = p['id']
        with self.connect() as db:
            db.executescript('''
            create table if not exists regional_drafts(
              user_id integer, problem_id text, body text not null, version integer not null,
              updated_at text not null, primary key(user_id,problem_id));
            create table if not exists regional_attempts(
              id integer primary key, user_id integer not null, problem_id text not null,
              request_id text not null, kind text not null, body text not null,
              accepted integer not null, verdict text not null, reason text not null, created_at text not null,
              unique(user_id,request_id));
            create index if not exists regional_attempt_user on regional_attempts(user_id,problem_id);
            create table if not exists regional_evidence(
              user_id integer, origin text, fingerprint text, problem_key text not null,
              verdict text not null, submitted_at integer, platform text not null, handle text not null,
              primary key(user_id,origin,fingerprint));
            create index if not exists regional_evidence_user on regional_evidence(user_id,problem_key);
            create table if not exists regional_bindings(
              id integer primary key, user_id integer not null, platform text not null, handle text not null,
              status text not null default 'idle', message text not null default '',
              last_sync integer not null default 0, cursor integer not null default 1,
              complete integer not null default 0, enabled integer not null default 1,
              unique(user_id,platform,handle));
            create table if not exists regional_imports(
              id text primary key,user_id integer not null, records text not null, summary text not null,
              status text not null, created_at text not null);
            create table if not exists regional_positions(user_id integer primary key,problem_id text not null);
            create table if not exists regional_statements(problem_id text primary key,body text not null,updated_at text not null);
            create table if not exists regional_difficulty(problem_id text primary key,rating integer not null,source text not null,updated_at text not null);
            ''')
            db.execute("update regional_bindings set status='failed',message='服务重启，请重新同步' where status in ('queued','running')")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('pragma busy_timeout=30000')
        return db

    def problem(self, pid):
        if pid not in self.problems:
            raise ChallengeError('problem_not_found', '没有收录这道区域赛题目。', 404)
        return self.problems[pid]

    def difficulties(self):
        # Published offline data is authoritative; ignore legacy model-only DB rows.
        return {pid: value for pid, value in self.rating_release['problems'].items() if pid in self.problems}

    def rating_metadata(self):
        return {key: self.rating_release[key] for key in ('method', 'source_revision', 'scale', 'contests')}

    def progress(self, user):
        result = {pid: {'oral': False, 'code': False, 'attempted': False, 'oralAttempted': False, 'draft': False, 'verdict': ''} for pid in self.problems}
        with self.connect() as db:
            for r in db.execute('select problem_id,body from regional_drafts where user_id=?', (user,)):
                if r['problem_id'] in result:
                    result[r['problem_id']]['draft'] = bool(r['body'].strip())
            for r in db.execute('select * from regional_attempts where user_id=? order by id', (user,)):
                p = result.get(r['problem_id'])
                if p is None:
                    continue
                if r['kind'] == 'oral':
                    p['oralAttempted'] = True
                    p['oral'] |= bool(r['accepted'])
                else:
                    p['attempted'] = True
                    p['code'] |= r['verdict'] == 'AC'
                    p['verdict'] = r['verdict']
            for r in db.execute('select * from regional_evidence where user_id=? order by coalesce(submitted_at,0)', (user,)):
                p = result.get(self.aliases.get(r['problem_key']))
                if p is not None:
                    p['attempted'] = True
                    p['code'] |= r['verdict'] == 'AC'
                    p['verdict'] = r['verdict']
            # Existing Web training belongs to the same authenticated user, including VP.
            for table, kind in [('submissions','oral'), ('code_submissions','code')]:
                if kind == 'oral':
                    rows = db.execute('select cf_id,accepted from submissions where group_id=? and user_id=?', ('-1',user))
                else:
                    rows = db.execute('select cf_id,accepted,verdict from code_submissions where group_id=? and user_id=?', ('-1',user))
                for r in rows:
                    p = result.get(self.aliases.get('codeforces:' + r['cf_id']))
                    if p is None:
                        continue
                    if kind == 'oral':
                        p['oralAttempted'] = True
                        p['oral'] |= bool(r['accepted'])
                    else:
                        p['attempted'] = True
                        p['code'] |= verdict(r['verdict']) == 'AC'
        return result

    def wall(self, user):
        with self.connect() as db:
            bindings = [dict(r) for r in db.execute('select * from regional_bindings where user_id=? and enabled=1 order by id', (user,))]
            batches = [dict(r) for r in db.execute("select id,summary,created_at from regional_imports where user_id=? and status='confirmed' order by created_at desc limit 20", (user,))]
            position = db.execute('select problem_id from regional_positions where user_id=?', (user,)).fetchone()
            ready = {r[0] for r in db.execute('select problem_id from regional_statements')}
        return {'contests': self.contests, 'progress': self.progress(user), 'bindings': bindings, 'imports': batches,
                'years': sorted({c['year'] for c in self.contests}, reverse=True), 'verifiedAt': self.catalog.get('verified_at'),
                'lastProblem': position[0] if position else None, 'ready': sorted(ready),
                'difficulty': self.difficulties(), 'ratingRelease': self.rating_metadata()}

    def detail(self, user, pid):
        p = self.problem(pid)
        with self.connect() as db:
            draft = db.execute('select * from regional_drafts where user_id=? and problem_id=?', (user,pid)).fetchone()
            attempts = [dict(r) for r in db.execute('select * from regional_attempts where user_id=? and problem_id=? order by id desc limit 30', (user,pid))]
            keys = p.get('aliases', [])
            evidence = [dict(r) for r in db.execute('select * from regional_evidence where user_id=? and problem_key in (' + ','.join('?' for _ in keys) + ') order by coalesce(submitted_at,0) desc limit 30', (user,*keys))] if keys else []
            db.execute('insert into regional_positions values (?,?) on conflict(user_id) do update set problem_id=excluded.problem_id', (user,pid))
        return {'problem': p, 'draft': dict(draft) if draft else {'body':'','version':0}, 'attempts':attempts,'evidence':evidence}

    def save_draft(self, user, pid, body, version):
        self.problem(pid)
        if not isinstance(body,str) or len(body)>20000:
            raise ValueError('做法最多 20000 字。')
        with self.connect() as db:
            db.execute('begin immediate')
            r = db.execute('select version from regional_drafts where user_id=? and problem_id=?',(user,pid)).fetchone()
            current = r[0] if r else 0
            if current != int(version):
                raise ChallengeError('draft_conflict','另一处已更新草稿。你的文字仍保留在编辑器中，请复制后重新打开本题合并。',409)
            stamp = now()
            db.execute('insert into regional_drafts values (?,?,?,?,?) on conflict(user_id,problem_id) do update set body=excluded.body,version=excluded.version,updated_at=excluded.updated_at', (user,pid,body,current+1,stamp))
        return {'version':current+1,'updatedAt':stamp}

    def attempt(self,user,pid,request_id,kind,body,accepted,v,reason):
        with self.connect() as db:
            db.execute('insert into regional_attempts(user_id,problem_id,request_id,kind,body,accepted,verdict,reason,created_at) values (?,?,?,?,?,?,?,?,?)',(user,pid,request_id,kind,body,int(accepted),v,reason,now()))

    def cached_attempt(self,user,pid,request_id,kind,body):
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request_id):
            raise ValueError('缺少提交请求 ID，请刷新页面。')
        with self.connect() as db:
            r = db.execute('select * from regional_attempts where user_id=? and request_id=?',(user,request_id)).fetchone()
        if r and (r['problem_id']!=pid or r['kind']!=kind or r['body']!=body):
            raise ChallengeError('request_conflict','提交 ID 已用于另一份做法，请重新提交。',409)
        return dict(r) if r else None

    def add_evidence(self,user,origin,records):
        with self.connect() as db:
            for r in records:
                db.execute('insert into regional_evidence values (?,?,?,?,?,?,?,?) on conflict(user_id,origin,fingerprint) do update set verdict=excluded.verdict,submitted_at=excluded.submitted_at', (user,origin,r['fingerprint'],r['key'],r['verdict'],r['time'],r['platform'],r['handle']))

    def preview_import(self,user,text):
        if not isinstance(text,str) or len(text)>220000:
            raise ValueError('文件过大，请按不超过 2000 条记录拆分导入。')
        text = text.lstrip('\ufeff').strip()
        if text.startswith(('[','{')):
            rows = json.loads(text)
            if isinstance(rows,dict):
                rows = rows.get('submissions', rows.get('records'))
        else:
            rows = list(csv.DictReader(io.StringIO(text)))
        if not isinstance(rows,list) or not rows or len(rows)>2000:
            raise ValueError('请提供 1–2000 条 CSV 或 JSON 提交记录。')
        records, errors, unknown, seen = [],[],[],set()
        duplicate = 0
        with self.connect() as db:
            existing = {r[0] for r in db.execute('select fingerprint from regional_evidence where user_id=?',(user,))}
        for i,r in enumerate(rows,1):
            try:
                if not isinstance(r,dict):
                    raise ValueError('每条记录应为对象。')
                item = normalize_record(r)
                if item['fingerprint'] in seen or item['fingerprint'] in existing:
                    duplicate += 1
                if item['fingerprint'] not in seen:
                    records.append(item)
                seen.add(item['fingerprint'])
                if item['key'] not in self.aliases:
                    unknown.append({'row':i,'key':item['key']})
            except (ValueError,TypeError,KeyError) as exc:
                errors.append({'row':i,'message':str(exc)})
        summary = {'total':len(rows),'valid':len(records),'matched':sum(r['key'] in self.aliases for r in records),'duplicates':duplicate,'unmatched':unknown[:30],'unmatchedCount':len(unknown),'errors':errors[:30],'invalidCount':len(errors)}
        token = secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute("delete from regional_imports where user_id=? and status='preview'",(user,))
            db.execute('insert into regional_imports values (?,?,?,?,?,?)',(token,user,json.dumps(records),json.dumps(summary,ensure_ascii=False),'preview',now()))
        return {'token':token,**summary}

    def confirm_import(self,user,token):
        with self.connect() as db:
            db.execute('begin immediate')
            row = db.execute('select * from regional_imports where user_id=? and id=?',(user,token)).fetchone()
            if not row or row['status']=='revoked':
                raise ValueError('导入预览已失效，请重新预览。')
            for r in json.loads(row['records']):
                db.execute('insert or ignore into regional_evidence values (?,?,?,?,?,?,?,?)',(user,'import:'+token,r['fingerprint'],r['key'],r['verdict'],r['time'],r['platform'],r['handle']))
            db.execute("update regional_imports set status='confirmed' where id=?",(token,))
        return {'ok':True}

    def revoke_import(self,user,token):
        with self.connect() as db:
            db.execute("update regional_imports set status='revoked' where id=? and user_id=?",(token,user))
            db.execute('delete from regional_evidence where user_id=? and origin=?',(user,'import:'+token))
        return {'ok':True}


def normalize_record(r):
    platform = str(r.get('platform') or '').strip().lower()
    key = problem_key(platform, r.get('problem_id') or r.get('problemId') or '')
    raw_time = r.get('submitted_at') if r.get('submitted_at') is not None else r.get('submittedAt')
    if raw_time=='':
        raw_time=None
    stamp = None
    if raw_time is not None:
        try:
            stamp = int(raw_time)
            if stamp>10_000_000_000:
                stamp //= 1000
        except (ValueError,TypeError):
            dt = datetime.fromisoformat(str(raw_time).replace('Z','+00:00'))
            if dt.tzinfo is None:
                raise ValueError('时间需要时区，或使用 Unix 秒时间戳。')
            stamp = int(dt.timestamp())
        if stamp<0:
            raise ValueError('时间戳不能为负数。')
    v = verdict(r.get('verdict'))
    if v=='UNKNOWN':
        raise ValueError('缺少 verdict，不能推测是否 AC。')
    handle = str(r.get('handle') or '')[:100]
    remote = str(r.get('submission_id') or r.get('remote_id') or r.get('remoteId') or '')[:100]
    # An actual run keeps its identity when TESTING later becomes AC.
    identity = [platform,handle,remote] if remote else [platform,handle,key,stamp,v]
    fingerprint = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()
    return {'key':key,'verdict':v,'time':stamp,'platform':platform,'handle':handle,'fingerprint':fingerprint}


class RegionalApplication:
    def __init__(self, web):
        from .regional_sync import SubmissionSync
        self.web = web
        self.service = web.service
        self.store = RegionalStore(self.service.store.db_path)
        self.sync = SubmissionSync(self.store, self.service.cf.base_urls)
        self.prepare_lock = threading.Lock()
        from .regional_qoj import QojPlugin
        self.qoj = QojPlugin(self.store)

    def state(self,session):
        data = self.store.wall(int(session['user_id']))
        data['qojAccounts'] = self.qoj.accounts(int(session['user_id']))
        for binding in data['bindings']:
            interval=900 if binding['complete'] else 120
            if binding['status']=='idle' and time.time()-binding['last_sync']>interval:
                self.sync.enqueue(int(session['user_id']),binding['id'])
                binding['status']='queued'
        data.update({'csrfToken':session['csrf_token'],'user':{'id':session['user_id'],'displayName':session['display_name']},'oralJudge':self.service.judge.configured,'codeJudge':self.service.code_judge_available})
        return data

    def post(self,session,action,payload):
        user = int(session['user_id'])
        pid = str(payload.get('problemId') or '')
        if action == 'qoj-authorize':
            return self.qoj.authorize(user,payload.get('uid'))
        if action == 'qoj-revoke':
            return self.qoj.revoke(user,str(payload.get('uid') or ''))
        if action == 'bind':
            return self.sync.bind(user,str(payload.get('platform') or ''),payload.get('handle') or '')
        if action == 'sync':
            return self.sync.enqueue(user,int(payload.get('bindingId') or 0))
        if action == 'unbind':
            return self.sync.unbind(user,int(payload.get('bindingId') or 0))
        if action == 'import-preview':
            return self.store.preview_import(user,payload.get('text'))
        if action == 'import-confirm':
            return self.store.confirm_import(user,str(payload.get('token') or ''))
        if action == 'import-revoke':
            return self.store.revoke_import(user,str(payload.get('token') or ''))
        if action == 'draft':
            return self.store.save_draft(user,pid,payload.get('body'),payload.get('version'))
        if action in {'difficulty', 'difficulty-year'}:
            raise ChallengeError('rating_read_only', '评级由离线校准后统一发布，网站不提供刷新。', 403)
        if action == 'open':
            detail = self.store.detail(user,pid)
            try:
                p,statement = self.prepare(pid)
                detail['statement'] = self.statement_json(statement)
                detail['title'] = statement.title
            except Exception as exc:
                LOGGER.warning('regional statement unavailable %s: %s',pid,type(exc).__name__)
                detail['statement'] = None
                detail['statementError'] = '中文题面尚未就绪：来源访问受限或翻译未完成。可以重试，已有草稿会保留。'
            return detail
        if action in {'oral','code'}:
            self.store.problem(pid)
            body = payload.get('solution') if action=='oral' else payload.get('source')
            limit = 20000 if action=='oral' else 100000
            if not isinstance(body,str) or not body.strip() or len(body)>limit:
                raise ValueError(f'提交内容不能为空且最多 {limit} 字。')
            request_id = str(payload.get('requestId') or '')
            cached = self.store.cached_attempt(user,pid,request_id,action,body)
            if cached:
                return cached
            if action=='oral' and not self.service.judge.configured:
                raise ChallengeError('judge_unavailable','口胡审核服务尚未配置；草稿仍可保存。',503)
            p,statement = self.prepare(pid)
            # Each request activates its explicit problem in a separate, untimed scope.
            # The web user lock serializes regional open/submit with existing training.
            actor = ChallengeActor(-3_000_000_000_000-user,-1,user,str(session['display_name']))
            self.service.store.set_active_problem(actor.scope_id,p,statement,[],ranked=False)
            if action=='oral':
                if p.contest_id:
                    outcome = self.service.submit_solution(actor,body,settle=False)
                    accepted,reason=outcome.accepted,outcome.reason
                else:
                    history=[{'raw_text':r['body'],'accepted':bool(r['accepted']),'reason':r['reason']} for r in self.store.detail(user,pid)['attempts'] if r['kind']=='oral']
                    context=''
                    generator=self.service.solution_bank.solution_generator
                    if generator and generator.configured:
                        context=generator.generate(p,statement).content
                    judged=self.service.judge.judge(p,statement,body,solution_context=context,submission_history=history)
                    if judged.accepted and context:
                        judged=self.service.judge.second_judge(p,statement,body,judged,solution_context=context,submission_history=history)
                    accepted,reason=judged.accepted,judged.reason
                v='ORAL_ACCEPTED' if accepted else 'ORAL_REVIEW'
            else:
                if not p.contest_id:
                    raise ValueError('此题请前往原平台提交代码，再同步或导入记录。')
                language=str(payload.get('language') or 'cpp')
                if language not in {'cpp','c','java','py','python'}:
                    raise ValueError('不支持这种语言。')
                outcome=self.service.submit_code(actor,CodeSubmission(language,body),expected_cf_id=p.cf_id,settle=False)
                v=verdict(outcome.remote_result.verdict) if outcome.remote_result else 'UNKNOWN'
                accepted,reason=outcome.accepted,outcome.reason
            self.store.attempt(user,pid,request_id,action,body,accepted,v,reason)
            return {'accepted':accepted,'verdict':v,'reason':reason}
        raise ChallengeError('not_found','没有这个区域赛操作。',404)

    def prepare(self,pid):
        item=self.store.problem(pid)
        cf_id=item.get('cf_contest_id')
        p=CFProblem(int(cf_id or 0),item['index'] if cf_id else 'QOJ'+str(item.get('qoj_id') or ''),item['name'],0,(),bool(cf_id))
        with self.store.connect() as db:
            cached=db.execute('select body from regional_statements where problem_id=?',(pid,)).fetchone()
        if cached:
            return p,_statement_from_json(cached[0])
        if not self.prepare_lock.acquire(blocking=False):
            raise ChallengeError('statement_busy','另一道中文题面正在准备，请稍后重试。',409)
        try:
            if item.get('qoj_id'):
                try:
                    statement=self.qoj_statement(item['qoj_id'])
                except Exception:
                    if not cf_id:
                        raise
                    statement=self.service.fetch_statement(p)
                statement=self.service._translate_and_cache_if_needed(p,statement,source='regional')
            elif cf_id:
                statement=self.service.fetch_statement(p)
            else:
                raise ChallengeError('statement_unavailable','此题的原平台映射尚待补齐。',503)
            # Existing random training deliberately allows English fallback; this mode does not.
            if not statement.description.strip() or not re.search(r'[\u4e00-\u9fff]',statement.description) or _needs_statement_translation(statement):
                raise ChallengeError('chinese_statement_required','中文题面尚未准备完成。请配置翻译服务后重试。',503)
            for section in (statement.input_format,statement.output_format,statement.hint):
                if re.search(r'[A-Za-z]{3,}',section) and not re.search(r'[\u4e00-\u9fff]',section):
                    # Formula-only sections are handled by the common language detector.
                    from .core import _visible_statement_text
                    if len(re.findall(r'[A-Za-z]{3,}',_visible_statement_text(section)))>=3:
                        raise ChallengeError('chinese_statement_required','输入输出说明仍待翻译。',503)
            with self.store.connect() as db:
                db.execute('insert or replace into regional_statements values (?,?,?)',(pid,json.dumps(_statement_to_json(statement),ensure_ascii=False),now()))
            return p,statement
        finally:
            self.prepare_lock.release()

    @staticmethod
    def qoj_statement(qid):
        from .regional_sync import fetch
        from html.parser import HTMLParser
        class ContentParser(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=False)
                self.depth=0
                self.parts=[]
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if self.depth:
                    self.parts.append(self.get_starttag_text())
                    if tag not in {'br','hr','img','input','meta','link','source','wbr'}:
                        self.depth+=1
                elif values.get('id') in {'problem-statement','problem-content'} or (tag=='article' and 'uoj-article' in values.get('class','')):
                    self.depth=1
            def handle_endtag(self,tag):
                if self.depth:
                    self.depth-=1
                    if self.depth:
                        self.parts.append('</'+tag+'>')
            def handle_data(self,data):
                if self.depth:
                    self.parts.append(data)
            def handle_entityref(self,name):
                self.handle_data('&'+name+';')
            def handle_charref(self,name):
                self.handle_data('&#'+name+';')
        url=f'https://qoj.ac/problem/{int(qid)}/statement/zh_cn'
        try:
            body=fetch(url,False)
        except Exception:
            url=f'https://qoj.ac/problem/{int(qid)}'
            body=fetch(url,False)
        parser=ContentParser()
        parser.feed(body)
        content=''.join(parser.parts)
        background=''
        if not content.strip() or '<iframe' in content.lower():
            # The PDF URL is fixed to this problem; never fetch arbitrary embedded URLs.
            if not re.search(r'<iframe\b[^>]*\bsrc=["\'][^"\']*download\.php\?',body,re.I):
                raise RuntimeError('QOJ statement unavailable')
            from pypdf import PdfReader
            from html import escape
            pdf_url=f'https://qoj.ac/download.php?type=statement&id={int(qid)}'
            pdf=fetch(pdf_url,False,binary=True)
            reader=PdfReader(io.BytesIO(pdf))
            if len(reader.pages)>30:
                raise RuntimeError('Unexpected full contest booklet')
            text='\n\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
            if len(text.strip())<100:
                raise RuntimeError('Scanned PDF needs a verified text source')
            background='<p>题面由原平台单题 PDF 转换。公式排版请结合<a href="'+pdf_url+'">原始 PDF</a>核对。</p>'
            content='<pre>'+escape(text)+'</pre>'
        return ProblemStatement('QOJ'+str(qid),'区域赛题目',content,'','',[],background=background,source_url=url)

    @staticmethod
    def statement_json(s):
        from .webapp import _safe_statement_html
        return {'title':s.title,'description':_safe_statement_html(s.background+'\n'+s.description,s.source_url),
                'input':_safe_statement_html(s.input_format,s.source_url),'output':_safe_statement_html(s.output_format,s.source_url),
                'hint':_safe_statement_html(s.hint,s.source_url),'samples':[{'input':a,'output':b} for a,b in s.samples], 'sourceUrl':s.source_url}
