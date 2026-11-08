# F · 暴击装备

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

先学习折半枚举和二维支配关系，再学习 Monge 矩阵的最优决策单调性、分治求行最值。不要直接假设前沿上的乘积单峰；本题需要证明的是不同查询之间的最优下标单调。

## 折半与支配删除

常数 $1$ 和分母不影响最优选择。记 $C=10^8$，只需最大化整数 $\min(P,C)D$。

分别枚举前三个槽位和后三个槽位的选择，每一半最多 $100^3=10^6$ 个二维点，表示这半边的属性和 $(p,d)$。

若一个点的两个属性都不大于另一点，就可以删除它：与任意另一半组合时，目标函数在两个属性上都不减。按 $p$ 从大到小、相同时 $d$ 从大到小排序，只保留 $d$ 严格超过此前最大值的点，再反转，得到 $p$ 严格递增、$d$ 严格递减的前沿。重复点只保留一个。

设左前沿为 $(p_i,d_i)$，右前沿为 $(q_j,e_j)$，两者暂时都按第一维递增。候选值为

$$F(i,j)=c_{ij}(d_i+e_j),\qquad c_{ij}=\min(p_i+q_j,C).$$

## 封顶后仍然成立的 Monge 性质

取相邻两行两列。设 $d_2=d_1-u$、$e_2=e_1-v$，其中 $u,v\ge0$，并记 $S=d_1+e_1\ge0$。则

$$F(2,2)-F(2,1)-F(1,2)+F(1,1)$$
$$=S(c_{22}-c_{21}-c_{12}+c_{11})-u(c_{22}-c_{21})-v(c_{22}-c_{12})\le0.$$

原因是 $\min(z,C)$ 单调且凹：第一项的括号不大于零，后两项的括号非负。这个证明同时覆盖未封顶、部分封顶和全部封顶，不能只对 $P<C$ 的情况展开乘积。

将右前沿反转后，不等式方向变为非负，也就是较晚列相对较早列的优势随行号增加而不减。因此每行取**最左侧**最大值时，最优列号不减。

## 分治求行最大值

对行区间 $[l,r]$，维护最优列必在 $[L,R]$。扫描中间行 $mid$ 的所有候选列，求最左最优列 $best$；左半部分递归到 $[L,best]$，右半部分递归到 $[best,R]$。

```text
solve(l, r, L, R):
    若 l > r，返回
    mid = (l+r)/2
    扫描 j=L..R，求中间行的最左最大值 best
    用该值更新全局答案
    solve(l, mid-1, L, best)
    solve(mid+1, r, best, R)
```

比较时只在候选值**严格更大**时更新 best，即可保持最左优先。记录全局最大整数值 $V$，最后输出 $1+V/10^{16}$，使用 `long double` 并保留足够小数位。

## 正确性与复杂度

折半枚举涵盖全部装备方案；删除被支配点不会损失最优值；Monge 性质保证两侧递归保留各行的最优列；因此算法求出的全局最大值就是答案。

记两边枚举规模为 $N_1,N_2\le10^6$，前沿大小为 $L,R$。排序时间为 $O(N_1\log N_1+N_2\log N_2)$，分治扫描为 $O((L+R)\log(L+1))$，空间 $O(N_1+N_2)$。合并后的 $D\le6\cdot10^8$，目标值不超过 $6\cdot10^{16}$，有符号 64 位整数足够；乘法前务必提升到 64 位。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <array>
#include <functional>
#include <iomanip>
#include <iostream>
#include <utility>
#include <vector>
using namespace std;
using ll = long long;
using Point = pair<ll, ll>;
vector<Point> frontier(vector<Point> a) {
    sort(a.begin(), a.end(), greater<Point>());
    vector<Point> b; ll best = -1;
    for (auto [p, d] : a) if (d > best) {
        best = d; b.emplace_back(p, d);
    }
    reverse(b.begin(), b.end()); return b;
}
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    array<int, 6> c;
    for (int &x : c) if (!(cin >> x)) return 0;
    array<vector<Point>, 6> slots;
    for (int i = 0; i < 6; ++i) {
        slots[i].resize(c[i]);
        for (auto &[p, d] : slots[i]) cin >> p >> d;
    }
    auto enumerate = [&](int start) {
        vector<Point> a;
        a.reserve(c[start] * c[start + 1] * c[start + 2]);
        for (auto [p, d] : slots[start])
            for (auto [q, e] : slots[start + 1])
                for (auto [r, f] : slots[start + 2])
                    a.emplace_back(p + q + r, d + e + f);
        return frontier(move(a));
    };
    auto a = enumerate(0), b = enumerate(3);
    reverse(b.begin(), b.end());
    ll answer = 0;
    function<void(int,int,int,int)> solve = [&](int l, int r, int L, int R) {
        if (l > r) return;
        int mid = (l + r) / 2, opt = L;
        ll best = -1;
        for (int j = L; j <= R; ++j) {
            ll value = min(a[mid].first + b[j].first, 100000000LL)
                       * (a[mid].second + b[j].second);
            if (value > best) best = value, opt = j;
        }
        answer = max(answer, best);
        solve(l, mid - 1, L, opt);
        solve(mid + 1, r, opt, R);
    };
    solve(0, int(a.size()) - 1, 0, int(b.size()) - 1);
    cout << fixed << setprecision(15) << 1.0L + answer / 10000000000000000.0L << '\n';
}
```
