#!/usr/bin/env python3
"""Small independent oracles for the published 2026 Changchun explanations.

These are teaching/reference checks, not contest submissions or performance tests.
Run with Python 3.9+, optionally --report /path/to/report.json.
"""
import argparse
from collections import Counter, deque
from fractions import Fraction as Q
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, permutations, product
from math import comb, gcd
from pathlib import Path
import hashlib
import json
import random

RNG = random.Random(20261024)
REPORT = {}


def record(letter, cases, method):
    REPORT[letter] = {'cases': cases, 'method': method, 'passed': True}
    print(f'{letter}: {cases} cases passed ({method})', flush=True)


def check_a():
    cases = 0
    for n, m in [(1, 4), (2, 3), (3, 2)]:
        paths = []
        for l in range(m):
            for r in range(l, m):
                for rows in combinations_with_replacement(range(n), r-l+1):
                    paths.append(tuple(i*m+j for i, j in zip(rows, range(l, r+1))))

        @lru_cache(None)
        def oracle(a):
            if not any(a):
                return 0
            return 1+min(oracle(tuple(v-(i in p) for i, v in enumerate(a)))
                         for p in paths if all(a[i] for i in p))

        for a in product(range(2), repeat=n*m):
            ans = sum(a)
            for j in range(m-1):
                available = 0
                for i in range(n):
                    available += a[i*m+j]
                    take = min(available, a[i*m+j+1])
                    available -= take
                    ans -= take
            assert ans == oracle(a), (n, m, a)
            cases += 1
    record('A', cases, 'binary matrices: enumerate every legal operation and shortest clearing sequence')


def check_c_j_m():
    for _ in range(300):
        n = RNG.randrange(2, 9); k = RNG.randrange(2, n+1)
        a = [RNG.randrange(1, k+3) for _ in range(n)]
        cnt = Counter((v-1-i) % k for i, v in enumerate(a) if v <= k)
        got = n-max(cnt.values(), default=0)
        want = min(sum(v != (s+i) % k+1 for i, v in enumerate(a)) for s in range(k))
        assert got == want
    record('C', 300, 'all cyclic starting points as oracle')
    for _ in range(300):
        n = RNG.randrange(1, 4)
        rules = [(RNG.randrange(n), RNG.randrange(n), RNG.randrange(4)) for _ in range(RNG.randrange(7))]
        a = [0]*n
        for x, y, z in rules:
            a[x] |= z; a[y] |= z
        got = sum(a) if all(a[x] & a[y] == z for x, y, z in rules) else -1
        want = min((sum(v) for v in product(range(4), repeat=n)
                    if all(v[x] & v[y] == z for x, y, z in rules)), default=-1)
        assert got == want
    record('J', 300, 'enumerate all 2-bit arrays, including self constraints and contradictions')
    for _ in range(300):
        n = RNG.randrange(1, 9); upper = RNG.randrange(2, 10)
        a = [RNG.randrange(upper+1) for _ in range(n)]
        divs = [0]*(upper+1)
        for d in range(2, upper+1):
            for x in range(d, upper+1, d):
                divs[x] += 1
        got = 0
        for c in range(n):
            for left, right in [(c-1, c+1), (c, c+1)]:
                g = 0
                while left >= 0 and right < n:
                    g = gcd(g, abs(a[left]-a[right]))
                    got += divs[g] if g else upper-1
                    left -= 1; right += 1
        want = sum(1 for l in range(n) for r in range(l+1, n) for d in range(2, upper+1)
                   if (v := [x % d for x in a[l:r+1]]) == v[::-1])
        assert got == want
    record('M', 300, 'enumerate all intervals and moduli, compare elementwise palindromes')


def encode(p):
    majority = '0' if p.count('0') >= p.count('1') else '1'
    bit = int(p[0]); out = []
    for x in p:
        out.append(str(bit)*(1 if x == majority else 2)); bit ^= 1
    return ''.join(out)


def decode(q):
    runs = []
    for i, x in enumerate(q):
        if i == 0 or x != q[i-1]:
            runs.append(1)
        else:
            runs[-1] += 1
    majority = int(q[0]) ^ (runs[0] == 2)
    return ''.join(str(majority ^ (r == 2)) for r in runs)


