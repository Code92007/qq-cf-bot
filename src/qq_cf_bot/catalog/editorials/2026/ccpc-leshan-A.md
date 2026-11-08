# A · 传送

本文按用户提供的 QOJ 题面截图独立推导。下面给出避免显式建立四次方条边的实现。

## 先学什么

先掌握 Floyd、Dijkstra 和隐式图最短路，再理解“按距离全局有序处理后，一个前缀只展开一次”的优化。代码使用整数键的单调 Radix Heap。

## 一次传送的代价

每次传送后两个人都在顶点上。设普通边长最短路为 $d(a,k)$，一个人从顶点 $a$ 出发，在下一次传送后到达 $i$ 的最小耗时为

$$
c(a,i)=\min_{ki\in E}\{2d(a,k)+w_{ki}\},\qquad c(a,a)=0.
$$

先走到 $k$，再走到边 $ki$ 的中点，立即传送到 $i$ 即可。到中点消耗的时间正好是边长。任何一次到达 $i$ 的传送都必须从某条邻边的靠近 $i$ 的半边发生，或此前已走到 $i$；因此这个下界可以达到。较早到达中点的人可以等待，使两个人的传送时刻同步。

于是在二元顶点状态 $(a,b)$ 上，到 $(i,j)$ 的一条边权为 $\max(c(a,i),c(b,j))$。最后一次步行到目标后补一次无影响的传送，也属于这个模型。连续两次传送之间没有其他传送，分段最优；反过来每条状态边都能实现，所以此图最短路就是答案。

## 把四次方条边变成三次方次展开

将每一行 $c(b,*)$ 从小到大排序。考虑边权由第一人的 $c(a,i)=w$ 决定的转移：固定目标 $i$ 后，第二人的所有合法目标正好是 $c(b,j)\le w$ 的一个前缀，整段候选距离都是 $D(a,b)+w$。再对称处理由第二人决定边权的情况，相等时重复覆盖无妨。

对每个“第一人目标 $i$、第二人起点 $b$”维护已展开前缀长度。所有候选按**到达时刻**从小到大出队。当前候选允许前缀长为 $k$ 时，只展开以前没展开过的部分：已经展开过的位置，必有一个到达时刻不大于当前时刻的候选覆盖它。因此删去重复展开不会丢失更短路。

每个前缀最多增长 $n$ 次，两个方向共 $2n^3$ 个元素。某个二元状态第一次被覆盖时，其距离已经最短，直接确定即可。

## 堆中也不能存三次方个候选

每个确定的状态对两个方向各开一个迭代器，按对应 $c$ 行的升序产生候选。堆中只保存每个迭代器的下一个有效候选；出队后再推进。候选距离单调，且在加入堆前可以跳过已被完整覆盖的前缀。

这样最多同时存在 $2n^2$ 个迭代器候选和 $n^2$ 个状态事件。Radix Heap 对非负整数键按位分桶，适合这些单调插入的键。

## 正确性与复杂度

单次传送建模证明状态图等价。全局时刻顺序保证前缀删除只删除已有不劣候选的边；迭代器按边权递增产生候选，保证堆仍能取得所有剩余候选中最早的一个。因此首次覆盖距离正确，所有输出都是状态图最短路。

Floyd 和预处理为 $O(n^3)$。迭代器扫描与前缀展开为 $O(n^3)$，Radix Heap 给出 $O(n^3\log U)$ 的整数键上界，空间 $O(n^2)$；$U$ 是键的上界。这里无需开四维数组。边权上限下所有答案不超过 $798000000$，暂存候选也在 32 位无符号整数范围内。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <numeric>
#include <utility>
#include <vector>
using namespace std;
using u32 = uint32_t;
struct RadixHeap {
    array<vector<pair<u32,u32>>,33> bucket;
    u32 last = 0; size_t count = 0;
    static int index(u32 x) { return x ? 32 - __builtin_clz(x) : 0; }
    void push(u32 key, u32 value) { assert(key >= last); bucket[index(key ^ last)].emplace_back(key,value); ++count; }
    pair<u32,u32> pop() {
        if (bucket[0].empty()) {
            int i = 1; while (bucket[i].empty()) ++i;
            last = numeric_limits<u32>::max();
            for (auto entry : bucket[i]) last = min(last, entry.first);
            for (auto entry : bucket[i]) bucket[index(entry.first ^ last)].push_back(entry);
            bucket[i].clear();
        }
        auto answer = bucket[0].back(); bucket[0].pop_back(); --count; return answer;
    }
};
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n,m; cin >> n >> m;
    const int INF = 1000000000;
    vector<vector<int>> edge(n, vector<int>(n, INF)), distance = edge;
    for (int i = 0; i < n; ++i) distance[i][i] = 0;
    for (int t = 0; t < m; ++t) {
        int u,v,w; cin >> u >> v >> w; --u; --v;
        edge[u][v] = edge[v][u] = distance[u][v] = distance[v][u] = w;
    }
    int s1,s2; cin >> s1 >> s2; --s1; --s2;
    for (int k = 0; k < n; ++k) for (int i = 0; i < n; ++i) for (int j = 0; j < n; ++j)
        distance[i][j] = min(distance[i][j], distance[i][k] + distance[k][j]);
    vector<vector<int>> cost(n, vector<int>(n, INF)), order(n, vector<int>(n));
    for (int a = 0; a < n; ++a) {
        cost[a][a] = 0;
        for (int k = 0; k < n; ++k) for (int i = 0; i < n; ++i) if (edge[k][i] != INF)
            cost[a][i] = min(cost[a][i], 2 * distance[a][k] + edge[k][i]);
        iota(order[a].begin(), order[a].end(), 0);
        sort(order[a].begin(), order[a].end(), [&](int i, int j) { return cost[a][i] < cost[a][j]; });
    }
    int states = n*n;
    const u32 UNREACHED = numeric_limits<u32>::max();
    vector<u32> answer(states, UNREACHED);
    vector<array<int,2>> done(states), cursor(states);
    RadixHeap heap;
    int start = s1*n+s2; answer[start] = 0; heap.push(0,start);
    auto schedule = [&](int state, int axis) {
        int a = state/n, b = state%n;
        int origin = axis == 0 ? a : b, other = axis == 0 ? b : a;
        int &position = cursor[state][axis];
        while (position < n) {
            int target = order[origin][position], weight = cost[origin][target];
            int covered = done[target*n+other][axis];
            if (covered < n && cost[other][order[other][covered]] <= weight) {
                heap.push(answer[state] + u32(weight), states + 2*state + axis); return;
            }
            ++position;
        }
    };
    int discovered = 1;
    while (heap.count && discovered < states) {
        auto [time, id] = heap.pop();
        if (id < u32(states)) { schedule(int(id),0); schedule(int(id),1); continue; }
        int encoded = int(id) - states, state = encoded/2, axis = encoded%2;
        int a = state/n, b = state%n;
        int origin = axis == 0 ? a : b, other = axis == 0 ? b : a;
        int target = order[origin][cursor[state][axis]], weight = cost[origin][target];
        int &covered = done[target*n+other][axis];
        while (covered < n && cost[other][order[other][covered]] <= weight) {
            int destination = order[other][covered++];
            int next = axis == 0 ? target*n+destination : destination*n+target;
            if (answer[next] == UNREACHED) {
                answer[next] = time; heap.push(time,next); ++discovered;
            }
        }
        ++cursor[state][axis]; schedule(state,axis);
    }
    for (int i = 0; i < n; ++i) for (int j = 0; j < n; ++j)
        cout << answer[i*n+j] << (j+1 == n ? '\n' : ' ');
}
```
