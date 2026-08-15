# QQ Codeforces 题目推送机器人

基于 OneBot v11 的 QQ 群机器人。核心目标是群里发送 `/new` 后推送一题不重复的 Codeforces 题目，题面使用洛谷 CF 中文镜像渲染成图片；代码提交使用绑定的 Codeforces 练习账号远端提交，最终结果以 Codeforces verdict 为准。

## 功能

- `/new`：按本群默认难度推送一道题，默认 `1900-2600`。
- `/new 2100 2400`：临时按 `2100-2400` 推一道题，不修改群默认配置。
- `/cfset rating 1900 2600`：设置本群默认题目难度。
- `/rating`：查看本群默认题目难度。
- `/cur`：重新发送当前题目。
- `/giveup`：放弃当前题目；该题仍计入已推送，不会重复。
- `/submitcode cpp + 代码`：提交当前题代码到 Codeforces，返回 AC/WA/TLE/CE 等 verdict。
- `/ranklist`：发送群内榜单图片。
- `/submit 做法`：大模型口头做法审核，默认开启。审核前会优先读取题解库，用题面、洛谷公开题解、CF 题解链接/内容和可选 AC 代码片段校对做法。
- `/solutions`：查看当前题已经缓存的题解来源和链接。

## 部署前准备

1. 准备一个 OneBot v11 网关，例如 NapCat、Lagrange.OneBot 或其他兼容实现。
2. OneBot HTTP API 示例：`http://127.0.0.1:3000`。
3. OneBot 反向 HTTP 上报地址填：`http://机器人服务器:8088/onebot`。
4. 准备一个专用 Codeforces 练习账号。不要用主号，避免账号风控影响正常使用。

## Docker 部署

```bash
cp .env.example .env
# 编辑 .env，填 ONEBOT_HTTP_URL、BOT_ALLOWED_GROUPS、CF_* 等配置
docker compose up -d --build
```

健康检查：

```bash
curl http://127.0.0.1:8088/health
```

OneBot 和机器人在同一台机器时，`ONEBOT_HTTP_URL` 通常填 `http://127.0.0.1:3000`。如果 OneBot 在另一台机器，填 OneBot HTTP API 的可访问地址。

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
playwright install chromium
python -m qq_cf_bot
```

如果系统 Python 低于 3.10，建议直接使用 Docker；Dockerfile 默认使用 Python 3.11。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ONEBOT_HTTP_URL` | `http://127.0.0.1:3000` | OneBot HTTP API 地址 |
| `ONEBOT_ACCESS_TOKEN` | 空 | OneBot access token |
| `ONEBOT_IMAGE_MODE` | `base64` | 图片发送方式；`base64` 不要求 OneBot 读取本地文件 |
| `BOT_HOST` | `127.0.0.1` | 机器人监听地址；Docker 中为 `0.0.0.0` |
| `BOT_PORT` | `8088` | 机器人监听端口 |
| `BOT_ALLOWED_GROUPS` | 空 | 允许使用的群号，逗号分隔；空表示所有群 |
| `BOT_DATA_DIR` | `data` | SQLite、题库缓存和图片输出目录 |
| `CF_MIN_RATING` | `1900` | 默认最低题目 rating |
| `CF_MAX_RATING` | `2600` | 默认最高题目 rating |
| `BOT_DEDUP_SCOPE` | `group` | `group` 每群去重，`global` 全局去重 |
| `FALLBACK_STATEMENT_SOURCE` | `codeforces` | 洛谷中文题面失败时，回退到 Codeforces 官方英文题面 |
| `CF_SUBMIT_ENABLED` | `false` | 是否开启 `/submitcode` 远端提交 |
| `CF_USERNAME` | 空 | Codeforces 登录账号或邮箱 |
| `CF_PASSWORD` | 空 | Codeforces 密码，只放在服务器 `.env`，不要提交到 GitHub |
| `CF_HANDLE` | `CF_USERNAME` | Codeforces handle，用于轮询提交记录 |
| `CF_SUBMIT_DEFAULT_LANGUAGE` | `cpp` | `/submitcode` 未指定语言时的默认语言 |
| `CF_SUBMIT_LANGUAGE_ID` | 空 | 可选，强制使用 CF 表单里的语言 ID |
| `CF_SUBMIT_MIN_INTERVAL_SECONDS` | `180` | 全局最小提交间隔，避免短期大量提交 |
| `CF_SUBMIT_POLL_INTERVAL_SECONDS` | `8` | 轮询 verdict 间隔 |
| `CF_SUBMIT_POLL_TIMEOUT_SECONDS` | `180` | 单次提交最长等待 verdict 时间 |
| `CF_AUTO_SUBMIT_DIRECT_CODE` | `false` | 是否自动识别群里的裸代码并提交，建议保持关闭 |
| `JUDGE_ENABLED` | `true` | 是否开启 `/submit` 口头做法审核 |
| `JUDGE_API_URL` | `https://api.openai.com/v1/chat/completions` | OpenAI-compatible chat completions 地址 |
| `JUDGE_API_KEY` | 空 | 口头做法审核模型 key |
| `JUDGE_MODEL` | 空 | 口头做法审核模型名 |
| `JUDGE_STATEMENT_MAX_CHARS` | `12000` | 单次判题传给模型的题面最大字符数 |
| `JUDGE_SOLUTION_CONTEXT_MAX_CHARS` | `10000` | 单次判题传给模型的题解库上下文最大字符数 |
| `TRANSLATE_ENABLED` | `false` | 是否用 OpenAI-compatible 模型把 CF 英文题面翻译成中文 |
| `TRANSLATE_API_URL` | `JUDGE_API_URL` | 翻译模型 API；为空时复用 `JUDGE_API_URL` |
| `TRANSLATE_API_KEY` | `JUDGE_API_KEY` | 翻译模型 key；为空时复用 `JUDGE_API_KEY` |
| `TRANSLATE_MODEL` | `JUDGE_MODEL` | 翻译模型名；为空时复用 `JUDGE_MODEL` |
| `TRANSLATE_TIMEOUT_SECONDS` | `60` | 单次翻译请求超时 |
| `TRANSLATE_MAX_CHARS` | `24000` | 单次翻译传给模型的题面最大字符数 |
| `SOLUTION_BANK_ENABLED` | `true` | 是否开启题解库缓存 |
| `SOLUTION_BANK_MIN_REFS` | `1` | 每题至少缓存多少条参考材料后不再主动抓取 |
| `SOLUTION_BANK_MAX_REFS` | `4` | 每题最多缓存/提供多少条参考材料 |
| `SOLUTION_BANK_MAX_REF_CHARS` | `5000` | 每条参考材料最大缓存字符数 |
| `SOLUTION_BANK_FETCH_LUOGU` | `true` | 是否抓取洛谷公开题解 |
| `SOLUTION_BANK_FETCH_CF_EDITORIAL` | `true` | 是否抓取 Codeforces 题解/教程链接和内容 |
| `SOLUTION_BANK_FETCH_CF_AC_CODE` | `false` | 是否抓取少量 CF AC 代码；需要 CF 登录态，默认关闭 |

