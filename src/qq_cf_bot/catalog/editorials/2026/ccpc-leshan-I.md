# I · 下一站，终点站

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

需要有向矩阵树定理、模意义高斯消元和组合计数 DP。先把“选下一站”和“选发车时刻”拆开，再用三四个车站枚举所有出边，理解为什么普通车站之间不能形成有向环。

## 每条候选出边的权重

令 $w_{ij}$ 表示普通车站 $i$ 选择车站 $j\ne i$ 后，合法发车时刻序列的数量。对这一条边，置 $U_t=B_{j,t}-d_{ij}$，要求

$$A_t\le T_t\le U_t,\qquad T_1<T_2<\cdots<T_p.$$

如果某个 $A_t>U_t$，边权为零。否则 $A$ 和 $U$ 各自严格递增。

将所有 $A_t$ 和 $U_t+1$ 排序去重，划分出至多 $2p-1$ 个整数时间块 $[l,r)$。在一个块内，每个班次对整个块要么都允许、要么都不允许。

用 $dp[k]$ 表示处理完此前时间块、已安排最前面 $k$ 班车的方案数。当前块长度为 $\ell=r-l$。若在该块安排接下来的 $h$ 班车，就有 $\binom{\ell}{h}$ 种选择，选中的时间按升序唯一分配给这些班次。可转移当且仅当

$$A_{k+h}\le l,\qquad U_{k+1}\ge r-1.$$

因上下界都递增，这恰好保证涉及的每个班次都允许整个块。转移为

$$ndp[k+h]\mathrel{+}=dp[k]\binom{\ell}{h}.$$

允许 $h=0$。每个时间块使用新数组，避免重复使用当前块。初值 $dp[0]=1$，最终 $dp[p]$ 为边权。小下标组合数用乘法公式和 $1,\ldots,p$ 的逆元计算；$\ell<p$ 时超出的组合数为零。

每条边有 $O(p)$ 个块，每块 $O(p^2)$ 转移，总计 $O(p^3)$。

## 下一站构成有根森林

每座普通车站恰好选一条出边，终点站无出边。由于可以等到第二天，只要每条边有合法班次，任意一段路程都能完成；能否最终到达终点仅取决于下一站关系。

因此合法关系恰好是不含普通车站有向环、所有路径最终进入某个终点站的有向森林。每条边的权重是 $w_{ij}$，森林权重为各边权之积。

只对 $n-r$ 座普通车站建立矩阵 $L$：

$$L_{ii}=\sum_{j\ne i}w_{ij},\qquad L_{ij}=-w_{ij}\ (i\ne j).$$

这里对角线的求和包含所有终点站和普通车站，非对角线仅保留普通车站。矩阵树定理给出 $\det L$ 是全部有根森林的权重和。

## 加上从 x 到达 y 的条件

令列向量 $b_i=w_{iy}$。将 $L$ 中对应车站 $x$ 的整列替换为 $b$，得到 $L^{(x)}$，答案为

$$\boxed{\det L^{(x)}}.$$

可以用加权森林版本的矩阵树定理理解：该换列行列式只保留 $x$ 所在分支最终进入根 $y$ 的森林。

另一个推导是先取全部边权为正的情形。令 $q_i$ 为森林中车站 $i$ 连接到根 $y$ 的加权占比。矩阵树定理的余子式展开给出 $Lq=b$，克拉默法则便给出 $q_x\det L=\det L^{(x)}$。左右两侧都是边权的多项式，恒等式因此也适用于边权为零以及模数域中的情况。

**实现时直接计算换列后的行列式，不要计算 $L^{-1}$，也不要除以 $\det L$。**即使 $\det L$ 在模意义下为零，换列行列式仍然是正确的多项式计数方式。

## 复杂度与边界

边权计算 $O(n^2p^3)$，高斯消元 $O((n-r)^3)$。空间为 $O(n^2+p^2)$。按模 $998244353$ 运算；寻找非零主元，换行取反，找不到主元则行列式为零。禁止选择自身，故 $w_{ii}=0$。

