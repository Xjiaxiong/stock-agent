# Stock Agent — 7-Day Agent Engineering & Productization Plan

> **项目目标：**
>
> 用 7 天时间，从 Agent 基础概念开始，通过连续实战，完成一个可以运行、可以演示、可以继续产品化的 `stock-agent`。
>
> 本计划不是为了“学完 Agent 框架”，而是为了建立：
>
> 1. Agent 原理理解能力
> 2. Agent 工程实现能力
> 3. Tool / Memory / Workflow / MCP 能力
> 4. Agent 产品设计能力
> 5. Agent 商业化与市场分析能力
>
> **最终目标：**
>
> > 7 天后，能够独立解释、设计、实现和部署一个中等复杂度的 Agent，并拥有一个可以用于后续商业验证的 Stock Research Agent MVP。

---

# 0. Codex 工作协议

## 0.1 Codex 的角色

Codex 在本项目中不是单纯的代码生成器。

Codex 应同时承担：

* Agent 技术导师
* Pair Programmer
* Code Reviewer
* 测试工程师
* 产品经理助手
* 技术调研助手
* 学习进度监督者

但是：

> **Codex 不应该替用户完成所有思考。**

如果一个任务的核心目的是学习 Agent 原理，Codex 应优先：

1. 解释问题
2. 给出最小提示
3. 让用户实现
4. 检查用户实现
5. 最后才提供完整参考实现

---

# 1. 总体原则

## 1.1 学习比例

整个 7 天遵循：

```text
理论       20%
官方资料   20%
编码实战   40%
项目实战   15%
复盘验证   5%
```

不要把大量时间用于：

* 看视频
* 收藏文章
* 阅读大量论文
* 比较几十个 Agent Framework
* 研究没有实际用途的高级架构

---

# 2. 技术路线

本项目默认技术路线：

```text
Frontend
    ↓
Next.js / React / TypeScript

Backend
    ↓
Python

Agent
    ↓
OpenAI Agents SDK
    ↓
LangGraph
    ↓
MCP

Data
    ↓
Stock API
News API
Search API

Storage
    ↓
SQLite / PostgreSQL

Deployment
    ↓
Vercel + Railway/Render
```

---

# 3. 7 天最终能力模型

7 天结束时，必须具备以下能力：

| 能力               | 验收标准                              |
| ---------------- | --------------------------------- |
| Agent 基础         | 能解释 Agent 与普通 LLM Application 的区别 |
| Tool Calling     | 能独立实现至少 5 个 Tool                  |
| Function Calling | 能理解 Schema、参数、返回值和错误处理            |
| Memory           | 能实现短期和持久化 Memory                  |
| Workflow         | 能用 LangGraph 实现多节点 Agent          |
| MCP              | 能独立实现简单 MCP Server                |
| RAG              | 理解基本 RAG 架构和适用场景                  |
| Agent Evaluation | 能设计 Agent 测试用例                    |
| Observability    | 能定位 Agent 执行过程中的错误                |
| Product          | 有可运行 Stock Research Agent         |
| Deployment       | 有公网 Demo                          |
| Market           | 完成竞品和商业模式分析                       |

---

# 4. 项目边界

## 4.1 第一阶段产品定位

项目暂定：

> **Stock Research Agent**

不是：

> 自动炒股机器人

不是：

> 自动交易系统

不是：

> 股票买卖预测器

第一阶段只做：

> **AI 股票研究助手**

---

# 5. 产品 MVP

用户输入：

```text
分析贵州茅台
```

Agent 最终应该能够完成：

```text
用户问题
    ↓
Stock Research Agent
    ↓
识别股票
    ↓
获取基础行情
    ↓
获取新闻
    ↓
获取公告/财务资料
    ↓
分析
    ↓
风险检查
    ↓
生成研究报告
```

报告至少包含：

```text
1. 公司基本信息

2. 最新行情

3. 近期新闻

4. 基本面摘要

5. 市场热点

6. 技术面信息

7. 潜在催化剂

8. 潜在风险

9. 信息来源

10. Agent 总结
```

