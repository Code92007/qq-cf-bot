# E · 魔法矩阵

本文按用户提供的 QOJ 题面截图独立推导。构造中 $n=4$ 使用一个只有 1820 种输入集合的有限引理，文末附独立穷举验证代码。

## 先学什么

先学习用两条只差一个拐角的格路径推导局部约束，再学习用置换环给矩阵分配数值。这里的关键是同时满足路径和相等及两矩阵各为排列。

## 最多能改变哪些位置

记 $\Delta_{i,j}=B_{i,j}-A_{i,j}$。比较从同一格出发、分别先右后下和先下后右的两条路径，可得 $\Delta_{i,j+1}=\Delta_{i+1,j}$，所以差值在每条反对角线上恒定。第一行相同，迫使所有 $i+j\le n+1$ 的差值为零。

至多能改变剩余 $N=n(n-1)/2$ 个位置。只要给后面长度依次为 $n-1,n-2,\ldots,1$ 的反对角线分配非零差值 $\delta_t$，且 $\sum\delta_t=0$，每条路径各经过每条反对角线一次，路径和就相同。下面构造让这 $N$ 个位置全部改变。

## 三条一组、四条一组

连续三条反对角线取差值 $(1,-2,1)$；连续四条取 $(1,-1,-1,1)$。由于长度是连续等差数，这两个模式的差值总和、按格子数加权后的差值总和都为零。除 $n=6$ 外，$n-1\ge3$ 均可写为 $3a+4b$：模三为零全用三组；余一用一个四组；余二用两个四组。

把第一行的数删除后，其余数值按以下环分配：连续三数 $v,v+1,v+2$ 构成环，分别提供两个 $+1$ 格和一个 $-2$ 格；相邻两数互换，提供一个 $+1$ 格和一个 $-1$ 格。这些环在 $A,B$ 中使用完全相同的数，且每数一次。

先从小到大贪心取足够多连续三数，再贪心取足够多相邻数对。为什么不会找不到？删除首行的 $n$ 个数后，自由数形成至多 $n+1$ 个连续段。每段取三元组最多剩两个数，故最大三元组覆盖数至少为 $2N-2(n+1)$；$n\ge7$ 时 $N\ge2(n+1)$，足以覆盖构造所需的至多 $N$ 个数。先取的三元组总在各段左侧，不增加段数。剩余相邻对最多每段浪费一个数，而最终仍有 $N$ 个数无需改变，$N\ge n+1$，所以数对也足够。$n=5$ 只需要五个相邻数对，同样成立。

## 两个小规模边界

$n=6$ 使用 $(1,-2,2,-2,1)$。其中 $+1$ 有六格、$-2$ 有六格、$+2$ 有三格。先取三个连续三元组，消耗六个 $+1$ 和三个 $-2$；再取三个差为二的数对，消耗余下的正负二格。剩余自由数有 $21$ 个，差二图是两条各含 $18$ 个顶点的路径，其独立集总数上界为 $18$；最大匹配至少为 $21-18=3$。沿每条路径从小到大贪心匹配就是最大匹配，因此一定够用。

$n=4$ 时，任意删除四个首行数后，在 $1,\ldots,16$ 中总能找到两个互不相交、公共公差相同的三项等差数列。枚举公差 $1,\ldots,7$ 和起点即可；两个三元环实现 $(d,-2d,d)$。这个小引理可以用文末有限穷举完整验证：首行的排列顺序不影响自由集合，仅有 $\binom{16}{4}=1820$ 种集合。

所有未使用的数，填入两个矩阵的相同位置。

## 正确性与复杂度

所有改变格均获得规定的非零反对角线差值。每个数值环在两矩阵中各使用一次，其余数原位填入，所以两矩阵都是 $1..n^2$ 的排列，首行完全保留。差值总和为零保证每条路径和相等，并且恰好修改理论上限 $N$ 格，所以构造最优。

时间、空间均为 $O(n^2)$；$n=4$ 的枚举是固定常数。

## 小规模引理的完整验证器

