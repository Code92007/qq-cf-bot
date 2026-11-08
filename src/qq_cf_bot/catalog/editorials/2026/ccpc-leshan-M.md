# M · 三元组

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

学习二分定位、候选集合过滤和交互输出刷新。这里的三个查询坐标可以自由组合，不要求查询三元组出现在输入中。利用这一点，一次查询可以同时执行一棵深度为二的二分决策树。

## 一次查询把候选数降到四分之一

维护与此前所有回答一致的输入三元组集合 $S$，初始为全部 $n$ 个三元组。若只剩一个，立即输出它。

设当前 $|S|=m\ge2$。按第一坐标排序，取下标 $\lfloor m/2\rfloor$（从零开始）对应的第一坐标作为查询值 $a$，将候选分成

$$L=\{P:P.a<a\},\qquad R=\{P:P.a\ge a\}.$$

两组大小分别为 $\lfloor m/2\rfloor$ 和 $\lceil m/2\rceil$。每一列都是排列，保证不会出现相等坐标破坏二分大小的情况。

在 $L$ 内按第二坐标取同样定义的中位数，作为查询值 $b$；在 $R$ 内按第三坐标取中位数，作为查询值 $c$。输出 `? a b c` 并刷新，读取三个比较位。

第一位告诉我们目标在 $L$ 还是 $R$。若在 $L$，第二位又将 $L$ 至多对半；若在 $R$，第三位又将 $R$ 至多对半。因此不管回复是什么，剩余候选数至多

$$\left\lceil\frac{\lceil m/2\rceil}{2}\right\rceil=\left\lceil\frac m4\right\rceil.$$

另一个未用来证明上界的比较位也不能忽略：实际更新候选集时，保留**同时符合三个比较位**的候选。这只会进一步减少数量，并确保最终候选恰好与全部历史回复一致。

## 为什么十次足够

每次查询都保证四分之一收缩，且 $4^{10}=1048576\ge10^6$，所以最多十次就只剩一个候选。

交互器即使自适应改变目标，也必须选择与历史回复一致的三元组。我们的集合始终恰好保存这些可能值，收缩上界对每一种回复分支都成立，故无需假设存在一个从头到尾固定的隐藏目标。

## 比较方向和输出

返回位是 $[\text{查询值}>\text{目标值}]$，并非相反方向。第一位为 `1` 时进入第一坐标较小的 $L$，为 `0` 时进入 $R$。选择的三个中位坐标都来自输入，因此自动处于 $[1,n]$。

候选为一时输出 `! A B C`、换行并刷新。交互器不会返回成功确认，直接读取下个测试用例的 $n$。$n=1$ 时无需查询，直接回答。

## 复杂度

每轮对候选及两个半集排序，时间 $O(m\log m)$，候选数按四倍缩小，全部查询的总时间为 $O(n\log n)$，空间 $O(n)$。用选择算法取中位数可以进一步优化平均运行时间，但排序版本已具有清晰的确定性复杂度。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <array>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; if (!(cin >> T)) return 0;
    while (T--) {
        int n; cin >> n; vector<array<int,3>> points(n);
        for (auto &p : points) cin >> p[0] >> p[1] >> p[2];
        vector<int> candidates(n); iota(candidates.begin(), candidates.end(), 0);
        while (candidates.size() > 1) {
            sort(candidates.begin(), candidates.end(), [&](int i, int j) { return points[i][0] < points[j][0]; });
            int mid = int(candidates.size()) / 2;
            vector<int> left(candidates.begin(), candidates.begin() + mid);
            vector<int> right(candidates.begin() + mid, candidates.end());
            sort(left.begin(), left.end(), [&](int i, int j) { return points[i][1] < points[j][1]; });
            sort(right.begin(), right.end(), [&](int i, int j) { return points[i][2] < points[j][2]; });
            array<int,3> query = {points[candidates[mid]][0], points[left[left.size()/2]][1], points[right[right.size()/2]][2]};
            cout << "? " << query[0] << ' ' << query[1] << ' ' << query[2] << endl;
            string reply; if (!(cin >> reply) || reply.size() != 3) return 0;
            vector<int> next;
            for (int i : candidates) {
                bool ok = true;
                for (int d = 0; d < 3; ++d) if ((query[d] > points[i][d]) != (reply[d] == '1')) ok = false;
                if (ok) next.push_back(i);
            }
            candidates.swap(next);
            if (candidates.empty()) return 0;
        }
        auto answer = points[candidates[0]];
        cout << "! " << answer[0] << ' ' << answer[1] << ' ' << answer[2] << endl;
    }
}
```
