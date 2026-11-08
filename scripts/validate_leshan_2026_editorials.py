"""Independent small-instance checks for the Leshan tutorials."""
import itertools
import json
import math
import random
from pathlib import Path

RNG = random.Random(4685)
MOD = 998244353
checks = {}


def done(letter, count, detail):
    checks[letter] = dict(passed=True, cases=count, detail=detail)
    print(letter, count, detail, flush=True)


def robot(a):
    m = max(a)
    ids = [i + 1 for i, x in enumerate(a) if x == m]
    return ids[-1] if m % 2 else ids[0]


def robot_brute(a):
    a = list(a)
    last = None
    for turn in range(max(a)):
        for i in (range(len(a)) if turn % 2 == 0 else reversed(range(len(a)))):
            if a[i]:
                a[i] -= 1
                last = i + 1
    return last


def frontier(points):
    answer = []
    best = -1
    for p, d in sorted(points, reverse=True):
        if d > best:
            answer.append((p, d))
            best = d
    return answer[::-1]


def equipment(left, right, cap):
    a = frontier(left)
    b = frontier(right)[::-1]
    answer = 0

    def solve(lo, hi, qlo, qhi):
        nonlocal answer
        if lo > hi:
            return
        mid = (lo + hi) // 2
        p, d = a[mid]
        best = -1
        arg = qlo
        for j in range(qlo, qhi + 1):
            q, e = b[j]
            value = min(p + q, cap) * (d + e)
            if value > best:
                best, arg = value, j
        answer = max(answer, best)
        solve(lo, mid - 1, qlo, arg)
        solve(mid + 1, hi, arg, qhi)

    solve(0, len(a) - 1, 0, len(b) - 1)
    return answer


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(2)) % MOD for j in range(2)] for i in range(2)]


def sticks(x, a):
    result = [[1, 0], [0, 1]]
    for i in range(len(x) - 1):
        gap = x[i + 1] - x[i]
        mat = [[int(a[i + 1] <= gap), 1], [int(a[i] + a[i + 1] <= gap), int(a[i] <= gap)]]
        result = multiply(result, mat)
    return sum(map(sum, result)) % MOD


def sticks_brute(x, a):
    answer = 0
    for dirs in itertools.product([0, 1], repeat=len(x)):
        intervals = [(p - length, p) if d == 0 else (p, p + length) for p, length, d in zip(x, a, dirs)]
        answer += all(min(r, rr) <= max(l, ll) for i, (l, r) in enumerate(intervals) for ll, rr in intervals[:i])
    return answer


def timetables(a, u):
    p = len(a)
    if any(l > r for l, r in zip(a, u)):
        return 0
    cuts = sorted(set(a + [x + 1 for x in u]))
    dp = [1] + [0] * p
    for lo, hi in zip(cuts, cuts[1:]):
        length = hi - lo
        ndp = dp[:]
        choose = [math.comb(length, h) if h <= length else 0 for h in range(p + 1)]
        for k in range(p):
            for h in range(1, p - k + 1):
                if a[k + h - 1] <= lo and u[k] >= hi - 1:
                    ndp[k + h] += dp[k] * choose[h]
        dp = [v % MOD for v in ndp]
    return dp[p]


def det(matrix):
    a = [row[:] for row in matrix]
    answer = 1
    for col in range(len(a)):
        pivot = next((r for r in range(col, len(a)) if a[r][col] % MOD), None)
        if pivot is None:
            return 0
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            answer = -answer
        value = a[col][col] % MOD
        answer = answer * value % MOD
        inv = pow(value, MOD - 2, MOD)
        for r in range(col + 1, len(a)):
            factor = a[r][col] * inv % MOD
            for j in range(col, len(a)):
                a[r][j] = (a[r][j] - factor * a[col][j]) % MOD
    return answer % MOD


def rooted_forests(w, r, x, y):
    n = len(w)
    mat = []
    for i in range(r, n):
        mat.append([sum(w[i]) if i == j else -w[i][j] for j in range(r, n)])
    for i in range(r, n):
        mat[i - r][x - r] = w[i][y]
    return det(mat)


