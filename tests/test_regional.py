import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.core import ChallengeError
from qq_cf_bot.models import CFProblem, JudgeResult, ProblemStatement
from qq_cf_bot.regional import RegionalStore, normalize_record, problem_key
from qq_cf_bot.regional_sync import SubmissionSync, parse_nowcoder
from qq_cf_bot.storage import SentProblemStore
import test_webapp
_Handler = test_webapp._Handler


class RegionalStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'db.sqlite'
        self.base=SentProblemStore(self.path)
        self.store=RegionalStore(self.path)
        self.pid='icpc-2024-杭州:A'

    def tearDown(self):
        self.temp.cleanup()

    def test_aliases_normalize_across_platforms(self):
        for platform,pid in [('cf','CF105657A'),('vjudge','CodeForces-105657A'),('vjudge','Gym-105657A'),('luogu','CF105657A'),('codeforces','https://codeforces.com/gym/105657/problem/A')]:
            self.assertEqual(problem_key(platform,pid),'codeforces:105657A')
        self.assertEqual(problem_key('vjudge','QOJ-9726'),'qoj:9726')
        self.assertEqual(problem_key('vjudge','洛谷-P17121'),'luogu:P17121')
        self.assertEqual(self.store.aliases['qoj:9726'],self.store.aliases['codeforces:105657A'])
        self.assertEqual(self.store.aliases['qoj:15314'],self.store.aliases['luogu:P17121'])
        with self.assertRaises(ValueError):
            problem_key('cf','https://evil.example/105657A')

    def test_catalog_recent_seasons_cover_all_qoj_regional_sites(self):
        expected={
            2023:{'ICPC':{'杭州','合肥','济南','澳门','南京','沈阳','西安'},'CCPC':{'桂林','哈尔滨','秦皇岛','深圳'}},
            2024:{'ICPC':{'成都','杭州','香港','昆明','南京','上海','沈阳'},'CCPC':{'哈尔滨','济南','郑州','重庆'}},
            2025:{'ICPC':{'成都','香港','南京','上海','沈阳','武汉','西安'},'CCPC':{'哈尔滨','济南','郑州','重庆'}},
        }
        for year,series in expected.items():
            for name,sites in series.items():
                self.assertEqual({c['site'] for c in self.store.contests if c['year']==year and c['series']==name},sites)
        self.assertEqual(len(self.store.problems),426)
        for p in self.store.problems.values():
            self.assertIn('qoj:'+str(p['qoj_id']),p['aliases'])

    def test_nowcoder_pagination_and_result_detection(self):
        page='<table><tr><td><a href="/acm/problem/123">题目</a></td><td>2025-01-02 12:34:56 答案正确</td></tr></table><a data-page="3">末页</a>practice-coding'
        records,last=parse_nowcoder(page,'12345',1)
        self.assertFalse(last);self.assertEqual(records[0]['verdict'],'AC')
        self.assertEqual(records[0]['key'],'nowcoder:123')
        with self.assertRaises(RuntimeError):parse_nowcoder('practice-coding Please login','12345',1)

    def test_drafts_isolated_and_conflicts_preserve_data(self):
        r=self.store.save_draft(1,self.pid,'并查集',0)
        self.assertEqual(r['version'],1)
        with self.assertRaises(ChallengeError):
            self.store.save_draft(1,self.pid,'旧窗口覆盖',0)
        self.assertEqual(self.store.detail(1,self.pid)['draft']['body'],'并查集')
        self.assertEqual(self.store.detail(2,self.pid)['draft']['body'],'')
        again=RegionalStore(self.path)
        self.assertEqual(again.detail(1,self.pid)['draft']['body'],'并查集')
        self.store.save_draft(1,'icpc-2024-杭州:B','另一题',0)
        self.assertEqual(self.store.detail(1,self.pid)['draft']['body'],'并查集')

    def test_progress_wa_oral_and_true_ac_are_independent(self):
        self.store.attempt(1,self.pid,'test_req_1','oral','思路',True,'ORAL_ACCEPTED','通过')
        wa=normalize_record({'platform':'codeforces','problem_id':'105657A','verdict':'WA'})
        self.store.add_evidence(1,'test',[wa])
        p=self.store.progress(1)[self.pid]
        self.assertTrue(p['oral']);self.assertTrue(p['attempted']);self.assertFalse(p['code'])
        self.store.attempt(1,self.pid,'test_req_2','code','代码',True,'LLM_ACCEPTED','静态审核')
        self.assertFalse(self.store.progress(1)[self.pid]['code'])
        ac=normalize_record({'platform':'vjudge','problem_id':'CodeForces-105657A','verdict':'Accepted'})
        self.store.add_evidence(1,'sync',[ac])
        self.store.attempt(1,self.pid,'test_req_3','oral','复习失败',False,'ORAL_REVIEW','修改')
        p=self.store.progress(1)[self.pid]
        self.assertTrue(p['oral']);self.assertTrue(p['code'])
        self.assertFalse(self.store.progress(2)[self.pid]['oral'])
        self.assertFalse(self.store.progress(2)[self.pid]['code'])

    def test_import_preview_confirmation_idempotency_and_revoke(self):
        data='platform,problem_id,verdict\ncodeforces,105657A,AC\ncodeforces,105657A,AC\nqoj,999999,WA\ncodeforces,broken,AC\n'
        preview=self.store.preview_import(1,data)
        self.assertEqual(preview['matched'],1)
        self.assertEqual(preview['duplicates'],1)
        self.assertEqual(preview['invalidCount'],1)
        self.assertEqual(preview['unmatchedCount'],1)
        self.assertFalse(self.store.progress(1)[self.pid]['code'])
        with self.assertRaises(ValueError):self.store.confirm_import(2,preview['token'])
        self.store.confirm_import(1,preview['token'])
        self.store.confirm_import(1,preview['token'])
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        second=self.store.preview_import(1,data)
        self.store.confirm_import(1,second['token'])
        self.store.revoke_import(1,preview['token'])
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        self.store.revoke_import(1,second['token'])
        self.assertFalse(self.store.progress(1)[self.pid]['code'])

    def test_unknown_time_and_rejudged_submission_identity(self):
        a=normalize_record({'platform':'codeforces','handle':'alice','problem_id':'105657A','submission_id':123,'verdict':'TESTING'})
        b=normalize_record({'platform':'codeforces','handle':'alice','problem_id':'105657A','submission_id':123,'verdict':'OK'})
        self.assertIsNone(a['time']);self.assertEqual(a['fingerprint'],b['fingerprint'])
        self.store.add_evidence(1,'sync',[a]);self.store.add_evidence(1,'sync',[b])
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        with self.assertRaises(ValueError):normalize_record({'platform':'qoj','problem_id':'9726','verdict':'AC','submitted_at':'2025-01-01T12:00:00'})

    def test_retry_idempotency_rejects_reused_payload(self):
        self.store.attempt(1,self.pid,'req_same_1','oral','思路',True,'ORAL_ACCEPTED','通过')
        self.assertTrue(self.store.cached_attempt(1,self.pid,'req_same_1','oral','思路')['accepted'])
        self.assertIsNone(self.store.cached_attempt(2,self.pid,'req_same_1','oral','思路'))
        with self.assertRaises(ChallengeError):self.store.cached_attempt(1,self.pid,'req_same_1','oral','另一份思路')

    def test_sync_failure_does_not_advance_cursor_or_delete_evidence(self):
        with self.store.connect() as db:
            db.execute("insert into regional_bindings(user_id,platform,handle,cursor,last_sync) values (1,'codeforces','alice',31,1)")
            binding=dict(db.execute('select * from regional_bindings').fetchone())
        self.store.add_evidence(1,'binding:1',[normalize_record({'platform':'codeforces','problem_id':'105657A','verdict':'AC'})])
        sync=SubmissionSync(self.store,None)
        with patch('qq_cf_bot.regional_sync.fetch_page',side_effect=RuntimeError('403')):
            sync._run(binding)
        with self.store.connect() as db:r=db.execute('select * from regional_bindings').fetchone()
        self.assertEqual(r['cursor'],31);self.assertEqual(r['last_sync'],1);self.assertEqual(r['status'],'failed')
        self.assertTrue(self.store.progress(1)[self.pid]['code'])

    def test_historical_cursor_does_not_skip_capped_page(self):
        with self.store.connect() as db:
            db.execute("insert into regional_bindings(user_id,platform,handle) values (1,'codeforces','alice')")
            binding=dict(db.execute('select * from regional_bindings').fetchone())
        calls=[]
        def page(platform,handle,number,urls):calls.append(number);return [],False
        sync=SubmissionSync(self.store,None)
        with patch('qq_cf_bot.regional_sync.fetch_page',side_effect=page),patch('qq_cf_bot.regional_sync.time.sleep'):
            sync._run(binding)
        with self.store.connect() as db:r=dict(db.execute('select * from regional_bindings').fetchone())
        self.assertEqual(calls,list(range(1,11)));self.assertEqual(r['cursor'],11);self.assertFalse(r['complete'])

    def test_vjudge_summary_fallback_keeps_history_incomplete(self):
        with self.store.connect() as db:
            db.execute("insert into regional_bindings(user_id,platform,handle) values (1,'vjudge','alice')")
            binding=dict(db.execute('select * from regional_bindings').fetchone())
        sync=SubmissionSync(self.store,None)
        with patch('qq_cf_bot.regional_sync.fetch_page',side_effect=RuntimeError('403')),patch('qq_cf_bot.regional_sync.fetch',return_value=[['QOJ','9726',1730000000000]]):
            sync._run(binding)
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        with self.store.connect() as db:r=dict(db.execute('select * from regional_bindings').fetchone())
        self.assertFalse(r['complete']);self.assertIn('AC 汇总',r['message'])


