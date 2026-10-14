# 算法竞赛冰山资料说明

2026-10-15 合并版包含 355 个知识点、8 个深度层级、9 个领域。简介为重新撰写的短说明；层级、难度与常见程度属于编辑判断，不是使用频率统计，也不是学习路线。

## 资料来源

- [OI Wiki](https://oi-wiki.org/) 是主体阅读入口；首先核对其目录和文档路径，再补充具体专题。
- 用户提供的算法清单、五列算法表、XCPC 思维导图：补齐基础语言、排序、搜索、DP、数据结构、图论、数学与几何知识点。图中的奖牌等级和泛泛评价不作为算法条目。
- 用户提供的 Um_nik「Things I don't know」截图：补齐归并树、二项堆、SPQR 树、预流推进、强多项式费用流、动态凸包、生成函数微分方程与集合幂级数复合。原帖的玩笑与评价不作为技术结论。
- [codeforces-go，用户指定的 fork](https://github.com/Zhonghe-zhao/codeforces-go)：按 README 标注原模板库作者为灵茶山艾府，核对 `copypasta` 下的实际实现；模板入口固定到提交 `2a7acdb9cbb4ed25488e6ac84cc6e6f89b66a2a1` 的文件行号。只有 TODO 的条目不标注为已有实现。
- [cp-algorithms](https://cp-algorithms.com/)、[USACO Guide](https://usaco.guide/)、[KACTL](https://github.com/kth-competitive-programming/kactl)、[noshi91 Library](https://noshi91.github.io/Library/) 补充专题与实现。
- 更冷门的知识使用作者文章、原始论文或官方库文档，包括 Elegia 的集合幂级数复合文章、生成函数微分技巧文章、MIT 论文库中的 Orlin 费用流论文，以及 OGDF、CGAL 和 Princeton Algorithms 文档。

初稿的 221 个知识点，在前三份资料中补充 94 个；模板库和新截图再补充 40 个独立知识点。另为已有知识点添加模板或延伸阅读，避免为每份来源重复创建条目。

## 去重规则

以知识概念作为条目身份，常见中文名、英文名、缩写与别名合并到 `aliases`。概述与独立的进阶专题可以共存；同一概念的不同资料放在 `references`，不复制条目。

| 输入名称 | 合并到的知识点 |
| --- | --- |
| exKMP、扩展 KMP | Z 函数 |
| 回文自动机 | 回文树 |
| LCT、LinkCutTree | Link-Cut Tree |
| Prufer、普吕弗序列 | Prüfer 序列 |
| Burnside、Polya、Pólya | Burnside 与 Pólya 计数 |
| 基尔霍夫矩阵、Kirchhoff | 矩阵树定理 |
| 最小割树 | Gomory–Hu 树 |
| DLX | Dancing Links |
| 线段树合并、线段树分裂 | 线段树合并与分裂 |
| 动态树分治、动态点分治 | 动态点分治 |
| 有源汇上下界最大流等 | 上下界网络流 |
| 任意模数 NTT、MTT | 任意模数卷积 |
| 分治 FFT、分治 NTT | 分治 FFT / NTT |
| Sweepline Mo、Offline Again | 莫队二次离线 |
| 线性预处理、常数查询 RMQ | Farach–Colton–Bender |
| Wavelet Tree、小波树 | 划分树 / Wavelet Tree |
| Preflow Push、HLPP | 预流推进 |

Wavelet Matrix 保留为另一种组织方式；子集变换、子集卷积和集合幂级数复合保留为不同层次的专题。多项式求逆、除法、开根也有独立入口，原有初等函数条目聚焦 ln / exp。

## 数据与展示约定

- `url` 是名称点击后的主要学习资料，`kind` 区分文章与实现。
- `references` 是说明卡片中的可选补充资料，每个链接注明实现参考或延伸阅读。
- 公开地图无需登录；知识点数量和每层计数从 JSON 自动计算。
- 搜索包含标题、别名和简介；短英文缩写按词首匹配，避免搜索 NTT 时误中 Segment Tree。
- 数据检查保证 ID、标题唯一，领域、层级和分值有效，所有资料使用 HTTPS；模板入口必须固定提交并包含行号。
