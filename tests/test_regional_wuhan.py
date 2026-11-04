import json
from pathlib import Path
import unittest

from qq_cf_bot.regional_rating import build_release


class Wuhan2026Test(unittest.TestCase):
    def test_verified_mapping_and_ratings_rebuild_from_anonymous_final(self):
        root = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((root / 'regionals.json').read_text())
        contest = next(c for c in catalog['contests'] if c['id'] == 'icpc-2026-武汉')
        published = json.loads((root / 'regional_ratings.json').read_text())
        self.assertEqual(contest['qoj_contest_id'], 4616)
        self.assertEqual([p['qoj_id'] for p in contest['problems']], list(range(23656, 23669)))
        rebuilt = build_release({'contests': [contest]}, root, published['source_revision'], {},
                                lambda c: c['rating_evidence']['standings_path'])
        self.assertEqual(rebuilt['contests'][contest['id']], published['contests'][contest['id']])
        self.assertEqual(rebuilt['contests'][contest['id']]['official_teams'], 369)
        self.assertEqual(rebuilt['contests'][contest['id']]['excluded_teams'], 69)
        self.assertEqual([rebuilt['problems'][p['id']]['accepted_teams'] for p in contest['problems']],
                         [369,55,2,328,3,3,95,0,19,117,232,4,0])
        for pid, rating in rebuilt['problems'].items():
            self.assertEqual(rating, published['problems'][pid])

    def test_large_exponents_samples_and_interactive_protocols_survive_pdf_import(self):
        root = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot'
        release = json.loads((root / 'catalog/regional_statements.json').read_text())
        statements = {letter: release['problems']['icpc-2026-武汉:' + letter]['statement']
                      for letter in 'ABCDEFGHIJKLM'}
        self.assertIn('2^{200000}', statements['B']['input_format'])
        self.assertIn('10^{300}', statements['C']['input_format'])
        self.assertEqual(statements['C']['samples'],
                         [['3 2 2\n2','4'], ['2 297 1\n9876543210','216768474'], ['97 10 0\n2','193']])
        self.assertEqual(len(statements['H']['samples']), 4)
        for letter in 'EL':
            statement = statements[letter]
            self.assertIn('交互协议', statement['input_format'])
            self.assertIn('刷新输出缓冲区', statement['input_format'])
            self.assertIn('自适应', statement['input_format'])
            image = f'statement-wuhan-2026-{letter.lower()}-interaction.png'
            self.assertIn('/' + image, statement['hint'])
            self.assertTrue((root / 'web' / image).is_file())
        self.assertIn('至多三次', statements['E']['input_format'])
        self.assertIn('n −1 次', statements['L']['input_format'])