def check_i():
    cases = 0
    for n in range(1, 13):
        seen = set()
        for p in map(''.join, product('01', repeat=n)):
            q = encode(p)
            assert len(q) <= 3*n//2 and '000' not in q and '111' not in q
            assert decode(q) == p and q not in seen
            seen.add(q); cases += 1
    record('I', cases, 'all binary strings length 1..12: size, forbidden triples, uniqueness, decoding')


SEEDS = [((1,1,1), [(1,2),(2,3),(1,4)], [1,2,4,3]),
         ((2,0,1), [(1,2),(2,3),(1,4)], [1,2,3,4]),
         ((0,2,1), [(1,2),(2,3),(1,4)], [1,3,4,2]),
         ((1,0,4), [(1,2),(2,3),(1,4),(1,6),(4,5)], [1,2,5,6,3,4]),
         ((0,1,5), [(1,2),(2,3),(1,5),(1,7),(3,4),(5,6)], [1,4,2,6,7,3,5]),
         ((0,0,7), [(1,2),(2,3),(3,4),(2,5),(1,6),(6,7),(1,8)], [1,4,5,6,3,8,7,2])]


def construct_e(a, b, c):
    if a+c == 0:
        return None
    if c == 0:
        order = list(range(0, b+2, 2))+list(range((b+1) if (b+1) % 2 else b, 0, -2))
        edges = [(i, i+1) for i in range(b+1)]
        for _ in range(a-1):
            y = len(order); edges.append((order[-1], y)); order.append(y)
        return [(u+1, v+1) for u, v in edges], [x+1 for x in order]
    base, ed, seq = next(row for row in SEEDS if all(x <= y for x, y in zip(row[0], (a,b,c))))
    edges, order = list(ed), list(seq)
    adj = {i: [] for i in order}
    for u, v in edges:
        adj[u].append(v); adj[v].append(u)
    x = order[-1]
    p, q = next((p, q) for p in adj[x] for q in adj[p] if q != x)
    for distance, count in enumerate((a-base[0], b-base[1], c-base[2]), 1):
        for _ in range(count):
            y = len(order)+1
            edges.append(((x, p, q)[distance-1], y)); order.append(y)
            x, p, q = (y, x, p) if distance == 1 else (y, p, q) if distance == 2 else (y, q, p)
    return edges, order


def tree_distances(edges, n):
    adj = [[] for _ in range(n+1)]
    for u, v in edges:
        assert 1 <= u <= n and 1 <= v <= n and u != v
        adj[u].append(v); adj[v].append(u)
    result = []
    for s in range(n+1):
        d = [-1]*(n+1); d[s] = 0; todo = deque([s])
        while todo:
            u = todo.popleft()
            for v in adj[u]:
                if d[v] < 0:
                    d[v] = d[u]+1; todo.append(v)
        result.append(d)
    return result


def check_e():
    cases = 0
    for n in range(8, 31):
        for a in range(n):
            for b in range(n-a):
                c = n-1-a-b; result = construct_e(a,b,c)
                if a+c == 0:
                    assert result is None
                else:
                    edges, order = result
                    assert len(edges) == n-1 and sorted(order) == list(range(1,n+1))
                    d = tree_distances(edges, n)
                    assert all(x >= 0 for x in d[1][1:])
                    counts = Counter(d[u][v] for u, v in zip(order, order[1:]))
                    assert counts == +Counter({1:a, 2:b, 3:c}), (n,a,b,c)
                cases += 1
    record('E', cases, 'all triples for n=8..30, check tree, permutation and actual BFS distances')


def solve_f(a):
    n = len(a)

    @lru_cache(None)
    def f(l, r, t):
        if t < 0: return 0
        if l > r: return 1
        if t == 0: return 0
        if t > r-l+1: return f(l, r, r-l+1)
        ans = f(l, r, t-1)
        for x in range(l, r+1):
            if a[x] not in (-1, t): continue
            ways = f(l,x-1,t-1)*f(x+1,r,t-1)-f(l,x-1,t-2)*f(x+1,r,t-2)
            ans += comb(r-l, x-l)*ways
        return ans

    @lru_cache(None)
    def u(l, r):
        if l > r: return 1
        if l > 0 and r < n-1: return f(l,r,n)
        return sum(comb(r-l,x-l)*u(l,x-1)*u(x+1,r)
                   for x in range(l,r+1) if a[x] in (-1,0))
    return u(0,n-1)