## `/submitcode` 用法

推荐使用代码块：

````text
/submitcode cpp
```cpp
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    return 0;
}
```
````

也支持不带代码块：

```text
/submitcode cpp
#include <bits/stdc++.h>
using namespace std;
int main() { return 0; }
```

注意：

- `/submitcode` 只提交当前群的当前题。
- 提交队列是全局单线程，默认至少间隔 180 秒。
- Codeforces 可能触发验证码、二次验证或账号安全确认，此时远端提交会失败，需要先手动登录账号处理。
- 不要在正在进行的正式比赛中使用该机器人提交代码。

## `/submit` 和题解库

`/submit` 适合群友提交口头做法、复杂度和关键边界处理。机器人会：

1. 读取当前题的缓存题解库。
2. 如果题解库不足且之前没抓过，尝试抓取洛谷公开题解和 Codeforces 题解/教程。
3. 如果 `SOLUTION_BANK_FETCH_CF_AC_CODE=true` 且 CF 账号可登录，再限量抓取 AC 代码片段。
4. 把题面和受限长度的参考材料交给大模型审核。

题解库保存在 `data/bot.sqlite3`，一题可以对应多条题解，后续同一题不会重复抓取。模型只用于做法审核，不用于 `/submitcode` 的最终 verdict。

## 题面兜底和缓存

`/new` 优先抓取洛谷中文题面。若洛谷返回 403 或暂时不可用，默认回退到 Codeforces 官方英文题面，避免出题失败。

如果配置 `TRANSLATE_ENABLED=true` 且提供 OpenAI-compatible 翻译模型，机器人会把 Codeforces 英文题面翻译成中文再渲染。成功生成的题面会缓存到 `data/bot.sqlite3` 的题面缓存中，当前题图片也会保存在 `data/assets`；后续同题复用缓存，不会重复请求翻译。

## GitHub 上传注意

可以直接上传本工程，但不要上传以下内容：

- `.env`
- `data/`
- 任何真实账号、密码、access token

`.gitignore` 已经默认忽略这些文件。