```python
from itertools import combinations
for removed in combinations(range(1, 17), 4):
    free = set(range(1, 17)) - set(removed)
    found = False
    for d in range(1, 8):
        triples = [set((x, x+d, x+2*d)) for x in range(1, 17-2*d)
                   if {x, x+d, x+2*d} <= free]
        if any(not (a & b) for a, b in combinations(triples, 2)):
            found = True
            break
    assert found, removed
print("1820 / 1820 passed")
```

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <utility>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; cin >> T;
    while (T--) {
        int n; cin >> n; int limit = n * n;
        vector<vector<int>> A(n, vector<int>(n)), B = A;
        vector<bool> free(limit + 1, true); free[0] = false;
        for (int j = 0; j < n; ++j) { cin >> A[0][j]; B[0][j] = A[0][j]; free[A[0][j]] = false; }
        vector<int> delta(2 * n - 1);
        if (n == 4) {
            vector<array<int,3>> chosen; int step = 0;
            for (int d = 1; d <= 7 && chosen.empty(); ++d) {
                vector<array<int,3>> triples;
                for (int v = 1; v + 2 * d <= limit; ++v)
                    if (free[v] && free[v + d] && free[v + 2 * d]) triples.push_back({v,v+d,v+2*d});
                for (int i = 0; i < int(triples.size()) && chosen.empty(); ++i)
                    for (int j = i + 1; j < int(triples.size()); ++j) {
                        bool disjoint = true;
                        for (int x : triples[i]) for (int y : triples[j]) if (x == y) disjoint = false;
                        if (disjoint) { chosen = {triples[i], triples[j]}; step = d; break; }
                    }
            }
            assert(chosen.size() == 2);
            delta[4] = step; delta[5] = -2 * step; delta[6] = step;
            vector<pair<int,int>> pos, neg;
            for (int i = 1; i < n; ++i) for (int j = 0; j < n; ++j)
                if (delta[i+j] == step) pos.emplace_back(i,j);
                else if (delta[i+j] == -2*step) neg.emplace_back(i,j);
            int p = 0, q = 0;
            for (auto triple : chosen) {
                for (int t = 0; t < 2; ++t) { auto [i,j] = pos[p++]; A[i][j] = triple[t]; B[i][j] = triple[t+1]; }
                auto [i,j] = neg[q++]; A[i][j] = triple[2]; B[i][j] = triple[0];
                for (int v : triple) free[v] = false;
            }
        } else {
            if (n == 6) {
                array<int,5> pattern = {1,-2,2,-2,1};
                for (int t = 0; t < 5; ++t) delta[n+t] = pattern[t];
            } else {
                int remain = n - 1, at = n;
                int fours = remain % 3 == 1 ? 1 : remain % 3 == 2 ? 2 : 0;
                for (int block = 0; block < fours; ++block) {
                    for (int v : {1,-1,-1,1}) delta[at++] = v;
                    remain -= 4;
                }
                while (remain) { for (int v : {1,-2,1}) delta[at++] = v; remain -= 3; }
            }
            vector<pair<int,int>> positive1, negative1, positive2, negative2;
            for (int i = 1; i < n; ++i) for (int j = 0; j < n; ++j) {
                int d = delta[i+j];
                if (d == 1) positive1.emplace_back(i,j);
                if (d == -1) negative1.emplace_back(i,j);
                if (d == 2) positive2.emplace_back(i,j);
                if (d == -2) negative2.emplace_back(i,j);
            }
            auto assign = [&](pair<int,int> cell, int a, int b) {
                auto [i,j] = cell; A[i][j] = a; B[i][j] = b;
            };
            int p1 = 0, m1 = 0, p2 = 0, m2 = 0;
            int triples = n == 6 ? 3 : int(negative2.size());
            for (int v = 1, used = 0; used < triples; ++v) {
                if (v + 2 > limit) { assert(false); return 0; }
                if (free[v] && free[v+1] && free[v+2]) {
                    assign(positive1[p1++], v, v+1);
                    assign(positive1[p1++], v+1, v+2);
                    assign(negative2[m2++], v+2, v);
                    free[v] = free[v+1] = free[v+2] = false;
                    ++used; v += 2;
                }
            }
            if (n == 6) {
                for (int parity = 1; parity <= 2 && p2 < int(positive2.size()); ++parity)
                    for (int v = parity; v + 2 <= limit && p2 < int(positive2.size()); v += 2)
                        if (free[v] && free[v+2]) {
                            assign(positive2[p2++], v, v+2);
                            assign(negative2[m2++], v+2, v);
                            free[v] = free[v+2] = false; v += 2;
                        }
            } else {
                for (int v = 1; p1 < int(positive1.size()); ++v) {
                    if (v + 1 > limit) { assert(false); return 0; }
                    if (free[v] && free[v+1]) {
                        assign(positive1[p1++], v, v+1);
                        assign(negative1[m1++], v+1, v);
                        free[v] = free[v+1] = false; ++v;
                    }
                }
            }
            assert(p1 == int(positive1.size()) && m1 == int(negative1.size()));
            assert(p2 == int(positive2.size()) && m2 == int(negative2.size()));
        }
        int next = 1;
        for (int i = 1; i < n; ++i) for (int j = 0; j < n; ++j) if (A[i][j] == 0) {
            while (!free[next]) ++next;
            A[i][j] = B[i][j] = next; free[next] = false;
        }
        for (const auto &matrix : {A, B}) for (const auto &row : matrix) {
            for (int j = 0; j < n; ++j) cout << row[j] << (j + 1 == n ? '\n' : ' ');
        }
    }
}
```