def deletion_times(p):
    alive = list(range(len(p))); times = [0]*len(p); tick = 0
    while True:
        dead = [alive[i] for i in range(1,len(alive)-1)
                if p[alive[i]] < p[alive[i-1]] and p[alive[i]] < p[alive[i+1]]]
        if not dead: return tuple(times)
        tick += 1
        for i in dead: times[i] = tick
        alive = [i for i in alive if i not in dead]


def check_f():
    cases = 0
    for n in range(2, 8):
        hist = Counter(deletion_times(p) for p in permutations(range(n)))
        queries = set(hist) | {(-1,)*n}
        queries |= {tuple(-1 if RNG.randrange(2) else x for x in RNG.choice(list(hist))) for _ in range(60)}
        queries |= {tuple(RNG.randrange(-1,n+1) for _ in range(n)) for _ in range(30)}
        for a in queries:
            want = sum(v for key, v in hist.items() if all(x == -1 or x == y for x,y in zip(a,key)))
            assert solve_f(a) == want, (a, solve_f(a), want)
            cases += 1
    record('F', cases, 'enumerate all permutations through n=7; synchronous deletion with exact and masked constraints')


def story(s):
    weights = []; last = -10
    for i, x in enumerate(s):
        if x == '1':
            if i-last == 2: weights[-1] += 1
            else: weights.append(1)
            last = i
    if not weights: return 1
    total = sum(weights); peak = max(weights); left = max(total % 2, 2*peak-total)
    if not left: return 1
    if 2*peak > total:
        at = weights.index(peak)
        return 2*left+1-(at == 0 and s[0] == '1')-(at == len(weights)-1 and s[-1] == '1')
    return 2 if s[0] == '1' or s[-1] == '1' else 3


@lru_cache(None)
def story_oracle(s):
    return min([len(s)]+[story_oracle(s[:i]+'0'+s[j:]) for i in range(len(s))
                        for j in range(i+2,len(s)+1,2) if s[i:j] == s[i:j][::-1]])


def check_l():
    cases = 0
    for n in range(1,12):
        for s in map(''.join, product('01', repeat=n)):
            assert story(s) == story_oracle(s), s
            cases += 1
    record('L', cases, 'all binary strings length 1..11, enumerate every even palindrome replacement')


