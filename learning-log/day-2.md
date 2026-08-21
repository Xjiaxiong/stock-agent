# Day 2

## 今日目标

掌握 Function Calling / Tool Schema / JSON Schema / 参数与错误处理；
实现至少 5 个工具；10 个测试用例 Tool Selection 正确率 ≥ 90%。

## 今日学习

理论 Q1~Q5（见 day2/理论.md）：
- 原生 Function Calling 与手写 JSON 协议的区别：API 协议保证 vs 提示词约定
- Tool Schema 是模型了解工具的唯一渠道，描述质量决定选对率
- JSON Schema 约束工具参数（类型 / 必填 / 描述 / 可选值），代码可校验
- Tool Result 要结构化、带完整信息；失败时返回可操作的结构化错误

## 我的理解

（待用户补充）

## 今天实现了什么

- day2/tools.py：5 个工具（calculate / get_stock_price / get_stock_news / get_company_info / search_web），
  全部带 JSON Schema 与结构化错误处理（get_stock_news 由用户实现）
- day2/agent.py：DeepSeek 原生 Function Calling 循环（tools 参数 → tool_calls → tool_call_id 回传）
- day2/main.py / run_tests.py：命令行入口 + 批量测试脚本
- day2/test-cases.md：10 个测试用例及记录
- 配置管理：API key 改为项目根目录 .env 共享，day 目录向上查找加载

## 遇到的问题

- API key 重复写在各个 day 目录 → 改为根目录 .env 单份配置
- get_stock_news 返回"暂无数据"时，模型需要能正确消化错误并转述给用户

## 如何解决

- .env 加载器改为从脚本目录向上查找，项目根目录只存一份 key
- 工具全部返回结构化结果（error + message），异常不逃逸，由模型根据错误信息调整

## 今天新增的代码

- day2/tools.py / agent.py / main.py / run_tests.py / test-cases.md / 理论.md
- .env.example（根目录）

## 测试结果

- 10 个用例全部正确选择工具：10/10 = 100%
- 用例 2：模型并行调用 3 个工具综合分析（行情 + 新闻 + 公司信息）
- 用例 9：错误处理链路验证通过——工具报错后模型如实说明并给出建议

## 今日验收

- [x] 理论验收
- [x] 实战验收
- [x] 测试验收（≥90%：100%）
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

Day 3：Memory / State——短期与长期记忆、对话上下文、SQLite 持久化，
重启程序后仍能记住"刚才那家公司"。
