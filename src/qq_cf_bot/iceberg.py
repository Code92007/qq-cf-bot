"""Owner-scoped knowledge achievements, derived from accepted code evidence."""
from __future__ import annotations

import json
import random
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from .core import ChallengeError

TZ = timezone(timedelta(hours=8))
# Broad platform tags never expand into all algorithms in that field.
PLATFORM_TAGS = {
    'brute force': 'basic-enumerate', 'binary search': 'basic-binary',
    'greedy': 'basic-greedy', 'divide and conquer': 'basic-divide-and-conquer',
    'sortings': 'basic-sort-intro', 'two pointers': 'misc-two-pointer',
    'dp': 'dp-basic', 'strings': 'string-basic',
    'trees': 'graph-tree-basic', 'shortest paths': 'graph-shortest-path',
    'bitmasks': 'math-bit', 'constructive algorithms': 'basic-construction',
    'dsu': 'ds-dsu', 'fft': 'math-poly-fft',
    'combinatorics': 'math-combinatorics-combination',
    'ternary search': 'misc-ternary-search', 'meet-in-the-middle': 'search-meet-in-middle',
    '2-sat': 'graph-2-sat', 'probabilities': 'math-probability-basic',
    'dfs and similar': 'search-dfs',
    'fenwick tree': 'ds-fenwick', 'binary indexed tree': 'ds-fenwick',
    'segment tree': 'ds-seg', 'ntt': 'math-poly-ntt', 'kmp': 'string-kmp',
    'lca': 'graph-lca', 'scc': 'graph-scc', 'bfs': 'search-bfs',
    'dijkstra': 'graph-shortest-path', 'minimum spanning tree': 'graph-mst',
    'maximum flow': 'graph-flow-max-flow', 'min cost flow': 'graph-flow-min-cost',
    'convex hull': 'geometry-convex-hull', 'suffix automaton': 'string-sam',
    'suffix array': 'string-sa', 'trie': 'string-trie', 'heavy light decomposition': 'graph-hld',
    'implementation': 'basic-simulate',
    # Exact Luogu algorithm labels whose wording differs from the atlas.
    '动态规划 DP': 'dp-basic', '高精度': 'math-bignum', '莫队': 'misc-mo-algo',
    '堆': 'ds-binary-heap', '优先队列': 'ds-binary-heap', '递归': 'basic-divide-and-conquer',
    '剪枝': 'search-backtracking', '启发式迭代加深搜索 IDA*': 'search-idastar',
    '爬山算法 Local search': 'misc-hill-climbing', '分治': 'basic-divide-and-conquer',
    '颜色段均摊（珂朵莉树 ODT）': 'misc-odt', '原根': 'math-number-theory-primitive-root',
    '后缀自动机 SAM': 'string-sam', '凸完全单调性（wqs 二分）': 'dp-opt-wqs-binary-search',
    '四边形不等式': 'dp-opt-quadrangle', '最近公共祖先 LCA': 'graph-lca',
    '欧拉回路': 'graph-euler', '仙人掌': 'graph-cactus',
    '一般图的最大匹配': 'graph-graph-matching-general-match',
    '动态树 LCT': 'ds-lct', '最大公约数 gcd': 'math-number-theory-gcd',
    '扩展欧几里德算法': 'math-number-theory-bezouts', '进制': 'math-numeral-sys-base',
    '置换': 'math-permutation', 'Pólya 定理': 'math-combinatorics-polya',
    '中国剩余定理 CRT': 'math-number-theory-crt', '前缀和': 'basic-prefix-sum',
    '差分': 'basic-prefix-sum', '鸽笼原理': 'math-combinatorics-drawer-principle',
    'Fibonacci 数列': 'math-fibonacci', 'Catalan 数': 'math-combinatorics-catalan',
    'Stirling 数': 'math-combinatorics-stirling', 'A*  算法': 'search-astar',
    '逆元': 'math-number-theory-inverse', '向量': 'geometry-2d', '叉积': 'geometry-2d',
    '字典树 Trie': 'string-trie', 'KMP 算法': 'string-kmp', '后缀数组 SA': 'string-sa',
    '快速傅里叶变换 FFT': 'math-poly-fft', '快速数论变换 NTT': 'math-poly-ntt',
    '回文自动机 PAM': 'string-pam', '快速沃尔什变换 FWT': 'math-poly-fwt',
    '快速莫比乌斯变换 FMT': 'math-subset-transform', 'Manacher 算法': 'string-manacher',
    '结构体': 'basic-struct-class', '吉司机线段树 segment tree beats': 'ds-seg-beats',
    '线段树合并': 'ds-seg-merge-split', '动态树分治': 'graph-dynamic-tree-divide',
    'Berlekamp-Massey(BM) 算法': 'math-berlekamp-massey', '杨表': 'math-young-tableau',
    '欧拉降幂': 'math-number-theory-fermat', '拉格朗日插值法': 'math-numerical-interp',
    'SG 函数': 'math-game-theory-impartial-game', '整除分块': 'math-number-theory-sqrt-decomposition',
    '弦图': 'graph-chord', 'Dirichlet 卷积': 'math-number-theory-dirichlet',
    '大步小步算法 BSGS': 'math-number-theory-discrete-logarithm',
    'Bézout 定理': 'math-number-theory-bezouts', 'bitset': 'ds-bitset',
    '特征值': 'math-eigen', '最大流最小割定理': 'graph-flow-max-flow',
    '线性筛法': 'math-number-theory-sieve', '斜率维护技巧 slope trick': 'dp-opt-slope-trick',
    '闵可夫斯基和 Minkowski sum': 'minkowski', '二区间合并（猫树分治）': 'ds-cat-tree',
    'KTT / Kinetic Tournament Tree': 'ds-kinetic-tournament-tree', 'Hall 定理': 'graph-hall',
    # Reviewed synonyms only: atlas search aliases also contain ambiguous names
    # such as "Tarjan", "平衡树" and "树套树", so they cannot all be tags.
    'DFS': 'search-dfs', '深度优先搜索 DFS': 'search-dfs',
    'BFS': 'search-bfs', '广度优先搜索 BFS': 'search-bfs',
    '二分': 'basic-binary', '双指针 two-pointer': 'misc-two-pointer',
    '折半搜索 meet in the middle': 'search-meet-in-middle',
    'cdq': 'misc-cdq-divide', 'sparse table': 'ds-sparse-table',
    'chinese remainder theorem': 'math-number-theory-crt',
    '字符串': 'string-basic', '字符串（入门）': 'string-basic',
    '树的遍历': 'graph-tree-basic', '树论': 'graph-tree-basic',
    '素数判断': 'math-number-theory-prime', '矩阵加速': 'math-linear-algebra-matrix',
    '线性递推': 'basic-recurrence', '轮廓线 DP': 'dp-state',
    '二项式定理': 'math-combinatorics-combination', 'Floyd 算法': 'graph-shortest-path',
    '二次剩余': 'math-number-theory-quad-residue', '线段相交': 'geometry-2d',
}


