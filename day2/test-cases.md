# Day 2 测试记录

目标：10 个用例，Tool Selection 正确率 ≥ 90%。

| # | 测试问题 | 预期工具 | 实际工具 | 参数正确 | 返回正确 | 回答正确 | 备注 |
|---|---------|---------|---------|---------|---------|---------|------|
| 1 | 贵州茅台现在多少钱？ | get_stock_price | get_stock_price | ✓ | ✓ | ✓ | |
| 2 | 分析一下宁德时代最近发生了什么？ | get_stock_news | get_stock_price + get_stock_news + get_company_info | ✓ | ✓ | ✓ | 并行调用 3 个工具，合理扩展 |
| 3 | 帮我计算 2 + 8 等于多少？ | calculate | calculate | ✓ | ✓ | ✓ | |
| 4 | 最近英伟达有什么新闻？ | get_stock_news | get_stock_news | ✓ | ✓ | ✓ | |
| 5 | 告诉我贵州茅台属于什么行业。 | get_company_info | get_company_info | ✓ | ✓ | ✓ | |
| 6 | 比亚迪今天的股价是多少？涨了还是跌了？ | get_stock_price | get_stock_price | ✓ | ✓ | ✓ | |
| 7 | 帮我搜索一下 AI 芯片行业最近动态 | search_web | search_web | ✓ | ✓ | ✓ | 模型注明是模拟数据 |
| 8 | 招商银行的公司基本情况？ | get_company_info | get_company_info | ✓ | ✓ | ✓ | |
| 9 | 中际旭创最近有什么新闻？ | get_stock_news | get_stock_news | ✓ | ✓ | ✓ | 工具返回错误，模型正确说明并建议 search_web |
| 10 | 计算 (3 + 5) * 2 的结果 | calculate | calculate | ✓ | ✓ | ✓ | |

进阶（可选）：宁德时代现在多少钱？最近有什么新闻？（期望：连续调用 2 个工具）

统计：Tool Selection 正确 10 / 10 = 100%