边权 DP 直接使用原题的整数时间，不需要枚举一天的 86400 个时间点。允许跨日换乘，因此无需在不同普通车站的发车时刻之间增加额外衔接限制。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>
using namespace std;
using ll = long long;
const ll MOD = 998244353;
ll power(ll a, ll b) { ll r = 1; for (; b; b >>= 1, a = a * a % MOD) if (b & 1) r = r * a % MOD; return r; }
ll edgeWeight(const vector<int> &a, const vector<int> &b, int distance, const vector<ll> &inv) {
    int p = int(a.size()); vector<int> u(p), cuts;
    for (int i = 0; i < p; ++i) {
        u[i] = b[i] - distance;
        if (a[i] > u[i]) return 0;
        cuts.push_back(a[i]); cuts.push_back(u[i] + 1);
    }
    sort(cuts.begin(), cuts.end()); cuts.erase(unique(cuts.begin(), cuts.end()), cuts.end());
    vector<ll> dp(p + 1); dp[0] = 1;
    for (int t = 0; t + 1 < int(cuts.size()); ++t) {
        int l = cuts[t], r = cuts[t + 1], len = r - l;
        vector<ll> choose(p + 1), next = dp; choose[0] = 1;
        for (int h = 1; h <= p && h <= len; ++h)
            choose[h] = choose[h - 1] * (len - h + 1) % MOD * inv[h] % MOD;
        for (int k = 0; k < p; ++k) if (dp[k] && u[k] >= r - 1)
            for (int h = 1; k + h <= p && h <= len; ++h) {
                if (a[k + h - 1] > l) break;
                next[k + h] = (next[k + h] + dp[k] * choose[h]) % MOD;
            }
        dp.swap(next);
    }
    return dp[p];
}
ll determinant(vector<vector<ll>> a) {
    int n = int(a.size()); ll ans = 1;
    for (int c = 0; c < n; ++c) {
        int pivot = c; while (pivot < n && a[pivot][c] == 0) ++pivot;
        if (pivot == n) return 0;
        if (pivot != c) { swap(a[pivot], a[c]); ans = (MOD - ans) % MOD; }
        ans = ans * a[c][c] % MOD;
        ll inv = power(a[c][c], MOD - 2);
        for (int i = c + 1; i < n; ++i) if (a[i][c]) {
            ll factor = a[i][c] * inv % MOD;
            for (int j = c; j < n; ++j) a[i][j] = (a[i][j] - factor * a[c][j] % MOD + MOD) % MOD;
        }
    }
    return ans;
}
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n, r, p; cin >> n >> r >> p;
    vector<vector<int>> d(n, vector<int>(n)), a(n, vector<int>(p)), b(n, vector<int>(p));
    for (auto &row : d) for (int &v : row) cin >> v;
    for (int i = r; i < n; ++i) for (int &v : a[i]) cin >> v;
    for (auto &row : b) for (int &v : row) cin >> v;
    int x, y; cin >> x >> y; --x; --y;
    vector<ll> inv(p + 1); for (int i = 1; i <= p; ++i) inv[i] = power(i, MOD - 2);
    vector<vector<ll>> w(n, vector<ll>(n));
    for (int i = r; i < n; ++i) for (int j = 0; j < n; ++j)
        if (i != j) w[i][j] = edgeWeight(a[i], b[j], d[i][j], inv);
    vector<vector<ll>> L(n - r, vector<ll>(n - r));
    for (int i = r; i < n; ++i) {
        ll sum = accumulate(w[i].begin(), w[i].end(), 0LL) % MOD;
        for (int j = r; j < n; ++j) L[i - r][j - r] = i == j ? sum : (MOD - w[i][j]) % MOD;
        L[i - r][x - r] = w[i][y];
    }
    cout << determinant(L) << '\n';
}
```
