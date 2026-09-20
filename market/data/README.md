# 盘面数据层

封装同花顺金融数据 API 的盘面类接口，只负责取数，不做业务判断。

## 使用

```bash
# 在项目根目录执行
.venv/bin/python -c "
import sys; sys.path.insert(0, 'market')
from data import hithink as h
print(len(h.fetch_limit_up_pool('2026-09-11')))
"
```

需要项目根目录 `.env` 里有 `HITHINK_FINANCE_API_KEY`。

## 已封装接口

| 函数 | 对应端点 | 说明 |
|---|---|---|
| `fetch_limit_up_pool(day)` | `/api/a-share/special-data/limit-up-pool` | 涨停/连板池（连板数、封单额、涨停时间、涨停原因） |
| `fetch_limit_down_pool(day)` | `/api/a-share/special-data/limit-down-pool` | 跌停池 |
| `fetch_limit_break_pool(day)` | `/api/a-share/special-data/limit-break-pool` | 炸板池 |
| `fetch_limit_up_ladder()` | `/api/a-share/special-data/limit-up-ladder` | 连板天梯（近 30 个交易日） |
| `fetch_anomalies(tags)` | `/api/a-share/special-data/anomaly-analysis-list` | 个股异动原因 + 关键词 |
| `fetch_hot_stocks(kind)` | `/api/a-share/special-data/hot-stock-list` 等 | 热股榜 / 飙升榜 |
| `fetch_index_catalog(tag)` | `/api/a-share-index/catalog/ths-index-list` | 同花顺概念/行业板块清单 |
| `fetch_index_snapshot(codes)` | `/api/a-share-index/prices/snapshot` | 板块/指数行情快照 |
| `fetch_market_snapshot(step)` | `/api/a-share/prices/snapshot` | 全市场行情快照（支持采样） |

## 约定

- 业务错误码会转成带接口路径的 `RuntimeError`；`code=3002`（数据未就绪，如非交易日）返回空。
- 内置节流（请求间隔 ≥0.35s）与退避重试，规避同花顺动态限流（HTTP 429 / code 4001）。
- 日期参数统一用 `YYYY-MM-DD`，内部转成上海时区零点毫秒戳。
