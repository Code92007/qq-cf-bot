# B · 雨鹿行走

本文按用户提供的 QOJ 题面截图独立推导。需要严格处理“强者自己也在等待时，弱者仍须等待”的规则。

## 先学什么

先学习事件驱动模拟、双向链表和带版本号的优先队列失效处理。这里维护两份随时间变化的排序；相邻元素的相遇就是排序证书失效事件。

## 阻挡关系与两份坐标排序

对每对相向、尚未相遇的鹿，间距进入 $(0,K]$ 时，给较弱者增加一个阻挡者；相遇或强者离开时，删除这个阻挡者。某只鹿的阻挡者数为零才以速度 $1$ 前进，否则静止。无需沿阻挡链递归更新：阻挡资格与强者是否静止无关。

阻挡关系只在两类几何事件改变：东向鹿与西向鹿间距等于 $K$，以及两鹿实际坐标相等。前者可转成两条移动轨迹相交：将所有东向鹿坐标加 $K$，西向鹿不变。

因此维护两份有序双向链表，一份按真实坐标，一份将东向鹿平移 $K$ 后排序。另维护离开端点的事件。只有相邻轨迹需要预约相遇事件；每个预约记版本号，邻接关系或速度改变时使旧预约失效。

## 同向鹿的平局顺序为什么重要

同坐标时固定规定：西向在东向之前；同为东向时弱者在前、强者在后；同为西向时强者在前、弱者在后。这正是运动方向上“强者可以穿过弱者”的顺序。

若同向弱者追到前方静止的强者，阻挡强者的每只异向鹿也会阻挡这个弱者，弱者不能越过强者。所以这种只接触、不改变上述顺序的追及无需触发事件。只预约速度上确实接近、且平局顺序将反转的相邻元素。异向鹿朝彼此前进，最多相遇一次；同向只有强者越过弱者，最多一次。每份链表的真实换序总数为 $O(n^2)$。

## 同一时刻必须整体处理

将时间和位置都扩大两倍，速度仍为 $-1,0,1$。所有事件时刻均为整数：运动与等待转折可在 $t+x,t-x$ 两坐标中归纳，整数初始位置和整数 $K$ 使等待结束所累积的等待时间为整数；两条运动轨迹相交至多产生半整数时间。最后离开时间为整数。

一次取出堆中最早时刻的全部事件。此时先保持旧速度不变，在每份链表中收集事件处**所有同坐标元素**。真实坐标组里的东西向配对删除阻挡，平移坐标组里的配对增加阻挡，然后按固定平局顺序重排整组。这样也覆盖很多轨迹同时相遇、部分轨迹正在等待的情况。

处理离开的鹿并清除其阻挡关系后，统一按新的阻挡数修改速度，再预约受影响的相邻对和离开事件。不能处理一对鹿后立刻修改速度，否则会改变同一时刻其他事件的含义。初始时即在出口的鹿先移除；初始同坐标鹿视为已经相遇。

## 正确性与复杂度

初始直接枚举所有配对建立正确的阻挡关系。在两个连续事件之间，排序、阻挡关系和速度均不变，线性移动准确。关系改变只可能发生在上述两种相交或离开事件；排序首次改变必有相邻证书失效，整组处理保证不会漏掉同一时刻的相交。统一更新后的阻挡计数再次与规则一致，归纳得出所有离开时间正确。

每次真正换序可计入某对鹿的一次穿越，组内操作也可计入这些相遇配对。邻居和速度改变只增加常数个预约。时间 $O(n^2\log n)$，空间 $O(n^2)$，包括配对标记和允许延迟删除的事件堆。实现用 64 位时间。

## 完整代码（C++17）

