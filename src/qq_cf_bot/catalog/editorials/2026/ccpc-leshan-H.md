# H · 区间和

本文按用户提供的 QOJ 题面截图独立推导。这是同一程序运行两次的通信题：第二次只能使用第一次产生的权重和，不能读取 $m$。

## 先学什么

先学习正权值下的严格单调编码、区间匹配的贪心和 Hall 定理。把所有可行 $m$ 连成一条每步只增加一个格子的规范构造链，就可以二分解码。

## 固定终点：最长的 n 个区间

将全部区间按长度降序、左端点升序排序，选前 $n$ 个，记为目标区间 $I_1,\ldots,I_n$。它们的长度和显然就是题目允许的最大值 $M$。这些区间可以在 $O(n)$ 次枚举中生成。

给每个目标区间匹配一个属于它的不同位置 $p_i$，使这些位置恰好是 $1..n$。按右端点升序处理目标，每次取不小于左端点的最小未用位置，就是标准区间匹配贪心。

为什么一定匹配成功？这 $n$ 个最长区间两两相交：$n\ge5$ 时长度大于 $n/2$ 的区间已有至少 $n$ 个；$n=1,2,3,4$ 可直接列出。任取 $k$ 个目标区间，其并集于是为某段连续的 $d$ 个位置。长度分别为 $d+1,\ldots,n$ 的 $n-d$ 个前缀区间，都比这 $k$ 个区间长，必定也在选出的前 $n$ 个区间中，且不属于这个子集。因此 $k+(n-d)\le n$，即 $k\le d$，满足 Hall 条件。贪心的交换论证保证它能找到这份完美匹配。

## 从 n 到 M 的规范链

起点是 $n$ 个互不相同的单点区间 $[p_i,p_i]$，长度和为 $n$。按目标编号依次处理：把当前区间先向左扩展到 $I_i$ 的左端点，再向右扩展到右端点，每次只扩一格。全部完成后到达长度和 $M$。

中途始终有 $n$ 个互异区间。已完成目标的长度不小于当前目标；当前区间未完成时长度更短，不会和已完成目标相同，完成时目标本来互异。尚未处理的是不同的单点；当前一旦开始增长就不是单点，开始前所有单点也不同。所以每个整数长度和都对应合法输出。

每扩一格，总权重和增加对应的正整数 $a_j$，因此规范链上的 $s(m)$ 严格递增。狗知道相同的 $A$，可以重建整条链并二分唯一的 $m$。

## 不实际走完平方级步骤

第 $i$ 个目标从单点扩到完整区间，需要 $|I_i|-1$ 步，权重增量是该区间元素和减 $a_{p_i}$。预处理这两个量的前缀和，给定 $m-n$ 次扩展后，二分定位正在处理的目标；之前的目标完整、之后的仍是单点，当前的左右端点直接计算。数组前缀和使一次 $s(m)$ 查询只需 $O(\log n)$。

猫按这个规则输出 $n$ 个区间；狗二分 $m$。注意题目示例的猫可以使用别的合法策略，不能要求本策略的狗单独解码另一个策略产生的示例数据；必须用同一份程序的两次运行检验。

## 正确性与复杂度

匹配保证规范链起点合法，逐步扩展保证整条链合法并覆盖全部允许的 $m$，正权值保证权重和严格单调，因此二分解码恰好得到猫的输入。

构造及匹配 $O(n\log n)$；猫另需 $O(n)$ 输出，狗另需 $O(\log M\log n)$ 查询，空间 $O(n)$。长度总和及权重和使用 64 位整数；最大权重和不超过 $4\cdot10^{18}$。两次运行输出完毕都要刷新缓冲区。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <cassert>
#include <iostream>
#include <numeric>
#include <set>
#include <string>
#include <utility>
#include <vector>
using namespace std;
using ll = long long;
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    string role; cin >> role; int T; cin >> T;
    while (T--) {
        int n; ll value; cin >> n >> value;
        vector<ll> a(n + 1), sum(n + 1);
        for (int i = 1; i <= n; ++i) { cin >> a[i]; sum[i] = sum[i - 1] + a[i]; }
        vector<pair<int,int>> target;
        for (int length = n; length >= 1 && int(target.size()) < n; --length)
            for (int l = 1; l + length - 1 <= n && int(target.size()) < n; ++l)
                target.emplace_back(l, l + length - 1);
        vector<int> order(n), start(n); iota(order.begin(), order.end(), 0);
        sort(order.begin(), order.end(), [&](int i, int j) {
            if (target[i].second != target[j].second) return target[i].second < target[j].second;
            return target[i].first < target[j].first;
        });
        set<int> unused; for (int i = 1; i <= n; ++i) unused.insert(i);
        for (int i : order) {
            auto it = unused.lower_bound(target[i].first);
            assert(it != unused.end() && *it <= target[i].second);
            start[i] = *it; unused.erase(it);
        }
        vector<ll> cost(n + 1), gain(n + 1);
        for (int i = 0; i < n; ++i) {
            auto [l,r] = target[i];
            cost[i + 1] = cost[i] + r - l;
            gain[i + 1] = gain[i] + sum[r] - sum[l - 1] - a[start[i]];
        }
        auto partial = [&](int i, ll steps) {
            auto [l,r] = target[i]; int p = start[i];
            ll left = min<ll>(steps, p - l);
            return pair<int,int>{p - int(left), p + int(steps - left)};
        };
        auto weight = [&](ll m) {
            ll steps = m - n;
            int full = int(upper_bound(cost.begin(), cost.end(), steps) - cost.begin()) - 1;
            ll result = sum[n] + gain[full];
            if (full < n) {
                auto [l,r] = partial(full, steps - cost[full]);
                result += sum[r] - sum[l - 1] - a[start[full]];
            }
            return result;
        };
        if (role == "cat") {
            ll steps = value - n;
            int full = int(upper_bound(cost.begin(), cost.end(), steps) - cost.begin()) - 1;
            for (int i = 0; i < n; ++i) {
                pair<int,int> interval = i < full ? target[i] : i == full ? partial(i, steps - cost[i]) : pair<int,int>{start[i], start[i]};
                cout << interval.first << ' ' << interval.second << '\n';
            }
        } else {
            ll low = n, high = n + cost[n];
            while (low < high) { ll mid = (low + high) / 2; if (weight(mid) >= value) high = mid; else low = mid + 1; }
            cout << low << '\n';
        }
    }
    cout.flush();
}
```
