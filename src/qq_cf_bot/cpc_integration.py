"""Optional OJ Wall connection; remote snapshots never mutate oral history."""
from __future__ import annotations
import json
import os
import threading
import time
from urllib.error import HTTPError
from .cpc_common import connect, uid, fetch, validate_snapshot


class WallConnection:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.wake = threading.Event()
        with self.db() as db:
            self.authority = uid(db, 'authority', 'self')
        if self.configured:
            threading.Thread(target=self.worker, daemon=True, name='cpc-wall').start()

    @property
    def configured(self):
        return bool(os.environ.get('CPC_OJWALL_URL') and os.environ.get('CPC_OJWALL_AUTHORITY_ID'))

    def db(self):
        db = connect(self.path)
        db.executescript('''create table if not exists cpc_wall_links(
          user_id integer primary key,token text not null,body text not null,
          checked integer not null,error text not null default '');''')
        return db

    def sync(self, user, token=None):
        if not self.configured:
            raise ValueError('管理员尚未配置 OJ Wall 联动地址和信源 ID')
        with self.lock:
            with self.db() as db:
                row = db.execute('select * from cpc_wall_links where user_id=?', (user,)).fetchone()
            supplied = token is not None
            token = str(token).strip() if supplied else (row['token'] if row else '')
            authority = os.environ['CPC_OJWALL_AUTHORITY_ID']
            if not token.startswith(authority + '.') or len(token) > 200:
                raise ValueError('连接码不属于已配置的 OJ Wall')
            try:
                body = validate_snapshot(fetch(os.environ['CPC_OJWALL_URL'], '/api/integration/v1/me/progress/snapshot', token), authority)
                if not isinstance(body.get('problems'), dict) or body.get('record_count') != len(body['problems']):
                    raise ValueError('进度快照不完整')
                for pid, progress in body['problems'].items():
                    if not isinstance(pid, str) or not isinstance(progress, dict) or any(type(progress.get(k)) is not bool for k in ('personal','team','onsite','attempted')):
                        raise ValueError('进度格式错误')
                identity = body.get('identity')
                if (not isinstance(identity, dict)
                        or identity.get('status') not in {'unverified','pending','approved','rejected','revoked','superseded'}
                        or type(identity.get('verified_until')) not in {int,float}):
                    raise ValueError('身份状态缺失')
                with self.db() as db:
                    uid(db, 'subject', user)
                    db.execute('insert or replace into cpc_wall_links values (?,?,?,?,?)', (user,token,json.dumps(body),int(time.time()),''))
            except HTTPError as exc:
                if not supplied and exc.code in {401,403}:
                    self.disconnect(user)
                raise ValueError('连接码已失效或服务暂不可用，请在 OJ Wall 检查后重新连接') from None
        return {'ok': True}

    def disconnect(self, user):
        with self.lock, self.db() as db:
            db.execute('delete from cpc_wall_links where user_id=?', (user,))
        return {'ok': True}

    def state(self, user):
        with self.db() as db:
            row = db.execute('select body,checked,error from cpc_wall_links where user_id=?', (user,)).fetchone()
        if not row:
            return {'configured': self.configured, 'connected': False}
        return {'configured': self.configured, 'connected': True, 'lastSync': row['checked'],
                'stale': row['checked'] + 86400 < time.time(), 'error': row['error'],
                'identity': json.loads(row['body']).get('identity', {})}

    def merge(self, user, progress):
        with self.db() as db:
            row = db.execute('select body,checked from cpc_wall_links where user_id=?', (user,)).fetchone()
        if not row or row['checked'] + 86400 < time.time():
            return
        body = json.loads(row['body'])
        identity = body.get('identity', {})
        onsite_valid = identity.get('status') == 'approved' and identity.get('verified_until', 0) > time.time()
        for pid, external in body['problems'].items():
            local = progress.get(pid)
            if local is None:
                continue  # Entire raw snapshot is retained for future catalog versions.
            local['code'] |= external['personal'] or external['team']
            local['attempted'] |= external['attempted']
            local['onsite'] = external['onsite'] and onsite_valid
            local['wallPersonal'] = external['personal']
            local['wallTeam'] = external['team']
            local['onsiteEvidence'] = external.get('evidence', []) if local['onsite'] else []

    def worker(self):
        while True:
            with self.db() as db:
                users = [r[0] for r in db.execute('select user_id from cpc_wall_links')]
            for user in users:
                try:
                    self.sync(user)
                except Exception:
                    with self.db() as db:
                        db.execute('update cpc_wall_links set error=? where user_id=?', ('同步失败，保留上次成功结果',user))
            self.wake.wait(300)
            self.wake.clear()
