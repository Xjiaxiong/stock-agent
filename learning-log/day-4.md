# Day 4

## 今日目标

理解 State / Node / Edge / Conditional Edge / Checkpoint / Human-in-the-loop；
用 LangGraph 实现 ResearchGraph（行情→新闻→财务→分析→风险→报告），
支持无效代码走 ErrorNode、新闻不足走 SearchMoreNode。

## 今日学习

理论 6 问（见 day4/理论.md）：

- State = 任务执行中的共享工作台账（Redux store / 全局变量），与对话 Memory 不同
- Node = 读 State、干活、写回 State 的函数；Edge = 节点间的执行顺序
- Conditional Edge = 路由函数，读 State 决定下一步去哪个节点
- Checkpoint = 每步的 State 快照（存档），支持暂停/恢复/回退
- Human-in-the-loop = 关键不可逆动作前让人审核批准
- Workflow（固定流程）vs Agent（模型自主决策），可混用

## 我的理解

理解了State 在任务执行中的共用性，每个任务节点就是一个函数，可以拿到最新的State 可以读取，可以修改，利用LangGraph 可以实现条件边决定下一步去哪一个节点，另外CheckPoint 是关于State快照, 方便在除了差错的时候去定位问题。

## 今天实现了什么

- day4/tools.py：Day 3 工具 + get_financial_data（财务数据模拟）+ 新闻扩展到 6 家公司
- day4/graph.py：LangGraph StateGraph——
State（ResearchState）+ 8 个节点 + 2 条条件边 + MemorySaver Checkpoint
- day4/main.py：命令行入口
- 用户实现：financial_node



## 遇到的问题

- 无（LangGraph 安装到 .venv，避免污染系统 Python）
- 未来可能在部署在有问题
- 当前电脑的版本混乱



## 如何解决

- 新建项目虚拟环境 .venv 并安装 langgraph 1.2.11



## 今天新增的代码

- day4/tools.py / graph.py / main.py / 理论.md
- .venv/（虚拟环境，已 gitignore）



## 测试结果

- 贵州茅台（新闻=3）：直通路径 stock→news→financial→analysis→risk→report ✓
- 宁德时代/比亚迪/招商银行（新闻=2）：走 search_more 补搜后再继续 ✓
- 苹果（无效公司）：stock→error，错误信息清晰 ✓
- 四家正常公司报告均包含第 3 节"基本面"财务数据 ✓



## 今日验收

- [x] 理论验收
- [x] 实战验收（完整 Graph + 条件分支）
- [x] 测试验收
- [ ] Git Commit



## 今日最重要的三个知识点

1. State的理解
2. 节点和边以及条件边的理解
3. LangGraph 的使用

## 我还不会什么

1. 环境的部署和安装
2. 以及对接真是的API 数据来支持实时的分析 
3. 一个好的股票分析agent 的产品形态是怎样的，前端后端部署，需要思考的点等

## 明天计划

Day 5：MCP——实现 mcp-server（get_stock_price / get_stock_news / get_company_info），
Agent 通过 MCP Client 发现并调用工具。