# Day 1

## 今日目标

理解 Agent 核心概念（LLM / Tool / Function Calling / Prompt / Memory / Workflow），
完成第一个可以自主选择 Tool 的 Agent。

## 今日学习

理论 Q1~Q5（见 day01-理论.md）：
- Agent 是拥有状态、可调用工具、通过感知-计划-执行-观察循环完成任务的系统
- Chatbot 回答问题，Agent 解决问题
- Workflow 是预先写死的固定流程，Agent 由模型运行时自主决策，两者可混用
- Tool 是 LLM 与真实世界之间的接口，弥补 LLM 静态知识、无法实时获取信息的问题

## 我的理解

（待用户补充）

## 今天实现了什么

- day1/tools.py：calculate / get_weather / get_stock_price 三个工具 + 工具注册表
- day1/agent.py：Agent 循环（LLM 决策 → 解析 JSON 工具调用 → 执行工具 → 结果回传 → 最终回答），
  含 JSON 解析容错、工具错误反馈、网络请求自动重试
- day1/main.py：命令行入口（交互模式 + 直接提问）

## 遇到的问题

- 模型输出工具调用 JSON 时，带 markdown 代码围栏或前后夹带文字，嵌套 JSON 提取失败
- 第二次调用 DeepSeek API 时偶发 TLS 握手失败（SSL: UNEXPECTED_EOF_WHILE_READING）

## 如何解决

- 解析前先去掉代码围栏，解析失败时提取第一个 {...}（支持嵌套）
- 连接类错误（URLError / Timeout）自动重试 3 次（1s/2s 退避），HTTP 层错误直接报错

## 今天新增的代码

- day1/tools.py
- day1/agent.py
- day1/main.py
- day01-理论.md
- learning-log/day-1.md
- .gitignore

## 测试结果

- "2 + 8" → Calculator → 10 ✓
- "查询上海天气" → Weather → 多云 28℃ ✓
- "查询贵州茅台行情" → Stock → 1680.50 元 +0.77% ✓
- 错误处理：未知城市 / 未知公司 / 非法表达式均返回清晰报错 ✓
- 工具调用 JSON 解析容错：5 个用例全部通过 ✓

## 今日验收

- [x] 理论验收
- [x] 实战验收
- [x] 测试验收
- [ ] Git Commit

## 今日最重要的三个知识点

1.（待用户补充）
2.
3.

## 我还不会什么

1.（待用户补充）
2.
3.

## 明天计划

Day 2：Tool Calling / Function Calling / Tool Schema / 真实数据接入，
准备 10 个测试问题，要求 Tool Selection 正确率 ≥ 90%。
