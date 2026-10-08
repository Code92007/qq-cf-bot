import copy
import json
from pathlib import Path
import unittest

from qq_cf_bot.regional_rating import rate_problem, summarize_standings


class StandingsRatingTest(unittest.TestCase):
    def fixture(self):
        config = {'start_time': 1700000000, 'end_time': 1700018000, 'penalty': 1200,
                  'problems': [{'id': '1009', 'label': 'A'}, {'id': '1013', 'label': 'B'}],
                  'medal': {'official': {'gold': 1, 'silver': 1, 'bronze': 1}},
                  'options': {'submission_timestamp_unit': 'millisecond'}}
        teams = [{'id': str(i), 'group': ['official']} for i in range(1, 5)]
        teams += [{'id': 'star', 'group': ['unofficial']}]
        runs = [{'id': str(i), 'team_id': str(i), 'problem_id': '1009',
                 'timestamp': i * 60000, 'status': 'CORRECT'} for i in range(1, 5)]
        return config, teams, runs

    def test_official_unique_solves_real_labels_and_contest_window(self):
        config, teams, runs = self.fixture()
        runs += [
            {'id': 'again', 'team_id': '1', 'problem_id': '1009', 'timestamp': 300000, 'status': 'ACCEPTED'},
            {'id': 'star', 'team_id': 'star', 'problem_id': '1013', 'timestamp': 1000, 'status': 'ACCEPTED'},
            {'id': 'late', 'team_id': '1', 'problem_id': '1013', 'timestamp': 18000001, 'status': 'ACCEPTED'},
            {'id': 'jury', 'team_id': 'jury', 'problem_id': '1013', 'timestamp': 1000, 'status': 'ACCEPTED'},
        ]
        result = summarize_standings(config, teams, runs)
        self.assertEqual(result['problems']['A']['accepted_teams'], 4)
        self.assertEqual(result['problems']['B']['accepted_teams'], 0)
        self.assertEqual(result['problems']['A']['medal_accepted'], {'gold': 1, 'silver': 1, 'bronze': 1})
        self.assertEqual(result['excluded_teams'], 1)
        self.assertEqual(result['unlisted_team_runs'], 1)
        self.assertEqual(result['medal_boundaries']['gold']['last_penalty_minutes'], 1)

    def test_legacy_teams_seconds_and_final_rejudgement(self):
        config, teams, runs = self.fixture()
        config['options'] = {'calculation_of_penalty': 'accumulate_in_seconds_and_finally_to_the_minute'}
        for team in teams:
            team['team_id'] = team.pop('id')
            team['official'] = 'official' in team.pop('group')
        for run in runs:
            run['timestamp'] //= 1000
        runs += [
            {'id': 'ce', 'team_id': '1', 'problem_id': '1013', 'timestamp': 61, 'status': 'COMPILATION_ERROR'},
            {'id': 'wa', 'team_id': '1', 'problem_id': '1013', 'timestamp': 62, 'status': 'WRONG_ANSWER'},
            {'id': 'ac', 'team_id': '1', 'problem_id': '1013', 'timestamp': 63, 'status': 'ACCEPTED'},
            {'id': 'rejudge', 'team_id': '2', 'problem_id': '1013', 'timestamp': 50, 'status': 'ACCEPTED'},
            {'id': 'rejudge', 'team_id': '2', 'problem_id': '1013', 'timestamp': 50, 'status': 'WRONG_ANSWER'},
        ]
        result = summarize_standings(config, teams, runs)
        self.assertEqual(result['problems']['B']['accepted_teams'], 1)
        self.assertEqual(result['medal_boundaries']['gold']['last_solved'], 2)
        self.assertEqual(result['medal_boundaries']['gold']['last_penalty_minutes'], 22)

    def test_ccpc_preset_uses_effective_teams_and_includes_boundary_ties(self):
        config, teams, runs = self.fixture()
        config['medal'] = 'ccpc'
        teams = [{'id': str(i), 'official': True} for i in range(22)]
        runs = [{'team_id': str(i), 'problem_id': '1009', 'timestamp': (i + 1) * 60000,
                 'status': 'ACCEPTED'} for i in range(20)]
        runs[2]['timestamp'] = runs[1]['timestamp']
        result = summarize_standings(config, teams, runs)
        self.assertEqual(result['effective_teams'], 20)
        self.assertEqual(result['medal_rank_limits'], {'gold': 2, 'silver': 6, 'bronze': 12})
        self.assertEqual(result['medal_boundaries']['gold']['teams'], 3)
        self.assertEqual(result['medal_boundaries']['silver']['teams'], 3)

    def test_frozen_or_unmapped_final_data_is_rejected(self):
        config, teams, runs = self.fixture()
        runs[0]['status'] = 'FROZEN'
        with self.assertRaises(ValueError):
            summarize_standings(config, teams, runs)
        runs[0]['status'] = 'ACCEPTED'
        runs[0]['problem_id'] = '9999'
        with self.assertRaises(ValueError):
            summarize_standings(config, teams, runs)

    def test_model_cannot_escape_empirical_interval(self):
        stats = {'official_teams': 320, 'accepted_teams': 320,
                 'medal_teams': {'gold': 32, 'silver': 64, 'bronze': 96},
                 'medal_accepted': {'gold': 32, 'silver': 64, 'bronze': 96}}
        easy = rate_problem(stats, 3500)
        self.assertLessEqual(easy['rating'], 1000)
        self.assertLessEqual(easy['range'][1], 1400)
        unsolved = copy.deepcopy(stats)
        unsolved.update(accepted_teams=0, medal_accepted={'gold': 0, 'silver': 0, 'bronze': 0})
        hard = rate_problem(unsolved, 800)
        self.assertGreaterEqual(hard['rating'], 3100)

    def test_release_is_complete_auditable_and_obeys_all_intervals(self):
        directory = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((directory / 'regionals.json').read_text())
        release = json.loads((directory / 'regional_ratings.json').read_text())
        self.assertEqual(set(release['problems']), {p['id'] for c in catalog['contests'] for p in c['problems']})
        self.assertEqual(len(release['contests']), 33)
        for result in release['problems'].values():
            self.assertLessEqual(result['range'][0], result['rating'])
            self.assertLessEqual(result['rating'], result['range'][1])
            self.assertEqual(result['rating'] % 100, 0)
            self.assertLessEqual(result['accepted_teams'], result['official_teams'])
            self.assertEqual(result, {**rate_problem(result, result['model_rating']),
                                      'contest': result['contest'], 'method': result['method'],
                                      'standings_url': result['standings_url']})
        for contest in release['contests'].values():
            self.assertTrue(all(len(h) == 64 for h in contest['sha256'].values()))
