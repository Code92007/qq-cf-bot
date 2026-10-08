"""Public submission adapters, adapted from oj-submission-wall's approach.

A bounded historical page cursor survives restarts; failed fetches never move it.
"""
from __future__ import annotations
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from .codeforces import _fetch_json_from_codeforces_variants
from .regional import normalize_record


def fetch(url, as_json=True, *, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 RegionalPractice/1.0','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if '/login' in response.url:
            raise RuntimeError('平台要求登录，无法读取公开记录；可使用历史记录导入。')
        body = response.read(8_000_001)
        if len(body)>8_000_000:
            raise RuntimeError('平台响应过大。')
    if binary:
        return body
    return json.loads(body) if as_json else body.decode('utf-8',errors='replace')


def normalize_handle(platform, handle):
    handle = str(handle).strip()
    if platform == 'nowcoder':
        match = re.fullmatch(r'https://ac\.nowcoder\.com/acm/contest/profile/(\d+)/?',handle)
        handle = match[1] if match else handle
        pattern = r'[1-9]\d{0,19}'
    else:
        pattern = r'[A-Za-z0-9_.-]{2,64}'
    if platform not in {'codeforces','vjudge','nowcoder'} or not re.fullmatch(pattern,handle):
        raise ValueError('请选择支持的平台并填写有效账号；牛客使用个人 UID。QOJ / 洛谷记录可通过文件导入。')
    return handle


def fetch_page(platform, handle, page, cf_urls=None):
    """Return normalized records and whether this is the last page."""
    size = 100
    if platform == 'codeforces':
        query = urllib.parse.urlencode({'handle':handle,'from':(page-1)*size+1,'count':size})
        data = _fetch_json_from_codeforces_variants('/api/user.status?'+query,cf_urls,timeout_seconds=25)
        if data.get('status')!='OK' or not isinstance(data.get('result'),list):
            raise RuntimeError('Codeforces 公开记录接口返回异常。')
        items = data['result']
        records = []
        for r in items:
            p = r.get('problem') or {}
            cid = p.get('contestId') or r.get('contestId')
            if not cid or not p.get('index'):
                continue
            records.append(normalize_record({'platform':platform,'handle':handle,'problem_id':f"{cid}{p['index']}",'verdict':r.get('verdict') or 'TESTING','submitted_at':r.get('creationTimeSeconds'),'submission_id':r['id']}))
        return records,len(items)<size
    if platform == 'vjudge':
        query = urllib.parse.urlencode({'draw':1,'start':(page-1)*size,'length':size,'un':handle,'OJId':'All','probNum':'','res':'all','language':'','onlyFollowee':'false'})
        data = fetch('https://vjudge.net/status/data?'+query)
        if not isinstance(data,dict) or not isinstance(data.get('data'),list):
            raise RuntimeError('VJudge 公开提交接口返回异常。')
        items = data['data']
        records = [normalize_record({'platform':platform,'handle':handle,'problem_id':str(r['oj'])+'-'+str(r['probNum']),'verdict':'AC' if r.get('statusType')==0 else r.get('status') or 'TESTING','submitted_at':r.get('time'),'submission_id':r['runId']}) for r in items]
        return records,len(items)<size
    query = urllib.parse.urlencode({'pageSize':size,'page':page,'search':'','statusTypeFilter':-1,'languageCategoryFilter':-1,'orderType':'DESC'})
    body = fetch(f'https://ac.nowcoder.com/acm/contest/profile/{handle}/practice-coding?{query}',False)
    return parse_nowcoder(body,handle,page)


def parse_nowcoder(body,handle,page):
    if not re.search(r'practice-coding|提交时间|提交记录|答案正确',body):
        raise RuntimeError('牛客页面结构变化或访问受限，保留上次数据。')
    records=[]
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',body,re.I|re.S):
        text=html.unescape(re.sub(r'<[^>]+>',' ',row))
        date=re.search(r'(20\d\d[-/]\d\d[-/]\d\d)\s+(\d\d:\d\d(?::\d\d)?)',text)
        pid=re.search(r'/acm/problem/([0-9A-Za-z_-]+)',row)
        remote=re.search(r'(?:submissionId|submitId|id)=([0-9]+)',row)
        if not date or not pid:
            continue
        stamp=int(datetime.fromisoformat(date[1].replace('/','-')+'T'+date[2]).replace(tzinfo=timezone(timedelta(hours=8))).timestamp())
        v='AC' if re.search(r'答案正确|Accepted',text,re.I) else next((v for marker,v in [('答案错误','WA'),('运行超时','TLE'),('编译错误','CE'),('运行错误','RE'),('内存超限','MLE')] if marker in text),'UNKNOWN_RESULT')
        records.append(normalize_record({'platform':'nowcoder','handle':handle,'problem_id':pid[1],'verdict':v,'submitted_at':stamp,'submission_id':remote[1] if remote else ''}))
    pages=[int(p) for p in re.findall(r'(?:[?&]|&amp;)page=(\d+)',body)]
    if not records and re.search(r'<tr\b[^>]*>.*?20\d\d[-/]',body,re.S):
        raise RuntimeError('无法解析牛客历史记录，未推进游标。')
    pages += [int(p) for p in re.findall(r'data-page=["\'](\d+)',body)]
    if not records and not re.search(r'暂无(?:提交|数据|记录)|没有(?:提交|数据|记录)',body) and not re.search(r'<table\b',body,re.I):
        raise RuntimeError('牛客没有返回有效记录表，未推进游标。')
    return records,page>=max(pages or [page])


class SubmissionSync:
    def __init__(self,store,cf_urls):
        self.store,self.cf_urls=store,cf_urls
        self.guard=threading.Lock()
        self.remote_lock=threading.Lock()
        self.active=set()

    def bind(self,user,platform,handle):
        handle=normalize_handle(platform,handle)
        with self.store.connect() as db:
            count=db.execute('select count(*) from regional_bindings where user_id=? and enabled=1',(user,)).fetchone()[0]
            existing=db.execute('select enabled from regional_bindings where user_id=? and platform=? and handle=?',(user,platform,handle)).fetchone()
            if count>=8 and not (existing and existing[0]):
                raise ValueError('最多绑定 8 个公开账号，请先解绑不用的账号。')
            db.execute('insert into regional_bindings(user_id,platform,handle) values (?,?,?) on conflict(user_id,platform,handle) do update set enabled=1',(user,platform,handle))
            bid=db.execute('select id from regional_bindings where user_id=? and platform=? and handle=?',(user,platform,handle)).fetchone()[0]
        return self.enqueue(user,bid)

    def enqueue(self,user,bid):
        with self.guard:
            with self.store.connect() as db:
                row=db.execute('select * from regional_bindings where id=? and user_id=? and enabled=1',(bid,user)).fetchone()
                if not row:
                    raise ValueError('绑定不存在。')
                if bid in self.active:
                    return {'ok':True,'status':row['status']}
                if int(time.time())-row['last_sync']<120:
                    return {'ok':True,'status':'idle','message':'刚刚同步过，请稍后重试。'}
                db.execute("update regional_bindings set status='queued',message='' where id=?",(bid,))
            self.active.add(bid)
            threading.Thread(target=self._run,args=(dict(row),),daemon=True,name='regional-sync').start()
        return {'ok':True,'status':'queued'}

    def _run(self,binding):
        bid,user=binding['id'],binding['user_id']
        started=int(time.time())
        try:
            with self.remote_lock:
                self._update(bid,status='running',message='正在同步公开记录')
                # Re-read newest pages each run, including a two-hour overlap.
                floor=max(0,binding['last_sync']-7200)
                page=1
                records=[]
                end=False
                while page<=10:
                    batch,end=fetch_page(binding['platform'],binding['handle'],page,self.cf_urls)
                    records.extend(batch)
                    if end or (floor and batch and min(r['time'] or 0 for r in batch)<floor):
                        break
                    page+=1
                    time.sleep(2)
                if page>10 and binding['last_sync']:
                    raise RuntimeError('本次新记录超过分页窗口，请稍后重试或导入历史。')
                cursor=binding['cursor']
                complete=bool(binding['complete'])
                if not complete:
                    if cursor==1:
                        cursor=min(page,10)+1
                        complete=end
                    else:
                        for _ in range(5):
                            batch,end=fetch_page(binding['platform'],binding['handle'],cursor,self.cf_urls)
                            records.extend(batch)
                            cursor+=1
                            if end:
                                complete=True
                                break
                            time.sleep(2)
                # Transaction includes both evidence and cursor; no half-updated success.
                with self.store.connect() as db:
                    owned=db.execute('select enabled from regional_bindings where id=?',(bid,)).fetchone()
                    if not owned or not owned[0]:
                        return
                    for r in records:
                        db.execute('insert into regional_evidence values (?,?,?,?,?,?,?,?) on conflict(user_id,origin,fingerprint) do update set verdict=excluded.verdict,submitted_at=excluded.submitted_at',(user,'binding:'+str(bid),r['fingerprint'],r['key'],r['verdict'],r['time'],r['platform'],r['handle']))
                    db.execute("update regional_bindings set cursor=?,complete=?,last_sync=?,status='idle',message=? where id=?",(cursor,int(complete),started,'历史回填完成' if complete else '已同步近期记录，历史尚未回填完；再次同步继续',bid))
        except Exception:
            message='公开记录同步失败，已有进度已保留；可重试或导入记录。'
            if binding['platform']=='vjudge':
                try:
                    solved=fetch('https://vjudge.net/user/solveDetail2/'+urllib.parse.quote(binding['handle']))
                    if not isinstance(solved,list):
                        raise RuntimeError('Invalid solved summary')
                    records=[]
                    for item in solved:
                        if not isinstance(item,list) or len(item)<3 or not item[2]:
                            continue
                        records.append(normalize_record({'platform':'vjudge','handle':binding['handle'],'problem_id':str(item[0])+'-'+str(item[1]),'verdict':'AC','submitted_at':item[2],'submission_id':'solved:'+str(item[0])+'-'+str(item[1])}))
                    with self.store.connect() as db:
                        owned=db.execute('select enabled from regional_bindings where id=?',(bid,)).fetchone()
                        if owned and owned[0]:
                            self.store.add_evidence(user,'binding:'+str(bid),records)
                            message='已读取 AC 汇总；完整提交历史访问失败，未标记历史回填完成。'
                except Exception:
                    pass
            self._update(bid,status='failed',message=message)
        finally:
            with self.guard:
                self.active.discard(bid)

    def _update(self,bid,status,message):
        with self.store.connect() as db:
            db.execute('update regional_bindings set status=?,message=? where id=?',(status,message,bid))

    def unbind(self,user,bid):
        with self.store.connect() as db:
            db.execute('update regional_bindings set enabled=0 where id=? and user_id=?',(bid,user))
        return {'ok':True}
