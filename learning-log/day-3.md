# Day 3

## 今日目标

理解 Memory（短期/长期）与 State；实现 Conversation Memory；
用 SQLite 持久化，做到重启程序后仍记得上下文。

## 今日学习

理论 5 问（见 day3/理论.md）：
- 短期记忆 = 当前对话上下文；长期记忆 = 跨会话保存的用户信息，需外部存储
- State 像函数的局部变量（任务过程数据），Memory 像数据库（长期保留）
- 不能把所有历史塞进 Context：窗口有限 / 成本 / 无效上下文 / 长上下文中间信息易丢失
- RAG 检索领域知识，Memory 记录用户与任务信息

## 我的理解

Rag 是检索增强生成，解决大模型不知道的事情。
Memory 分短期和长期，短期记忆是当前对话的记忆，长期记忆是夸对话的用户说过的记忆。

## 今天实现了什么

- day3/memory.py：SQLite 三张表（conversations / messages / memory）+ 全套增删查改
- day3/agent.py：每次提问加载历史 + 注入长期记忆；回答后持久化对话、抽取记忆
- day3/main.py：新建/继续会话的 CLI
- day3/tools.py：复用 Day 2 的 5 个工具
- 注释增强：面向 TS/JS 开发者的 Python 对照注释（memory / agent / main / tools）

## 遇到的问题

- 框架版 Python 3.10 SSL 证书验证失败（CERTIFICATE_VERIFY_FAILED）
- 用 Homebrew Python 3.12 可正常连接 DeepSeek API
- _update_memory 只按完整公司名匹配，"茅台"这类简称匹配不到（已知限制）

## 如何解决

- 换用 /opt/homebrew/bin/python3.12 运行
- 公司名匹配逻辑：遍历 _MOCK_STOCK / _MOCK_COMPANY_INFO 全名，命中即写入记忆

## 今天新增的代码

- day3/memory.py / agent.py / main.py / tools.py / 理论.md
- 用户实现：_update_memory（抽取"关注的股票"写入长期记忆）

## 测试结果

- 单元测试：写入 / 不写入 / 覆盖更新全部正确
- 端到端验收（重启前后）：
  - "我正在研究贵州茅台。" → 调 3 个工具生成研究概览 ✓
  - "它最近有什么风险？" → 正确理解"它"= 贵州茅台 ✓
  - 重启后选择同一会话 → 历史从 SQLite 恢复 ✓
  - "分析刚才那家公司" → 仍知道是贵州茅台，生成完整分析报告 ✓
- 数据库核验：messages 6 条，memory 表有 {"关注的股票": "贵州茅台"} ✓

## 今日验收

- [x] 理论验收
- [x] 实战验收（重启后仍记得上下文）
- [x] 测试验收
- [ ] Git Commit

## 今日最重要的三个知识点

1.记忆的理解和实现，通过长期记忆和短期记忆，实现会话上下文，SQLite 持久化，重启程序后仍记得上下文。
2.agent 拥有长期记忆的流程，每次重启对话都会读取长期记忆，让大模型记住你们聊过什么？
3.更新记忆的方式，如何让大模型记住你们聊过什么？

## 我还不会什么

1. 具体的python代码实现，需要大模型辅助完成开发，我需要会实现吗？如果我找工作的话，我需要会吗？

## 明天计划

Day 4：LangGraph / Agent Workflow——State、Node、Edge、Conditional Edge、
用图结构实现 ResearchGraph（行情→新闻→财务→分析→风险→报告）。
