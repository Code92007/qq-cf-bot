"""Offline, evidence-based regional ratings; CF scale anchors are heuristic."""
from __future__ import annotations

import hashlib
import json
import math

METHOD = 'standings-medal-v1'
ACCEPTED = {'ACCEPTED', 'CORRECT', 'OK', 'AC'}
REJECTED = {'WRONG_ANSWER', 'TIME_LIMIT_EXCEEDED', 'RUNTIME_ERROR', 'MEMORY_LIMIT_EXCEEDED',
            'OUTPUT_LIMIT_EXCEEDED', 'IDLENESS_LIMIT_EXCEEDED', 'NO_OUTPUT', 'REJECTED'}
IGNORED = {'COMPILATION_ERROR', 'PRESENTATION_ERROR', 'CONFIGURATION_ERROR', 'SYSTEM_ERROR',
           'CANCELED', 'SKIPPED'}


def summarize_standings(config, teams, runs):
    """Reconstruct official final standings using XCPCIO scoring/award rules."""
    problem_map = {str(p['id']): p['label'] for p in config['problems']}
    options = config.get('options', {})
    unit = options.get('submission_timestamp_unit', 'second')
    if unit not in {'second', 'millisecond'}:
        raise ValueError('Unsupported submission timestamp unit')
    clock_scale = 1000 if config['start_time'] > 100_000_000_000 else 1
    duration = (config['end_time'] - config['start_time']) / clock_scale
    if not 0 < duration <= 24 * 3600:
        raise ValueError('Invalid contest duration')
    all_teams = {str(t.get('id', t.get('team_id'))): t for t in teams}
    if len(all_teams) != len(teams) or 'None' in all_teams:
        raise ValueError('Duplicate or missing team IDs')
    official = {tid: t for tid, t in all_teams.items()
                if ('official' in t['group'] if 'group' in t else bool(t.get('official')))
                and not ('unofficial' in t.get('group', []) or t.get('unofficial'))}
    if not official:
        raise ValueError('No explicitly official teams')
    # A rejudged submission has one final verdict; do not count an earlier AC.
    final_runs = {}
    for i, run in enumerate(runs):
        rid = run.get('id', run.get('submission_id'))
        final_runs[('id', str(rid)) if rid is not None else ('row', i)] = run
    scores = {tid: {'solved': {}, 'wrong': {}, 'penalty': 0, 'last': 0} for tid in official}
    unlisted_runs = 0
    for run in sorted(final_runs.values(), key=lambda r: r['timestamp']):
        tid, problem = str(run['team_id']), str(run['problem_id'])
        if problem not in problem_map:
            raise ValueError('Unmapped submission problem')
        if tid not in all_teams:
            # Jury/system runs are present in several official raw exports.
            unlisted_runs += 1
            continue
        elapsed = run['timestamp'] / (1000 if unit == 'millisecond' else 1)
        if elapsed < 0 or elapsed >= duration or run.get('is_ignore', run.get('ignore', False)):
            continue
        status = run['status'].upper()
        if status not in ACCEPTED | REJECTED | IGNORED:
            raise ValueError(f'Unresolved/unknown verdict {status}: final standings required')
        if tid not in official:
            continue
        score = scores[tid]
        if problem in score['solved'] or status in IGNORED:
            continue
        if status in ACCEPTED:
            score['solved'][problem] = elapsed
            score['last'] = int(elapsed // 60)
            rule = options.get('calculation_of_penalty', 'in_minutes')
            accepted_time = elapsed if rule in {'in_seconds', 'accumulate_in_seconds_and_finally_to_the_minute'} else elapsed // 60 * 60
            score['penalty'] += accepted_time + score['wrong'].get(problem, 0) * config.get('penalty', 1200)
        else:
            score['wrong'][problem] = score['wrong'].get(problem, 0) + 1
    if options.get('calculation_of_penalty') == 'accumulate_in_seconds_and_finally_to_the_minute':
        for score in scores.values():
            score['penalty'] = int(score['penalty'] // 60) * 60
    ordered = sorted(scores, key=lambda tid: (-len(scores[tid]['solved']), scores[tid]['penalty'], scores[tid]['last'], tid))
    effective = sum(bool(s['solved']) for s in scores.values())
    medal = config.get('medal')
    if medal == 'ccpc':
        # Preset uses teams with >= 1 solve, cumulative ceil(10%/30%/60%).
        limits = [math.ceil(effective * x) for x in (0.1, 0.3, 0.6)]
        medal_rule = 'XCPCIO ccpc：正式有效队伍的 10% / 30% / 60% 累计名次，向上取整'
    elif isinstance(medal, dict) and 'official' in medal:
        counts = [int(medal['official'][m]) for m in ('gold', 'silver', 'bronze')]
        limits = [sum(counts[:i]) for i in (1, 2, 3)]
        medal_rule = 'XCPCIO config.medal.official：金银铜分别枚数，累计为名次分界'
    else:
        raise ValueError('Missing verified official medal rules')
    if not 0 < limits[0] < limits[1] < limits[2] <= len(official):
        raise ValueError('Invalid medal boundaries')
    cohorts = {m: [] for m in ('gold', 'silver', 'bronze')}
    previous_key, rank = None, 0
    for pos, tid in enumerate(ordered, 1):
        score = scores[tid]
        key = (len(score['solved']), score['penalty'], score['last'])
        if key != previous_key:
            rank = pos
        previous_key = key
        if score['solved']:
            for medal_name, limit in zip(cohorts, limits):
                if rank <= limit:
                    cohorts[medal_name].append(tid)
                    break
    boundaries = {}
    for medal_name, members in cohorts.items():
        if not members:
            raise ValueError('Empty medal cohort')
        last = scores[members[-1]]
        boundaries[medal_name] = {'teams': len(members), 'last_solved': len(last['solved']),
                                  'last_penalty_minutes': int(last['penalty'] // 60)}
    problems = {}
    for problem, label in problem_map.items():
        passed = {tid for tid in official if problem in scores[tid]['solved']}
        problems[label] = {
            'accepted_teams': len(passed), 'official_teams': len(official),
            'medal_accepted': {m: len(passed.intersection(members)) for m, members in cohorts.items()},
            'medal_teams': {m: len(members) for m, members in cohorts.items()},
        }
    return {'official_teams': len(official), 'effective_teams': effective,
            'excluded_teams': len(teams) - len(official), 'unlisted_team_runs': unlisted_runs,
            'duration_seconds': duration,
            'medal_rule': medal_rule, 'medal_rank_limits': dict(zip(cohorts, limits)),
            'medal_boundaries': boundaries, 'problems': problems}


def round_hundred(value):
    return int(math.floor(value / 100 + 0.5)) * 100


def rate_problem(stats, prior=None):
    """Medal-size anchors + cohort hard bounds; never infer official CF rating."""
    n, solved = stats['official_teams'], stats['accepted_teams']
    cohorts, accepted = stats['medal_teams'], stats['medal_accepted']
    gold = cohorts['gold']
    silver = gold + cohorts['silver']
    bronze = silver + cohorts['bronze']
    # Log(1+solvers) smooths the sparse tail. Actual medal counts adapt to each site.
    knots = [(0, 3300), (max(1, gold / 4), 2900), (gold, 2500),
             (silver, 2100), (bronze, 1700), ((bronze + n) / 2, 1300), (n, 800)]
    base = 800.0
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x0 <= solved <= x1:
            fraction = (math.log1p(solved) - math.log1p(x0)) / (math.log1p(x1) - math.log1p(x0))
            base = y0 + fraction * (y1 - y0)
            break
    base = round_hundred(base)
    low, high = max(800, base - 200), min(3500, base + 200)
    constraints = []
    if solved / n >= .8:
        high = min(high, 1400)
        constraints.append('正式队通过率至少 80%：上限 1400')
    for medal_name, ceiling in (('bronze', 1900), ('silver', 2300), ('gold', 2700)):
        if accepted[medal_name] / cohorts[medal_name] >= .6:
            high = min(high, ceiling)
            constraints.append(f'{medal_name} 队通过率至少 60%：上限 {ceiling}')
    if solved == 0:
        low = max(low, 3100)
        constraints.append('正式队零通过：下限 3100，稀疏证据')
    elif solved <= max(2, gold * .05):
        low = max(low, 2800)
        constraints.append('通过队数不超过 max(2,金牌队数×5%)：下限 2800')
    if low > high:
        raise ValueError('Contradictory statistical constraints')
    model_rating = prior.get('rating') if isinstance(prior, dict) else prior
    # Existing statement-only estimates may move the anchor by at most 100 points.
    rating = base
    if model_rating is not None:
        if isinstance(model_rating, bool) or not isinstance(model_rating, int) or not 800 <= model_rating <= 3500:
            raise ValueError('Invalid model prior')
        rating = round_hundred(base + max(-100, min(100, (model_rating - base) * .25)))
    rating = max(low, min(high, rating))
    source = '赛时通过队数 + 金银铜牌约束' + (' + 题面模型辅助' if model_rating is not None else '') + '，非官方 Rating'
    return {'rating': rating, 'source': source, 'range': [low, high], 'statistical_rating': base,
            'model_rating': model_rating, 'constraints': constraints, **stats}


def build_release(catalog, snapshot, revision, priors, path_for_contest):
    release = {'method': METHOD, 'source_revision': revision, 'scale': 'CF 风格经验分数，非官方 Rating',
               'contests': {}, 'problems': {}, 'unrated_contests': {}}
    for contest in catalog['contests']:
        path = path_for_contest(contest)
        evidence = contest.get('rating_evidence', {})
        if path is None:
            reason = evidence.get('unavailable_reason')
            if not reason:
                raise ValueError(f"Missing standings exclusion reason: {contest['id']}")
            release['unrated_contests'][contest['id']] = reason
            continue
        files = {name: (snapshot / path / (name + '.json')).read_bytes() for name in ('config', 'team', 'run')}
        config, teams, runs = (json.loads(files[name]) for name in ('config', 'team', 'run'))
        override = evidence.get('medal_override')
        if override:
            if config.get('medal') is not None or not override.get('source_url'):
                raise ValueError('Medal override requires a source and missing upstream rules')
            config['medal'] = {'official': override['counts']}
        summary = summarize_standings(config, teams, runs)
        for key, expected in evidence.get('expected_summary', {}).items():
            if summary[key] != expected:
                raise ValueError(f"Official report differs: {contest['id']} {key}")
        if override:
            summary['medal_rule'] = '主办方报告：金银铜分别枚数，累计为名次分界'
            summary['medal_source_url'] = override['source_url']
        if set(summary['problems']) != {p['index'] for p in contest['problems']}:
            raise ValueError(f"Contest problem labels differ: {contest['id']}")
        for problem in contest['problems']:
            pid = problem['id']
            result = rate_problem(summary['problems'][problem['index']], priors.get(pid))
            result.update({'contest': contest['id'], 'method': METHOD,
                           'standings_url': 'https://board.xcpcio.com/' + path.removeprefix('data/') + '/'})
            release['problems'][pid] = result
        summary.pop('problems')
        summary.update({'source_name': config['contest_name'],
                        'source_url': f'https://github.com/xcpcio/board-data/tree/{revision}/{path}',
                        'sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}})
        release['contests'][contest['id']] = summary
    return release
