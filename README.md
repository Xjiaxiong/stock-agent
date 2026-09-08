# Stock Research Agent

> AI 股票研究助手 MVP：输入一家公司，Agent 自动完成行情、新闻、财务、风险分析，生成 10 章节研究报告。

## 1. 项目介绍

这是一个 7 天从零构建的 Agent 产品，用实战串联了 Agent 全栈能力：
原生 Function Calling、对话/长期记忆（SQLite）、LangGraph 工作流、MCP、
Next.js 前端与 FastAPI 后端。当前数据为**模拟数据**（产品演示用），
真实数据源接入规划在 Roadmap。

## 2. 为什么做这个产品

散户和财经内容创作者研究一只股票需要跨多个网站收集行情、新闻、财务数据，
再手工整理。本项目验证"输入公司名 → 自动生成结构化研究报告"是否是一个
值得做的产品，并作为 Agent 工程能力的实战载体。

## 3. 产品截图

（待补充：/analysis 页面截图、Agent 进度截图、报告截图）

## 4. Architecture

```text
Next.js (frontend, :3000)
    │  POST /api/analysis (SSE 流式)
    ▼
FastAPI (backend, :8000)
    ▼
LangGraph ResearchGraph
    ├─ company → stock → news → financial（工具节点，模拟数据）
    ├─ analysis / risk（DeepSeek LLM 生成）
    └─ report（10 章节 Markdown）
```

另有 day1~day5 学习模块（Tool Calling / Memory / LangGraph / MCP）与 mcp-server/。

## 5. Tech Stack

- Frontend：Next.js 16 / React 19 / TypeScript / Tailwind / react-markdown
- Backend：Python / FastAPI / LangGraph / uvicorn
- Agent 模型：DeepSeek（OpenAI 兼容 API，原生 Function Calling）
- Storage：SQLite（对话记忆演示）
- MCP：官方 Python SDK（mcp<2，学习演示）

## 6. Local Development

```bash
# 1. 安装依赖
.venv/bin/pip install -r backend/requirements.txt
cd frontend && pnpm install && cd ..

# 2. 配置环境变量（根目录一份，前后端共享查找）
cp .env.example .env   # 填入 DEEPSEEK_API_KEY

# 3. 终端 1：启动后端
.venv/bin/python -m uvicorn backend.server:app --port 8000

# 4. 终端 2：启动前端
cd frontend && pnpm dev   # 打开 http://localhost:3000/analysis
```

## 7. Environment Variables

| 变量 | 位置 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 根目录 `.env` | DeepSeek API Key |
| `NEXT_PUBLIC_API_URL` | Vercel / `frontend/.env.local` | 后端地址，默认 `http://localhost:8000` |
| `CORS_ORIGINS` | 后端环境变量 | 允许跨域的前端来源，逗号分隔 |

## 8. Agent Workflow

`POST /api/analysis {company}`，SSE 逐节点推送进度：

```text
company（公司概况）→ stock（行情）→ news（新闻）→ financial（财务）
→ analysis（LLM 基本面/技术面/情绪/催化剂）→ risk（LLM 风险）
→ report（10 章节 Markdown）
公司无效 → error 事件
```

## 9. MCP Architecture

`mcp-server/`：FastMCP Server 暴露行情/新闻/公司信息三个工具，
`client.py` 演示运行时发现与调用，`agent.py` 把 MCP 工具接入 DeepSeek Function Calling。
产品后端当前直接调用工具层，MCP 化作为后续演进方向。

## 10. Demo

在线 Demo（部署于 Vercel）：

- 前端：https://stock-agent-fontend.vercel.app
- 后端 API：https://stock-agent-backend-blond.vercel.app（`GET /health` 健康检查）

演示视频：待录制（2~5 分钟）。

## 11. Roadmap

- [x] 前端部署 Vercel + 后端部署 Vercel（Python FastAPI，SSE 流式）
- [ ] 真实数据源接入（A股行情/财务，评估中：同花顺官方金融 API）
- [ ] 新闻数据源（评估东财/其他）
- [ ] 用户访谈与商业模式验证（MARKET-VALIDATION.md）
- [ ] Demo 视频

## 12. License

MIT