```cpp
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <queue>
#include <utility>
#include <vector>
using namespace std;
using ll = long long;
struct Event {
    ll time; int type, left, right, version;
    bool operator>(const Event &other) const { return time > other.time; }
};
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int T; cin >> T;
    while (T--) {
        int n; ll L,K; cin >> n >> L >> K;
        vector<ll> position(n), last(n), answer(n,-1);
        vector<int> direction(n), velocity(n), blockers(n), exitVersion(n), changedStamp(n,-1);
        vector<unsigned char> alive(n,1), active(size_t(n)*n);
        int remaining = n;
        for (int i = 0; i < n; ++i) {
            ll a; char d; cin >> a >> d; position[i] = 2*a; direction[i] = d == 'E' ? 1 : -1;
            if ((direction[i] == 1 && a == L) || (direction[i] == -1 && a == 0)) {
                alive[i] = 0; answer[i] = 0; --remaining;
            }
        }
        for (int i = 0; i < n; ++i) if (alive[i]) for (int j = i+1; j < n; ++j) if (alive[j] && direction[i] != direction[j]) {
            ll gap = direction[i] == 1 ? position[j]-position[i] : position[i]-position[j];
            if (gap > 0 && gap <= 2*K) { active[size_t(i)*n+j] = 1; ++blockers[i]; }
        }
        for (int i = 0; i < n; ++i) velocity[i] = alive[i] && blockers[i] == 0 ? direction[i] : 0;
        vector<vector<int>> previous(2,vector<int>(n,-1)), next(2,vector<int>(n,-1));
        vector<vector<int>> version(2,vector<int>(n)), dirtyStamp(2,vector<int>(n,-1)), seen(2,vector<int>(n,-1));
        auto tieLess = [&](int i, int j) {
            if (direction[i] != direction[j]) return direction[i] == -1;
            return direction[i] == 1 ? i < j : i > j;
        };
        auto coordinate = [&](int list, int i, ll time) {
            return position[i] + velocity[i]*(time-last[i]) + (list == 1 && direction[i] == 1 ? 2*K : 0);
        };
        priority_queue<Event,vector<Event>,greater<Event>> heap;
        auto scheduleEdge = [&](int list, int i, ll time) {
            if (i < 0 || !alive[i]) return;
            int j = next[list][i];
            if (j < 0 || !alive[j] || velocity[i] <= velocity[j] || !tieLess(j,i)) return;
            ll gap = coordinate(list,j,time)-coordinate(list,i,time);
            assert(gap >= 0 && gap % (velocity[i]-velocity[j]) == 0);
            ll when = time + gap/(velocity[i]-velocity[j]);
            assert(when > time);
            heap.push({when,list,i,j,version[list][i]});
        };
        auto scheduleExit = [&](int i, ll time) {
            if (!alive[i] || velocity[i] == 0) return;
            ll p = coordinate(0,i,time);
            ll when = time + (velocity[i] == 1 ? 2*L-p : p);
            assert(when > time);
            heap.push({when,2,i,-1,exitVersion[i]});
        };
        for (int list = 0; list < 2; ++list) {
            vector<int> order;
            for (int i = 0; i < n; ++i) if (alive[i]) order.push_back(i);
            sort(order.begin(),order.end(),[&](int i,int j) {
                ll x = coordinate(list,i,0), y = coordinate(list,j,0);
                return x != y ? x < y : tieLess(i,j);
            });
            for (int p = 0; p < int(order.size()); ++p) {
                int i = order[p]; previous[list][i] = p ? order[p-1] : -1;
                next[list][i] = p+1 < int(order.size()) ? order[p+1] : -1;
            }
            for (int i : order) scheduleEdge(list,i,0);
        }
        for (int i = 0; i < n; ++i) scheduleExit(i,0);
        int epoch = 0;
        auto valid = [&](const Event &e) {
            if (!alive[e.left]) return false;
            if (e.type == 2) return exitVersion[e.left] == e.version && velocity[e.left] != 0;
            return alive[e.right] && next[e.type][e.left] == e.right && version[e.type][e.left] == e.version;
        };
        while (remaining) {
            while (!heap.empty() && !valid(heap.top())) heap.pop();
            assert(!heap.empty());
            ll time = heap.top().time; ++epoch;
            vector<pair<int,int>> dirty;
            vector<int> changed, exits;
            auto markDirty = [&](int list,int i) {
                if (i >= 0 && dirtyStamp[list][i] != epoch) {
                    dirtyStamp[list][i] = epoch; ++version[list][i]; dirty.emplace_back(list,i);
                }
            };
            auto markChanged = [&](int i) {
                if (changedStamp[i] != epoch) { changedStamp[i] = epoch; changed.push_back(i); }
            };
            auto changePair = [&](int i,int j,bool turnOn) {
                if (i > j) swap(i,j);
                auto &flag = active[size_t(i)*n+j];
                if (bool(flag) != turnOn) { flag = turnOn; blockers[i] += turnOn ? 1 : -1; markChanged(i); }
            };
            while (!heap.empty() && heap.top().time == time) {
                Event e = heap.top(); heap.pop(); if (!valid(e)) continue;
                if (e.type == 2) { exits.push_back(e.left); continue; }
                int list = e.type;
                if (seen[list][e.left] == epoch) continue;
                ll value = coordinate(list,e.left,time);
                int first = e.left;
                while (previous[list][first] >= 0 && coordinate(list,previous[list][first],time) == value) first = previous[list][first];
                vector<int> group, east, west;
                int after = first;
                while (after >= 0 && coordinate(list,after,time) == value) {
                    group.push_back(after); seen[list][after] = epoch;
                    (direction[after] == 1 ? east : west).push_back(after);
                    after = next[list][after];
                }
                for (int i : east) for (int j : west) changePair(i,j,list == 1);
                int before = previous[list][first]; markDirty(list,before);
                for (int i : group) markDirty(list,i);
                sort(group.begin(),group.end(),tieLess);
                if (before >= 0) next[list][before] = group.front();
                if (after >= 0) previous[list][after] = group.back();
                for (int p = 0; p < int(group.size()); ++p) {
                    int i = group[p]; previous[list][i] = p ? group[p-1] : before;
                    next[list][i] = p+1 < int(group.size()) ? group[p+1] : after;
                }
            }
            for (int i : exits) if (alive[i]) {
                position[i] = coordinate(0,i,time); last[i] = time;
                alive[i] = 0; --remaining; assert(time % 2 == 0); answer[i] = time/2;
                ++exitVersion[i];
                for (int list = 0; list < 2; ++list) {
                    int before = previous[list][i], after = next[list][i];
                    if (before >= 0) next[list][before] = after;
                    if (after >= 0) previous[list][after] = before;
                    markDirty(list,before); markDirty(list,i);
                    previous[list][i] = next[list][i] = -1;
                }
                for (int j = 0; j < n; ++j) if (j != i && direction[i] != direction[j]) changePair(i,j,false);
            }
            for (int i : changed) if (alive[i]) {
                int v = blockers[i] ? 0 : direction[i];
                if (velocity[i] != v) {
                    position[i] = coordinate(0,i,time); last[i] = time; velocity[i] = v; ++exitVersion[i];
                    for (int list = 0; list < 2; ++list) { markDirty(list,previous[list][i]); markDirty(list,i); }
                    scheduleExit(i,time);
                }
            }
            for (auto [list,i] : dirty) scheduleEdge(list,i,time);
        }
        for (int i = 0; i < n; ++i) cout << answer[i] << (i+1 == n ? '\n' : ' ');
    }
}
```
