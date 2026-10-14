# 算法竞赛冰山资料说明

2026-10-15 合并版包含 390 个知识点、8 个深度层级、9 个领域。简介为重新撰写的短说明；层级、难度与常见程度属于编辑判断，不是使用频率统计，也不是学习路线。

## 资料来源

- [OI Wiki](https://oi-wiki.org/) 是主体阅读入口；首先核对其目录和文档路径，再补充具体专题。
- 用户提供的算法清单、五列算法表、XCPC 思维导图：补齐基础语言、排序、搜索、DP、数据结构、图论、数学与几何知识点。图中的奖牌等级和泛泛评价不作为算法条目。
- 用户提供的 Um_nik「Things I don't know」截图：补齐归并树、二项堆、SPQR 树、预流推进、强多项式费用流、动态凸包、生成函数微分方程与集合幂级数复合。原帖的玩笑与评价不作为技术结论。
- [codeforces-go，用户指定的 fork](https://github.com/Zhonghe-zhao/codeforces-go)：按 README 标注原模板库作者为灵茶山艾府，核对 `copypasta` 下的实际实现；模板入口固定到提交 `2a7acdb9cbb4ed25488e6ac84cc6e6f89b66a2a1` 的文件行号。只有 TODO 的条目不标注为已有实现。
- [cp-algorithms](https://cp-algorithms.com/)、[USACO Guide](https://usaco.guide/)、[KACTL](https://github.com/kth-competitive-programming/kactl)、[noshi91 Library](https://noshi91.github.io/Library/) 补充专题与实现。
- 更冷门的知识使用作者文章、原始论文或官方库文档，包括 Elegia 的集合幂级数复合文章、生成函数微分技巧文章、MIT 论文库中的 Orlin 费用流论文，以及 OGDF、CGAL 和 Princeton Algorithms 文档。
- 用户补充的三张数学工具、字符串与图论目录截图：新增 35 个独立专题，覆盖组合恒等式、偏序、矩阵、概率模型与进阶几何；核对 Wolfram MathWorld、SageMath、MIT OpenCourseWare、StatLect、作者论文和大学讲义，保留可直接阅读的资料入口。

初稿的 221 个知识点，在前三份资料中补充 94 个；模板库和 Um_nik 截图再补充 40 个，最后三张目录截图补充 35 个。另为已有知识点添加别名、模板或延伸阅读，避免为每份来源重复创建条目。

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
| Taylor 平移、阶乘归一化与卷积 | 多项式与连续点值平移 |
| 置换循环类型与 EGF | 指数生成函数 |
| Burnside 与循环指标 | Burnside 与 Pólya 计数 |
| 静态 AC 自动机转动态模式集 | 二进制分组与静态结构动态化；附 AC 自动机入口 |
| 自动机状态乘积、避免连续 k 个相同符号 | 自动机 DP |
| 规范选择下一次出现 | 序列自动机 |
| Tarjan 优化朱刘算法 | 最小树形图；已有快速实现资料 |
| 矩阵树与矩阵森林定理 | 矩阵树定理、矩阵森林定理两个独立条目 |
| Gale–Ryser 与竞赛图得分序列 | 分开为 Gale–Ryser 定理和 Landau 定理，分别对应二分图和竞赛图 |
| Euler 函数与 Dirichlet 逆 | 欧拉函数、狄利克雷卷积 |
| 带符号整除与 floor_sum | 类欧几里得算法 |
| 无限棋盘上的骑士距离 | 无限棋盘骑士距离；不引用遗漏小坐标例外的模板 |
| 椭圆仿射表示、支撑函数、弦 | 仿射变换、支撑函数、圆锥曲线 |
| 椭圆弓形面积、椭圆弧长 | Green 公式与几何矩、椭圆积分，区分面积与弧长 |

Wavelet Matrix 保留为另一种组织方式；子集变换、子集卷积和集合幂级数复合保留为不同层次的专题。多项式求逆、除法、开根也有独立入口，原有初等函数条目聚焦 ln / exp。

截图中的“特殊矩阵速查”“偏统计数建模路线”“逻辑条件判定”等宽泛章节不直接变成知识点；可识别的工具并入相应条目。“Abel 型二项式反演”没有给出具体公式，先提供 Abel 二项式定理入口，不与微分方程中的 Abel 恒等式混淆。Carmichael 函数指单位群指数，不是 Carmichael 伪素数；SG 方法限于相应的公平组合游戏，二元能量图割注明次模条件。

## 数据与展示约定

- `url` 是名称点击后的主要学习资料，`kind` 区分文章与实现。
- `references` 是说明卡片中的可选补充资料，每个链接注明实现参考或延伸阅读。
- 公开地图无需登录；知识点数量和每层计数从 JSON 自动计算。
- 搜索包含标题、别名和简介；短英文缩写按词首匹配，避免搜索 NTT 时误中 Segment Tree。
- 数据检查保证 ID、标题唯一，领域、层级和分值有效，所有资料使用 HTTPS；模板入口必须固定提交并包含行号。