注意：

> 第一阶段不输出“确定性买卖建议”。

---

# 6. 每日工作制度

每天建议投入：

```text
8 小时左右
```

推荐：

```text
09:00 - 11:00
理论 + 官方文档

11:00 - 12:00
官方 Example

14:00 - 17:00
编码实战

19:00 - 20:00
项目开发

20:00 - 21:00
测试 + 复盘
```

如果当天只有 4 小时：

```text
1h 理论
2h 编码
1h 验证
```

---

# 7. 每日固定流程

每天必须执行：

```text
Step 1
阅读学习资料

Step 2
写自己的理解

Step 3
完成最小 Demo

Step 4
把能力集成进 stock-agent

Step 5
写测试

Step 6
运行验收

Step 7
Git commit

Step 8
写学习日志
```

---

# DAY 1 — Agent Fundamentals

## 今日目标

理解：

```text
LLM
Agent
Tool
Function Calling
Prompt
Memory
Workflow
```

并完成第一个可以自主选择 Tool 的 Agent。

---

## 上午：理论

必须回答：

### Q1

什么是 Agent？

要求：

不能只复制定义。

必须用自己的话解释。

---

### Q2

Agent 和 Chatbot 有什么区别？

---

### Q3

Agent 和 Workflow 有什么区别？

---

### Q4

为什么 Agent 需要 Tool？

---

### Q5

什么时候应该使用普通 LLM Application，而不是 Agent？

---

## 推荐资料

优先使用官方资料：

* OpenAI Agents / Agent SDK 官方文档
* Anthropic《Building Effective Agents》

重点理解：

```text
Model
Tool
Instructions
State
Loop
```

不要深入框架 API。

---

# DAY 1 实战

建立：

```text
day1/
```

实现：

```text
Calculator Tool

Weather Tool

Stock Tool
```

Agent：

```text
用户输入
    ↓
LLM
    ↓
选择 Tool
    ↓
执行 Tool
    ↓
返回结果
```

---

# DAY 1 验收

必须通过：

```text
2 + 8
```

调用 Calculator。

---

```text
查询上海天气
```

调用 Weather。

---

```text
查询贵州茅台行情
```

调用 Stock。

---

## DAY 1 自测

用户必须能够不看代码回答：

* Agent 是什么？
* Tool 是什么？
* Tool Calling 是什么？
* Agent Loop 是什么？
* 为什么不能所有任务都使用 Agent？

如果不能回答：

> DAY 1 不允许进入 DAY 2。

---

## DAY 1 Git

提交：

```bash
git add .
git commit -m "learn: complete agent fundamentals"
```

---

# DAY 2 — Tool Calling / Function Calling

## 今日目标

掌握 Agent 最核心的工程能力：

> **让 LLM 使用外部能力。**

---

# 上午理论

学习：

```text
Function Calling
Tool Schema
JSON Schema
Arguments
Tool Result
Error Handling
```

必须理解：

```text
LLM
 ↓
决定调用什么
 ↓
生成参数
 ↓
Tool
 ↓
Tool Result
 ↓
LLM
 ↓
Final Answer
```

---

# DAY 2 实战

实现至少：

```text
get_stock_price()

get_stock_news()

search_web()

calculate()

get_company_info()
```

每个 Tool 必须有：

```text
name

description

input schema

output

error handling
```

---

# Tool 设计原则

不要：

```python
tool1()
tool2()
tool3()
```

写完就结束。

必须思考：

> LLM 能不能正确理解这个 Tool？

Tool description 必须清楚。

例如：

```text
get_stock_price

用途：
获取指定股票最近交易日的行情数据。

输入：
symbol: 股票代码

输出：
price
change
change_percent
timestamp
```

---

# DAY 2 测试

准备至少 10 个用户问题。

例如：

```text
贵州茅台现在多少钱？

分析一下宁德时代最近发生了什么？

帮我计算过去五天涨幅。

最近英伟达有什么新闻？

告诉我贵州茅台属于什么行业。
```

