# Stock Research Agent

> A 股 AI 投研助手。两个入口、两条链路，同一套数据层与后端：
>
> - `/analysis` 个股研究：输入公司名 → 自动产出 10 章节研究报告
> - `/daily` 每日复盘：输入交易日 → 自动产出盘面复盘报告 + 可分享的复盘卡片
>
> 数据来自**同花顺金融数据 API（真实数据）**：指标、龙头排名、卡片字段全部由代码计算，
> DeepSeek 只负责定性判断，它写进正文的盘面数字还会被逐个回查校验。

## 1. 项目介绍

这是一个 7 天从零构建、之后持续迭代的 Agent 产品：用实战串联 Agent 全栈能力
（原生 Function Calling、记忆、LangGraph 工作流、MCP、SSE 流式前端），
并落成一个能天天用的**垂直领域 Agent**。

规模参考：产品代码约 5.7k 行（后端 + 数据/指标层 + 前端 + MCP，不含测试），
另有 30 个 pytest 用例与 GitHub Actions CI。

## 2. 为什么做这个产品

- 散户和财经内容创作者研究一只股票，要在多个网站之间搬运行情、财务、新闻，
  再手工整理；每天收盘后还要重新判断情绪与主线。
- 本项目验证「输入公司名 / 交易日 → 自动生成结构化研究结论」这件事能不能做成产品，
  同时作为 Agent 工程能力的实战载体。
- 关键取舍：**数字归代码，判断归模型**。LLM 一旦参与算数字，报告就没法复核了。

## 3. 架构总览

```text
浏览器（Next.js 16 / React 19 / Tailwind 4）
  /            落地页
  /analysis    个股研究页
  /daily       每日复盘页（报告 + 分享卡片）
        │  fetch + 手写 SSE 解析（EventSource 只支持 GET，本项目是 POST）
        ▼
FastAPI（:8000）
  POST /api/analysis             个股研究，SSE 推 7 个节点进度
  POST /api/daily-review         每日复盘，SSE：meta → 3 阶段 → report + card
  GET  /api/daily-review/latest  当前可复盘的最新交易日
  GET  /api/metrics              LLM 调用观测（次数/成功率/耗时/token）
  GET  /health
        │
        ├─ backend/graph.py     LangGraph 研究链路
        │     company → stock → news → financial → analysis → risk → report
        │     （取数 4 节点走工具层，analysis / risk 调 LLM，report 模板组装 10 章节）
        │
        └─ market/              每日复盘链路
              daily_snapshot.py  6 步取数 → 落盘快照（含数据就绪校验）
              indicators.py      纯函数指标层：情绪 / 广度 / 风格 / 题材 / 核心龙头
              daily_review.py    Prompt → LLM → 结构化结果 → Markdown 报告 + 卡片数据
              verify.py         输出侧数字校验（把 LLM 写的数字回快照核对）
              llm_client.py     统一的 DeepSeek 调用（重试 / 超时 / 用量日志）
        │
        └─ 外部依赖：同花顺金融数据 API、DeepSeek API
```

### 目录结构

```text
backend/          FastAPI 服务 + LangGraph 个股研究链路 + 工具层（同花顺取数）
market/           盘面数据与复盘链路（取数 / 指标 / 报告 / 校验 / LLM 客户端）
  data/hithink.py   同花顺客户端：限流、退避重试、数据就绪校验
  snapshots/        每日快照（本地数据，不入库）
  reports/          每日复盘存档（本地数据，不入库）
api/index.py      Vercel 后端入口：挂上 sys.path 后导出 server.app
frontend/         Next.js 前端
  lib/shareCard.ts      分享卡片排版引擎（Canvas 手绘，导出即所见）
  scripts/card-audit.py 卡片排版自检（无头 Chrome 渲染 + 包围盒碰撞检测）
tests/            pytest 用例（纯函数，不联网，秒级跑完）
mcp-server/       MCP 学习模块：FastMCP Server + client + agent
day1/ ~ day5/     7 天学习模块（Tool Calling / 记忆 / LangGraph / MCP）
```

