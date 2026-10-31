import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from qq_cf_bot.core import ChallengeError
from qq_cf_bot.models import CFProblem, ProblemStatement
from qq_cf_bot.regional import RegionalApplication, RegionalStore
from qq_cf_bot.regional_statements import seed_cached_statements
from qq_cf_bot.storage import SentProblemStore


class RegionalStatementCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'bot.sqlite3'
        self.base = SentProblemStore(self.path)
        self.store = RegionalStore(self.path)
        self.app = RegionalApplication.__new__(RegionalApplication)
        self.app.store = self.store
        self.app.service = Mock()
        self.app.prepare_lock = threading.Lock()
        self.app.qoj_statement = Mock(side_effect=AssertionError('unexpected QOJ request'))
        self.app.service.fetch_statement.side_effect = AssertionError('unexpected fetch')
        self.app.service._translate_and_cache_if_needed.side_effect = AssertionError('unexpected translation')
        self.chinese = ProblemStatement('x', '中文标题', '给定一个整数数组，求满足条件的排列。', '输入数组。', '输出排列。', [])
        self.english = ProblemStatement('x', 'Array order', 'You are given an array. Find a permutation satisfying all constraints.', 'Read the array elements.', 'Print the resulting permutation.', [])
        self.pid = 'icpc-2024-杭州:A'

    def tearDown(self):
        self.tmp.cleanup()

    def cache(self, statement, *, qoj=False, translated=True):
        p = self.store.problem(self.pid)
        problem = CFProblem(0, 'QOJ' + str(p['qoj_id']), '', 0) if qoj else CFProblem(p['cf_contest_id'], p['index'], '', 0)
        self.base.cache_statement(problem, statement, source='test', translated=translated)

    def test_chengdu_complete_and_other_contests_remain_on_demand(self):
        ready = self.store.wall(1)['ready']
        self.assertEqual(set(ready), {'icpc-2026-成都:' + letter for letter in 'ABCDEFGHIJKLM'})
        for pid in ready:
            _, statement = self.app.prepare(pid)
            self.assertTrue(statement.description)
            self.assertIn('/contest/4600/problem/', statement.source_url)
        h = self.app.prepare('icpc-2026-成都:H')[1]
        self.assertIn('2n-3', h.description)
        self.assertIn('自适应', h.description)
        self.assertIn('a_i>a_j', h.output_format)
        self.assertIn('! p_1 p_2 ... p_n', h.output_format)
        self.assertIn('? 1 2', h.hint)
        self.assertEqual(len(self.app.prepare('icpc-2026-成都:D')[1].samples), 2)
        self.app.qoj_statement.assert_not_called()

    def test_existing_training_cache_is_reused_and_survives_restart(self):
        self.cache(self.chinese)
        self.app.statement_json = Mock(return_value={'description': 'cached'})
        opened = self.app.post({'user_id': 1}, 'open', {'problemId': self.pid, 'prepareStatement': False})
        self.assertEqual(opened['statement'], {'description': 'cached'})
        self.assertEqual(self.app.prepare(self.pid)[1], self.chinese)
        self.assertEqual(RegionalStore(self.path).cached_statement(self.pid), self.chinese)
        self.app.service._translate_and_cache_if_needed.assert_not_called()

    def test_existing_qoj_cache_is_promoted_on_startup(self):
        self.cache(self.chinese, qoj=True)
        restarted = RegionalStore(self.path)
        self.assertIn(self.pid, restarted.wall(1)['ready'])
        self.assertEqual(restarted.cached_statement(self.pid), self.chinese)

    def test_raw_cached_statement_can_be_translated_without_refetch(self):
        self.cache(self.english, qoj=True, translated=False)
        self.app.service._translate_and_cache_if_needed.side_effect = None
        self.app.service._translate_and_cache_if_needed.return_value = self.chinese
        self.assertEqual(self.app.prepare(self.pid)[1], self.chinese)
        self.assertEqual(self.app.prepare(self.pid)[1], self.chinese)
        self.app.service._translate_and_cache_if_needed.assert_called_once()
        self.app.qoj_statement.assert_not_called()

    def test_failed_translation_keeps_raw_cache_for_retry(self):
        self.cache(self.english, translated=False)
        self.app.service._translate_and_cache_if_needed.side_effect = None
        self.app.service._translate_and_cache_if_needed.return_value = self.english
        with self.assertRaises(ChallengeError):
            self.app.prepare(self.pid)
        self.assertNotIn(self.pid, self.store.wall(1)['ready'])
        self.app.service._translate_and_cache_if_needed.return_value = self.chinese
        self.assertEqual(self.app.prepare(self.pid)[1], self.chinese)
        self.app.qoj_statement.assert_not_called()

    def test_english_is_not_ready_even_if_old_cache_flag_says_translated(self):
        self.cache(self.english, translated=True)
        restarted = RegionalStore(self.path)
        self.assertIsNone(restarted.cached_statement(self.pid))
        self.assertNotIn(self.pid, restarted.wall(1)['ready'])

    def test_existing_usable_local_statement_is_preserved(self):
        pid = 'icpc-2026-成都:H'
        with self.store.connect() as db:
            db.execute('update regional_statements set updated_at=? where problem_id=?', ('preserve-me', pid))
        RegionalStore(self.path)
        with self.store.connect() as db:
            self.assertEqual(db.execute('select updated_at from regional_statements where problem_id=?', (pid,)).fetchone()[0], 'preserve-me')

    def test_release_requires_verified_problem_alias(self):
        path = Path(self.tmp.name) / 'invalid.json'
        path.write_text(json.dumps({'published_at': 'now', 'problems': {self.pid: {'problem_key': 'qoj:0'}}}))
        with self.store.connect() as db, self.assertRaises(ValueError):
            seed_cached_statements(db, self.store.problems, path)


if __name__ == '__main__':
    unittest.main()
