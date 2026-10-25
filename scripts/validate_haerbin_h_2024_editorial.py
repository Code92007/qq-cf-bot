"""Independent checks for the run-length Euclidean matrix algorithm in Harbin H."""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

MOD = 998244353
RNG = random.Random(20241020)


def identity(n):
    return tuple(int(i == j) for i in range(n) for j in range(n))


def multiply(a, b, n):
    c = [0] * (n * n)
    for i in range(n):
        for k in range(i, n):
            if a[i*n+k]:
                for j in range(k, n):
                    c[i*n+j] += a[i*n+k] * b[k*n+j]
        for j in range(i, n):
            c[i*n+j] %= MOD
    return tuple(c)


def power(a, e, n):
    out = identity(n)
    while e:
        if e & 1:
            out = multiply(out, a, n)
        a = multiply(a, a, n)
        e //= 2
    return out


def append_run(runs, length, matrix):
    if not length:
        return
    if runs and runs[-1][1] == matrix:
        runs[-1] = (runs[-1][0] + length, matrix)
    else:
        runs.append((length, matrix))


def reverse_tail(runs):
    first = runs[0][1]
    tail = [(runs[0][0] - 1, first)] + runs[1:]
    out = [(1, first)]
    for length, matrix in reversed(tail):
        append_run(out, length, matrix)
    return out


class ProductTree:
    def __init__(self, values, dimension):
        self.dimension = dimension
        self.size = 1
        while self.size < len(values):
            self.size *= 2
        self.nodes = [identity(dimension)] * (2 * self.size)
        self.nodes[self.size:self.size+len(values)] = values
        for p in range(self.size - 1, 0, -1):
            self.nodes[p] = multiply(self.nodes[2*p], self.nodes[2*p+1], dimension)

    def set(self, p, value):
        p += self.size
        self.nodes[p] = value
        while p > 1:
            p //= 2
            self.nodes[p] = multiply(self.nodes[2*p], self.nodes[2*p+1], self.dimension)


def fold_columns(runs, d, dimension):
    events = {}
    counts, choices, values = [], [], []
    start = 0
    for i, (length, matrix) in enumerate(runs):
        end = start + length
        q = length // d
        low = power(matrix, q, dimension)
        high = multiply(low, matrix, dimension)
        count = (end - 1) // d - (start - 1) // d
        counts.append(count)
        choices.append((q, low, high))
        values.append(low if count == q else high)
        for boundary, delta in ((start % d, 1), (end % d, -1)):
            if boundary:
                events.setdefault(boundary, []).append((i, delta))
        start = end
    tree = ProductTree(values, dimension)
    out, previous = [], 0
    for boundary in sorted(set(events) | {d}):
        append_run(out, boundary - previous, tree.nodes[1])
        for i, delta in events.get(boundary, []):
            counts[i] += delta
            q, low, high = choices[i]
            assert counts[i] in (q, q+1)
            tree.set(i, low if counts[i] == q else high)
        previous = boundary
    assert sum(length for length, _ in out) == d
    return out


def shuffled_product(runs, d, dimension):
    length = sum(x for x, _ in runs)
    assert math.gcd(length, d) == 1
    while length > 1:
        if 2*d > length:
            runs = reverse_tail(runs)
            d = length - d
        else:
            runs = fold_columns(runs, d, dimension)
            length, d = d, d - length % d
        assert sum(x for x, _ in runs) == length
    return runs[0][1]


def transition(value, target):
    n = len(target) + 1
    a = list(identity(n))
    for i, v in enumerate(target):
        if v == value:
            a[i*n+i+1] = 1
    return tuple(a)


def count_rle(rle, target, k):
    length = sum(x for x, _ in rle)
    runs = []
    for count, value in rle:
        append_run(runs, count, transition(value, target))
    return shuffled_product(runs, pow(k, -1, length), len(target)+1)[len(target)]


def direct(rle, target, k):
    sequence = [v for length, v in rle for _ in range(length)]
    shuffled = [None] * len(sequence)
    for i, v in enumerate(sequence):
        shuffled[i*k % len(sequence)] = v
    dp = [1] + [0] * len(target)
    for v in shuffled:
        for j in range(len(target)-1, -1, -1):
            if target[j] == v:
                dp[j+1] = (dp[j+1] + dp[j]) % MOD
    return dp[-1]


def validate():
    cases = 0
    # Test the noncommutative reduction independently of subsequence matrices.
    for _ in range(1200):
        length = RNG.randint(2, 70)
        dimension = RNG.randint(2, 5)
        d = RNG.choice([x for x in range(1, length) if math.gcd(x, length) == 1])
        runs = []
        remaining = length
        while remaining:
            count = RNG.randint(1, remaining)
            matrix = tuple(RNG.randrange(4) if i <= j else 0
                           for i in range(dimension) for j in range(dimension))
            append_run(runs, count, matrix)
            remaining -= count
        expanded = [v for count, v in runs for _ in range(count)]
        expected = identity(dimension)
        for i in range(length):
            expected = multiply(expected, expanded[i*d % length], dimension)
        assert shuffled_product(runs, d, dimension) == expected
        cases += 1
    for _ in range(2000):
        length = RNG.randint(2, 100)
        k = RNG.choice([x for x in range(1, length) if math.gcd(x, length) == 1])
        rle, remaining = [], length
        while remaining:
            count = RNG.randint(1, remaining)
            rle.append((count, RNG.randrange(4)))
            remaining -= count
        target = [RNG.randrange(4) for _ in range(RNG.randint(1, 7))]
        assert count_rle(rle, target, k) == direct(rle, target, k)
        cases += 1
    for length in (10**9, 999999937, 999999929):
        for k in (1, 7, 123456789, length-1):
            if math.gcd(k, length) > 1:
                continue
            for m in range(1, 11):
                assert count_rle([(length, 42)], [42]*m, k) == math.comb(length, m) % MOD
                cases += 1
    for rle, target, k, expected in (
        ([(10,3),(6,1),(10,3),(1,1)], [3,1], 17, 76),
        ([(72,555),(1029,718),(5807,726),(1002,718),(7240,555)], [555,718,726], 1789, 390415327),
    ):
        assert count_rle(rle, target, k) == direct(rle, target, k) == expected
        cases += 1
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    cases = validate()
    print('H:', cases, 'passed')
    article = Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog/editorials/2024/ccpc-haerbin-H.md'
    if args.report:
        report = {'scope':'2024 CCPC 哈尔滨 H', 'status':'passed', 'seed':20241020,
                  'limitations':'实际实现了非交换矩阵列折叠、线段树更新和欧几里得归约；小规模独立模拟、官方样例及10^9长度常值序列校验，未在线评测或验证2000段极限运行时间。',
                  'checks':{'H':{'passed':True,'cases':cases,'method':'1200组随机非交换上三角矩阵模下标乘积、2000组真实洗牌子序列DP、巨大长度二项式恒等式和全部官方样例。'}},
                  'content_sha256':{article.name:hashlib.sha256(article.read_bytes()).hexdigest()}}
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