def forest_brute(w, r, x, y):
    n = len(w)
    answer = 0
    for targets in itertools.product(range(n), repeat=n - r):
        if any(j == i for i, j in enumerate(targets, r)):
            continue
        value = math.prod(w[i][j] for i, j in enumerate(targets, r))
        if not value:
            continue
        roots = []
        for i in range(r, n):
            seen = set()
            while i >= r and i not in seen:
                seen.add(i)
                i = targets[i - r]
            if i >= r:
                break
            roots.append(i)
        if len(roots) == n - r and roots[x - r] == y:
            answer += value
    return answer % MOD


def mice(a):
    if a.count(0) > 1:
        return -1
    a = sorted(a)
    k = len(a)

    def feasible(m):
        sums = [1]
        c = 1
        for h in range(1, m + 1):
            c = c * (m - h + 1) // h
            sums.append(min(k, sums[-1] + c))
            if sums[-1] == k:
                break
        return all(sums[min(bound, len(sums) - 1)] >= i for i, bound in enumerate(a, 1))

    lo, hi = 0, k - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def mice_brute(a):
    for m in range(len(a)):
        masks = list(range(1 << m))
        match = {}

        def augment(i, seen):
            for mask in masks:
                if bin(mask).count('1') <= a[i] and mask not in seen:
                    seen.add(mask)
                    if mask not in match or augment(match[mask], seen):
                        match[mask] = i
                        return True
            return False

        if all(augment(i, set()) for i in range(len(a))):
            return m
    return -1


def direction(p):
    x, y = p
    g = math.gcd(x, y)
    return x // g, y // g


def polar_key(p):
    return math.atan2(p[1], p[0])


def hull_valid(points):
    dirs = sorted(set(map(direction, points)), key=polar_key)
    return len(dirs) >= 3 and all(a[0] * b[1] - a[1] * b[0] >= 0 for a, b in zip(dirs, dirs[1:] + dirs[:1]))


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def hull_brute(points):
    points = sorted(set(points))
    lo, hi = [], []
    for a in points:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], a) <= 0:
            lo.pop()
        lo.append(a)
    for a in reversed(points):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], a) <= 0:
            hi.pop()
        hi.append(a)
    h = lo[:-1] + hi[:-1]
    return len(h) >= 3 and all(cross(a, b, (0, 0)) >= 0 for a, b in zip(h, h[1:] + h[:1]))


def letters(s):
    n = len(s)
    dp = [[-10**9, -10**9] for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n):
        for t in range(2):
            if dp[i][t] < 0:
                continue
            last = s[i - 1 - t] if i else None
            dp[i + 1][0] = max(dp[i + 1][0], dp[i][t] + (last == s[i]))
            if i + 1 < n:
                dp[i + 2][1] = max(dp[i + 2][1], dp[i][t] + (last == s[i + 1]) + (s[i + 1] == s[i]))
    return max(dp[n])


def letters_brute(s):
    best = 0

    def dfs(i, a):
        nonlocal best
        if i >= len(a) - 1:
            best = max(best, sum(x == y for x, y in zip(a, a[1:])))
            return
        dfs(i + 1, a)
        a[i], a[i + 1] = a[i + 1], a[i]
        dfs(i + 2, a)
        a[i], a[i + 1] = a[i + 1], a[i]

    dfs(0, list(s))
    return best


