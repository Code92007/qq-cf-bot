import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote, unquote

from qq_cf_bot.regional import RegionalStore
from qq_cf_bot.regional_editorials import RegionalEditorials, render_editorial
from qq_cf_bot.models import ProblemStatement
from qq_cf_bot.storage import SentProblemStore, _statement_to_json
import test_webapp


class EditorialReleaseTest(unittest.TestCase):
    def test_release_is_complete_mapped_and_matches_validation(self):
        bank = RegionalEditorials()
        catalog = json.loads((bank.root / 'regionals.json').read_text())
        problems = {p['id']: p for c in catalog['contests'] for p in c['problems']}
        self.assertTrue({'ccpc-2026-长春:'+x for x in 'ABCDEFGHIJKLM'} <= set(bank.ready()))
        self.assertTrue({'icpc-2025-上海:'+x for x in 'ABCDEFGHIJKLM'} <= set(bank.ready()))
        for pid, entry in bank.entries.items():
            report = json.loads((bank.root / entry.get('validation_report', 'regional_editorial_validation.json')).read_text())
            self.assertTrue(problems[pid]['qoj_id'])
            content = bank.content(pid)
            self.assertIn('## 先学什么', content)
            self.assertGreater(len(content), 300)
            self.assertEqual(len(entry['hints']), 3)
            self.assertTrue(all(entry['hints']))
            file = bank.root / entry['file']
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), report['content_sha256'][file.name])
            self.assertTrue(report['checks'][pid[-1]]['passed'])
            self.assertIn('<h1>', bank.read(pid, 'full')['html'])
        self.assertFalse(bank.metadata('icpc-2026-西安:A')['available'])

    def test_markdown_is_sanitized_without_losing_headings_and_code(self):
        value = render_editorial('# Heading\n\n<script>alert(1)</script>\n\n[bad](javascript:alert)\n\n```text\na < b\n```')
        self.assertNotIn('<script', value)
        self.assertNotIn('javascript:', value)
        # Normal Markdown takes the renderer's Markdown path.
        clean = render_editorial('# Heading\n\n```text\na < b\n```')
        self.assertIn('<h1>Heading</h1>', clean)
        self.assertIn('a &lt; b', clean)
        comparison = render_editorial('# Geometry\n\nx<a：起点位于上方；x>a：起点位于下方。')
        self.assertIn('<h1>Geometry</h1>', comparison)
        self.assertIn('x&lt;a', comparison)
        self.assertIn('起点位于下方', comparison)

    def test_reading_is_private_monotonic_and_does_not_complete_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bot.sqlite'
            SentProblemStore(path)
            store = RegionalStore(path)
            pid = 'ccpc-2026-长春:I'
            before = store.progress(1)[pid]
            store.save_draft(1,pid,'自己先写下的做法',0)
            study = store.read_editorial(1,pid,'learning')
            self.assertNotIn('hints',study)
            self.assertFalse(store.detail(1,pid)['editorial']['fullViewed'])
            store.read_editorial(1,pid,'hint',2)
            store.read_editorial(1,pid,'hint',1)
            store.read_editorial(1,pid,'full')
            state = RegionalStore(path).detail(1,pid)
            self.assertEqual(state['editorial']['hintLevel'],2)
            self.assertTrue(state['editorial']['fullViewed'])
            self.assertFalse(store.detail(2,pid)['editorial']['fullViewed'])
            self.assertEqual(state['draft']['body'],'自己先写下的做法')
            after = store.progress(1)[pid]
            for key in ('oral','code','attempted','oralAttempted'):
                self.assertEqual(before[key],after[key])
            self.assertEqual(state['attempts'],[])


