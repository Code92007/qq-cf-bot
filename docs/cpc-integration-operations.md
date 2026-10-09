# 三工程联动首版运维

方案：[内部使用简化版](cpc-cross-project-integration.md)。历史：[迭代记录](cpc-integration/CHANGELOG.md)。

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

用户登录 oj-wall，进入 `/regionals`，选择真实成员并填写核验说明。管理员在 dlut-cpc 执行：

```sh
docker compose exec -T dlut-cpc python tools/cpc_admin.py list
docker compose exec -T dlut-cpc python tools/cpc_admin.py review 申请UUID approved --reviewer 管理员名称
```

拒绝用 `rejected`，撤销已批准认领用 `revoked`。确认申请中的账号、成员、校区和联系证明；不根据相同姓名自动批准。批准后 oj-wall 的后台轮询会更新结果，也可手动安排更新。

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