记录：

```text
是否调用正确 Tool
参数是否正确
Tool 是否返回正确结果
最终回答是否正确
```

---

# DAY 2 验收

至少：

```text
10 个测试
≥ 90% Tool Selection 正确
```

如果低于 90%：

优先修改：

```text
Tool Description
Schema
Prompt
```

而不是马上增加复杂 Agent。

---

# DAY 2 Git

```bash
git commit -m "learn: implement agent tool calling"
```

---

# DAY 3 — Memory / State

## 今日目标

理解：

```text
Context

Conversation Memory

Long-term Memory

State
```

---

# 理论

必须理解：

### Short-term Memory

当前对话上下文。

---

### Long-term Memory

跨会话保存的信息。

例如：

```text
用户偏好：

偏好短线交易

偏好研究 A 股

风险偏好较高
```

---

### State

Agent 当前任务状态。

例如：

```json
{
  "symbol": "600519",
  "news": [],
  "financial": {},
  "analysis": {},
  "risk": {}
}
```

---

# DAY 3 实战

建立：

```text
memory/
```

实现：

```text
Conversation Memory
```

测试：

```text
用户：

我正在研究贵州茅台。
```

然后：

```text
用户：

它最近有什么风险？
```

Agent 必须知道：

```text
它 = 贵州茅台
```

---

# DAY 3 第二阶段

加入 SQLite。

实现：

```text
user_id
conversation_id
messages
memory
created_at
updated_at
```

---

# DAY 3 验收

关闭程序。

重新启动。

继续：

```text
分析刚才那家公司
```

Agent 仍然知道上下文。

---

# DAY 3 思考题

必须回答：

> 为什么不能把所有历史对话全部塞进 Context？

---

> Memory 和 RAG 有什么区别？

---

> State 和 Memory 有什么区别？

---

# DAY 3 Git

```bash
git commit -m "learn: implement agent memory and state"
```

---

# DAY 4 — LangGraph / Agent Workflow

## 今日目标

理解：

```text
State
Node
Edge
Conditional Edge
Checkpoint
Human-in-the-loop
```

---

# 为什么需要 Workflow？

一个复杂任务：

```text
分析股票
```

实际上：

```text
获取行情
    ↓
获取新闻
    ↓
获取财务
    ↓
分析
    ↓
风险检查
    ↓
生成报告
```

不是一个 Prompt 就能稳定完成。

---

# DAY 4 实战

使用 LangGraph 实现：

```text
ResearchGraph
```

结构：

```text
START

↓

StockNode

↓

NewsNode

↓

FinancialNode

↓

AnalysisNode

↓

RiskNode

↓

ReportNode

↓

END
```

---

# State

设计：

```python
class ResearchState:
    symbol
    stock_data
    news
    financial_data
    analysis
    risks
    report
```

---

# DAY 4 增加 Conditional Edge

例如：

```text
如果股票代码无效

↓

ErrorNode
```

如果：

```text
新闻数量 < 3
```

则：

```text
SearchMoreNode
```

---

# DAY 4 验收

必须可以：

```text
输入贵州茅台

↓

完整执行 Graph

↓

输出研究报告
```

同时：

```text
输入错误股票代码

↓

进入 ErrorNode
```

---

# DAY 4 自测

必须能解释：

```text
为什么需要 State？

Node 是什么？

Edge 是什么？

Conditional Edge 是什么？

LangGraph 和普通 Agent Loop 有什么区别？
```

---

# DAY 4 Git

```bash
git commit -m "learn: build stock research workflow with langgraph"
```

---

# DAY 5 — MCP

## 今日目标

理解：

```text
MCP

MCP Client

MCP Server

Tool

Resource

Prompt
```

---

# 为什么学习 MCP？

未来 Agent 需要连接：

```text
GitHub

Slack

Notion

Database

Browser

File System

Company Internal Tools
```

MCP 的核心价值：

> 标准化 Agent 与外部工具/数据之间的连接方式。