class RegionalWebTest(unittest.TestCase):
    setUp = test_webapp.WebApplicationTest.setUp
    tearDown = test_webapp.WebApplicationTest.tearDown
    def register_user(self):
        h=_Handler({'username':'alice','displayName':'Alice','password':'password123'})
        self.app.handle_post(h,'/api/auth/register')
        return h.header('Set-Cookie').split(';',1)[0],h.json()['state']['csrfToken']

    def call(self,action,payload,cookie,csrf):
        h=_Handler(payload,cookie,csrf);self.app.handle_post(h,'/api/regionals/'+action);return h

    def test_wall_auth_and_csrf(self):
        public=_Handler();self.app.handle_get(public,'/api/regional-catalog')
        self.assertEqual(public.status,200);self.assertNotIn('progress',public.json())
        private=_Handler();self.app.handle_get(private,'/api/regionals');self.assertEqual(private.status,401)
        cookie,csrf=self.register_user()
        wall=_Handler(cookie=cookie);self.app.handle_get(wall,'/api/regionals')
        self.assertEqual(wall.status,200)
        h=self.call('draft',{'problemId':'icpc-2024-杭州:A','body':'草稿','version':0},cookie,'')
        self.assertEqual(h.status,403)

    def test_chinese_required_and_draft_can_survive_unavailable_statement(self):
        cookie,csrf=self.register_user();pid='icpc-2024-杭州:A'
        h=self.call('draft',{'problemId':pid,'body':'先记下观察','version':0},cookie,csrf)
        self.assertEqual(h.status,200)
        english=ProblemStatement('x','AUS','You are given three strings. Decide whether there is a function satisfying all the following constraints.','Input consists of several test cases.','Print YES or NO for each test case.',[])
        with patch.object(self.app.regionals,'qoj_statement',side_effect=RuntimeError('offline')),patch.object(self.app.service,'fetch_statement',return_value=english):
            opened=self.call('open',{'problemId':pid},cookie,csrf)
        self.assertIsNone(opened.json()['statement'])
        self.assertEqual(opened.json()['draft']['body'],'先记下观察')
        self.assertEqual(self.app.regionals.store.wall(1)['ready'],[])

    def test_explicit_problem_oral_retry_and_unranked_progress(self):
        cookie,csrf=self.register_user();pid='icpc-2024-杭州:A'
        statement=ProblemStatement('x','密码函数','给出三个字符串，判断是否存在满足条件的密码函数。','输入三行字符串。','输出答案。',[])
        from qq_cf_bot.core import SubmissionOutcome
        from qq_cf_bot.models import ActiveProblem
        active=ActiveProblem(CFProblem(105657,'A','AUS',0,is_gym=True),statement,[],'2025-01-01')
        payload={'problemId':pid,'solution':'按对应字母建立并查集，判断第三串是否仍能区分。','requestId':'unique_req_1'}
        with patch.object(self.app.service.judge.__class__,'configured',new_callable=__import__('unittest').mock.PropertyMock,return_value=True),patch.object(self.app.regionals,'qoj_statement',return_value=statement),patch.object(self.app.service,'submit_solution',return_value=SubmissionOutcome(active,True,'通过')) as judge:
            first=self.call('oral',payload,cookie,csrf)
            second=self.call('oral',payload,cookie,csrf)
        self.assertEqual(first.status,200);self.assertEqual(second.status,200);self.assertEqual(judge.call_count,1)
        self.assertFalse(judge.call_args.kwargs['settle'])
        self.assertTrue(self.app.regionals.store.progress(1)[pid]['oral'])

    def test_qoj_article_extraction_keeps_chinese_and_excludes_navigation(self):
        from qq_cf_bot.regional import RegionalApplication
        page='<nav>Login</nav><article class="uoj-article"><p>给定一个数组。</p><h3>输入格式</h3><p>输入长度。</p><h3>输出格式</h3><p>输出答案。</p></article><footer>广告</footer>'
        with patch('qq_cf_bot.regional_sync.fetch',return_value=page):
            statement=RegionalApplication.qoj_statement(9726)
        self.assertIn('给定',statement.description);self.assertNotIn('Login',statement.description);self.assertNotIn('广告',statement.description)

    def test_pdf_annotation_does_not_disguise_english_as_chinese(self):
        from types import SimpleNamespace
        from qq_cf_bot.regional import RegionalApplication
        from qq_cf_bot.core import _needs_statement_translation
        text='Given an array of integers, find the maximum possible sum over all contiguous subarrays. Input contains multiple test cases. Output one integer for each test case.'
        reader=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda **kw:text)])
        fake_pdf=SimpleNamespace(PdfReader=lambda data:reader)
        with patch.dict('sys.modules',{'pypdf':fake_pdf}),patch('qq_cf_bot.regional_sync.fetch',side_effect=[RuntimeError('404'),'<article class="uoj-article"></article><iframe src="/download.php?type=statement&id=15032"></iframe>',b'pdf']):
            s=RegionalApplication.qoj_statement(15032)
        self.assertTrue(_needs_statement_translation(s))
        self.assertIn('原始 PDF',s.background)


