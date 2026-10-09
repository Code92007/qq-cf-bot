#!/usr/bin/env python3
"""Build a reproducible offline rating release from pinned XCPCIO standings."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
SITES = dict(zip(
    ['哈尔滨', '济南', '郑州', '重庆', '上海', '南京', '成都', '武汉', '沈阳', '西安', '香港', '桂林', '深圳', '秦皇岛', '合肥', '杭州', '澳门', '昆明'],
    ['harbin', 'jinan', 'zhengzhou', 'chongqing', 'shanghai', 'nanjing', 'chengdu', 'wuhan', 'shenyang', 'xian', 'hongkong', 'guilin', 'shenzhen', 'qinhuangdao', 'hefei', 'hangzhou', 'macau', 'kunming'],
))


def board_path(contest):
    if 'rating_evidence' in contest:
        evidence = contest['rating_evidence']
        if evidence.get('unavailable_reason'):
            return None
        return evidence['standings_path']
    if contest['year'] < 2023:
        raise ValueError(f"Historical standings source must be verified: {contest['id']}")
    series = contest['series'].lower()
    edition = (contest['year'] - 1975 if series == 'icpc' else contest['year'] - 2014)
    return f"data/{series}/{edition}th/{SITES[contest['site']]}"


def download(snapshot, revision, contest):
    path = board_path(contest)
    if path is None:
        return
    directory = snapshot / path
    directory.mkdir(parents=True, exist_ok=True)
    for name in ('config', 'team', 'run'):
        target = directory / (name + '.json')
        if target.exists():
            continue
        url = f'https://raw.githubusercontent.com/xcpcio/board-data/{revision}/{path}/{name}.json'
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={'User-Agent': 'regional-rating-builder/1.0'}), timeout=25) as response:
                    raw = response.read()
                json.loads(raw)
                target.write_bytes(raw)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)
    print('downloaded', contest['id'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True, help='Pinned full board-data commit SHA')
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--priors', type=Path, help='Optional existing model ratings, keyed by canonical problem ID')
    parser.add_argument('--output', type=Path, default=ROOT / 'src/qq_cf_bot/catalog/regional_ratings.json')
    args = parser.parse_args()
    if len(args.revision) != 40 or any(c not in '0123456789abcdef' for c in args.revision):
        parser.error('revision must be a full Git commit SHA')
    catalog = json.loads((ROOT / 'src/qq_cf_bot/catalog/regionals.json').read_text())
    if args.download:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda c: download(args.snapshot, args.revision, c), catalog['contests']))
    from qq_cf_bot.regional_rating import build_release
    priors = json.loads(args.priors.read_text()) if args.priors else {}
    if 'problems' in priors:
        priors = {pid: p['model_rating'] for pid, p in priors['problems'].items() if p.get('model_rating') is not None}
    release = build_release(catalog, args.snapshot, args.revision, priors, board_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(release, ensure_ascii=False, indent=2) + '\n')
    print(f"Published artifact: {len(release['contests'])} contests, {len(release['problems'])} ratings -> {args.output}")


if __name__ == '__main__':
    main()