---

# DAY 5 实战

建立：

```text
mcp-server/
```

实现至少：

```text
get_stock_price

get_stock_news

get_company_info
```

---

# DAY 5

让 Agent：

```text
Agent
 ↓
MCP Client
 ↓
MCP Server
 ↓
Stock API
```

---

# DAY 5 验收

必须能够：

```text
启动 MCP Server

↓

Agent 连接 MCP

↓

Agent 发现 Tool

↓

Agent 调用 Tool

↓

得到结果
```

---

# DAY 5 思考题

必须回答：

> MCP 和普通 Function Calling 有什么区别？

---

> MCP 解决的是模型问题还是系统集成问题？

---

> 为什么 MCP 对 Agent Ecosystem 有意义？

---

# DAY 5 Git

```bash
git commit -m "learn: integrate stock tools with mcp"
```

---

# DAY 6 — Stock Research Agent MVP

今天开始停止“学习 Demo”。

进入：

> 产品开发模式。

---

# 产品目标

用户输入：

```text
分析贵州茅台
```

系统自动：

```text
1. 识别股票

2. 获取行情

3. 获取新闻

4. 获取公司信息

5. 获取财务信息

6. 分析基本面

7. 分析技术面

8. 分析风险

9. 生成报告
```

---

# Agent Architecture

目标架构：

```text
                    ┌─────────────┐
                    │   User      │
                    └──────┬──────┘
                           ↓
                    ┌─────────────┐
                    │ Agent       │
                    └──────┬──────┘
                           ↓
                  ┌─────────────────┐
                  │ Research Graph  │
                  └───────┬─────────┘
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   Stock Tool        News Tool        Financial Tool
        ↓                 ↓                 ↓
        └─────────────────┼─────────────────┘
                          ↓
                    Analysis Node
                          ↓
                     Risk Node
                          ↓
                    Report Node
```

---

# DAY 6 Frontend

使用：

```text
Next.js
React
TypeScript
```

实现：

```text
/analysis
```

页面：

```text
股票代码输入框

研究按钮

Loading 状态

Agent Progress

最终 Markdown 报告
```

---

# Agent Progress

不要只显示：

```text
Loading...
```

显示：

```text
✓ 获取股票行情

✓ 获取新闻

● 分析基本面

○ 风险分析

○ 生成报告
```

让用户看到 Agent 正在执行什么。

---

# DAY 6 Report

报告至少：

```text
# 贵州茅台研究报告

## 1. 公司概况

## 2. 最新行情

## 3. 近期新闻

## 4. 基本面

## 5. 技术面

## 6. 市场情绪

## 7. 催化剂

## 8. 风险

## 9. 信息来源

## 10. Agent 总结
```

---

# DAY 6 验收

至少测试：

```text
贵州茅台
宁德时代
比亚迪
招商银行
```

每家公司：

```text
可以正常完成分析

没有明显 Hallucination

关键数据有来源

失败时有明确错误提示
```

---

# DAY 6 Git

```bash
git commit -m "feat: build stock research agent mvp"
```

---

# DAY 7 — Productization / Deployment / Market Validation

这是最重要的一天。

目标不是继续学习框架。

目标：

> **证明这个东西有没有商业价值。**

---

# PART A — 工程验收

检查：

```text
[ ] Agent 可以运行

[ ] Tool Calling 正常

[ ] Memory 正常

[ ] LangGraph 正常

[ ] MCP 正常

[ ] Error Handling 正常

[ ] Frontend 正常

[ ] Backend 正常

[ ] README 完整

[ ] Demo 视频完成
```

---

# PART B — 部署

推荐：

```text
Frontend
Vercel

Backend
Railway / Render

Database
PostgreSQL
```

如果部署复杂：

> 优先保证 Demo 能跑，不要为了“完美架构”浪费一天。

---

# PART C — README

README 必须包含：

```text
1. 项目介绍

2. 为什么做这个产品

3. 产品截图

4. Architecture

5. Tech Stack

6. Local Development

7. Environment Variables

8. Agent Workflow

9. MCP Architecture

10. Demo

11. Roadmap

12. License
```

