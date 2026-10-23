# 区域赛预置题解

当前共 **37 篇**，按“2026 → 2025 → 更早年份”的顺序补充。本批在既有长春 13 篇基础上新增 2025 年 24 篇。

| 年份 / 比赛 | 收录 | 状态 |
| --- | --- | --- |
| 2026 CCPC 长春 | 13/13 | A–M 齐全 |
| 2026 ICPC 西安 | 0/13 | 按用户要求跳过；尚未取得官方题解 |
| 2025 ICPC 上海 | 13/13 | A–M 齐全 |
| 2025 ICPC 南京 | 11/13 | D、L 已取得官方讲义，但详细推导或构造校验未完成 |
| 2025 其余比赛 | 0 | 尚未扩写，不代表没有官方题解 |

2025 全年目录有 13 场、167 题，目前覆盖其中 24 题。尚未开始 2024 及更早年份；这里记录的是实际进度，未启用定时生成任务。

## 在网页中阅读

登录本站，进入 `/regionals` → 选择 2026 长春 → 点击题号。工作台提供：

- **先学什么**：先修知识的学习顺序，以及判断自己是否掌握的练习。
- **渐进提示**：每次只展开下一条，共三条，从观察逐步走到算法。
- **完整题解**：核心观察、推导、例子、正确性、复杂度、实现细节和易错点。

只有主动点击才返回相应内容，切题会收起题解。提示级别和完整题解的查看记录按用户保存；读题解不会计为口胡通过或代码 AC，也不会改动草稿与 Rating。没有题面缓存时，已预置题解的题目仍能立即打开阅读；「准备中文题面」沿用原有取题和翻译流程。

阅读本地题解无需调用模型或访问 QOJ。原题链接与官方附件的访问权限由 QOJ 决定。

## 按场次下载 Markdown

在比赛墙每场赛站名称下点击 **下载题解 Markdown · 已收录数/总题数**。文件名包含赛事、年份与赛站，UTF-8 编码，内容包括：

- 全场目录与题号锚点，始终按原题号排序，不受页面 Rating 排序影响。
- 已收录题目的完整详解与学习路径、官方来源、PDF 页码、版本和校验范围。
- 尚未收录题目的占位与原因；例如南京当前为 11/13，不能视为 13 题齐全。

无题解的比赛显示「题解待补」。下载只读取工程内文件，不调用模型、抓取题面，也不更改个人草稿、查看记录、口胡状态或 AC 状态。合集属于公开材料，下载接口无需登录；单题阅读记录仍按用户保存。

接口：`GET /api/regionals/editorials.md?contest=<比赛ID>`。返回 Markdown 附件；不存在、未收录或含多个比赛 ID 的请求返回 404。可用于离线阅读和后续批量备份。

## 来源与内容目录