def coefficients(a, b, target):
    for k in range(61):
        count = 1 << k; value = count*target; g = gcd(a,b)
        if value % g: continue
        p = (value//g * pow(a//g, -1, b//g)) % (b//g)
        q = (value-a*p)//b
        if q >= 0 and p+q <= count: return k,p,q
    return None


def average_layers(a, b, k, p, q):
    counts = Counter({0:(1 << k)-p-q,a:p,b:q}); layers = []
    for _ in range(k):
        counts = +counts; odd = [x for x in counts if counts[x] % 2]
        nxt = Counter(); parents = {}
        if odd:
            x,y = odd; assert (x+y) % 2 == 0
            take = min(counts[x], counts[y]); z = (x+y)//2
            counts[x] -= take; counts[y] -= take
            nxt[z] += take; parents[z] = (x,y)
        for x, count in counts.items():
            assert count % 2 == 0
            if count:
                nxt[x] += count//2; parents[x] = (x,x)
        counts = nxt; layers.append(parents)
        assert len(counts) <= 3
    return +counts, layers


def check_d():
    cases = 0
    for a in range(1,10):
        for b in range(a+1,11):
            reachable = [{0,a,b}]
            while True:
                old = reachable[-1]
                new = {(x+y)//2 for x in old for y in old if (x+y) % 2 == 0}
                if new == old: break
                reachable.append(new)
            for t in range(b+1):
                want = next((i for i,s in enumerate(reachable) if t in s), None)
                result = coefficients(a,b,t)
                assert (result[0] if result else None) == want, (a,b,t,result,want)
                if result:
                    k,p,q = result
                    top,layers = average_layers(a,b,k,p,q)
                    assert top == Counter({t:1})
                    for i, layer in enumerate(layers):
                        for parent, (x,y) in layer.items():
                            assert x in reachable[i] and y in reachable[i] and x+y == 2*parent
                cases += 1
    # The largest allowed coefficient scale also stays compressed and exact.
    k,p,q = 60,(1 << 59),(1 << 59)
    top,layers = average_layers(2,1 << 30,k,p,q)
    assert top == Counter({(2+(1 << 30))//2:1}) and len(layers) == 60
    record('D', cases+1, 'explicit reachable sets, minimal rounds, both branches at every layer, 60-level compression')


def check_g():
    for _ in range(350):
        n = RNG.randrange(1,7)
        intervals = list(combinations(range(n+1),2)); RNG.shuffle(intervals)
        edges = intervals[:RNG.randrange(1,min(8,len(intervals))+1)]
        target = RNG.randrange(1 << n)
        c = [0]+[(target >> i) & 1 for i in range(n)]+[0]
        bits = [c[i] ^ c[i+1] for i in range(n+1)]
        adj = [[] for _ in bits]
        for eid,(u,v) in enumerate(edges):
            adj[u].append((v,eid));adj[v].append((u,eid))
        tin = [-1]*(n+1); low = [0]*(n+1); sub = bits[:]; answer = [True]*len(edges); timer = [0]
        def dfs(u, pe=-1):
            tin[u] = low[u] = timer[0]; timer[0] += 1
            for v,eid in adj[u]:
                if eid == pe: continue
                if tin[v] < 0:
                    dfs(v,eid);sub[u] ^= sub[v];low[u] = min(low[u],low[v])
                    if low[v] > tin[u]: answer[eid] = sub[v] == 0
                else: low[u] = min(low[u],tin[v])
        valid = True
        for u in range(n+1):
            if tin[u] < 0:
                dfs(u);valid &= sub[u] == 0
        answer = [x and valid for x in answer]
        for banned in range(len(edges)):
            states = {0}
            for eid,(u,v) in enumerate(edges):
                if eid == banned: continue
                mask = ((1 << v)-1) ^ ((1 << u)-1)
                states |= {x ^ mask for x in states}
            assert answer[banned] == (target in states)
    record('G', 350, 'Tarjan answer versus all subsets of allowed interval flips for every banned edge')


def check_k():
    for _ in range(250):
        n = RNG.randrange(1,9); m = RNG.randrange(1,14)
        operations = [(RNG.randrange(2),RNG.randrange(1,n+1)) for _ in range(m)]
        segments = deque([(1,n,0)]); active = set()
        for idx,(side,x) in enumerate(operations,1):
            if side == 0:
                while segments and segments[0][1] <= x:
                    active.discard(segments.popleft()[2])
                if segments and segments[0][0] <= x:
                    l,r,color = segments.popleft(); segments.appendleft((x+1,r,color))
                segments.appendleft((1,x,idx))
            else:
                while segments and segments[-1][0] >= x:
                    active.discard(segments.pop()[2])
                if segments and segments[-1][1] >= x:
                    l,r,color = segments.pop(); segments.append((l,x-1,color))
                segments.append((x,n,idx))
            active.add(idx)
            for start in range(1,idx+1):
                cells = [0]*n
                for j in range(start,idx+1):
                    side,x = operations[j-1]
                    for pos in (range(x) if side == 0 else range(x-1,n)): cells[pos] = j
                want = len(set(cells)-{0})
                assert sum(color >= start for color in active) == want
    record('K', 250, 'deque and offline color filtering versus every query simulated on actual cells')


def gaussian(a, b):
    n = len(b); rows = [list(map(Q,row))+[Q(value)] for row,value in zip(a,b)]
    for col in range(n):
        pivot = next(r for r in range(col,n) if rows[r][col])
        rows[col],rows[pivot] = rows[pivot],rows[col]
        scale = rows[col][col]; rows[col] = [x/scale for x in rows[col]]
        for r in range(n):
            if r != col:
                factor = rows[r][col]
                rows[r] = [x-factor*y for x,y in zip(rows[r],rows[col])]
    return [row[-1] for row in rows]


def partitions(n, lo=1):
    if n == 0:
        yield ()
    for first in range(lo,n+1):
        for tail in partitions(n-first,first): yield (first,)+tail


def check_h():
    cases = 0
    for n in range(1,9):
        states = list(partitions(n)); ids = {s:i for i,s in enumerate(states)}
        mat = [[Q(int(i == j)) for j in range(len(states))] for i in range(len(states))]
        for i,s in enumerate(states):
            if len(s) == 1: continue
            den = sum(x*y for j,x in enumerate(s) for l,y in enumerate(s) if j != l)
            for j in range(len(s)):
                for l in range(len(s)):
                    if j == l: continue
                    t = list(s);t[j] -= 1;t[l] += 1;t = tuple(sorted(x for x in t if x))
                    mat[i][ids[t]] -= Q(s[j]*s[l],den)
        first = gaussian(mat,[int(len(s) > 1) for s in states])
        second = gaussian(mat,[2*first[i]-1 if len(s) > 1 else 0 for i,s in enumerate(states)])
        for i,s in enumerate(states):
            e1=e2=e3=0
            for x in s: e3 += e2*x;e2 += e1*x;e1 += x
            expected = Q((n*n-2)*e2-2*e2*e2+n*e3,3)
            assert expected == second[i]-first[i]*first[i]
            cases += 1
    record('H', cases, 'exact rational Markov-chain equations for every population partition n<=8')


def min_cost_flow(graph, source, sink, limit):
    flow=cost=0
    while flow < limit:
        dist=[10**30]*len(graph);dist[source]=0;prev=[None]*len(graph);todo=deque([source]);inside={source}
        while todo:
            u=todo.popleft();inside.remove(u)
            for i,(v,rev,cap,fee) in enumerate(graph[u]):
                if cap and dist[v] > dist[u]+fee:
                    dist[v]=dist[u]+fee;prev[v]=(u,i)
                    if v not in inside:todo.append(v);inside.add(v)
        if prev[sink] is None:break
        v=sink
        while v != source:
            u,i=prev[v];edge=graph[u][i];edge[2]-=1;graph[v][edge[1]][2]+=1;v=u
        flow+=1;cost+=dist[sink]
    return cost if flow == limit else -1


def check_b():
    for _ in range(200):
        modules=RNG.randrange(1,5);courses=RNG.randrange(2,7);slots=RNG.randrange(1,6);k=RNG.randrange(2,courses+1)
        parent=[-1]+[RNG.randrange(i) for i in range(1,modules+1)]
        weights=[0]
        for i in range(1,modules+1):weights.append(weights[parent[i]]+RNG.randrange(5))
        parent += [RNG.randrange(modules+1) for _ in range(courses)]
        options=[RNG.sample(range(slots),RNG.randrange(1,slots+1)) for _ in range(courses)]
        def ancestors(x):
            out=[]
            while x >= 0:out.append(x);x=parent[x]
            return out
        leaf_anc=[ancestors(modules+1+i) for i in range(courses)]
        def objective(chosen):
            direct=sum(weights[next(x for x in leaf_anc[i] if x in leaf_anc[j])] for i,j in combinations(chosen,2))
            transformed=sum((weights[u]-weights[parent[u]])*comb(sum(u in leaf_anc[i] for i in chosen),2) for u in range(1,modules+1))
            assert direct == transformed
            return direct
        best=None
        for chosen in combinations(range(courses),k):
            score=objective(chosen)
            if any(len(set(times)) == k for times in product(*(options[i] for i in chosen))):
                best=score if best is None else min(best,score)
        # Small expanded unit arcs are an independent check of the convex flow model.
        timebase=modules+courses+1;source=timebase+slots;sink=source+1;graph=[[] for _ in range(sink+1)]
        def add(u,v,cap,fee):
            graph[u].append([v,len(graph[v]),cap,fee]);graph[v].append([u,len(graph[u])-1,0,-fee])
        add(source,0,k,0)
        for u in range(1,modules+1):
            for f in range(k):add(parent[u],u,1,f*(weights[u]-weights[parent[u]]))
        for i in range(courses):
            u=modules+1+i;add(parent[u],u,1,0)
            for t in options[i]:add(u,timebase+t,1,0)
        for t in range(slots):add(timebase+t,sink,1,0)
        assert min_cost_flow(graph,source,sink,k) == (best if best is not None else -1)
    record('B', 200, 'LCA objective identity and convex flow model versus exhaustive course subsets and schedules')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    check_a();check_b();check_c_j_m();check_d();check_e();check_f();check_g();check_h();check_i();check_k();check_l()
    root=Path(__file__).resolve().parents[1]
    paths=sorted((root/'src/qq_cf_bot/catalog/editorials/2026').glob('ccpc-changchun-*.md'))
    result={'scope':'2026 CCPC Changchun A-M','seed':20261024,'status':'passed',
            'limitations':'Small-case correctness checks only; no online judge submissions or full-scale timing claims.',
            'checks':dict(sorted(REPORT.items())),
            'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'Total: {sum(x["cases"] for x in REPORT.values())} cases; all 13 problems checked.')


if __name__ == '__main__':
    main()