## 4. 关键设计决策

1. **算数字和做判断彻底分层**：`market/indicators.py` 只做确定性计算，不调用 LLM；
   LLM 只拿指标做定性推理。报告里的每个数字都能在快照里复算。
2. **数据就绪校验**：涨停池接口在目标日数据未生成时会**静默回退到上一交易日**，
   会把昨天的盘面写成今天。`daily_snapshot.py` 先校验再落盘，快照里记录上游
   实际可用日期，读取时也会拒绝复用"不可信快照"（详见 `market/README.md`）。
3. **输出侧数字校验**：`market/verify.py` 把 LLM 正文里的盘面数字（家 / % / 亿 / 万 / pct）
   逐个回指标快照核对（含"昨日 X 家 = 今日 X − 环比 delta"这类可推导值，
   阈值型表述"回升至 60% 以上"则跳过），结果附在报告末尾与 `fact_check` 字段里。
4. **可解释的规则层**：板块强度 = 概念指数涨幅 × 涨停原因聚类交叉验证；
   核心龙头 = 标签聚类还原产业链（半导体硅片 / 设备 / 材料 → 半导体链），
   链内按 `身位 > 板别（同身位 10cm 优先） > 首封时间 > 封单额` 排序，
   并同时给出 10cm 龙头 / 20cm 龙头与"赚钱特征词"。规则可读、可复算、可测试。
5. **流式交互按真实阶段推送**：`progress` 事件的语义是"该阶段**开始**"，
   因为采集盘面数据本身要 20~40 秒；前端据此渲染阶段状态机（进行中 / 已完成）。
6. **观测与回归**：LLM 调用统一走 `llm_client.py` 记用量日志，`GET /api/metrics` 汇总；
   指标 / 契约 / 校验逻辑用 pytest 覆盖，CI 在 push 与 PR 时执行。

## 5. 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Next.js 16 / React 19 / TypeScript / Tailwind 4 / react-markdown（+ remark-gfm） |
| 后端 | Python 3.12 / FastAPI / uvicorn / LangGraph |
| Agent | DeepSeek（OpenAI 兼容 API，原生 Function Calling） |
| 数据 | 同花顺金融数据 API（行情 / 财务 / 新闻 / 涨停池 / 概念指数） |
| 画图 | 自研 Canvas 排版引擎（分享卡片，1080 宽 × 2 倍图） |
| 存储 | 每日快照与复盘存档（JSON / Markdown，本地数据不入库）；SQLite 用于学习模块的记忆演示 |
| 质量 | pytest（30 用例）+ GitHub Actions（pytest / tsc --noEmit / eslint） |

## 6. 本地开发

```bash
# 1. 安装依赖
.venv/bin/pip install -r requirements.txt        # 运行依赖（Vercel 也用这份）
# 需要跑 day1~day5 / mcp-server 学习模块时再装：
# .venv/bin/pip install -r requirements-dev.txt
cd frontend && pnpm install && cd ..

# 2. 配置环境变量（根目录一份，前后端脚本共享查找）
cp .env.example .env      # 填 DEEPSEEK_API_KEY 与 HITHINK_FINANCE_API_KEY

# 3. 终端 1：启动后端（:8000）
.venv/bin/python -m uvicorn backend.server:app --port 8000

# 4. 终端 2：启动前端（:3000）
cd frontend && pnpm dev    # /analysis 个股研究，/daily 每日复盘
```

命令行也可以直接跑复盘链路（不经过前端）：

```bash
.venv/bin/python market/daily_snapshot.py --date 2026-09-16 --show   # 只看当日盘面指标
.venv/bin/python market/daily_review.py  --date 2026-09-16           # 生成复盘报告并落盘
```

