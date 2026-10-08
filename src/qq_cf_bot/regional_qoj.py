"""User-authorized QOJ browser bridge; tokens can only upload one bound QOJ identity."""
import hashlib
import re
import secrets
import time

from .core import ChallengeError
from .regional import normalize_record, now


def qoj_verdict(value):
    text=value.strip()
    marked=text.endswith(('✓','✔','✅'))
    cleaned=text.rstrip('✓✔✅').strip().upper()
    if not cleaned or cleaned in {'NAN','INF','+INF','ACCESS DENIED','CENTRAL FAILURE'}:
        raise ValueError('QOJ 判定结果无效。')
    if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',cleaned):
        if float(cleaned)>1000000:
            raise ValueError('QOJ 分数无效。')
        return 'AC' if marked else 'WA'
    return {'COMPILE ERROR':'CE','JUDGED, WAITING':'WAITING','WAITING REJUDGE':'WAITING','JUDGED, JUDGING':'JUDGING'}.get(cleaned,cleaned)


class QojPlugin:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('''create table if not exists regional_qoj_accounts(
                user_id integer, uid text, token_hash text not null, created_at text not null,
                last_sync text, primary key(user_id,uid))''')
            db.execute('create unique index if not exists regional_qoj_token on regional_qoj_accounts(token_hash)')

    def accounts(self, user):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute(
                'select uid,created_at,last_sync from regional_qoj_accounts where user_id=? order by uid', (user,))]

    def authorize(self, user, uid):
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', uid):
            raise ValueError('无法识别 QOJ 账号，请从已登录 QOJ 的插件发起连接。')
        token = secrets.token_urlsafe(40)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.store.connect() as db:
            if db.execute('select count(*) from regional_qoj_accounts where user_id=?', (user,)).fetchone()[0] >= 12 and not db.execute('select 1 from regional_qoj_accounts where user_id=? and uid=?', (user,uid)).fetchone():
                raise ValueError('最多连接 12 个个人或团队账号。')
            db.execute('insert into regional_qoj_accounts values (?,?,?,?,null) on conflict(user_id,uid) do update set token_hash=excluded.token_hash,created_at=excluded.created_at',
                       (user,uid,digest,now()))
        return {'token': token, 'uid': uid}

    def revoke(self, user, uid):
        with self.store.connect() as db:
            db.execute('delete from regional_qoj_accounts where user_id=? and uid=?', (user,uid))
        return {'ok': True}

    def upload(self, authorization, payload):
        if not authorization.startswith('Bearer ') or len(authorization) > 150:
            raise ChallengeError('unauthorized','请先通过插件连接并授权本站。',401)
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        uid = payload.get('uid')
        rows = payload.get('records')
        if not isinstance(rows,list) or not 1 <= len(rows) <= 100:
            raise ValueError('每批应为 1–100 条提交记录。')
        normalized = []
        for row in rows:
            if not isinstance(row,dict) or row.get('submitter') != uid:
                raise ValueError('提交者与授权的个人 / 团队账号不一致。')
            if not re.fullmatch(r'[1-9][0-9]{0,14}', str(row.get('id',''))) or not re.fullmatch(r'[1-9][0-9]{0,9}',str(row.get('problemId',''))):
                raise ValueError('QOJ 提交编号或题号不正确。')
            if not isinstance(row.get('submittedAt'),int) or isinstance(row['submittedAt'],bool) or not 0 <= row['submittedAt'] <= time.time()+86400:
                raise ValueError('QOJ 提交时间不正确。')
            raw_verdict=row.get('verdict')
            if not isinstance(raw_verdict,str) or not raw_verdict.strip() or len(raw_verdict)>80:
                raise ValueError('QOJ 判定结果不正确。')
            # Scores alone are not evidence of AC; only explicit Accepted / AC qualifies.
            normalized.append(normalize_record({'platform':'qoj','problem_id':row['problemId'],
                'submission_id':row['id'],'submitted_at':row['submittedAt'],'handle':uid,'verdict':qoj_verdict(raw_verdict)}))
        with self.store.connect() as db:
            db.execute('begin immediate')
            account=db.execute('select user_id,uid from regional_qoj_accounts where token_hash=? and uid=?',(digest,uid)).fetchone()
            if not account:
                raise ChallengeError('unauthorized','授权已失效，请重新连接。',401)
            for r in normalized:
                db.execute('insert into regional_evidence values (?,?,?,?,?,?,?,?) on conflict(user_id,origin,fingerprint) do update set verdict=excluded.verdict,submitted_at=excluded.submitted_at,problem_key=excluded.problem_key',
                    (account['user_id'],'qoj-plugin:'+uid,r['fingerprint'],r['key'],r['verdict'],r['time'],'qoj',uid))
            db.execute('update regional_qoj_accounts set last_sync=? where user_id=? and uid=?',(now(),account['user_id'],uid))
        return {'ok':True,'processed':len(normalized),'matched':sum(r['key'] in self.store.aliases for r in normalized)}
