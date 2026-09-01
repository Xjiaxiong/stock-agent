# Day 5

## 今日目标

理解 MCP / MCP Server / MCP Client / Tool / Resource / Prompt；
实现一个 MCP Server，让 Agent 通过 MCP 发现并调用工具。

## 今日学习

理论 4 问（见 day5/理论.md）：
- MCP = AI 应用接入外部工具的统一标准协议（类比 USB-C）
- MCP Server = 工具/数据/提示词的提供方；MCP Client = AI 应用端，发现并调用
- Function Calling 解决"模型怎么表达调用意图"；MCP 解决"应用怎么发现并连接工具"，两者配合使用
- MCP 解决的是系统集成问题，不是模型问题；标准化消除生态碎片化

## 我的理解
 MCP 是模型上下文协议，主要解决AI应用和外部工具的工程集成问题。
 MCP实现链路：
 - MCP Client 链接 MCP Server  
 - 运行时发现工具集合、转化成 tools 参数
 - 模型用 Function Calling 表达调用意图
 - MCP 跨进程执行工具，结果回传模型


## 今天实现了什么

- mcp-server/server.py：FastMCP Server，暴露 get_stock_price / get_stock_news / get_company_info
- mcp-server/client.py：离线演示——启动 Server、list_tools 发现、call_tool 调用
- mcp-server/agent.py：MCP Client + DeepSeek Function Calling——
  运行时发现 MCP 工具 → 转成 tools 参数 → 模型选择 → MCP 执行 → 结果回传
- 用户实现：get_company_info

## 遇到的问题

- mcp 2.x 把 FastMCP 改名 MCPServer，API 大改
- 解决：固定使用 mcp 1.29.1（成熟稳定的 FastMCP API），概念与 2.x 一致

## 如何解决

- 安装时锁定版本：pip install "mcp<2"

## 今天新增的代码

- mcp-server/server.py / client.py / agent.py
- day5/理论.md

## 测试结果

- client 离线验收：发现 3 个工具，三个工具全部返回正确数据 ✓
- agent 端到端验收：
  - Agent 启动 → MCP 发现 3 个工具（运行时）✓
  - "贵州茅台现在多少钱？" → 选择 get_stock_price → MCP 跨进程调用 → 1680.50 元 +0.77% ✓

## 今日验收

- [x] 理论验收
- [x] 实战验收（Server → Client → Agent 全链路）
- [x] 测试验收
- [ ] Git Commit

## 今日最重要的三个知识点

1. 理解了MCP 的作用，以及如何使用 MCP 集成工具
2. MCP 在AI应用中是如何应用的
3. 对MCP 和 DeepSeek Function Calling 的区别的理解

## 我还不会什么

1. 需要将知识点进一步的强化
2.
3.

## 明天计划

Day 6：Stock Research Agent MVP——后端把 Day 4 的 ResearchGraph + Day 5 的 MCP 串成产品，
前端 Next.js 页面（输入股票 → Agent Progress → Markdown 报告）。
