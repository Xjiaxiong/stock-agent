# Day 6

## 今日目标

产品化 MVP：后端把 ResearchGraph 升级为产品服务（SSE 进度 + LLM 分析），
前端 Next.js 页面实时展示 Agent 进度并渲染 Markdown 报告。

## 今日学习

- 产品后端 = 工具层 + LangGraph 工作流 + HTTP 服务三层
- SSE（Server-Sent Events）流式推送：节点完成一个推送一条，前端逐条更新
- graph.stream(stream_mode="updates") 是 LangGraph 内置的逐节点流式能力
- 前后端契约先行：节点名/顺序/事件类型两端的常量保持一致

## 我的理解

初步的理解了流式推送，SSE的实现方式，根据推送节点任务，完成一个推送一条，可以清晰的看到agent的处理过程。

前后端在定义节点和顺序的时候，要约定一致，方便开发；

## 今天实现了什么

- backend/tools.py：产品版工具层（公司/行情/新闻/财务，模拟数据）
- backend/graph.py：ResearchGraph 产品版——analysis/risk 节点改 LLM 生成，
report 节点组装 10 章节 Markdown，带错误分支
- backend/server.py：FastAPI + SSE（POST /api/analysis），CORS 放开 localhost:3000
- frontend/：Next.js 16 项目，/analysis 页面（输入框 + 按钮 + AgentProgress +
ReportView + 错误提示），SSE 客户端解析在 lib/api.ts
- 修复：backend sys.path 导入、Google Fonts 联网依赖、双锁文件统一 pnpm



## 遇到的问题

- uvicorn 从项目根启动时 backend 内部 import 失败 → sys.path 修复
- Next.js 默认 next/font/google 构建时要联网拉字体 → 改系统字体
- Turbopack 构建在本机沙箱环境报 EPERM（本地环境问题，非代码问题）



## 如何解决

- 同前文；`pnpm build` 待用户本机确认



## 今天新增的代码

- backend/tools.py / graph.py / server.py
- frontend/（app/analysis/page.tsx、components/AgentProgress.tsx、ReportView.tsx、lib/api.ts）
- learning-log/day-6.md



## 测试结果

- 贵州茅台 / 宁德时代 / 比亚迪 / 招商银行：7 节点进度 + 10/10 章节 + 价格 + 来源，全部通过
- 无效公司（苹果）：错误提示清晰
- 前端 /analysis 页面 HTTP 200



## 今日验收

- [x] 实战验收（四家公司端到端）
- [x] 测试验收
- [x] 前端人工体验（用户在浏览器跑一遍）
- [ ] Git Commit



## 今日最重要的三个知识点

1. 流式推送的服务端和前端的完整实现
2.  langGraph 设计特定的任务节点，通过SSE，不断的往特定的任务结构中写。

## 我还不会什么

1. 接入真实数据 
2. 部署

## 明天计划

Day 7：工程验收清单 + 部署（Vercel/Railway）+ README + Demo 视频 +
竞品与用户画像分析 + MARKET-VALIDATION.md。