class EditorialAPITest(unittest.TestCase):
    setUp = test_webapp.WebApplicationTest.setUp
    tearDown = test_webapp.WebApplicationTest.tearDown

    def register(self):
        h = test_webapp._Handler({'username':'reader','displayName':'Reader','password':'password123'})
        self.app.handle_post(h,'/api/auth/register')
        return h.header('Set-Cookie').split(';',1)[0],h.json()['state']['csrfToken']

    def call(self, action, payload, cookie='', csrf=''):
        h = test_webapp._Handler(payload,cookie,csrf)
        self.app.handle_post(h,'/api/regionals/'+action)
        return h

    def test_contest_download_is_utf8_attachment_without_personal_state(self):
        handler = test_webapp._Handler()
        handler.path = '/api/regionals/editorials.md?contest='+quote('ccpc-2026-长春')
        with patch.object(self.app.regionals,'prepare',side_effect=AssertionError('offline export')):
            self.assertTrue(self.app.handle_get(handler,'/api/regionals/editorials.md'))
        self.assertEqual(handler.status,200)
        self.assertEqual(handler.header('Content-Type'),'text/markdown; charset=utf-8')
        self.assertIn("attachment;",handler.header('Content-Disposition'))
        self.assertIn('ccpc-2026-长春-题解.md',unquote(handler.header('Content-Disposition')))
        text = handler.wfile.getvalue().decode('utf-8')
        self.assertIn('13/13',text)
        self.assertEqual(text.count('<a id="problem-'),13)
        self.assertIn('### 先学什么',text)
        self.assertIn('qoj.ac/download.php?',text)
        self.assertLess(text.index('## A ·'),text.index('## M ·'))
        self.assertNotIn('password',text)
        self.assertEqual(len(handler.wfile.getvalue()),int(handler.header('Content-Length')))
        with self.app.regionals.store.connect() as db:
            self.assertEqual(db.execute('select count(*) from regional_editorial_reads').fetchone()[0],0)

    def test_download_rejects_unknown_empty_and_ambiguous_contests(self):
        for query in ('','contest=../../README','contest='+quote('icpc-2026-西安'),
                      'contest='+quote('ccpc-2026-长春')+'&contest=',
                      'contest='+quote('ccpc-2026-长春')+'&contest='+quote('ccpc-2026-长春')):
            h = test_webapp._Handler()
            h.path = '/api/regionals/editorials.md?'+query
            self.app.handle_get(h,'/api/regionals/editorials.md')
            self.assertEqual(h.status,404)

    def test_partial_contest_download_marks_missing_problems_and_preserves_code(self):
        h = test_webapp._Handler()
        h.path = '/api/regionals/editorials.md?contest='+quote('icpc-2025-南京')
        # Keep partial coverage testable after the real collection becomes complete.
        from copy import deepcopy
        partial = RegionalEditorials()
        partial.release = deepcopy(partial.release)
        partial.entries = partial.release['problems']
        for letter in ('D', 'L'):
            partial.entries.pop('icpc-2025-南京:'+letter, None)
        partial.release.setdefault('pending_problems', {})['icpc-2025-南京:D'] = {
            'reason': '测试中的待补题解，保留全场原题号。'}
        with patch.object(self.app.regionals.store, 'editorials', partial):
            self.app.handle_get(h,'/api/regionals/editorials.md')
        self.assertEqual(h.status,200)
        text = h.wfile.getvalue().decode('utf-8')
        self.assertIn('11/13',text)
        self.assertEqual(text.count('<a id="problem-'),13)
        self.assertIn('测试中的待补题解，保留全场原题号。',text)
        self.assertIn('sua.ac/wiki/2025-icpc-nanjing/tutorial-sketch-zh.pdf',text)
        self.assertIn('```text\n',text)

    def test_public_catalog_exposes_coverage_without_editorial_text(self):
        h = test_webapp._Handler()
        self.app.handle_get(h,'/api/regional-catalog')
        self.assertEqual(h.json()['editorialContests']['ccpc-2026-长春'],{'ready':13,'total':13})
        self.assertEqual(h.json()['editorialContests']['icpc-2026-西安']['ready'],0)
        self.assertNotIn('hints',json.dumps(h.json()))

    def test_explicit_reveal_requires_login_csrf_and_no_network(self):
        pid = 'ccpc-2026-长春:C'
        payload = {'problemId':pid,'view':'full'}
        self.assertEqual(self.call('editorial',payload).status,401)
        cookie,csrf = self.register()
        self.assertEqual(self.call('editorial',payload,cookie).status,403)
        with patch.object(self.app.regionals,'prepare',side_effect=AssertionError('no remote work')):
            opened = self.call('open',{'problemId':pid,'prepareStatement':False},cookie,csrf)
            self.assertEqual(opened.status,200)
            self.assertNotIn('hints',opened.json()['editorial'])
            self.assertNotIn('html',opened.json()['editorial'])
            self.assertNotIn('投票',json.dumps(opened.json(),ensure_ascii=False))
            hint = self.call('editorial',{'problemId':pid,'view':'hint','level':1},cookie,csrf)
            self.assertEqual(len(hint.json()['hints']),1)
            self.assertNotIn('html',hint.json())
            full = self.call('editorial',payload,cookie,csrf)
            self.assertEqual(full.status,200)
            self.assertIn('投票',full.json()['html'])
        public = test_webapp._Handler()
        self.app.handle_get(public,'/api/regional-catalog')
        self.assertNotIn('投票',json.dumps(public.json(),ensure_ascii=False))

    def test_cached_open_keeps_statement_and_title(self):
        cookie,csrf = self.register()
        pid = 'ccpc-2026-长春:C'
        statement = ProblemStatement('22912','无忧旋律','已缓存中文题面','输入','输出',[])
        with self.app.regionals.store.connect() as db:
            db.execute('insert into regional_statements values (?,?,?)',
                       (pid,json.dumps(_statement_to_json(statement)),'2026-10-24'))
        with patch.object(self.app.regionals,'prepare',side_effect=AssertionError('no remote work')):
            opened = self.call('open',{'problemId':pid,'prepareStatement':False},cookie,csrf)
        self.assertEqual(opened.status,200)
        self.assertEqual(opened.json()['title'],'无忧旋律')
        self.assertIn('已缓存中文题面',json.dumps(opened.json(),ensure_ascii=False))
        self.assertNotIn('statementError',opened.json())

    def test_invalid_problem_pending_source_and_invalid_levels(self):
        cookie,csrf = self.register()
        for pid in ('../../README','icpc-2026-西安:A'):
            h = self.call('editorial',{'problemId':pid},cookie,csrf)
            self.assertEqual(h.status,404)
        for level in (0,4,'2',True,None):
            h = self.call('editorial',{'problemId':'ccpc-2026-长春:C','view':'hint','level':level},cookie,csrf)
            self.assertEqual(h.status,400)
        for view in ('secret',None,[],{}):
            self.assertEqual(self.call('editorial',{'problemId':'ccpc-2026-长春:C','view':view},cookie,csrf).status,400)


if __name__ == '__main__':
    unittest.main()
