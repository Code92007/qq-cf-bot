#!/usr/bin/env python3
"""Validate the maintained catalog without network or database access."""
import json
from collections import Counter
from pathlib import Path


def main():
    path = Path(__file__).resolve().parents[1] / 'src/qq_cf_bot/catalog/regionals.json'
    catalog = json.loads(path.read_text(encoding='utf-8'))
    contests, problems, aliases = set(), set(), {}
    counts = Counter()
    for contest in catalog['contests']:
        cid = contest['id']
        assert cid not in contests, f'Duplicate contest: {cid}'
        contests.add(cid)
        counts[contest['year'], contest['series']] += 1
        indices = set()
        for problem in contest['problems']:
            pid = problem['id']
            assert pid == cid + ':' + problem['index'], f'Unstable canonical ID: {pid}'
            assert pid not in problems and problem['index'] not in indices, f'Duplicate problem: {pid}'
            problems.add(pid)
            indices.add(problem['index'])
            assert problem['name'], f'Missing problem name: {pid}'
            assert problem['aliases'] or (problem.get('unmapped') and problem.get('mapping_status') == 'pending' and contest.get('ranklist_url')), f'Unexplained missing mapping: {pid}'
            if problem.get('qoj_id'):
                assert 'qoj:' + str(problem['qoj_id']) in problem['aliases'], pid
            if problem.get('cf_contest_id'):
                assert 'codeforces:' + str(problem['cf_contest_id']) + problem['index'] in problem['aliases'], pid
            for alias in problem['aliases']:
                assert alias not in aliases, f'Duplicate alias: {alias}'
                aliases[alias] = pid
    print(f'{len(contests)} contests / {len(problems)} problems / {len(aliases)} platform aliases')
    for (year, series), count in sorted(counts.items()):
        print(f'{year} {series}: {count} sites')


if __name__ == '__main__':
    main()
