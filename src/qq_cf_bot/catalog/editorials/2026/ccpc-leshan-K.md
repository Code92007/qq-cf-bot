# K · 凸包序列

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

学习叉积、极角排序、滑动窗口，以及有序集合中前驱后继的维护。可以先用单调链凸包写暴力，逐个检查区间，再与下面的角度判据比较。

## 将包含原点转成角度判据

所有点都不是原点。它们的凸包不包含原点，当且仅当存在一条过原点的直线，使所有点严格位于同一侧；等价于所有方向都落在某个长度**严格小于** $\pi$ 的圆弧内。

将不同方向按极角循环排序，这又等价于存在相邻方向之间的逆时针空隙**严格大于** $\pi$。

所以原点属于凸包，当且仅当所有循环相邻极角空隙都不大于 $\pi$。恰好 $\pi$ 是允许的，它对应原点可能位于凸包边界。

还要检查正面积。当包含原点时，面积为零只能是所有点落在同一条过原点的直线上，也就是最多两个不同射线方向。因此完整判据为：

1. 至少有三个不同的射线方向；
2. 没有严格大于 $\pi$ 的循环角度空隙。

仅判断原点在凸包中而忽略第一个条件，会把一对反向共线点误判为合法。

## 用整数维护极角集合

把向量 $(x,y)$ 除以 $\gcd(|x|,|y|)$，同一射线得到同一个键，反方向仍保留为不同键。用频次表处理多个点落在同一射线的情况。

极角比较先比较所在半平面，再比较叉积符号，不要用浮点角度。对于循环相邻的两个**不同**方向 $u,v$，逆时针空隙大于 $\pi$ 当且仅当 $u\times v<0$；叉积为零且方向不同只能是反向，空隙为 $\pi$，合法。

维护有序集合和坏空隙数 $bad$。插入一个此前不存在的方向时，将“前驱到后继”这一个空隙替换成“前驱到新点”和“新点到后继”；删除时反过来。出现频次变化但射线仍存在时，不改空隙。

集合只有一个方向时，将它到自己的整周空隙视为坏空隙；集合为空时 $bad=0$。这样从一个方向变成两个方向及反向删除时，仍可以使用同一套局部增减规则。最后用“不同方向数至少三且 $bad=0$”判断即可。

## 双指针

区间一旦合法，添加更多点仍然合法：旧凸包包含于新凸包，包含原点和正面积都不会失去。因此右端点递增，每次插入新点后，只要窗口合法，就记录长度并删除左端点，直到不合法。

```text
left = 0
for right = 0..n-1:
    加入 P[right]
    while 当前窗口合法:
        ans = min(ans, right-left+1)
        删除 P[left]
        left++
```

每个点加入、删除各一次。由单调性，每个右端点对应的最短合法窗口都会被记录，所以得到全局最短长度。

## 复杂度与数值

时间 $O(n\log n)$，空间 $O(n)$。叉积中间运算建议使用 `__int128`。不要将一条射线上的多个不同坐标当成多个不同方向，也不要把反向向量归一化成同一个键。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <numeric>
#include <utility>
#include <vector>
using namespace std;
using ll = long long;
using Dir = pair<ll,ll>;
__int128 cross(Dir a, Dir b) { return (__int128)a.first * b.second - (__int128)a.second * b.first; }
int half(Dir a) { return a.second > 0 || (a.second == 0 && a.first > 0) ? 0 : 1; }
struct AngleLess {
    bool operator()(Dir a, Dir b) const {
        if (half(a) != half(b)) return half(a) < half(b);
        return cross(a, b) > 0;
    }
};
struct Window {
    map<Dir, int, AngleLess> count;
    int bad = 0;
    static int gap(Dir a, Dir b) { return a == b || cross(a, b) < 0; }
    void add(Dir d) {
        auto it = count.find(d);
        if (it != count.end()) { ++it->second; return; }
        if (count.empty()) { count[d] = 1; bad = 1; return; }
        auto right = count.lower_bound(d);
        if (right == count.end()) right = count.begin();
        auto left = right == count.begin() ? prev(count.end()) : prev(right);
        bad -= gap(left->first, right->first);
        bad += gap(left->first, d) + gap(d, right->first);
        count[d] = 1;
    }
    void remove(Dir d) {
        auto it = count.find(d);
        if (--it->second) return;
        if (count.size() == 1) { count.clear(); bad = 0; return; }
        auto right = next(it); if (right == count.end()) right = count.begin();
        auto left = it == count.begin() ? prev(count.end()) : prev(it);
        bad -= gap(left->first, d) + gap(d, right->first);
        bad += gap(left->first, right->first);
        count.erase(it);
    }
    bool valid() const { return count.size() >= 3 && bad == 0; }
};
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; cin >> T;
    while (T--) {
        int n; cin >> n; vector<Dir> a(n);
        for (auto &[x, y] : a) {
            cin >> x >> y; ll g = gcd(llabs(x), llabs(y)); x /= g; y /= g;
        }
        Window w; int left = 0, answer = n + 1;
        for (int right = 0; right < n; ++right) {
            w.add(a[right]);
            while (w.valid()) { answer = min(answer, right - left + 1); w.remove(a[left++]); }
        }
        cout << (answer == n + 1 ? -1 : answer) << '\n';
    }
}
```