---

# PART D — Demo 视频

录制：

```text
打开网站

↓

输入：

分析贵州茅台

↓

展示 Agent Progress

↓

展示 Tool Calling

↓

展示最终报告

↓

展示 Sources
```

控制在：

```text
2~5 分钟
```

---

# PART E — 市场分析

今天必须回答：

## 竞争对手

研究至少：

```text
5 个股票 AI 产品

5 个通用 AI Research 产品

5 个 Agent 产品
```

记录：

```text
产品名称

用户是谁

解决什么问题

价格

核心功能

数据来源

Agent 能力

优点

缺点

你能否做得更好
```

---

# PART F — 用户画像

至少设计：

```text
用户 A
短线交易者

用户 B
中长期投资者

用户 C
金融研究人员

用户 D
证券从业者

用户 E
财经内容创作者
```

然后判断：

> 谁最可能付钱？

---

# PART G — 商业模式

至少研究：

### Freemium

```text
免费：

每天 3 次

Pro：

¥49/月
```

---

### 高级订阅

```text
¥99/月

¥199/月

¥499/月
```

---

### B2B

```text
研究团队

投顾团队

财经媒体
```

---

### API

```text
Agent API

Research API
```

---

# PART H — 用户验证

至少找：

```text
3~5 个真实用户
```

不要问：

> 你觉得这个产品怎么样？

应该问：

```text
你现在怎么研究股票？

每天花多少时间？

最痛苦的步骤是什么？

现在使用什么工具？

一个月花多少钱？

如果这个产品帮你节省 1 小时/天，你愿意付多少钱？
```

---

# PART I — 商业验证结果

最终写：

```text
MARKET-VALIDATION.md
```

包含：

```text
用户数量：

真实访谈：

愿意试用：

愿意付费：

愿意付费价格：

最重要需求：

最大痛点：

最大竞争对手：

我们的差异化：

下一步：
```

---

# 7 天最终验收

项目必须达到：

```text
                    ┌──────────────┐
                    │ Stock Agent  │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
       Agent             Tools            Memory
          ↓                ↓                ↓
      LangGraph           MCP            SQLite
          └────────────────┼────────────────┘
                           ↓
                     Research Report
                           ↓
                       Web UI
                           ↓
                        Deploy
```

---

# 最终能力考试

不要看资料，独立回答以下问题。

## Level 1

```text
什么是 Agent？

Agent 和 LLM 有什么区别？

Tool Calling 是什么？

Function Calling 是什么？
```

---

## Level 2

```text
Memory 和 RAG 的区别？

Workflow 和 Agent 的区别？

为什么需要 State？

如何设计 Tool？
```

---

## Level 3

```text
什么时候使用 LangGraph？

什么时候不应该使用 LangGraph？

MCP 解决什么问题？

MCP 和 Function Calling 的区别？
```

---

## Level 4

设计：

```text
一个企业销售 Agent
```

要求包含：

```text
Tools

Memory

Workflow

MCP

Human-in-loop

Evaluation

Observability
```

如果能够独立设计出来：

> Agent 基础能力达到可工作的程度。

---

# Codex 每天必须执行的工作方式

当用户开始某一天学习时，Codex 首先检查：

```text
当前是 Day N

↓

检查 Day N 的 Git 状态

↓

检查上一天验收是否通过

↓

检查当前代码

↓

提出今日学习任务

↓

让用户先完成理论问题

↓

再开始编码

↓

运行测试

↓

检查验收标准
```

---

# Codex 禁止行为

## 1. 不要过度实现

不要在 MVP 阶段主动增加：

```text
Multi-Agent

复杂 RAG

复杂向量数据库

复杂权限系统

支付系统

复杂 Kubernetes

微服务

```

除非这些东西是当前任务真正需要的。

---

## 2. 不要为了技术炫技

不要因为某个技术很热门就加入：