### 测试

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest   # 30 个用例：指标公式、板别判定、龙头排序、报告/卡片契约、事实校验
```

## 7. 环境变量

| 变量 | 位置 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 根目录 `.env` | DeepSeek API Key（分析 / 复盘必需） |
| `HITHINK_FINANCE_API_KEY` | 根目录 `.env` | 同花顺金融数据 API Key（取数必需） |
| `DEEPSEEK_MODEL` / `DEEPSEEK_API_URL` | 环境变量 | 可选，默认 `deepseek-chat` 与官方地址 |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` 或 Vercel | 后端地址，默认 `http://localhost:8000` |
| `CORS_ORIGINS` | 后端环境变量 | 允许跨域的前端来源，逗号分隔，默认 `http://localhost:3000` |
| `LLM_USAGE_LOG` | 后端环境变量 | LLM 用量日志路径，默认 `market/logs/llm-usage.jsonl` |
| `MARKET_DATA_DIR` | 后端环境变量 | 快照目录，默认 `market/snapshots` |
| `DAILY_REPORT_DIR` | 后端环境变量 | 复盘存档目录，默认 `market/reports` |

`.env` 只在项目根目录放一份，`backend/` 与 `market/` 下的脚本都会向上查找。
线上（Vercel）只有 `/tmp` 可写，所以要配 `MARKET_DATA_DIR=/tmp/snapshots`、
`DAILY_REPORT_DIR=/tmp/reports`；即使忘配也不会崩，落盘会降级成警告。

## 8. 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/analysis` | 个股研究，SSE 推 7 节点进度，最后一条是 `report` |
| `POST` | `/api/daily-review` | 每日复盘，SSE：`meta`（这次用了哪一天）→ `progress`×3 → `report`（Markdown + card） |
| `GET` | `/api/daily-review/latest` | 当前可复盘的最新交易日（避免默认填成还没有数据的今天） |
| `GET` | `/api/metrics` | LLM 调用次数、成功率、平均 / 最慢耗时、token、最近几次调用 |
| `GET` | `/health` | 健康检查 |

### 个股研究链路（7 节点）

```text
company（公司概况）→ stock（行情）→ news（新闻）→ financial（财务）
→ analysis（基本面/技术面/情绪/催化剂，LLM）→ risk（风险，LLM）
→ report（10 章节 Markdown）
公司无效 / 异常 → error 事件
```

### 每日复盘链路（3 阶段）

```text
snapshot（采集盘面数据）→ indicators（计算情绪与板块指标）→ review（LLM 判断）
→ 复盘报告（八节：情绪 / 盘面数据 / 热点板块与核心龙头 / 风格 / 机会 / 手法 / 风险 / 结论）
→ 分享卡片数据（阶段 + 一句话结论 + 四个关键数字 + 核心依据 + 热点板块 + 核心龙头 + 明日应对 + 风险）
```

指标口径（封板率、板块强度、核心龙头、特征词等）统一写在
[`market/README.md`](market/README.md)，本文件不重复。

## 9. 分享卡片

复盘结果会同时生成一张 Canvas 卡片（1080 宽、2 倍图，高度随内容自适应），
支持下载 PNG / 复制图片 / 复制文字版结论。

- 版式与配色在 `frontend/lib/shareCard.ts`，市场阶段决定主色
  （退潮红 / 修复橙 / 主升绿 / 分化紫 / 冰点灰蓝）。
- 排版是自研的：逐字折行（数字与字母 token 不断词）、字号自适应，
  每个元素登记包围盒；`frontend/scripts/card-audit.py` 用无头 Chrome 真渲染一遍再
  做碰撞检测，改版式时可自检"压字 / 越界"。

截图待补：本地跑一次 `/daily` 复盘即可在页面上「下载图片」拿到卡片 PNG；
`/analysis` 的报告页与 Agent 进度条同样可以就地截图。

## 10. 质量保障

| 手段 | 位置 | 覆盖什么 |
| --- | --- | --- |
| 单元测试 | `tests/`（30 用例） | 指标公式、板别判定、同链合并与龙头排序、报告/卡片字段契约、事实校验、用量汇总 |
| CI | `.github/workflows/ci.yml` | push / PR 跑 pytest + 前端 `tsc --noEmit` + `eslint` |
| 数字校验 | `market/verify.py` | LLM 正文里的盘面数字必须能在快照中复现（阈值型表述除外） |
| 用量观测 | `market/llm_client.py`、`GET /api/metrics` | 调用次数、成功率、耗时、token、失败原因 |
| 排版自检 | `frontend/scripts/card-audit.py` | 卡片压字 / 越界 / 最小字号 |