class RegionalQojWebTest(unittest.TestCase):
    setUp=RegionalWebTest.setUp
    tearDown=RegionalWebTest.tearDown
    register_user=RegionalWebTest.register_user
    call=RegionalWebTest.call
    def test_qoj_token_upload_requires_authorization_but_not_session(self):
        cookie,csrf=self.register_user()
        denied=self.call('qoj-authorize',{'uid':'ucup-team123'},cookie,'')
        self.assertEqual(denied.status,403)
        grant=self.call('qoj-authorize',{'uid':'ucup-team123'},cookie,csrf)
        self.assertEqual(grant.status,200)
        payload={'uid':'ucup-team123','records':[{'id':'1234','problemId':'9726','submitter':'ucup-team123','submittedAt':1720000000,'verdict':'100 ✓'}]}
        request=_Handler(payload);request.headers['Authorization']='Bearer '+grant.json()['token']
        self.app.handle_post(request,'/api/regional-qoj/import')
        self.assertEqual(request.status,200)
        self.assertEqual(request.json()['matched'],1)
        self.call('qoj-revoke',{'uid':'ucup-team123'},cookie,csrf)
        request=_Handler(payload);request.headers['Authorization']='Bearer '+grant.json()['token']
        self.app.handle_post(request,'/api/regional-qoj/import')
        self.assertEqual(request.status,401)

    def test_plugin_download_is_public_and_scoped(self):
        request=_Handler();self.app.handle_get(request,'/regional-qoj-sync.user.js')
        self.assertEqual(request.status,200)
        script=request.wfile.getvalue().decode()
        self.assertIn('// @match        https://qoj.ac/*',script)
        self.assertIn('/api/regional-qoj/import',script)
        self.assertNotIn('__SITE_JSON__',script)