```text
CrewAI

AutoGen

A2A

各种 Vector DB

各种 Agent Framework
```

如果当前项目不需要：

> 不加入。

---

## 3. 不要让我陷入教程地狱

如果已经掌握：

```text
Tool Calling
```

就进入实战。

不要继续看：

```text
10 个 Tool Calling 教程。
```

---

# Agent Engineering 学习原则

始终遵循：

```text
Understand
    ↓
Build
    ↓
Break
    ↓
Debug
    ↓
Evaluate
    ↓
Improve
```

而不是：

```text
Watch
Watch
Watch
Watch
Watch
```

---

# 最终目标：从学习转向现金流

7 天之后，项目不再以：

> “学习 Agent”

为目标。

而变成：

> “寻找 Agent 能解决的真实商业问题”。

重点探索：

```text
企业自动化

AI Research

AI Customer Service

AI Sales

AI Content

AI Coding

AI Data Analysis

Vertical Agents
```

---

# 第 8~21 天方向

7 天结束以后，进入：

```text
Day 8~10

真实数据质量

↓

Day 11~13

用户测试

↓

Day 14~15

产品定位

↓

Day 16~18

收费模型

↓

Day 19~21

获客
```

目标：

> 获得第一个真实付费用户，而不是继续学习 Agent Framework。

---

# 每日学习日志模板

每天创建：

```text
learning-log/day-N.md
```

模板：

```markdown
# Day N

## 今日目标

## 今日学习

## 我的理解

## 今天实现了什么

## 遇到的问题

## 如何解决

## 今天新增的代码

## 测试结果

## 今日验收

- [ ] 理论验收
- [ ] 实战验收
- [ ] 测试验收
- [ ] Git Commit

## 今日最重要的三个知识点

1.
2.
3.

## 我还不会什么

1.
2.
3.

## 明天计划

```

---

# Git Commit 规范

每天至少一个 Commit。

格式：

```text
learn: xxx

feat: xxx

fix: xxx

refactor: xxx

docs: xxx

test: xxx
```

例如：

```bash
git commit -m "learn: complete agent fundamentals"

git commit -m "feat: add stock research tools"

git commit -m "feat: implement research workflow"

git commit -m "feat: integrate mcp tools"

git commit -m "feat: build stock agent mvp"
```

---

# 最终交付物

7 天结束，项目根目录至少包含：

```text
stock-agent/

├── AGENTS-7DAY.md
│
├── README.md
│
├── learning-log/
│   ├── day-1.md
│   ├── day-2.md
│   ├── day-3.md
│   ├── day-4.md
│   ├── day-5.md
│   ├── day-6.md
│   └── day-7.md
│
├── market/
│   └── MARKET-VALIDATION.md
│
├── frontend/
│
├── backend/
│
├── tools/
│
├── mcp-server/
│
├── tests/
│
└── demo/
    └── demo.mp4
```

---

# 最终毕业标准

满足以下条件才算完成：

```text
[ ] 能解释 Agent 核心概念

[ ] 能独立实现 Tool Calling

[ ] 能实现 Memory

[ ] 能实现 State

[ ] 能使用 LangGraph

[ ] 能实现 MCP Server

[ ] 能构建 Stock Research Agent

[ ] 能处理错误

[ ] 能进行 Agent Evaluation

[ ] 有完整前端

[ ] 有公网 Demo

[ ] 有 GitHub Repository

[ ] 有 Demo 视频

[ ] 完成竞品分析

[ ] 完成用户访谈

[ ] 找到潜在付费用户

[ ] 明确下一步商业方向
```

---

# 最重要的一条规则

> **7 天的终点不是“我学会了 Agent”。**

真正的终点是：

```text
我理解 Agent
        ↓
我可以自己构建 Agent
        ↓
我可以把 Agent 做成产品
        ↓
我可以找到真实用户
        ↓
我可以让用户愿意付钱
```

最终目标：

> **Agent 能力 → 产品能力 → 商业能力 → 现金流**

而不是：

> **Agent Framework → Framework → Framework**
