import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from qq_cf_bot.regional_rating import build_release, rate_problem, summarize_standings, summarize_rankland, rankland_snapshot, summarize_final_scoreboard, medal_safety


class StandingsRatingTest(unittest.TestCase):
    def test_safe_medal_counts_use_best_team_outside_cumulative_tier(self):
        cohorts = {'gold': ['g'], 'silver': ['s'], 'bronze': ['b']}
        result = medal_safety({'g': 8, 's': 8, 'b': 6, 'iron': 3}, cohorts)
        self.assertEqual([result[m]['safe_solved'] for m in cohorts], [9, 7, 4])
        # A clear gap means the last gold count itself can already be safe.
        self.assertEqual(medal_safety({'g': 8, 's': 7, 'b': 6, 'iron': 3}, cohorts)['gold']['safe_solved'], 8)

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

    def test_report_backed_medals_and_explicit_missing_standings(self):
        config, teams, runs = self.fixture()
        config.pop('medal')
        config['contest_name'] = 'Historical contest'
        contest = {'id': 'old', 'problems': [{'id': 'old:A', 'index': 'A'}, {'id': 'old:B', 'index': 'B'}],
                   'rating_evidence': {'medal_override': {'counts': {'gold': 1, 'silver': 1, 'bronze': 1},
                                                        'source_url': 'https://organizer.example/report.pdf'},
                                       'expected_summary': {'official_teams': 4}}}
        unavailable = {'id': 'missing', 'problems': [{'id': 'missing:A', 'index': 'A'}],
                       'rating_evidence': {'unavailable_reason': 'No verified final standings'}}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, data in [('config', config), ('team', teams), ('run', runs)]:
                (directory / (name + '.json')).write_text(json.dumps(data))
            path_for = lambda c: '' if c['id'] == 'old' else None
            release = build_release({'contests': [contest, unavailable]}, directory, 'a' * 40, {}, path_for)
            self.assertEqual(set(release['problems']), {'old:A', 'old:B'})
            self.assertEqual(release['unrated_contests'], {'missing': 'No verified final standings'})
            self.assertEqual(release['contests']['old']['medal_source_url'], 'https://organizer.example/report.pdf')
            contest['rating_evidence']['expected_summary']['official_teams'] = 5
            with self.assertRaisesRegex(ValueError, 'Official report differs'):
                build_release({'contests': [contest]}, directory, 'a' * 40, {}, path_for)
            contest['rating_evidence'].pop('expected_summary')
            contest['rating_evidence']['medal_override'].pop('source_url')
            with self.assertRaisesRegex(ValueError, 'override requires a source'):
                build_release({'contests': [contest]}, directory, 'a' * 40, {}, path_for)
            unavailable['rating_evidence'].clear()
            with self.assertRaisesRegex(ValueError, 'exclusion reason'):
                build_release({'contests': [unavailable]}, directory, 'a' * 40, {}, path_for)

    def test_release_accounts_for_every_contest_and_obeys_all_intervals(self):
        directory = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((directory / 'regionals.json').read_text())
        release = json.loads((directory / 'regional_ratings.json').read_text())
        rated = release['contests']
        unrated = release['unrated_contests']
        self.assertFalse(set(rated).intersection(unrated))
        self.assertEqual(set(rated) | set(unrated), {c['id'] for c in catalog['contests']})
        self.assertEqual(set(release['problems']), {p['id'] for c in catalog['contests'] if c['id'] in rated for p in c['problems']})
        self.assertEqual(len(rated), 97)
        self.assertEqual(len(unrated), 7)
        self.assertEqual(len(release['problems']), 1231)
        self.assertTrue(all(unrated.values()))
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