class RegionalDifficultyTest(unittest.TestCase):
    setUp = RegionalWebTest.setUp
    tearDown = RegionalWebTest.tearDown

    def test_year_estimation_skips_cached_and_retains_failures_as_unrated(self):
        regional=self.app.regionals
        problems=regional.store.contests[0]['problems'][:3]
        year=regional.store.contests[0]['year']
        regional.store.contests=[{'year':year,'problems':problems}]
        with regional.store.connect() as db:
            db.execute('insert into regional_difficulty values (?,?,?,?)',(problems[0]['id'],1700,'已有评级','2026-10-08'))
        def estimate(pid):
            if pid==problems[2]['id']:raise RuntimeError('source unavailable')
            with regional.store.connect() as db:
                db.execute('insert into regional_difficulty values (?,?,?,?)',(pid,2200,'模型估算，非官方 Rating','2026-10-08'))
        with patch.object(regional.service.judge.__class__,'configured',new_callable=__import__('unittest').mock.PropertyMock,return_value=True),patch.object(regional,'estimate_difficulty',side_effect=estimate) as mock:
            result=regional.estimate_year(year)
            regional.difficulty_thread.join(timeout=2)
        self.assertEqual(result['total'],2)
        self.assertEqual(mock.call_count,2)
        self.assertEqual(regional.difficulty_job,{'year':year,'status':'finished','total':2,'done':1,'failed':1})
        public=_Handler();self.app.handle_get(public,'/api/regional-catalog')
        scores=public.json()['difficulty']
        self.assertEqual(scores[problems[0]['id']]['rating'],1700)
        self.assertEqual(scores[problems[1]['id']]['rating'],2200)
        self.assertNotIn(problems[2]['id'],scores)
        self.assertNotIn('progress',public.json())
