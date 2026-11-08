# G · 倾斜木棍

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

先学习路径上的两状态计数 DP，再学习矩阵乘法与线段树维护有序乘积。矩阵乘法不可交换，线段树合并必须始终为左子树乘右子树。

## 为什么只需检查相邻木棍

每根倒下的木棍都是包含其原坐标 $x_i$ 的区间，且 $x_i$ 严格递增。若相邻木棍都没有正长度交集，它们的区间也只能按这个顺序排列：第 $i$ 根区间的右端点不大于第 $i+1$ 根的左端点。将这些不等式串起来，就保证任意两根都没有正长度交集。

设相邻坐标差 $g=x_{i+1}-x_i$。行表示第 $i$ 根方向，列表示第 $i+1$ 根方向，方向顺序均为左、右，兼容矩阵是

$$
M_i=\begin{pmatrix}
\mathbf{1}_{a_{i+1}\le g}&1\\
\mathbf{1}_{a_i+a_{i+1}\le g}&\mathbf{1}_{a_i\le g}
\end{pmatrix}.
$$

例如右、左相向倒下时，必须满足两根长度之和不超过间距；左、右背向倒下时总合法。所有比较都用 $\le$，因为允许端点接触。

## 矩阵乘积统计方案

$M_1M_2\cdots M_{n-1}$ 的 $(u,v)$ 项，统计第一根为方向 $u$、最后一根为方向 $v$ 的所有合法方向序列。乘法中的中间下标恰好枚举中间木棍的方向，所以答案为乘积矩阵四个元素的和。

$n=1$ 时没有兼容矩阵，空乘积取单位矩阵，四项之和为 $2$，正好对应一根木棍的两种方向。

## 点修改

改变 $a_p$ 只会影响 $M_{p-1}$ 和 $M_p$ 中存在的那些矩阵。在线段树上维护所有 $M_i$ 的有序乘积，修改至多两个叶子，再读取根节点的四项和即可。若 $n=1$，每次直接输出 $2$。

## 正确性证明

相邻兼容条件与整个方案合法等价。矩阵乘法对每个中间方向求和，且只累加兼容转移，因此每个合法方向序列恰好贡献一次，不合法方案贡献零。点修改后所有受影响的矩阵都被更新，其他兼容关系不变，所以每次根矩阵仍统计当前数组的全部合法方案。

## 复杂度与实现细节

建树 $O(n)$，每次修改 $O(\log n)$，空间 $O(n)$，所有矩阵运算模 $998244353$。

坐标差可达 $2\cdot10^9$，长度和可达 $2\cdot10^9$；统一使用 64 位整数做坐标、长度和及矩阵乘法更稳妥。无需把所有木棍两两建立冲突边。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <array>
#include <iostream>
#include <vector>
using namespace std;
using ll = long long;
const ll MOD = 998244353;
struct Matrix { array<array<ll, 2>, 2> a{}; };
Matrix identity() { Matrix x; x.a[0][0] = x.a[1][1] = 1; return x; }
Matrix operator*(const Matrix &x, const Matrix &y) {
    Matrix z;
    for (int i = 0; i < 2; ++i) for (int j = 0; j < 2; ++j)
        for (int k = 0; k < 2; ++k)
            z.a[i][j] = (z.a[i][j] + x.a[i][k] * y.a[k][j]) % MOD;
    return z;
}
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n, q; cin >> n >> q;
    vector<ll> x(n), a(n);
    for (ll &v : x) cin >> v;
    for (ll &v : a) cin >> v;
    int size = 1; while (size < n - 1) size *= 2;
    vector<Matrix> tree(size * 2, identity());
    auto leaf = [&](int i) {
        ll gap = x[i + 1] - x[i]; Matrix m;
        m.a[0][0] = a[i + 1] <= gap; m.a[0][1] = 1;
        m.a[1][0] = a[i] + a[i + 1] <= gap; m.a[1][1] = a[i] <= gap;
        return m;
    };
    for (int i = 0; i + 1 < n; ++i) tree[size + i] = leaf(i);
    for (int i = size - 1; i; --i) tree[i] = tree[i * 2] * tree[i * 2 + 1];
    auto update = [&](int i) {
        if (i < 0 || i + 1 >= n) return;
        int p = size + i; tree[p] = leaf(i);
        while (p > 1) { p /= 2; tree[p] = tree[p * 2] * tree[p * 2 + 1]; }
    };
    auto print = [&]() {
        ll ans = 0; for (auto row : tree[1].a) for (ll v : row) ans += v;
        cout << ans % MOD << '\n';
    };
    print();
    while (q--) {
        int p; ll v; cin >> p >> v; --p; a[p] = v;
        update(p - 1); update(p); print();
    }
}
```
