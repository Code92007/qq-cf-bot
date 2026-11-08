# J · 有毒药物

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

学习二进制编码、组合数和二分答案。关键不是瓶数总和，而是每种药能让多少只不同老鼠喝到它。

## 将药物编码成老鼠的子集

假设有 $m$ 只老鼠。对第 $i$ 种药，令 $S_i$ 为喝到它的老鼠集合。因为每瓶最多喂一只，必须有 $|S_i|\le a_i$。同一种药给同一只老鼠多瓶不会增加信息，所以无需这样安排。

若第 $i$ 种药有毒，恰好 $S_i$ 内的老鼠死亡。故能识别所有药物，当且仅当能为每种药选择互不相同的集合 $S_i$，满足各自的大小上界。

大小不超过 $b$ 的集合共有

$$F_m(b)=\sum_{j=0}^{\min(b,m)}\binom mj.$$

将瓶数排序为 $a_1\le\cdots\le a_k$。可行性条件恰好是

$$F_m(a_i)\ge i\quad\text{对所有 }i=1,\ldots,k.$$

必要性：前 $i$ 种药都只能使用大小不超过 $a_i$ 的集合，至少要有 $i$ 个。充分性：按此顺序分配，第 $i$ 步最多只有 $i-1$ 个集合被使用，而允许集合至少有 $i$ 个，一定还能选出一个。这里允许的集合族随 $a_i$ 增大而嵌套，所以简单的贪心计数已经充分。

## 无解与答案上界

空集只有一个，因此若至少两种药的瓶数为零，永远无法区分，输出 $-1$。

否则 $k-1$ 只老鼠一定足够：一种药使用空集，其余每种药各使用一个不同的单元素集合。只有一种药时答案为 $0$，即使没有药物样本也能直接确定它有毒。

可行性关于 $m$ 单调，在 $[0,k-1]$ 上二分最小可行值。

## 如何避免组合数溢出

只关心数量是否达到 $k$。从 $\binom m0=1$ 开始递推

$$\binom m{j+1}=\binom mj\frac{m-j}{j+1}.$$

累计和一旦达到 $k$ 就停止，后续所有更大的瓶数上界都视为可用集合至少 $k$ 个。不要把单项组合数提前截断后继续递推，否则整除关系会被破坏。停止前单项不超过 $k$，与 $m\le k-1$ 相乘可用 64 位整数容纳，也可以使用 `__int128` 作为中间类型。

每次检查只需生成少量累加组合数，再扫描排序后的瓶数。组合数累计至 $k$ 所需项数为 $O(\log k)$；否则会在 $m$ 项结束，仍不超过这个数量级。

## 复杂度

排序 $O(k\log k)$，二分共 $O(\log k)$ 次检查，每次 $O(k+\log k)$，总时间 $O(k\log k)$，空间 $O(k)$。输出所需老鼠数，不需要实际构造全部编码。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;
using ll = long long;
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; cin >> T;
    while (T--) {
        int k; cin >> k; vector<int> a(k);
        for (int &v : a) cin >> v;
        sort(a.begin(), a.end());
        if (k >= 2 && a[1] == 0) { cout << -1 << '\n'; continue; }
        auto feasible = [&](int m) {
            vector<ll> prefix(1, 1); ll comb = 1;
            for (int h = 1; h <= m && prefix.back() < k; ++h) {
                comb = comb * (m - h + 1) / h;
                prefix.push_back(min<ll>(k, prefix.back() + comb));
            }
            for (int i = 0; i < k; ++i)
                if (prefix[min<int>(a[i], int(prefix.size()) - 1)] < i + 1) return false;
            return true;
        };
        int l = 0, r = k - 1;
        while (l < r) { int m = (l + r) / 2; if (feasible(m)) r = m; else l = m + 1; }
        cout << l << '\n';
    }
}
```
