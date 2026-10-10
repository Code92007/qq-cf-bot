# 三工程联动首版运维

方案：[内部使用简化版](cpc-cross-project-integration.md)。历史：[迭代记录](cpc-integration/CHANGELOG.md)。

各工程也有独立说明：[DLUT CPC](https://github.com/Code92007/dlut-cpc/blob/main/docs/cpc-integration.md)、[OJ Wall](https://github.com/Code92007/oj-submission-wall/blob/main/docs/cpc-integration.md)。

本文命令在对应工程目录执行。服务先更新代码并保留实时运行库，再按以下步骤配置；命令不会用本地 seed 覆盖生产库。启用前分别用 SQLite 备份 API 或停写备份，保存原环境配置。

## 1. 配置和启用

dlut-cpc 的 `.env` 增加 `CPC_SYNC_TOKEN`，由管理员生成足够随机的服务间凭据。Compose 会传给容器。容器更新后执行：

```sh
docker compose exec -T dlut-cpc python tools/cpc_admin.py meta
```

该命令输出持久 authority UUID。它保存在运行库，搬迁时保留。

oj-submission-wall 的 `.env` 增加：

```dotenv
CPC_DLUT_URL=https://你的DLUT站点
CPC_DLUT_AUTHORITY_ID=上一步取得的UUID
CPC_SYNC_TOKEN=与DLUT配置相同的凭据
```

同机也可使用已配置的私网地址；跨服务器推荐 HTTPS。浏览器公开地址继续通过原 `PUBLIC_BASE_URL` 配置，必须与真实站点一致。初次同步：

```sh
docker compose exec -T oj-submission-wall python tools/cpc_admin.py sync
docker compose exec -T oj-submission-wall python tools/cpc_admin.py rosters
docker compose exec -T oj-submission-wall python tools/cpc_admin.py meta
```

cf-bot 的 `.env` 增加：

```dotenv
CPC_OJWALL_URL=https://你的OJWall站点
CPC_OJWALL_AUTHORITY_ID=OJWall上一步取得的UUID
```

CF Bot 已通过 `env_file` 接收配置。重启后用户可在区域赛页连接；未配置时原功能照常使用。三个服务地址可不同，不依赖同机 Docker 名称。

## 2. 成员审核

用户登录 oj-wall，进入 `/regionals`，输入部分姓名或学校/校区搜索成员，选择真实成员并填写核验说明。

管理员打开 [DLUT CPC 管理后台](https://dlut-cpc.wannafly.cn/admin)，用原管理员账号登录，进入“成员认证”。默认列出待审核申请，核对账号、成员、校区与核验说明后点击“通过”或“拒绝”并确认。切换到“已通过”可撤销认证；“全部状态”可查历史。审核者自动记录为当前管理员，核验材料只对管理员可见。现有后台密码及配置继续使用，迁移时连同原运行配置保存。

需要命令行时，在 dlut-cpc 执行：

```sh
docker compose exec -T dlut-cpc python tools/cpc_admin.py list
docker compose exec -T dlut-cpc python tools/cpc_admin.py review 申请UUID approved --reviewer 管理员名称
```

拒绝用 `rejected`，撤销已批准认领用 `revoked`。确认申请中的账号、成员、校区和联系证明；不根据相同姓名自动批准。批准后 oj-wall 的后台轮询会更新结果，也可手动安排更新。

2026-10-09 的 v4.1 已部署上述网页入口及成员搜索。备份目录为 `/root/backups/cpc-web-review-20261009-205955/`，内有两服务的 SQLite 一致备份、原环境配置、工作区补丁、构建日志、镜像回滚标签清单和上线验证结果；路径标记保存在 `/root/.cpc-web-review-backup`。管理员读取、匿名拒绝与 CSRF 拒绝已在线核验，实际认领没有被代审。

## 3. 现场榜单导入

先用 oj-wall 的 `rosters` 命令取得稳定 participation UUID。逐场核验榜单队伍行及题序，准备 JSON，例如：

```json
{
  "participation_id": "从rosters取得的参赛UUID",
  "contest_id": "icpc-2024-杭州",
  "team": "与参赛记录完全相同的队名",
  "source_url": "https://example.com/verified-final-scoreboard",
  "source_row": "来源榜单中的稳定队伍行ID",
  "accepted": ["A", "C"],
  "raw_row": {"说明": "建议保留原始榜单行或核验记录"}
}
```

这里的示例不是实际比赛结果。题号必须对应公共目录中的官方题序，管理员负责核对镜像是否换序；未知题号整批拒绝。将文件保存到容器可读的持久目录，例如宿主机 `data/onsite-row.json` 对应容器 `/data/onsite-row.json`。

```sh
docker compose exec -T oj-submission-wall python tools/cpc_admin.py import /data/onsite-row.json
docker compose exec -T oj-submission-wall python tools/cpc_admin.py import /data/onsite-row.json --confirm
```

无 `--confirm` 只输出文件预览，不代表验证通过。确认导入输出证据 ID；相同来源/行/参赛记录重导会替换当前结果，保留历史。撤销：

```sh
docker compose exec -T oj-submission-wall python tools/cpc_admin.py revoke 证据ID
```

历史缺少逐题榜单时暂不导入，不能用总解题数猜通过题。首版没有外站自动抓取，不会自动补全历年现场成绩。

## 4. 用户连接和迁移

用户在 oj-wall 区域赛页生成只读连接码，在 cf-bot 区域赛页粘贴。连接码生成时仅显示一次，不写 URL；180 天到期。重新生成或撤销会使旧码失效，cf-bot 下次同步识别后清除远端投影，口胡不受影响。

迁移需保留三工程主库及 UUID 映射、原始榜单文件、环境配置、oj-wall 令牌校验记录、cf-bot 保存的连接码。不能只复制源码或展示 JSON；SQLite 活跃库使用一致备份以包含 WAL 事务。

停止被迁服务写入，恢复到新机，核对 `meta` UUID，修改地址后恢复同步；同域名搬迁不需要重新连接。换域名时更新公开/API 地址，QOJ/洛谷插件可能需要更新目标并重新连接；成员认领和已导入成绩仍保留。同一 UUID 不同时运行两个生产写入端。

## 5. 验证

在 qq-cf-bot 目录运行跨工程合同测试：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_cpc_flow.py
```

默认使用相邻的 `../dlut-cpc`、`../oj-submission-wall` checkout；也可设置 `CPC_DLUT_CHECKOUT`、`CPC_WALL_CHECKOUT` 指向其他位置。测试使用三个临时数据库，不接触真实账号或真实榜单。领域流程在传输边界替换外站请求，HTTP 测试另起两个仅监听 `127.0.0.1` 的临时服务，验证真实路由、Bearer 鉴权和 Origin 检查；不访问生产服务器。部署时仍需检查实际 HTTPS 及服务凭据。

各工程还需运行自身回归测试。首次启用后用一个获批成员、一场核验榜单验证：oj-wall 显示现场标识，cf-bot 综合标记“现”，纯口胡视角没有新增通过；撤销证据后可在同步周期内取消现场覆盖。

## 6. 首版开发验收记录（2026-10-09）

以下为开发阶段的验收记录；发布前另对提交集独立验证，生产部署结果在本文后续追加。真人认领与现场榜单仍须管理员实际核验。

| 验证 | 结果 |
| --- | --- |
| qq-cf-bot Python 回归 | 合并已发布评级更新后，提交集 214 项通过 |
| dlut-cpc Python 回归 | 225 项运行，224 项通过、1 项跳过（缺少可选的一次性导入库） |
| oj-submission-wall Python 回归 | 完整工作区 58 项通过；本次提交集 24 项通过 |
| 三数据库流程与本地 HTTP 验收 | 10 项通过 |
| 前端统计合同 | 个人/现场默认覆盖、团队开关、去重、文本转义、口胡/代码隔离均通过 |
| 交付检查 | 三工程差异无空白错误；两个区域赛脚本语法通过；目录与协议辅助代码副本一致 |

流程入口为 `scripts/test_cpc_flow.py`，前端入口为 `tests/test_cpc_frontend.cjs`。部署启用仍按本文第 1–3 节执行，线上榜单可信度依赖管理员实际核验。

## 7. 生产部署记录（2026-10-09）

三工程代码已分别推送到 `origin/main`，部署在原服务器 `/root/` 下的同名目录。各工程新增自己的联动说明；服务器原有未提交的模型、浏览器同步等功能在合并时保留，并保存了 Git stash 和文件备份。

| 工程 | 本次代码提交 | 生产验证 |
| --- | --- | --- |
| qq-cf-bot | `1b01005` | 容器运行、`/health` 与区域赛页面正常；容器可通过 HTTPS 访问 OJ Wall；既有离线评级数据保留 |
| dlut-cpc | `1b2a1e5` | 容器 healthy；同步接口核对发布方 UUID；错误服务凭据返回 403 |
| oj-submission-wall | `90cc879` | 容器运行、`/api/health` 与区域赛页面正常；首次名单/认证同步完成；匿名读取本人进度返回 401 |

当前启用地址为 `https://dlut-cpc.wannafly.cn` → `https://oj-train-wall.wannafly.cn` → `https://cf-bot.wannafly.cn`。服务间同步凭据已配置并仅保存在服务器；用户本人连接码仍由用户在页面生成。

首次同步包含 284 名成员、318 条已确认参赛记录。部署未代替管理员进行真人审核或现场逐题榜单核验；用户可开始提交成员申请、生成连接码，现场成绩按第 3 节逐场导入。

| 生产发布方 | 持久 UUID（仅作本次部署核验记录） |
| --- | --- |
| dlut-cpc | `ecd45fa0-814d-44f2-afa9-40966e39a57f` |
| oj-submission-wall | `e2f792c3-4536-45ef-9b6e-bfd497c0f346` |
| qq-cf-bot | `c1c166cf-112c-4b1a-a75e-fddb83d08501` |

部署前后数据数量一致：CF Bot 5 个网站账号、75 条原提交；DLUT CPC 284 名成员、359 条成绩、954 条成员参赛关联；OJ Wall 17 个账号、95 条平台绑定、114123 条提交。未删除旧记录。

服务器回滚点为 `/root/backups/cpc-integration-20261009-173123/`：`manifest.json` 记录原镜像标签/提交/Compose 文件；每个工程保存 `database.sqlite3`、原工作区改动及原环境。上线后另存 `database-after.sqlite3`、`linked.env` 和 `verification.json`，一致备份及 UUID 映射核对通过。该目录包含私密配置，应保持仅管理员可读，不提交 Git。

回滚优先使用备份镜像、原配置和已保存源码，保留当前运行库；新增表可由旧代码忽略。不要用上线前数据库覆盖上线后的新记录。需要完整搬迁时，按第 4 节重新做停写的一致备份，不把本次发布备份当作长期增量备份。


## 9. v4.2 自动现场成绩同步

DLUT 原榜单入口统一沿用 `data/contest_ranklists.json`，由 roster 快照发布可选链接和学校别名，OJ Wall 不需要挂载 DLUT 目录。支持 XCPCIO 固定版本的 config/team/run 与 RankLand 原页面 SRK；CPC Finder 用于比赛链接和档案 ID 补充，不按解题总数生成 AC。

认证批准后最多约 5 分钟安排首次抓取；成功每天复核、失败每 5 分钟重试。已有批准认证会在升级后自动补刷。用户点击“更新认证状态”可主动安排重试；管理员补刷命令：

```sh
docker compose exec -T oj-submission-wall python tools/cpc_admin.py sync
```

页面“现场比赛通过”列出每场 AC、打星标记、原榜单和同步状态。线上提交表保持原始记录，按题与现场证据取并集；旧比赛未入公共目录时显示题目待映射。匹配失败、封榜或未知逐题状态保留上一份有效成绩并重试。

迁移除原有 SQLite、配置和公共目录外，保留 DLUT 的 `data/contest_ranklists.json` 与 OJ Wall 的整个 `data/cpc_sources/`。新 `cpc_onsite_sync` 表随主库备份，固定版本原始文件和哈希可供复核；无需新增地址耦合或中心服务。


v4.2 生产验证（2026-10-09）：DLUT CPC `838ca4a`、OJ Wall `a75117e`、主工程方案与验收 `df8713b` 已推送；前两者镜像重建，CF Bot 仅更新方案/验收文件。部署前一致备份和旧镜像标签位于 `/root/backups/cpc-auto-onsite-20261009-231051/`，标记文件 `/root/.cpc-auto-onsite-backup`；两个服务 UUID 保持原值，原有未提交功能保留。

已有认证用户衣泽民的后台同步实测完成 9/9 场，无失败项，保存 36 道现场 AC、17 份原始来源文件；2024 昆明打星队 C/E/H/J/L/M 六道进入当前目录。其余八场 30 道题保留现场历史及逐题证据，待公共目录映射；其中唯一 Gym 重现链接可与现有线上题号合并。本人进度实测个人线上 5 道、现场 36 道、重合 1 道，并集 40 道（含待目录映射的现场题）。原有 114,159 条线上提交全部仍在、无缺失；已有 1 条 CF Bot 连接刷新后收到 36 道现场 AC，身份保持 approved，未生成或更换连接码。

本次通过 DLUT 229 项后端测试（1 项可选依赖跳过）、OJ Wall 33 项、跨三工程 14 项与前端回归；公网页面现场记录入口、匿名进度接口 401、容器健康均实测通过。验证报告在备份目录 `onsite-verification.json`、`cf-onsite-verification.json`、`verification.json`。回滚可用 manifest 中镜像标签恢复前一版本，保留主库及证据文件；只有需要恢复数据库时才停写并使用一致备份，避免覆盖上线后新的真实提交。

## 10. 2019–2022 目录与区域赛页面迭代（2026-10-10）

CF Bot `7ca496a`、OJ Wall `8e21e32` 已推送并重建部署；DLUT CPC 无需改动。两运行服务使用相同 75 场、954 题目录，保留原 2023–2025 年，新增 2019–2022 年 42 场、528 题。OJ Wall 上线宽松题格表格、现场参赛记录表格、小团队开关及页面内年份菜单；匿名进度接口仍为 401。源码、目录来源及待补映射见 [历史目录说明](regional-history-catalog.md)。

部署前一致备份、原工作区补丁、配置及旧镜像标签保存在 `/root/backups/cpc-regional-history-20261010-004406/`，标记 `/root/.cpc-regional-history-backup`；两服务 UUID 与既有未提交功能保持。数据库恢复仍须先停写，避免覆盖上线后真实新增记录。

已有认证衣泽民强制补刷完成 9/9 场、36 道现场 AC，无失败项。其中 31 道映射到当前区域赛：2019 年 9 道、2020 年 16 道、2024 年 6 道；保留 2024 昆明打星队 C/E/H/J/L/M。另 5 道属于 2018 秦皇岛和 2019 CCPC 总决赛，继续保留现场历史，未扩展本次区域赛范围。扩展目录后识别个人线上 41 道，与现场重合 1 道，并集 76 道（含 5 道目录外现场题）；只增加题号识别，不生成个人提交。

部署前的 114,160 条线上提交均在、缺失 0。已有两个 CF Bot 连接分别收到 36/21 道现场 AC，当前目录可显示 31/21 道，身份均保持 approved；原有口胡、代码、草稿和导入记录未减少。验证报告位于备份目录 `verification.json`、`onsite-verification.json`、`cf-onsite-verification.json`。

本次通过目录校验、CF Bot 区域赛/评级 26 项及认证相关 16 项、OJ Wall 榜单/认证 14 项和前端回归。浏览器检查七年菜单、团队开关、现场表格、窄屏表格容器滚动。老赛 7 场线上题号待核验，不猜测平台题号；现场 AC 已可按规范题目 ID 展示，既有评级产物保持不变。

当日目录对齐复核：CF Bot `00c8440`、OJ Wall `fab5f9a` 已推送并重建，保留同期独立迭代的历史评级和原工作区功能。两份目录 SHA-256 为 `2b0dfa9343fde10e9a7e99262e3fa7a9c2c14e04c6630b0900f7229770a04dd5`；新增 528 题中 488 题具有核验后的线上别名、40 题仍待映射。秦皇岛重现 Gym 缺少 C 时不再推导不存在的线上别名，现场 C 的真实成绩继续保留。OJ Wall 不展示 rating。

此次备份在 `/root/backups/cpc-regional-align-20261010-132112/`，标记 `/root/.cpc-regional-align-backup`。现场补刷再次完成 9/9 场、36 AC，其中当前目录 31 AC、7 场已映射；两个既有 CF Bot 连接的现场缓存分别为 36/21 AC，目录内为 31/21 AC。核对备份中 114,767 条线上提交全部保留、缺失 0；CF Bot 原提交、代码、草稿及导入证据均未减少。两服务 UUID 保持原值，公网页面及匿名接口鉴权通过。验证报告存于本次备份；区域赛/评级 27 项、OJ Wall 联动 15 项及前端回归通过。

## 11. Coach 补题授权同步（2026-10-10）

Gym 104076（济南 2022）公开 VP 的 A/E/K/M 已在 OJ Wall，后续截图中的 C/D/G/J 不在匿名个人接口、按 handle 的比赛接口或该比赛全部 40,007 条公开提交中。用户确认开过 Coach，需本人授权核验非公开 MANAGER 提交。截图不作为直接导入依据。

OJ Wall `a2f8d34` 增加可选的官方签名 API 与交互配置命令，按 Wall 正式用户 ID 和 CF handle 双重匹配；首次授权自动回补十年窗口内历史，之后增量同步，分页失败不提交半份数据或推进回补标记。MANAGER 的真实 AC 进入线上进度，与团队 VP 和现场通过按题合并，但不生成参赛成绩或计入赛中对战。CF Bot 仍只读取 Wall 的进度接口，DLUT CPC 的职责不变。具体配置与迁移说明在 OJ Wall `docs/cpc-integration.md`。

已重建部署，备份 `/root/backups/cpc-coach-auth-20261010-172954/`，标记 `/root/.cpc-coach-auth-backup`；服务健康、原 114,767 条提交缺失 0、Wall UUID 保留，服务器原未提交功能通过 autostash 保留并恢复。新增签名与历史回补等 8 项测试、原有 Wall 测试共 43 项通过，前端回归通过。模拟数据验证目标 8/13；真实四道补题暂未导入，等待本人配置 API Key/secret 后复核并补刷。

在 CF API 设置生成本人 Key/secret 后，服务器交互输入，不把凭据写进命令历史或聊天：

```sh
cd /root/oj-submission-wall
docker compose exec oj-submission-wall python tools/configure_codeforces.py --owner-id 3 --handle Yzm007
```

授权文件在持久卷 `/data/codeforces-auth.json`，权限 0600；迁移时与原 Wall 数据库及 data 卷一起复制。Key 只保存在 Wall，其他两服务不接收该凭据。