class ArchivedFinalScoreboardTest(unittest.TestCase):
    def test_2026_chengdu_rebuilds_published_ratings_from_pinned_final_rows(self):
        directory = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((directory / 'regionals.json').read_text())
        contest = next(c for c in catalog['contests'] if c['id'] == 'icpc-2026-成都')
        release = json.loads((directory / 'regional_ratings.json').read_text())
        rebuilt = build_release({'contests': [contest]}, directory, release['source_revision'], {},
                                lambda c: c['rating_evidence']['standings_path'])
        self.assertEqual(contest['source_url'], 'https://qoj.ac/contest/4600')
        self.assertEqual(contest['qoj_url'], contest['source_url'])
        self.assertEqual(contest['qoj_contest_id'], 4600)
        self.assertEqual([p['index'] for p in contest['problems']], list('ABCDEFGHIJKLM'))
        self.assertEqual([p['qoj_id'] for p in contest['problems']], list(range(23592, 23605)))
        self.assertEqual(rebuilt['contests'][contest['id']], release['contests'][contest['id']])
        self.assertEqual(rebuilt['contests'][contest['id']]['official_teams'], 319)
        self.assertEqual(rebuilt['contests'][contest['id']]['excluded_teams'], 9)
        self.assertEqual([rebuilt['problems'][p['id']]['accepted_teams'] for p in contest['problems']],
                         [11, 1, 129, 312, 31, 0, 9, 26, 131, 0, 219, 0, 283])
        for pid, rating in rebuilt['problems'].items():
            self.assertEqual(rating, release['problems'][pid])

    def fixture(self):
        return {'schema': 'regional-final-scoreboard-v1', 'contest_id': 'old', 'labels': ['A', 'B'],
                'source_name': 'Archived contest', 'duration_seconds': 18000,
                'medal_rule': 'Original final awards', 'medal_source_url': 'https://organizer.example/awards',
                'source_sha256': {'https://organizer.example/board': 'a' * 64},
                'teams': [{'id': str(i), 'official': i != 0, 'solved': 1,
                           'penalty_seconds': i * 60, 'accepted': ['A'],
                           'medal': {1: 'gold', 2: 'silver', 3: 'bronze'}.get(i)} for i in range(5)]}

    def test_explicit_awards_and_starred_rows(self):
        result = summarize_final_scoreboard(self.fixture(), 'old')
        self.assertEqual(result['official_teams'], 4)
        self.assertEqual(result['excluded_teams'], 1)
        self.assertEqual(result['problems']['A']['medal_accepted'], {'gold': 1, 'silver': 1, 'bronze': 1})
        self.assertEqual(result['problems']['B']['accepted_teams'], 0)

    def test_snapshot_changes_and_catalog_label_mismatches_are_rejected(self):
        raw = json.dumps(self.fixture()).encode()
        contest = {'id': 'old', 'problems': [{'id': 'old:A', 'index': 'A'}, {'id': 'old:B', 'index': 'B'}],
                   'rating_evidence': {'provider': 'final-scoreboard', 'source_url': 'https://organizer.example/board',
                                       'sha256': hashlib.sha256(raw).hexdigest()}}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            snapshot = directory / 'board.json'
            snapshot.write_bytes(raw)
            build = lambda: build_release({'contests': [contest]}, directory, 'a' * 40, {}, lambda c: 'board.json')
            self.assertEqual(len(build()['problems']), 2)
            snapshot.write_bytes(raw + b'\n')
            with self.assertRaisesRegex(ValueError, 'snapshot hash differs'):
                build()
            snapshot.write_bytes(raw)
            contest['problems'][1]['index'] = 'C'
            with self.assertRaisesRegex(ValueError, 'problem labels differ'):
                build()

    def test_inconsistent_or_ambiguous_archives_fail_closed(self):
        for mutate in [lambda d: d.update(contest_id='wrong'),
                       lambda d: d['teams'][1].update(id='0'),
                       lambda d: d['teams'][1].update(official=1),
                       lambda d: d['teams'][1].update(solved=2),
                       lambda d: d['teams'][1].update(accepted=['Z']),
                       lambda d: d['teams'][0].update(medal='gold'),
                       lambda d: d['teams'][2].update(medal='bronze'),
                       lambda d: d['teams'][1].update(penalty_seconds=float('nan'))]:
            data = self.fixture()
            mutate(data)
            with self.assertRaises(ValueError):
                summarize_final_scoreboard(data, 'old')

    def test_every_pinned_historical_snapshot_reproduces_published_statistics(self):
        directory = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog'
        catalog = json.loads((directory / 'regionals.json').read_text())
        published = json.loads((directory / 'regional_ratings.json').read_text())
        contests = [c for c in catalog['contests'] if c.get('rating_evidence', {}).get('provider') == 'final-scoreboard']
        self.assertEqual(len(contests), 20)
        release = build_release({'contests': contests}, directory, published['source_revision'], {},
                                lambda c: c['rating_evidence']['standings_path'])
        for pid, result in release['problems'].items():
            self.assertEqual(result, published['problems'][pid])
        self.assertEqual(published['contests']['icpc-2019-香港']['medal_boundaries']['gold']['teams'], 4)
        self.assertEqual(published['contests']['ccpc-2018-秦皇岛']['medal_boundaries']['gold']['teams'], 26)


