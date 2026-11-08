# D · 自动穿串机器人

本文按用户提供的 QOJ 题面截图独立推导。

## 先学什么

学习数组扫描、最大值和奇偶性即可。先手动模拟两三轮，再观察每个篮子在一轮中被访问的次数。不要按食材总数模拟：单个篮子的食材数可达十亿。

## 从最后一轮倒推

设 $M=\max_i a_i$。每个篮子在每轮中恰好被访问一次，因此第 $t$ 轮开始时，第 $i$ 个篮子剩余 $\max(0,a_i-t+1)$ 份食材。

所以最后一轮恰好是第 $M$ 轮。这一轮只有满足 $a_i=M$ 的篮子还有食材，且每个这样的篮子都只剩一份。机器人最后取到的食材，就是这一轮最后访问的非空篮子：

- $M$ 为奇数时，从左向右，答案为最大值的**最右位置**。
- $M$ 为偶数时，从右向左，答案为最大值的**最左位置**。

扫描数组，记录最大值及其最左、最右位置即可。

## 正确性证明

小于 $M$ 的篮子最迟在第 $M-1$ 轮清空，不能贡献最后一份食材。所有等于 $M$ 的篮子都在第 $M$ 轮各贡献一份，且之后所有篮子清空。按该轮的访问方向取最后一个最大值位置，必然恰好对应整个过程的最后一次取食材操作。

## 实现与复杂度

```text
long long mx = -1;
int first = -1, last = -1;
for (int i = 1; i <= n; ++i) {
    long long x;
    cin >> x;
    if (x > mx) mx = x, first = last = i;
    else if (x == mx) last = i;
}
cout << (mx % 2 ? last : first) << '\n';
```

时间 $O(n)$，额外空间 $O(1)$。单个篮子以及最大值出现多次的情况无需特判。

## 完整代码（C++17）

```cpp
#include <iostream>
using namespace std;
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; cin >> T;
    while (T--) {
        int n; cin >> n;
        long long mx = -1; int first = 0, last = 0;
        for (int i = 1; i <= n; ++i) {
            long long x; cin >> x;
            if (x > mx) mx = x, first = last = i;
            else if (x == mx) last = i;
        }
        cout << (mx % 2 ? last : first) << '\n';
    }
}
```