依据 [QOJ 4582 长春正式赛](https://qoj.ac/contest/4582) 提供的 [官方讲义](https://qoj.ac/download.php?type=attachments&id=4582&r=1)，并对照 [官方题面](https://qoj.ac/download.php?type=attachments&id=4582&r=0)。讲义署名清华大学学生算法协会 THUSAA。以下文字是本工程重新组织的中文详解，补充的推导与例子不代表出题方原文。

| 题号 | 题目 | 主要内容 |
| --- | --- | --- |
| [A](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-A.md) | 又一道纸笔问题 | 路径拆分、相邻列贪心匹配 |
| [B](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-B.md) | 别样的选课大战 | LCA 费用拆分、凸费用最小费用流 |
| [C](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-C.md) | 无忧旋律 | 循环起点、计数投票 |
| [D](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-D.md) | 平均 | 丢番图方程、最少轮数、交互构造 |
| [E](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-E.md) | 遍历 | 小种子与可重复扩展的树构造 |
| [F](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-F.md) | 删除 | 最大值划分、删除轮数前缀、区间 DP |
| [G](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-G.md) | 异或王国 | 异或差分、连通块奇偶、桥 |
| [H](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-H.md) | 数学王国 | 一步期望递推、对称多项式、方差推导 |
| [I](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-I.md) | 事不过三 | 游程编码、长度界与唯一解码 |
| [J](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-J.md) | 送给好友的惊喜 | 按位必要条件、构造与验证 |
| [K](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-K.md) | 纸带染色 | 双端队列维护区间、离线询问与树状数组 |
| [L](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-L.md) | 故事 | 基本操作、交替权值、可达性与下界 |
| [M](../src/qq_cf_bot/catalog/editorials/2026/ccpc-changchun-M.md) | 余镜 | 回文中心、差值 gcd、约数累计 |

### 2025 ICPC 上海

依据 [THUSAA 公开仓库](https://www.gitlink.org.cn/thusaa/ICPC2025shanghai) 中的 `solutions.pdf`、正式题面和 accepted 标程；该仓库由出题方公开，清单保存所用提交版本和 PDF 哈希，对应 [QOJ 2908](https://qoj.ac/contest/2908)。

| 题号 | 题目 | 前置知识入口 |
| --- | --- | --- |
| [A](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-A.md) | Menji, we miss you! | 依次学习树的深度、LCA 的距离公式、二分答案、带点权的树重心。 |
| [B](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-B.md) | Hamu | 先学图的连通分量、二分染色、DFS 回溯和奇偶不变量。 |
| [C](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-C.md) | Singularity | 先学排列、逆序、按中位数二分值域、前缀和以及构造中的倍增势能。 |
| [D](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-D.md) | Not a subset sum | 需要二进制下标、分治、递归复杂度。 |
| [E](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-E.md) | Flower' s land 3 | 先学汉明距离、乘法原理、DFS 的进入与撤销，以及维护“当前与目标不同的位置集合”。 |
| [F](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-F.md) | Flower' s land 4 | 依次学习线段与直线的区别、点在线的哪一侧、离线扫描线、直线包络。 |
| [G](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-G.md) | Gemcrate | 依次学按位异或、按位与、线性基的插入与最大子集异或。 |
| [H](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-H.md) | AGI | 需要异或、奇偶计数和博弈中的配对策略。 |
| [I](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-I.md) | Round screws | 需要动态规划、按二进制位理解异或、值域分块。 |
| [J](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-J.md) | Yet another mailbox problem | 先学字典序、Trie 的先序遍历、懒生成，以及“第一个孩子/下一个兄弟”的树表示。 |
| [K](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-K.md) | No more regrets | 建议依次学平方分块、区间加/赋值懒标记、前缀最小值与最大值、二分查找。 |
| [L](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-L.md) | Yet another permutation problem | 依次学习区间 DP、排列相对大小、计数去重的规范形式。 |
| [M](../src/qq_cf_bot/catalog/editorials/2025/icpc-shanghai-M.md) | Yet another 01 problem | 依次学习满二叉树与卡塔兰数、加权计数、生成函数、分治多项式乘法与 NTT。 |

### 2025 ICPC 南京

依据 [SUA 官方比赛页](https://sua.ac/wiki/2025-icpc-nanjing/) 的 [中文讲义](https://sua.ac/wiki/2025-icpc-nanjing/tutorial-sketch-zh.pdf) 与 [正式中文题面](https://sua.ac/wiki/2025-icpc-nanjing/contest-zh.pdf)，对应 [QOJ 2581](https://qoj.ac/contest/2581)。A 的行号笔误、I 的“上次支付车费”历史起点均按正式规则展开。D、L 尚未发布可读详解，不能把官方材料存在等同于扩写已经完成。

| 题号 | 题目 | 前置知识入口 |
| --- | --- | --- |
| [A](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-A.md) | Wow, It’s Yesterday Six Times More | 需要理解交互题的输出刷新、网格移动模拟，以及用观测值排除候选的分类讨论。 |
| [B](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-B.md) | What, More Kangaroos? | 学习顺序是：向量点积的正负 → 叉积与极角排序 → 环形双指针。 |
| [C](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-C.md) | Distributing Candies | 只需要正整数、整除和奇偶性。 |
| D | Fallleaves01 and Golf | 待推导 / 构造校验 |
| [E](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-E.md) | Cyan White Tree | 建议依次学：树上路径与 LCA、树形 DP、按一个条件取后缀最大值、长链剖分的“继承最长儿子”思想。 |
| [F](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-F.md) | Bitwise And Path | 先学并查集维护无向图连通性，再学二进制集合的包含关系。 |
| [G](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-G.md) | Bucket Bonanza | 需要排序、前缀和、二分查找，以及比较一次操作前后总量的贪心证明。 |
| [H](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-H.md) | Pen Pineapple Apple Pen | 需要 KMP 的前缀函数、border（同时为前缀和后缀的串）、二维容斥。 |
| [I](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-I.md) | Chi Fan | 按顺序学习背包 DP、条件期望、用少量二进制位记录历史。 |
| [J](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-J.md) | Trajan Algorithm | 先掌握无向图 DFS 的树边、返祖边，再学割点与桥的不同判定。 |
| [K](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-K.md) | Xiangqi | 需要有向图、反向边、队列和“存在一个选择”与“所有选择”的区别。 |
| L | Regional Champion | 待推导 / 构造校验 |
| [M](../src/qq_cf_bot/catalog/editorials/2025/icpc-nanjing-M.md) | Many Convex Polygons | 学习路径是：叉积与鞋带公式 → 组合数与阶乘逆元 → 多项式卷积 → NTT。 |

版本清单在 `src/qq_cf_bot/catalog/regional_editorials.json`，包含文件路径、三条提示、学习入口、官方 URL、文件 SHA-256、核验时间和对应 PDF 实际页码。官方 PDF 有动画重复页，页码不等于页脚的幻灯片编号。原 PDF 未复制进发行包。

## 已完成的校验

长春 13 题完成 **20,001 项**校验；上海 13 题完成 **8,265 项**；南京 11 题完成 **225,282 项**（其中 A 的 213,444 项覆盖全部合法隐藏棋盘）。总计 **253,548 项**。这些数量包含穷举、构造模拟与随机对拍，不能当作在线 AC 证明。验证程序不调用模型或远端 OJ：

```bash
python3 scripts/validate_changchun_editorials.py --report src/qq_cf_bot/catalog/regional_editorial_validation.json
python3 scripts/validate_shanghai_editorials.py --report src/qq_cf_bot/catalog/regional_editorial_validation_shanghai_2025.json
# 南京校验脚本使用 int.bit_count，需要 Python 3.10+
python3 scripts/validate_nanjing_editorials.py --report src/qq_cf_bot/catalog/regional_editorial_validation_nanjing_2025.json
PYTHONPATH=src:tests python3 -m unittest test_regional_editorials test_regional
python3 scripts/validate_regional_catalog.py
```

示例：F 与小规模所有排列的同步删除模拟比较；H 与精确有理数马尔可夫方程比较；I 枚举长度至 12 的所有二进制串检查长度限制、禁止连续三字符和唯一解码；L 枚举全部可执行的回文替换。D 检查压缩构造的两条交互分支；E 用树上真实 BFS 距离核验构造。

三个 `regional_editorial_validation*.json` 分别记录每题方法、数量与对应 Markdown 哈希；清单中的 `validation_report` 指向适用报告。上海 M 与南京 M 只验证组合公式及朴素卷积，未验证 NTT 的完整实现；南京 E 只验证数学转移，未验证长链延迟数组的极限实现。这里验证的是算法解释和构造在所列小规模上的一致性，**尚未在线评测，也未完成极限数据性能验证**。自动化测试另外覆盖鉴权、CSRF、未点击时不返回题解正文、阅读记录隔离与持久化、HTML 安全过滤、不等式显示、整场 UTF-8 附件、部分收录提示、草稿和完成状态不变。相关接口与存储测试共 48 项通过；浏览器已实际下载上海 13 题合集并检查几何题的不等式显示。

## 后续维护

先核实比赛题单和官方题解来源，再逐题独立扩写。以正式题面为准记录输入范围与模数，解释官方讲义略过的推导；每题写出具体先修知识与自检问题。来源不完整时保留待补，不能用猜测补成“官方题解”。

新增 Markdown 后，在清单中登记来源、页码、版本、学习入口和三条递进提示；执行与该算法适合的独立验证，再更新报告哈希。打包配置已包含 `catalog/editorials/*/*.md`，服务直接随发行包加载，不需要运行时生成或人工导入数据库。