class RanklandRatingTest(unittest.TestCase):
    def fixture(self):
        rows = []
        for group in ['undergraduate', 'hv']:
            for i in range(4):
                statuses = [{'result': 'AC', 'time': [i + 1, 'min']},
                            {'result': 'FB', 'time': [10, 'min']} if i == 0 else {'result': 'RJ'}]
                rows.append({'user': {'id': group + str(i), 'official': True, 'markers': [group]},
                             'score': {'value': 2 if i == 0 else 1, 'time': [20 + i, 'min']}, 'statuses': statuses})
        rows.append({'user': {'id': 'star', 'official': False}, 'score': {'value': 2, 'time': [1, 'min']},
                     'statuses': [{'result': 'AC', 'time': [1, 'min']}] * 2})
        series = [{'segments': [{'style': m} for m in ['gold', 'silver', 'bronze']],
                   'rule': {'preset': 'ICPC', 'options': {'filter': {'byMarker': g}, 'count': {'value': [1, 1, 1]}}}}
                  for g in ['undergraduate', 'hv']]
        return {'info': {'uniqueKey': 'ccpc-test'}, 'srk': {'type': 'general', 'sorter': {'algorithm': 'ICPC'},
                'contest': {'title': 'Test', 'duration': [5, 'h']}, 'problems': [{'alias': 'A'}, {'alias': 'B'}],
                'rows': rows, 'series': series}}

    def test_grouped_medals_exclude_starred_and_keep_separate_cohorts(self):
        summary = summarize_rankland(json.dumps(self.fixture()).encode(), 'ccpc-test')
        self.assertEqual(summary['official_teams'], 8)
        self.assertEqual(summary['excluded_teams'], 1)
        self.assertEqual(summary['problems']['B']['accepted_teams'], 2)
        self.assertEqual(summary['problems']['B']['medal_accepted'], {'gold': 2, 'silver': 0, 'bronze': 0})
        self.assertEqual(summary['problems']['A']['medal_teams'], {'gold': 2, 'silver': 2, 'bronze': 2})

    def test_frozen_missing_medals_ambiguous_teams_and_wrong_scores_rejected(self):
        for mutate in [lambda d: d['srk']['rows'][0]['statuses'][0].update(result='FZ'),
                       lambda d: d['srk']['rows'][0]['score'].update(value=1),
                       lambda d: d['srk']['rows'][0]['user'].update(official=1),
                       lambda d: d['srk']['series'][0]['rule']['options']['count'].update(value=[0, 0, 0]),
                       lambda d: d['info'].update(uniqueKey='another-contest')]:
            data = self.fixture()
            mutate(data)
            with self.assertRaises(ValueError):
                summarize_rankland(json.dumps(data).encode(), 'ccpc-test')

    def test_published_snapshot_is_pinned_and_page_counters_do_not_affect_it(self):
        data = self.fixture()
        for row in data['srk']['rows']:
            if row['user']['id'].endswith('1'):
                row['statuses'][1] = {'result': 'AC', 'time': [10, 'min']}
                row['score']['value'] = 2
        first = rankland_snapshot(json.dumps(data).encode())
        data['info']['viewCnt'] = 123
        self.assertEqual(rankland_snapshot(json.dumps(data).encode()), first)
        contest = {'id': 'test', 'problems': [{'id': 'test:A', 'index': 'A'}, {'id': 'test:B', 'index': 'B'}],
                   'rating_evidence': {'provider': 'rankland', 'rankland_key': 'ccpc-test',
                                       'source_url': 'https://rl.algoux.cn/ranklist/ccpc-test',
                                       'sha256': hashlib.sha256(first).hexdigest()}}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'standings.json').write_bytes(first)
            release = build_release({'contests': [contest]}, directory, 'a' * 40, {}, lambda c: 'standings.json')
            self.assertEqual(release['problems']['test:B']['accepted_teams'], 4)
            (directory / 'standings.json').write_bytes(first + b' ')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                build_release({'contests': [contest]}, directory, 'a' * 40, {}, lambda c: 'standings.json')