## 11. 部署

### 前端（Vercel）

Root Directory 选 `frontend`，环境变量配 `NEXT_PUBLIC_API_URL` 指向后端域名。

### 后端（Vercel，推荐）

后端与复盘链路分居 `backend/`、`market/` 两个目录，Vercel 的函数只认 `api/` 下的入口，
所以仓库根放了一个薄入口：

```text
api/index.py     把 market/ 与 backend/ 挂上 sys.path，导出 server.app
requirements.txt 运行期依赖（Vercel 只从项目根安装依赖）
vercel.json      functions.api/index.py：maxDuration 60 + includeFiles: "market/**"
```

面板上的四步：

1. **Root Directory 留空（= 仓库根）**，不要指到 `backend/`——指错了 `market/` 不会被打包，
   `/api/daily-review` 会返回"每日复盘模块不可用"（个股研究不受影响）。
2. 环境变量：`DEEPSEEK_API_KEY`、`HITHINK_FINANCE_API_KEY`、
   `CORS_ORIGINS=https://<前端域名>`、`MARKET_DATA_DIR=/tmp/snapshots`、`DAILY_REPORT_DIR=/tmp/reports`。
3. `maxDuration` 已经在 `vercel.json` 里设为 60s（Hobby 上限）。实测一次复盘
   ≈ 6.5s 采集（18 次同花顺请求）+ ≈9s 生成，正常远低于上限；被上游限流触发退避重试时可能变慢，
   这时前端会收到失败提示，重试即可。
4. 部署后先 `curl https://<后端域名>/health` 验证，再打开前端页面走一次复盘。

### 后端（其他平台）

- Render：`render.yaml` 蓝图（`rootDir: backend`，`startCommand: uvicorn server:app`）。
  Render 的文件系统可写，快照与存档可以正常持久化。
- Docker：`backend/Dockerfile`（构建上下文为 `backend/`）。
- 这两个路径都需要把 `market/` 随代码一起带上去（Render 从 Git 拉全仓库，天然满足）。

线上示例（以自己项目的实际域名为准）：

- 前端：https://stock-agent-fontend.vercel.app
- 后端：https://stock-agent-backend-blond.vercel.app（`GET /health`）

## 12. 数据边界与合规

- 同花顺公开能力不提供：分钟 K / tick、海外行情、宏观数据、新闻公告原文、研报原文。
- 全市场行情快照接口**只返回最新数据**、不支持历史日期：历史交易日的涨跌分布会带
  `is_stale=True` 标记，报告中会明确提示，不可当作当日分布使用。
- 个股所属行业 / 概念反查没有官方接口，板块归属只能从涨停原因与概念指数成分反向推断。
- 本项目仅供个人研究，输出**不构成投资建议**；报告与卡片底部都会带免责声明。

## 13. Roadmap

- [x] 个股研究链路：LangGraph 7 节点 + SSE 流式 + 10 章节报告
- [x] 真实数据接入（同花顺金融数据 API：行情 / 财务 / 新闻 / 涨停池 / 概念指数）
- [x] 每日盘面复盘：指标层 + LLM 判断 + 报告 + 分享卡片
- [x] 工程质量：pytest + CI + LLM 用量观测 + 输出侧数字校验
- [ ] 新闻源扩展（东财等）与公告解析
- [ ] MCP 接入产品主链路（当前 `mcp-server/` 为学习模块）
- [ ] 接口鉴权与调用配额（当前为本地 / 演示用途）
- [ ] LLM 输出质量评测集（回归对比不同 prompt / 模型）
- [ ] 用户访谈与商业模式验证（`market/MARKET-VALIDATION.md`）
- [ ] Demo 视频（2~5 分钟）

## 14. License

MIT
