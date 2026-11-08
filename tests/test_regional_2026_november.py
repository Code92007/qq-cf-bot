import copy
import json
from pathlib import Path
import tempfile
import unittest

from qq_cf_bot.regional_rating import build_release


class Leshan2026Test(unittest.TestCase):
    def test_official_final_reproduces_every_published_problem_and_medal_boundary(self):
        root = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((root / 'regionals.json').read_text())
        contest = next(c for c in catalog['contests'] if c['id'] == 'ccpc-2026-乐山')
        published = json.loads((root / 'regional_ratings.json').read_text())
        rebuilt = build_release({'contests': [contest]}, root, published['source_revision'], {},
                                lambda c: c['rating_evidence']['standings_path'])
        self.assertEqual(rebuilt['contests'][contest['id']], published['contests'][contest['id']])
        summary = rebuilt['contests'][contest['id']]
        self.assertEqual((summary['official_teams'], summary['effective_teams'], summary['excluded_teams']),
                         (300, 299, 48))
        self.assertEqual([rebuilt['problems'][p['id']]['accepted_teams'] for p in contest['problems']],
                         [1, 0, 36, 299, 4, 16, 184, 53, 3, 261, 34, 278, 189])
        for pid, rating in rebuilt['problems'].items():
            self.assertEqual(rating, published['problems'][pid])
        self.assertEqual([(b['last_solved'], b['last_penalty_minutes']) for b in summary['medal_boundaries'].values()],
                         [(7, 783), (5, 533), (4, 487)])
        chengdu = next(c for c in catalog['contests'] if c['id'] == 'icpc-2026-成都')
        self.assertEqual(chengdu['qoj_contest_id'], 4607)
        self.assertEqual(chengdu['source_url'], 'https://qoj.ac/contest/4607')
        self.assertEqual([p['qoj_id'] for p in chengdu['problems']], list(range(23592, 23605)))

    def test_modified_evidence_cannot_silently_republish_ratings(self):
        root = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((root / 'regionals.json').read_text())
        contest = copy.deepcopy(next(c for c in catalog['contests'] if c['id'] == 'ccpc-2026-乐山'))
        relative = contest['rating_evidence']['standings_path']
        raw = (root / relative).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            target = snapshot / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(raw + b'\n')
            with self.assertRaisesRegex(ValueError, 'snapshot hash differs'):
                build_release({'contests': [contest]}, snapshot, 'a' * 40, {}, lambda c: relative)


class Nanjing2026Test(unittest.TestCase):
    def test_final_standings_support_ratings_without_a_practice_link(self):
        root = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((root / 'regionals.json').read_text())
        contest = next(c for c in catalog['contests'] if c['id'] == 'icpc-2026-南京')
        published = json.loads((root / 'regional_ratings.json').read_text())
        release = build_release({'contests': [contest]}, root, published['source_revision'], {},
                                lambda c: c['rating_evidence']['standings_path'])
        self.assertEqual(release['contests'][contest['id']], published['contests'][contest['id']])
        summary = release['contests'][contest['id']]
        self.assertEqual((summary['official_teams'], summary['effective_teams'], summary['excluded_teams']),
                         (332, 326, 42))
        self.assertEqual([(b['last_solved'], b['last_penalty_minutes']) for b in summary['medal_boundaries'].values()],
                         [(6, 1042), (4, 745), (2, 152)])
        self.assertEqual([release['problems'][p['id']]['accepted_teams'] for p in contest['problems']],
                         [5, 9, 294, 47, 0, 144, 10, 152, 4, 1, 323, 0, 62])
        for p in contest['problems']:
            self.assertEqual(release['problems'][p['id']], published['problems'][p['id']])
            self.assertTrue(p['unmapped'])
            self.assertEqual(p['mapping_status'], 'pending')
            self.assertEqual(p['aliases'], [])
