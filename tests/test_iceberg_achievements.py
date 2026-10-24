import importlib.util
import io
import json
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeService
from qq_cf_bot.iceberg import merge_records, timestamp, validate_knowledge
from qq_cf_bot.webapp import WebApplication
from test_webapp import _Handler


def ts(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


class AchievementTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        with patch.dict('os.environ', {'BOT_DATA_DIR': self.temp.name, 'CF_SUBMIT_ENABLED':'false', 'JUDGE_ENABLED':'false'}, clear=True):
            config = Config.from_env()
        self.app = WebApplication(config, ChallengeService(config))
        self.session = {'user_id': 1, 'display_name':'测试 <人>', 'csrf_token':'token'}
        self.first, self.last = ts('2020-01-01'), ts('2024-03-02')
        self.snapshot([
            self.record('codeforces:99001A', ['dp','greedy'], self.first, self.last, ['2020-01-01','2022-06-01','2024-03-02']),
            self.record('codeforces:1705A', ['greedy'], ts('2023-04-05'), ts('2023-04-05')),
            self.record('luogu:P1001', ['线段树'], None, None),
            self.record('qoj:999999', ['NTT'], self.first, self.last, kind='team'),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def record(self, key, tags, first, last, days=None, kind='personal'):
        return {'key':key,'kind':kind,'title':'题目 <标题>','tags':tags,'firstAt':first,'lastAt':last,'days':days or []}

    def snapshot(self, rows):
        with self.app.regionals.store.connect() as db:
            db.execute('insert or replace into cpc_wall_links values (?,?,?,?,?)', (1, 'private-token', json.dumps({'knowledge': {'version':1,'complete':True,'records':rows}}), int(time.time()), ''))

    def test_multi_tags_first_last_dates_and_distinct_counts(self):
        state = self.app.iceberg.state(self.session)
        self.assertEqual(state['topics']['dp-basic']['firstAt'], self.first)
        self.assertEqual(state['topics']['dp-basic']['lastAt'], self.last)
        self.assertEqual(state['topics']['basic-greedy']['count'], 2)
        self.assertEqual(state['summary']['solved'], 3)
        self.assertNotIn('private-token', json.dumps(state))
        self.assertEqual(state['topics']['math-poly-ntt']['count'], 0)
        self.assertEqual(self.app.iceberg.state(self.session, True)['topics']['math-poly-ntt']['count'], 1)

    def test_unknown_dates_never_become_sync_dates(self):
        state = self.app.iceberg.state(self.session)
        self.assertEqual(state['topics']['ds-seg']['count'], 1)
        self.assertIsNone(state['topics']['ds-seg']['firstAt'])
        self.assertIsNone(state['topics']['ds-seg']['lastAt'])
        self.assertEqual(state['topics']['ds-seg']['undated'], 1)

    def test_year_memory_includes_intermediate_ac_and_counts_new_topics_once(self):
        state = self.app.iceberg.state(self.session)
        self.assertEqual(state['memories']['2022']['solved'], 1)
        self.assertEqual(state['memories']['2022']['newTopics'], 0)
        self.assertEqual(state['memories']['2022']['first']['date'], '2022-06-01')
        self.assertEqual(state['memories']['2020']['newTopics'], 2)
        self.assertEqual(state['memories']['all']['activeDays'], 4)

    def test_manual_many_to_many_links_are_owner_scoped_and_reversible(self):
        for topic in ['math-poly-ntt','math-poly-fft']:
            self.app.iceberg.link(self.session, {'topicId':topic,'problemKey':'luogu:P1001'})
        state = self.app.iceberg.state(self.session)
        self.assertEqual(state['topics']['math-poly-ntt']['count'], 1)
        self.assertEqual(state['topics']['math-poly-fft']['count'], 1)
        other = self.app.iceberg.state({**self.session,'user_id':2})
        self.assertEqual(other['summary']['solved'], 0)
        with self.assertRaises(ValueError):
            self.app.iceberg.link({**self.session,'user_id':2}, {'topicId':'math-poly-ntt','problemKey':'luogu:P1001'})
        self.app.iceberg.link(self.session, {'topicId':'math-poly-ntt','problemKey':'luogu:P1001','remove':True})
        self.assertEqual(self.app.iceberg.state(self.session)['topics']['math-poly-ntt']['count'], 0)

    def test_metadata_fills_missing_tags_and_recommendations_exclude_solved(self):
        problems = [dict(contestId=99001,index='A',name='已做',rating=1500,tags=['dp']),dict(contestId=99999,index='A',name='未做',rating=1600,tags=['dp']),dict(contestId=99999,index='B',name='太难',rating=3000,tags=['dp']),dict(contestId=99999,index='C',name='别的标签',rating=1500,tags=['greedy'])]
        self.app.service.cf.cache_path.write_text(json.dumps({'result':{'problems':problems}}))
        handler = SimpleNamespace(path='/api/iceberg/recommendations?topic=dp-basic&minRating=1200&maxRating=2000')
        result = self.app.iceberg.recommendations(self.session, handler)
        self.assertEqual([p['key'] for p in result['problems']], ['codeforces:99999A'])
        self.snapshot([self.record('codeforces:99001A', [], self.first, self.last)])
        self.assertEqual(self.app.iceberg.state(self.session)['topics']['dp-basic']['count'], 1)

    def test_private_routes_require_login_and_mutation_requires_csrf(self):
        handler = _Handler()
        self.app.handle_get(handler, '/api/iceberg/progress')
        self.assertEqual(handler.status, 401)
        register = _Handler({'username':'alice','displayName':'Alice','password':'password123'})
        self.app.handle_post(register, '/api/auth/register')
        cookie = register.header('Set-Cookie').split(';',1)[0]
        handler = _Handler(cookie=cookie)
        self.app.handle_post(handler, '/api/iceberg/link')
        self.assertEqual(handler.status, 403)
        handler = _Handler(cookie=cookie)
        self.app.handle_get(handler, '/api/iceberg/progress')
        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json()['summary']['solved'], 3)

    def test_snapshot_validation_rejects_partial_or_bad_evidence(self):
        self.assertEqual(validate_knowledge({'version':1,'complete':True,'records':[
            self.record('regional:ccpc-2019-厦门:J', [], self.first, self.last)
        ]})['records'][0]['key'], 'regional:ccpc-2019-厦门:J')
        with self.assertRaises(ValueError):
            validate_knowledge({'version':1,'complete':False,'records':[]})
        with self.assertRaises(ValueError):
            validate_knowledge({'version':1,'complete':True,'records':[self.record('javascript:bad', [], True, True)]})
        with self.assertRaises(ValueError):
            validate_knowledge({'version':1,'complete':True,'records':[self.record('codeforces:99001A', [], self.last, self.first)]})

    def test_repeat_ac_merges_dates_and_does_not_multiply_problems(self):
        result = merge_records([self.record('codeforces:99001A', ['dp'],self.first,self.first),self.record('codeforces:99001A',['greedy'],self.last,self.last)])
        self.assertEqual(len(result),1)
        self.assertEqual(result['codeforces:99001A']['tags'],{'dp','greedy'})
        self.assertEqual(result['codeforces:99001A']['firstAt'],self.first)
        self.assertEqual(result['codeforces:99001A']['lastAt'],self.last)
        self.assertIsNone(timestamp(None))
        self.assertIsNone(timestamp(True))

    def test_precise_luogu_tags_light_each_algorithm_without_expanding_broad_tags(self):
        self.snapshot([self.record('luogu:P1234', ['线段树', '树形 DP', '最近公共祖先 LCA', '后缀自动机 SAM', '快速数论变换 NTT', 'dp'], self.first, self.last)])
        state = self.app.iceberg.state(self.session)
        for tid in ['ds-seg', 'dp-tree', 'graph-lca', 'string-sam', 'math-poly-ntt', 'dp-basic']:
            self.assertEqual(state['topics'][tid]['count'], 1)
            self.assertEqual(state['topics'][tid]['firstAt'], self.first)
        self.assertEqual(state['topics']['dp-interval']['count'], 0)
        self.assertEqual(state['topics']['ds-seg-beats']['count'], 0)

    def test_coarse_p5047_tags_gain_reviewed_secondary_offline_reference_and_original_dates(self):
        self.snapshot([self.record('luogu:P5047', ['分块', '莫队'], self.first, self.last)])
        state = self.app.iceberg.state(self.session)
        topic = state['topics']['misc-mo-algo-secondary-offline']
        self.assertEqual((topic['count'], topic['firstAt'], topic['lastAt']), (1, self.first, self.last))
        record = state['problems'][0]
        self.assertTrue({'ds-decompose', 'misc-mo-algo', 'misc-mo-algo-secondary-offline'} <= set(record['topicIds']))
        self.assertEqual(record['referenceTopics']['misc-mo-algo-secondary-offline'], 'https://oi-wiki.org/misc/mo-algo-secondary-offline/')
        self.assertEqual(record['manualTopicIds'], [])
        self.assertEqual(state['topics']['misc-modifiable-mo-algo']['count'], 0)
        self.assertEqual(state['topics']['misc-rollback-mo-algo']['count'], 0)

    def test_references_require_exact_owner_ac_and_respect_team_selection(self):
        self.snapshot([self.record('luogu:P5047', [], self.first, self.last, kind='team'),
                       self.record('luogu:P5048', ['莫队'], self.first, self.last)])
        self.assertEqual(self.app.iceberg.state(self.session)['topics']['misc-mo-algo-secondary-offline']['count'], 0)
        self.assertEqual(self.app.iceberg.state(self.session, True)['topics']['misc-mo-algo-secondary-offline']['count'], 1)
        self.assertEqual(self.app.iceberg.state({**self.session, 'user_id':2}, True)['summary']['lit'], 0)

    def test_shared_articles_and_nearby_notes_do_not_assign_other_algorithms(self):
        self.snapshot([self.record('codeforces:1009F', ['trees'], self.first, self.last),
                       self.record('codeforces:1304D', ['constructive algorithms'], self.first, self.last),
                       self.record('luogu:P4213', ['杜教筛'], self.first, self.last)])
        state = self.app.iceberg.state(self.session)
        for tid in ['graph-long-chain', 'dp-lis', 'math-number-theory-hyperbola']:
            self.assertEqual(state['topics'][tid]['count'], 1)
        for tid in ['graph-hld', 'dp-lcis', 'math-number-theory-min-25']:
            self.assertEqual(state['topics'][tid]['count'], 0)

    def test_precise_synonyms_and_ambiguous_labels_do_not_expand_to_implementations(self):
        self.snapshot([self.record('luogu:P999999', ['cdq', 'sparse table', 'chinese remainder theorem', '轮廓线 DP', '平衡树', '树套树', 'Tarjan', 'games', 'matrices', 'hashing'], self.first, self.last),
                       self.record('luogu:P1177', ['sortings'], self.first, self.last),
                       self.record('luogu:P3369', ['平衡树'], self.first, self.last)])
        state = self.app.iceberg.state(self.session)
        for tid in ['misc-cdq-divide', 'ds-sparse-table', 'math-number-theory-crt', 'dp-state', 'basic-sort-intro']:
            self.assertEqual(state['topics'][tid]['count'], 1)
        for tid in ['ds-treap', 'ds-rbtree', 'ds-splay', 'ds-seg-in-seg', 'graph-scc', 'graph-dmst', 'basic-quick-sort', 'basic-radix-sort', 'math-game-theory-impartial-game', 'math-linear-algebra-matrix', 'string-hash']:
            self.assertEqual(state['topics'][tid]['count'], 0)

    def test_reviewed_recommendations_match_coarse_tags_and_exclude_canonical_solved(self):
        self.app.service.cf.cache_path.write_text(json.dumps({'result':{'problems':[
            dict(contestId=1661,index='F',name='Teleporters',rating=2700,tags=['dp'])]}}))
        handler = SimpleNamespace(path='/api/iceberg/recommendations?topic=dp-opt-wqs-binary-search&minRating=2600&maxRating=2800')
        result = self.app.iceberg.recommendations(self.session, handler)
        self.assertEqual([p['key'] for p in result['problems']], ['codeforces:1661F'])
        self.app.iceberg.canonical['luogu:CF1661F'] = 'codeforces:1661F'
        self.snapshot([self.record('luogu:CF1661F', [], self.first, self.last)])
        self.assertEqual(self.app.iceberg.recommendations(self.session, handler)['total'], 0)

    def test_reviewed_catalog_has_unique_valid_topics_keys_and_traceable_sources(self):
        path = Path(__file__).parents[1]/'src/qq_cf_bot/catalog/iceberg-problem-topics.json'
        catalog = json.loads(path.read_text())
        seen = set()
        for row in catalog['entries']:
            with self.subTest(row=row):
                pair = (row['problemKey'], row['topicId'])
                self.assertNotIn(pair, seen)
                seen.add(pair)
                self.assertIn(row['topicId'], self.app.iceberg.topics)
                self.assertRegex(row['problemKey'], r'^[a-z]+:[A-Za-z0-9_]+$')
                self.assertTrue(row['source'].startswith(('https://oi-wiki.org/', 'https://github.com/Zhonghe-zhao/codeforces-go/blob/')))
                self.assertRegex(row['reference'], r'^https://github.com/(?:OI-wiki/OI-wiki|Zhonghe-zhao/codeforces-go)/blob/[0-9a-f]{40}/.+#L[1-9][0-9]*$')


class ExportTest(unittest.TestCase):
    def test_owner_active_accounts_aliases_multi_tags_repeats_and_placeholders(self):
        spec = importlib.util.spec_from_file_location('knowledge_export', Path(__file__).parents[1]/'integrations/oj-wall/knowledge_export.py')
        exporter = importlib.util.module_from_spec(spec); spec.loader.exec_module(exporter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.db'
            def db():
                conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row; return conn
            with db() as conn:
                conn.executescript('create table handles(id,platform,handle,owner_type,owner_id,active,stats_json);create table cpc_handle_kinds(handle_id,kind);create table submissions(platform,handle,owner_type,owner_id,problem_id,problem_name,submitted_at,url,raw_json,verdict);')
                conn.execute("insert into handles values (1,'codeforces','a','user','1',1,'{}')")
                for owner, verdict, stamp, pid in [('1','AC',1000,'1A'),('1','OK',2000,'1A'),('2','AC',3000,'2A'),('1','WA',4000,'3A'),('1','AC',5000,'activity')]:
                    conn.execute('insert into submissions values (?,?,?,?,?,?,?,?,?,?)',('codeforces','a','user',owner,pid,pid,stamp,'',json.dumps({'problem':{'tags':['dp','greedy']}}),verdict))
            app = SimpleNamespace(raw_json_dict=lambda r:json.loads(r['raw_json']),is_activity_placeholder=lambda r,raw:r['problem_id']=='activity',canonical_problem_key=lambda platform,pid,title,raw:platform+':'+pid)
            result = exporter.knowledge_snapshot(SimpleNamespace(db=db,app=app),'1')
            self.assertEqual(len(result['records']),1)
            record = result['records'][0]
            self.assertEqual((record['firstAt'],record['lastAt']),(1000,2000))
            self.assertEqual(record['tags'],['dp','greedy'])
            self.assertEqual(result['excludedActivity'],1)
            root = Path(directory)
            (root/'catalog').mkdir(); (root/'cache').mkdir()
            (root/'catalog/luogu_algorithm_tags.json').write_text(json.dumps({'tags': {'42': {'label':'线段树','key':'segment tree'}, '53': {'label':'树状数组','key':'fenwick tree'}}}))
            (root/'catalog/luogu_problems.json').write_text(json.dumps({'problems': {'P1234': {'tags': [19,42]}}}))
            (root/'cache/luogu-analysis.json').write_text(json.dumps({'problems': {'P1234': {'tags': [19,53]}}}))
            app.ROOT, app.CACHE_DIR = root, root/'cache'
            with db() as conn:
                conn.execute("insert into handles values (2,'luogu','b','user','1',1,'{}')")
                conn.execute('insert into submissions values (?,?,?,?,?,?,?,?,?,?)',('luogu','b','user','1','P1234','多标签题',6000,'',json.dumps({'problem':{'tags':[19,42]}}),'AC'))
            result = exporter.knowledge_snapshot(SimpleNamespace(db=db,app=app),'1')
            luogu = next(r for r in result['records'] if r['key']=='luogu:P1234')
            self.assertEqual(set(luogu['tags']), {'线段树','segment tree','树状数组','fenwick tree'})
            self.assertEqual((luogu['firstAt'],luogu['lastAt']), (6000,6000))


if __name__ == '__main__': unittest.main()
