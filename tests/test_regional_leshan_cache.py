import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from qq_cf_bot.regional import RegionalApplication, RegionalStore
from qq_cf_bot.regional_editorials import RegionalEditorials
from qq_cf_bot.regional_statements import seed_cached_statements
from qq_cf_bot.storage import SentProblemStore


ROOT = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot'
CID = 'ccpc-2026-乐山'


class LeshanScreenshotCacheTest(unittest.TestCase):
    def test_all_thirteen_open_offline_after_restart_without_fabricated_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'bot.sqlite'
            SentProblemStore(db)
            store = RegionalStore(db)
            app = RegionalApplication.__new__(RegionalApplication)
            app.store = store
            app.prepare_lock = threading.Lock()
            app.qoj_statement = Mock(side_effect=AssertionError('offline only'))
            app.service = Mock()
            app.service.fetch_statement.side_effect = AssertionError('offline only')
            ids = set()
            for letter in 'ABCDEFGHIJKLM':
                pid = CID + ':' + letter
                p, statement = app.prepare(pid)
                ids.add(p.cf_id)
                self.assertTrue(statement.description)
                self.assertEqual(RegionalStore(db).cached_statement(pid), statement)
                if letter not in 'AD':
                    self.assertEqual(store.problem(pid)['aliases'], [])
                    self.assertNotIn('qoj_id', store.problem(pid))
            self.assertEqual(len(ids), 13)
            app.qoj_statement.assert_not_called()
            app.service.fetch_statement.assert_not_called()

    def test_source_screenshots_samples_and_special_protocols(self):
        release = json.loads((ROOT / 'catalog/regional_statements.json').read_text())
        source = release['sources']['ccpc-2026-leshan-user-screenshots']
        self.assertEqual(set(source['screenshots']), set('ABCDEFGHIJKLM'))
        self.assertEqual(sum(map(len, source['screenshots'].values())), 20)
        for shots in source['screenshots'].values():
            for entry in shots:
                self.assertEqual(hashlib.sha256((ROOT / 'catalog' / entry['file']).read_bytes()).hexdigest(), entry['sha256'])
        statements = {letter: release['problems'][CID + ':' + letter]['statement'] for letter in 'ABCDEFGHIJKLM'}
        self.assertEqual([len(statements[x]['samples']) for x in 'ABCDEFGHIJKLM'],
                         [2, 1, 1, 1, 1, 3, 3, 2, 3, 1, 1, 1, 1])
        self.assertEqual(statements['D']['samples'][0][1], '4\n1\n1')
        self.assertEqual(statements['A']['samples'][1][1].splitlines()[0], '9 4 10 0 10 3 2 5')
        self.assertIn('同时作用于两个人', statements['A']['description'])
        self.assertIn('即使等级较高的雨鹿也正在低头等待', statements['B']['description'])
        self.assertIn('双次运行', statements['H']['description'])
        self.assertIn('不会获得 $m$', statements['H']['description'])
        self.assertIn('刷新输出缓冲区', statements['H']['output_format'])
        self.assertIn('自适应', statements['M']['input_format'])
        self.assertIn('[a>a_x]', statements['M']['output_format'])
        self.assertIn('最多查询 $10$ 次', statements['M']['output_format'])
        self.assertIn('不会额外发送确认', statements['M']['input_format'])
        for filename in ['statement-leshan-2026-e-path.png', 'statement-leshan-2026-k-hull.png']:
            self.assertTrue((ROOT / 'web' / filename).is_file())

    def test_local_release_identity_must_match_the_actual_contest_letter(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'bot.sqlite'
            SentProblemStore(db)
            store = RegionalStore(db)
            path = Path(temp) / 'bad.json'
            path.write_text(json.dumps({'published_at': 'now', 'problems': {
                CID + ':B': {'problem_key': 'regional:' + CID + ':C'}}}))
            with store.connect() as con, self.assertRaises(ValueError):
                seed_cached_statements(con, store.problems, path)

    def test_thirteen_complete_tutorials_export_with_code_and_math_intact(self):
        bank = RegionalEditorials()
        self.assertEqual({pid.split(':')[-1] for pid in bank.ready() if pid.startswith(CID + ':')}, set('ABCDEFGHIJKLM'))
        for letter in 'ABCDEFGHIJKLM':
            result = bank.read(CID + ':' + letter, 'full')
            self.assertEqual(result['source']['kind'], 'independent')
            self.assertEqual(result['pages'], [])
            self.assertIn('独立推导', result['html'])
            self.assertIn('<pre><code>#include ', result['html'])
            self.assertIn('int main()', result['html'])
        rendered = bank.read(CID + ':G', 'full')['html']
        self.assertIn(r'\mathbf{1}_{a_i+a_{i+1}\le g}', rendered)
        self.assertNotIn('<em>', rendered)
        self.assertIn('<h2>矩阵乘积统计方案</h2>', rendered)
        catalog = json.loads((ROOT / 'catalog/regionals.json').read_text())
        contest = next(c for c in catalog['contests'] if c['id'] == CID)
        text = bank.contest_markdown(contest)
        self.assertIn('13/13', text)
        self.assertNotIn('对应 PDF 页码', text)
        self.assertEqual(text.count('```cpp\n'), 13)
        self.assertIn('尚无 QOJ 在线评测结果', text)


if __name__ == '__main__':
    unittest.main()