def tag_key(value):
    return re.sub(r'[\s_–—-]+', '', unicodedata.normalize('NFKC', str(value)).casefold())


def timestamp(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            stamp = float(value)
        else:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            stamp = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
        return int(stamp) if 0 < stamp <= time.time() + 86400 else None
    except (ValueError, TypeError, OverflowError):
        return None


def problem_url(key):
    platform, pid = key.split(':', 1)
    if platform == 'codeforces' and (match := re.fullmatch(r'(\d+)([A-Z][A-Z0-9]*)', pid)):
        contest, index = match.groups()
        return f'https://codeforces.com/{"gym" if int(contest) >= 100000 else "contest"}/{contest}/problem/{index}'
    if platform == 'luogu':
        return 'https://www.luogu.com.cn/problem/' + pid
    if platform == 'qoj':
        return 'https://qoj.ac/problem/' + pid
    if platform == 'atcoder' and '_' in pid:
        return f'https://atcoder.jp/contests/{pid.rsplit("_", 1)[0].lower()}/tasks/{pid.lower()}'
    return ''


def merge_records(rows):
    result = {}
    for row in rows:
        key = row['key']
        item = result.setdefault(key, {'key': key, 'title': row.get('title') or key, 'firstAt': None, 'lastAt': None, 'tags': set(), 'days': set(), 'sources': set()})
        if row.get('title') and item['title'] == key:
            item['title'] = row['title']
        for field, choose in [('firstAt', min), ('lastAt', max)]:
            stamp = timestamp(row.get(field))
            if stamp:
                item[field] = choose(item[field], stamp) if item[field] else stamp
                item['days'].add(datetime.fromtimestamp(stamp, TZ).date().isoformat())
        item['days'].update(day for day in row.get('days', []) if isinstance(day, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day))
        item['tags'].update(t for t in row.get('tags', []) if isinstance(t, str))
        item['sources'].add(row.get('source', 'OJ Wall'))
    return result


def validate_knowledge(value):
    if not isinstance(value, dict) or value.get('version') != 1 or value.get('complete') is not True or not isinstance(value.get('records'), list):
        raise ValueError('知识点 AC 快照不完整')
    for row in value['records']:
        if (not isinstance(row, dict) or not isinstance(row.get('key'), str)
                or not re.fullmatch(r'[a-z][a-z0-9]{1,24}:[A-Za-z0-9_:-]{1,100}', row['key'])
                or row.get('kind') not in {'personal', 'team'}
                or not isinstance(row.get('tags'), list) or any(not isinstance(t, str) or len(t) > 100 for t in row['tags'])
                or not isinstance(row.get('days'), list)
                or any(not isinstance(d, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', d) for d in row['days'])
                or any(row.get(k) is not None and timestamp(row[k]) is None for k in ('firstAt', 'lastAt'))
                or (row.get('firstAt') is not None and row.get('lastAt') is not None and row['firstAt'] > row['lastAt'])):
            raise ValueError('知识点 AC 记录格式错误')
        try:
            for day in row['days']:
                datetime.fromisoformat(day)
        except ValueError:
            raise ValueError('知识点 AC 日期错误') from None
    return value


class IcebergAchievements:
    def __init__(self, web):
        self.web = web
        self.store = web.regionals.store
        self.atlas = json.loads((web.static_dir / 'iceberg-data.json').read_text())
        self.topics = {t['id']: t for t in self.atlas['topics']}
        self.canonical = {}
        for p in self.store.problems.values():
            aliases = p.get('aliases', [])
            if aliases:
                primary = min(aliases, key=lambda key: (not key.startswith('codeforces:'), key))
                self.canonical.update({key: primary for key in aliases})
        # Public, reviewed problem references complement platforms' coarse tags.
        # They are intersected with this owner's real AC history below.
        catalog = json.loads((self.web.static_dir.parent / 'catalog/iceberg-problem-topics.json').read_text())
        self.references = {}
        for entry in catalog['entries']:
            key = self.canonical.get(entry['problemKey'], entry['problemKey'])
            self.references.setdefault(key, {})[entry['topicId']] = entry['source']
        self.tags = {tag_key(t['title']): t['id'] for t in self.topics.values()}
        self.tags.update({tag_key(k): v for k, v in PLATFORM_TAGS.items() if v in self.topics})
        self.cache_stamp = None
        self.metadata = {}
        with self.store.connect() as db:
            db.execute('create table if not exists iceberg_links(user_id integer,problem_key text,topic_id text,primary key(user_id,problem_key,topic_id))')

    def cached_metadata(self):
        path = self.web.service.cf.cache_path
        try:
            stamp = path.stat().st_mtime_ns
            if stamp != self.cache_stamp:
                data = json.loads(path.read_text()).get('result', {}).get('problems', [])
                metadata = {'codeforces:' + str(p['contestId']) + str(p['index']).upper(): p for p in data if p.get('contestId') and p.get('index')}
                self.metadata, self.cache_stamp = metadata, stamp
        except (OSError, ValueError, TypeError):
            pass
        return self.metadata

    def records(self, user, teams=False):
        rows = []
        connection = self.web.regionals.wall_connection
        wall = connection.state(user)
        with self.store.connect() as db:
            linked = db.execute('select body from cpc_wall_links where user_id=?', (user,)).fetchone()
            knowledge = json.loads(linked['body']).get('knowledge') if linked else None
            wall['knowledgeReady'] = isinstance(knowledge, dict)
            if knowledge:
                for record in knowledge['records']:
                    if record['kind'] == 'personal' or teams:
                        rows.append({**record, 'source': 'OJ Wall · ' + ('团队' if record['kind'] == 'team' else '个人')})
            # Shared problems and virtual contests count too; oral judgements do not.
            for row in db.execute("select c.cf_id,c.created_at,s.name,s.tags_json from code_submissions c left join sent_problems s on s.group_id=c.group_id and s.cf_id=c.cf_id where c.group_id='-1' and c.user_id=? and c.accepted=1 and upper(c.verdict) in ('AC','OK','ACCEPTED')", (str(user),)):
                rows.append({'key': 'codeforces:' + row['cf_id'], 'title': row['name'], 'tags': json.loads(row['tags_json'] or '[]'), 'firstAt': row['created_at'], 'lastAt': row['created_at'], 'source': 'CF Bot'})
            for row in db.execute("select problem_id,created_at from regional_attempts where user_id=? and kind='code' and upper(verdict) in ('AC','OK','ACCEPTED')", (user,)):
                p = self.store.problems.get(row['problem_id'], {})
                key = next(iter(p.get('aliases', [])), None)
                if key:
                    rows.append({'key': key, 'title': p.get('name'), 'firstAt': row['created_at'], 'lastAt': row['created_at'], 'source': 'CF Bot 区域赛'})
            for row in db.execute("select problem_key,submitted_at from regional_evidence where user_id=? and upper(verdict) in ('AC','OK','ACCEPTED')", (user,)):
                rows.append({'key': row['problem_key'], 'firstAt': row['submitted_at'], 'lastAt': row['submitted_at'], 'source': '账号同步 / 导入'})
            links = [dict(r) for r in db.execute('select problem_key,topic_id from iceberg_links where user_id=?', (user,))]
        records = merge_records([{**r, 'key': self.canonical.get(r['key'], r['key'])} for r in rows])
        metadata = self.cached_metadata()
        for key, item in records.items():
            p = metadata.get(key, {})
            item['tags'].update(p.get('tags', []))
            item['rating'] = p.get('rating')
            item['url'] = problem_url(key)
            item['referenceTopics'] = self.references.get(key, {})
            item['topicIds'] = sorted({self.tags[tag_key(t)] for t in item['tags'] if tag_key(t) in self.tags} | item['referenceTopics'].keys())
            item['manualTopicIds'] = []
        for link in links:
            item = records.get(self.canonical.get(link['problem_key'], link['problem_key']))
            if item and link['topic_id'] in self.topics:
                item['manualTopicIds'].append(link['topic_id'])
                item['topicIds'] = sorted(set(item['topicIds']) | {link['topic_id']})
        return records, wall

    def state(self, session, teams=False):
        records, wall = self.records(int(session['user_id']), teams)
        topics = {}
        for tid in self.topics:
            matched = [r for r in records.values() if tid in r['topicIds']]
            first = min((r['firstAt'] for r in matched if r['firstAt']), default=None)
            last = max((r['lastAt'] for r in matched if r['lastAt']), default=None)
            topics[tid] = {'count': len(matched), 'firstAt': first, 'lastAt': last, 'undated': sum(r['firstAt'] is None for r in matched), 'problemKeys': [r['key'] for r in sorted(matched, key=lambda r: -(r['lastAt'] or 0))]}
        serialized = [{**r, **{k: sorted(r[k]) for k in ('tags', 'days', 'sources')}} for r in records.values()]
        years = sorted({d[:4] for r in serialized for d in r['days']}, reverse=True)
        topic_days = {tid: sorted({d for r in serialized if tid in r['topicIds'] for d in r['days']}) for tid in topics}
        return {'user': {'displayName': session['display_name']}, 'csrfToken': session['csrf_token'], 'now': int(time.time()), 'teams': teams, 'wall': wall, 'topics': topics, 'problems': serialized,
                'summary': {'solved': len(records), 'lit': sum(t['count'] > 0 for t in topics.values()), 'mapped': sum(bool(r['topicIds']) for r in serialized), 'undated': sum(r['firstAt'] is None for r in serialized)},
                'memories': {'all': self.memory(serialized, topics, topic_days), **{year: self.memory(serialized, topics, topic_days, year) for year in years}}}

    def memory(self, records, topics, topic_days, year=None):
        selected = [r for r in records if any(d.startswith(year) for d in r['days'])] if year else records
        unlocked = [tid for tid, t in topics.items() if t['firstAt'] and (not year or datetime.fromtimestamp(t['firstAt'], TZ).strftime('%Y') == year)]
        counts = Counter(t for r in selected for t in r['topicIds'])
        days = Counter(d for r in selected for d in r['days'] if not year or d.startswith(year))
        favorite = counts.most_common(1)
        peak = sorted(days.items(), key=lambda x: (-x[1], x[0]))[:1]
        deepest = max(unlocked, key=lambda t: (self.topics[t]['tier'], self.topics[t]['difficulty']), default=None)
        returns = []
        for tid in topics:
            dates = topic_days[tid]
            for before, after in zip(dates, dates[1:]):
                if year and not after.startswith(year):
                    continue
                gap = (datetime.fromisoformat(after) - datetime.fromisoformat(before)).days
                if gap >= 30:
                    returns.append({'topic': tid, 'days': gap, 'date': after})
        first_events = [(d, r) for r in selected for d in r['days'] if not year or d.startswith(year)]
        first = min(first_events, key=lambda event: (event[0], event[1]['key']), default=None)
        return {'solved': len(selected), 'newTopics': len(unlocked), 'activeDays': len(days), 'first': {'key': first[1]['key'], 'title': first[1]['title'], 'date': first[0]} if first else None,
                'favorite': {'topic': favorite[0][0], 'count': favorite[0][1]} if favorite else None,
                'peak': {'date': peak[0][0], 'count': peak[0][1]} if peak else None, 'deepest': deepest,
                'comeback': max(returns, key=lambda r: r['days'], default=None),
                'timeline': [{'topic': tid, 'at': topics[tid]['firstAt']} for tid in sorted(unlocked, key=lambda tid: (topics[tid]['firstAt'], tid))]}

    def link(self, session, payload):
        user = int(session['user_id'])
        tid, key = str(payload.get('topicId') or ''), str(payload.get('problemKey') or '')
        if tid not in self.topics:
            raise ValueError('请选择地图中的知识点。')
        records, _ = self.records(user, bool(payload.get('teams')))
        if key not in records:
            raise ValueError('只能关联你已有的 AC 题目。请先同步做题记录。')
        with self.store.connect() as db:
            if payload.get('remove') is True:
                db.execute('delete from iceberg_links where user_id=? and problem_key=? and topic_id=?', (user, key, tid))
            else:
                db.execute('insert or ignore into iceberg_links values (?,?,?)', (user, key, tid))
        return {'ok': True}

    def recommendations(self, session, handler):
        query = parse_qs(urlsplit(getattr(handler, 'path', '')).query)
        tid = query.get('topic', [''])[0]
        if tid not in self.topics:
            raise ChallengeError('invalid_topic', '请选择一个知识点。', 400)
        try:
            low, high = int(query.get('minRating', ['800'])[0]), int(query.get('maxRating', ['3500'])[0])
        except ValueError:
            raise ChallengeError('invalid_rating', '难度范围不正确。', 400)
        if not 800 <= low <= high <= 3500:
            raise ChallengeError('invalid_rating', '难度范围应在 800–3500 之间。', 400)
        records, _ = self.records(int(session['user_id']), query.get('teams') == ['1'])
        candidates = []
        for key, p in self.cached_metadata().items():
            rating = p.get('rating')
            canonical = self.canonical.get(key, key)
            if canonical in records or not isinstance(rating, int) or not low <= rating <= high:
                continue
            if tid in {self.tags.get(tag_key(t)) for t in p.get('tags', [])} or tid in self.references.get(canonical, {}):
                candidates.append({'key': key, 'title': p['name'], 'rating': rating, 'tags': p.get('tags', []), 'url': problem_url(key)})
        random.shuffle(candidates)
        return {'topic': tid, 'total': len(candidates), 'problems': candidates[:6]}