def triplet_partition(points):
    a = sorted(points)
    mid = len(a) // 2
    left, right = a[:mid], a[mid:]
    b = sorted(left, key=lambda p: p[1])
    c = sorted(right, key=lambda p: p[2])
    query = (a[mid][0], b[len(b) // 2][1], c[len(c) // 2][2])
    groups = {}
    for point in points:
        reply = tuple(int(q > v) for q, v in zip(query, point))
        groups.setdefault(reply, []).append(point)
    assert max(map(len, groups.values())) <= (len(points) + 3) // 4
    return groups


def main():
    count = 0
    for n in range(1, 7):
        for a in itertools.product(range(1, 5), repeat=n):
            assert robot(a) == robot_brute(a)
            count += 1
    done('D', count, '穷举 n≤6、食材数1..4，与逐轮模拟比较')
    count = 0
    for _ in range(3000):
        slots = [[(RNG.randrange(15), RNG.randrange(15)) for _ in range(RNG.randint(1, 3))] for _ in range(6)]
        left = [tuple(map(sum, zip(*xs))) for xs in itertools.product(*slots[:3])]
        right = [tuple(map(sum, zip(*xs))) for xs in itertools.product(*slots[3:])]
        cap = RNG.randint(1, 60)
        expected = max(min(p + q, cap) * (d + e) for p, d in left for q, e in right)
        assert equipment(left, right, cap) == expected
        count += 1
    # Arbitrary frontiers are stronger than only testing sums of three slots.
    for _ in range(3000):
        left = [(RNG.randrange(50), RNG.randrange(50)) for _ in range(RNG.randint(1, 30))]
        right = [(RNG.randrange(50), RNG.randrange(50)) for _ in range(RNG.randint(1, 30))]
        cap = RNG.randint(1, 100)
        assert equipment(left, right, cap) == max(min(p + q, cap) * (d + e) for p, d in left for q, e in right)
        count += 1
    done('F', count, '三槽折半与任意前沿随机数据，对比笛卡尔积穷举；含封顶、零属性、重复点')
    count = 0
    for _ in range(2000):
        n = RNG.randint(1, 8)
        x = sorted(RNG.sample(range(-15, 16), n))
        a = [RNG.randint(1, 20) for _ in x]
        for _ in range(4):
            assert sticks(x, a) == sticks_brute(x, a)
            a[RNG.randrange(n)] = RNG.randint(1, 20)
            count += 1
    done('G', count, '随机初值与点修改，与全部2^n朝向的任意两区间检测比较')
    count = 0
    for _ in range(4000):
        p = RNG.randint(1, 5)
        a = sorted(RNG.sample(range(8), p))
        u = sorted(RNG.sample(range(-2, 10), p))
        expected = sum(all(l <= v <= r for l, v, r in zip(a, ts, u)) for ts in itertools.combinations(range(10), p))
        assert timetables(a, u) == expected
        count += 1
    for _ in range(1500):
        n = RNG.randint(2, 6)
        r = RNG.randint(1, n - 1)
        w = [[RNG.randrange(4) if i != j else 0 for j in range(n)] for i in range(n)]
        x, y = RNG.randrange(r, n), RNG.randrange(r)
        assert rooted_forests(w, r, x, y) == forest_brute(w, r, x, y)
        count += 1
    done('I', count, '4000组边权DP对比严格递增时刻穷举；1500组换列行列式对比所有下一站选择及逐点根检测')
    count = 0
    for n in range(1, 7):
        for a in itertools.combinations_with_replacement(range(4), n):
            assert mice(list(a)) == mice_brute(a)
            count += 1
    done('J', count, '小规模所有非降瓶数，与死活位掩码二分图最大匹配比较')
    count = 0
    grid = [(x, y) for x in range(-3, 4) for y in range(-3, 4) if x or y]
    for _ in range(2500):
        a = RNG.sample(grid, RNG.randint(3, 12))
        for lo in range(len(a)):
            for hi in range(lo + 1, len(a) + 1):
                assert hull_valid(a[lo:hi]) == hull_brute(a[lo:hi])
                count += 1
    done('K', count, '极角判据对比单调链凸包及逐边原点检测；含同射线、反向、共线、原点在边界')
    count = 0
    for n in range(1, 10):
        for chars in itertools.product('ab', repeat=n):
            s = ''.join(chars)
            assert letters(s) == letters_brute(s)
            count += 1
    for _ in range(1500):
        s = ''.join(RNG.choices('abc', k=RNG.randint(1, 12)))
        assert letters(s) == letters_brute(s)
        count += 1
    done('L', count, '全部二元短串及三元随机串，对比所有不相交相邻交换集合')
    count = 0
    for _ in range(1500):
        n = RNG.randint(2, 200)
        cols = [RNG.sample(range(1, n + 1), n) for _ in range(3)]
        pending = [list(zip(*cols))]
        depth = 0
        while any(len(s) > 1 for s in pending):
            pending = [g for s in pending for g in (triplet_partition(s).values() if len(s) > 1 else [s])]
            depth += 1
        assert depth <= math.ceil(math.log(n, 4))
        count += 1
    assert 4**10 >= 10**6
    done('M', count, '遍历每个可能回复分支验证最坏剩余候选数与查询深度；自适应交互器同样适用')
    path = Path(__file__).resolve().parents[1] / 'leshan-method-checks.json'
    path.write_text(json.dumps(dict(seed=4685, checks=checks), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
