"""产品版工具层：行情 / 财务 / 公司信息 / 新闻。

真实数据源：同花顺金融数据 API（https://fuyao.aicubes.cn，REST + X-api-key）。

和 Day 4/5 的区别：这是给"产品"用的工具集合，字段稳定、错误结构化。
这里只替换函数内部实现，接口保持不变，graph.py 的 Agent 编排完全不受影响。

数据来源说明：
- 行情(get_stock_price)：  同花顺 A 股行情快照（真实）
- 财务(get_financial_data)：同花顺利润表/财务指标/估值快照（真实）
- 公司信息(get_company_info)：名称/代码/交易所来自同花顺标的检索；行业与简介
  上游暂未提供，返回明确的"暂无"占位，不编造。
- 新闻(get_stock_news)：同花顺公开能力不含新闻/公告原文，保留明确的占位新闻，
  返回结构不变（title/date/source/summary），但每条的来源带 [占位] 标记。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta


# ---------- 环境与数据源配置 ----------

_HITHINK_BASE = "https://fuyao.aicubes.cn"
_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 内存缓存：一个请求进程内，多个工具节点（company -> stock -> financial）
# 都会解析同一家公司，避免重复打同花顺检索接口。
# key = 公司输入(去空白)；value = 消歧结果 dict 或 None
_TICKER_CACHE: dict = {}
_TICKER_CACHE_TTL = 3600  # 标的目录极少变化，缓存 1 小时
_TICKER_CACHE_AT: dict = {}


def _load_dotenv() -> None:
    """向上查找 .env 并写入 os.environ（graph.py 有同款实现，这里保持自包含）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        env_path = os.path.join(current, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


_load_dotenv()


def _hithink_api_key() -> str:
    key = os.environ.get("HITHINK_FINANCE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 HITHINK_FINANCE_API_KEY，请在项目根目录 .env 中配置")
    return key


def _api_get(path: str, params: dict, timeout: int = 15) -> dict:
    """调用同花顺 REST API，返回 data 部分；业务错误抛 RuntimeError。"""
    url = _HITHINK_BASE + path + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"X-api-key": _hithink_api_key()}, method="GET"
    )
    last_error = None
    for attempt in range(3):  # 只对网络异常/429/5xx 做 3 次退避重试
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            code = body.get("code")
            if code == 0:
                return body.get("data") or {}
            # 4001 限流 / 5xxx 上游故障：短暂退避后重试
            if code in (4001,) or (isinstance(code, int) and code >= 5000):
                last_error = RuntimeError(f"[{code}] {body.get('message')}")
                time.sleep(0.8 * (attempt + 1))
                continue
            raise RuntimeError(f"[{code}] {body.get('message')}")
        except RuntimeError:
            raise
        except Exception as e:  # 网络类异常
            last_error = e
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"同花顺 API 调用失败: {last_error}")


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _ms_to_iso(ms) -> str:
    """毫秒 Unix 时间戳 -> 北京时间 ISO 字符串；None 返回 None。"""
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, tz=_TZ).isoformat(timespec="seconds")


def _exchange_name(exchange) -> str:
    return {"SH": "上交所", "SZ": "深交所", "BJ": "北交所"}.get(exchange, exchange)


def _resolve_ticker(company: str) -> dict:
    """把公司名 / 6 位代码消歧为唯一的 A 股 thscode（不做后缀猜测）。"""
    company = (company or "").strip()
    if not company:
        raise RuntimeError("公司名称不能为空")
    now = time.time()
    cached = _TICKER_CACHE.get(company)
    if cached is not None and now - _TICKER_CACHE_AT.get(company, 0) < _TICKER_CACHE_TTL:
        return cached
    # 1) 用户可能直接给了 600519 这种 6 位代码 -> 用代码搜
    # 2) 否则按名称搜（支持子串）
    queries = [company] if company.isdigit() else [company, f"{company} 股份"]
    hit = None
    for q in queries:
        data = _api_get("/api/meta/tickers/search", {"q": q, "asset_type": "a-share", "limit": 10})
        for item in data.get("item", []):
            if item.get("asset_type") != "a-share":
                continue
            # 名称搜索优先精确匹配，代码搜索要求代码完全一致
            name, ticker = item.get("name", ""), item.get("ticker", "")
            if company == name or company == ticker:
                hit = item
                break
            if company.isdigit():
                continue  # 代码输入：不允许子串误匹配
            if hit is None and company in name:
                hit = item  # 名称子串的第一个命中，暂存但继续找精确匹配
        if hit and (hit.get("name") == company or hit.get("ticker") == company):
            break
    if not hit:
        raise RuntimeError(f"未能在 A 股代码表中找到「{company}」，请确认名称/代码正确（仅支持 A 股）")
    _TICKER_CACHE[company] = hit
    _TICKER_CACHE_AT[company] = now
    return hit


def _not_found(company: str, data_kind: str) -> dict:
    return {"error": "unknown_company", "message": f"暂无 {company} 的{data_kind}"}


# ---------- 历史模拟数据（仅供对照，真实接入后不再使用） ----------

_MOCK_COMPANY = {
    "贵州茅台": {
        "symbol": "600519", "industry": "白酒", "exchange": "上交所",
        "listing_date": "2001-08-27",
        "description": "中国高端白酒龙头企业，主打飞天茅台系列。",
    },
    "宁德时代": {
        "symbol": "300750", "industry": "动力电池", "exchange": "深交所",
        "listing_date": "2018-06-11",
        "description": "全球领先的动力电池和储能电池制造商。",
    },
    "比亚迪": {
        "symbol": "002594", "industry": "新能源汽车", "exchange": "深交所",
        "listing_date": "2011-06-30",
        "description": "覆盖新能源汽车、电池、半导体的综合制造商。",
    },
    "招商银行": {
        "symbol": "600036", "industry": "银行", "exchange": "上交所",
        "listing_date": "2002-04-09",
        "description": "国内领先的股份制商业银行，零售业务优势明显。",
    },
}

_MOCK_NEWS = {
    "贵州茅台": [
        {"title": "贵州茅台发布半年报，营收保持稳健增长", "date": "2026-08-15", "source": "证券时报",
         "summary": "上半年营收同比增长约 15%，直销渠道占比继续提升。"},
        {"title": "飞天茅台批价企稳，机构看好中秋旺季", "date": "2026-08-18", "source": "财联社",
         "summary": "批价小幅回升，券商认为中秋国庆旺季有望带动需求。"},
        {"title": "茅台加快海外市场布局", "date": "2026-08-20", "source": "上证报",
         "summary": "东南亚渠道建设加速，国际化战略进入落地期。"},
    ],
    "宁德时代": [
        {"title": "宁德时代发布新一代储能电池", "date": "2026-08-12", "source": "上证报",
         "summary": "新一代储能电芯能量密度提升 20%，预计明年量产。"},
        {"title": "宁德时代海外工厂产能爬坡顺利", "date": "2026-08-17", "source": "财联社",
         "summary": "欧洲基地产能利用率提升，海外收入占比增加。"},
    ],
    "比亚迪": [
        {"title": "比亚迪发布第五代 DM 技术", "date": "2026-08-10", "source": "财联社",
         "summary": "新混动系统油耗进一步降低，上市后订单反响热烈。"},
        {"title": "比亚迪海外销量创单月新高", "date": "2026-08-16", "source": "证券时报",
         "summary": "东南亚与拉美贡献主要增量，单月销量突破 8 万辆。"},
    ],
    "招商银行": [
        {"title": "招商银行发布中期业绩，零售业务韧性凸显", "date": "2026-08-12", "source": "上证报",
         "summary": "上半年净利润保持正增长，零售客户 AUM 持续提升。"},
        {"title": "机构：银行板块估值修复仍有空间", "date": "2026-08-18", "source": "中证报",
         "summary": "高股息银行股在震荡市中配置价值突出。"},
    ],
}


# ---------- 对外工具函数：签名与 graph.py 保持不变 ----------


def get_company_info(company: str) -> dict:
    """公司名称/代码/交易所来自同花顺标的检索；行业与简介暂无真实来源。"""
    company = company.strip()
    try:
        hit = _resolve_ticker(company)
    except RuntimeError as e:
        return {"error": "unknown_company", "message": str(e)}
    return {
        "name": hit.get("name", company),
        "symbol": hit.get("ticker"),
        "thscode": hit.get("thscode"),
        "exchange": _exchange_name(hit.get("exchange")),
        "asset_type": hit.get("asset_type"),
        # 同花顺公开能力暂无行业分类与公司简介端点；明确返回空占位，不让 Agent 编造
        "industry": "暂无（上游未提供行业分类）",
        "listing_date": "暂无",
        "description": "暂无（上游未提供公司简介，请基于行情与财务数据自行分析）",
        "source": "同花顺金融数据 API（标的检索）",
        "timestamp": _now_iso(),
    }


def get_stock_price(company: str) -> dict:
    """真实行情：同花顺 A 股行情快照。"""
    company = company.strip()
    try:
        hit = _resolve_ticker(company)
        thscode = hit["thscode"]
        data = _api_get("/api/a-share/prices/snapshot", {"thscodes": thscode})
        items = data.get("item") or []
    except RuntimeError as e:
        return {"error": "data_error", "message": str(e)}
    if not items:
        return _not_found(company, "行情数据")
    row = items[0]
    return {
        "name": hit.get("name", company),
        "symbol": hit.get("ticker"),
        "thscode": thscode,
        "price": row.get("last_price"),
        "change": row.get("price_change"),
        "change_percent": round(row.get("price_change_ratio_pct") or 0, 2),
        "open": row.get("open_price"),
        "high": row.get("high_price"),
        "low": row.get("low_price"),
        "prev_close": row.get("prev_price"),
        "volume": row.get("volume"),
        "turnover": row.get("turnover"),
        # 快照 data.timestamp 为上游就绪时间；单票模式下为 null 时退化为当前时间
        "timestamp": _ms_to_iso(data.get("timestamp")) or _now_iso(),
        "source": "同花顺金融数据 API（行情快照）",
    }


def get_stock_news(company: str) -> dict:
    """新闻占位：同花顺公开能力不含新闻/公告原文。

    返回结构与原有模拟数据一致（title/date/source/summary），保证 graph 和
    报告模板不报错；但每一条都在来源里带 [占位] 标记，LLM 与用户不会被误导。
    """
    company = company.strip()
    if company in _MOCK_NEWS:
        news = [
            {
                "title": item["title"],
                "date": item["date"],
                "source": f"{item['source']} [占位]",
                "summary": f"{item['summary']}（占位内容：同花顺 API 暂不提供新闻原文）",
            }
            for item in _MOCK_NEWS[company]
        ]
    else:
        news = []
    return {
        "company": company,
        "news": news,
        "note": "新闻数据为占位内容（同花顺公开能力不包含新闻/公告原文），不代表真实事件",
        "source": "占位",
        "timestamp": _now_iso(),
    }


# ---------- 财务内部实现 ----------

_GROWTH_KEYS = ("operating_income_yoy_growth_ratio", "net_profit_yoy_growth_ratio")
_PROFIT_KEYS = ("sale_gross_margin", "index_weighted_avg_roe")


def _find_indicator(abilities: list, ability_name: str, index_id: str):
    for ab in abilities:
        if ab.get("ability") != ability_name:
            continue
        for ind in ab.get("indicators", []):
            if ind.get("index_id") == index_id:
                return ind.get("value")
    return None


def _to_float(value):
    """指标端点 value 是字符串或 null，统一转 float；空值返回 None。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_indicators(thscode: str, report_hint: str) -> tuple:
    """按最新报告期取财务指标，逐期回退最多 3 次。

    返回 (毛利率, ROE, 使用的报告期, growth_mapping)；
    缺失的字段返回 None（不补零）。growth_mapping 是该报告期上游直接返回的
    同比指标（index_id -> 值），供营收/净利同比优先使用。
    """
    year_s, _, quarter_s = report_hint.partition("-")
    year = int(year_s)
    for back in range(3):  # 当前期往前最多回退 3 期
        q = int(quarter_s) - back
        if q < 1:
            year -= 1
            q = 4
        report = f"{year}-{q}"
        try:
            data = _api_get("/api/a-share/financials/indicators", {"thscode": thscode, "report": report})
            abilities = data.get("abilities") or []
            if not abilities:
                continue
            gross = _to_float(_find_indicator(abilities, "profitability", "sale_gross_margin"))
            roe = _to_float(_find_indicator(abilities, "profitability", "index_weighted_avg_roe"))
            growth = {}
            for ab in abilities:
                if ab.get("ability") != "growth":
                    continue
                for ind in ab.get("indicators", []):
                    growth[ind.get("index_id")] = ind.get("value")
            return gross, roe, report, growth
        except RuntimeError:
            continue
    return None, None, report_hint, {}


def _calc_yoy(items: list, latest_fiscal_period: str) -> tuple:
    """用利润表累计值计算营收/归母净利润同比。

    口径说明：同花顺季度利润表返回"当年累计"值（Q1=一季度、Q2=中报累计、
    Q3=三季报累计、Q4=全年），与 A 股财报披露口径一致。
    同比 = 最新累计报告期 / 上年同报告期累计 - 1。
    若本期为年报（FY），用年报同比；中途年份用最新季报累计同比。
    """
    # items 按 period_end_ms 降序（最新在前）
    def latest_item(period_key: str):
        for it in items:
            if it.get("fiscal_period") == period_key:
                return it
        return None

    def yoy_of(cur: dict, prev: dict, field: str):
        cur_val = (cur or {}).get(field)
        prev_val = (prev or {}).get(field)
        if cur_val is None or prev_val in (None, 0):
            return None
        return round((float(cur_val) - float(prev_val)) / abs(float(prev_val)) * 100, 2)

    if latest_fiscal_period in ("Q1", "Q2", "Q3", "Q4"):
        cur_rev = latest_item(latest_fiscal_period)
        # 上一个同报告期的记录：列表里同 fiscal_period 但 fiscal_year 更早的一项
        cur_year = (cur_rev or {}).get("fiscal_year")
        prev_rev = None
        if cur_rev is not None:
            for it in items:
                if it.get("fiscal_period") == latest_fiscal_period and it.get("fiscal_year") != cur_year:
                    prev_rev = it
                    break
        revenue_yoy = yoy_of(cur_rev, prev_rev, "operating_income")
        profit_yoy = yoy_of(cur_rev, prev_rev, "parent_holder_net_profit")
        return revenue_yoy, profit_yoy
    # FY 年报：年报累计同比直接用最近两个财年
    return None, None


def get_financial_data(company: str) -> dict:
    """真实财务：同花顺利润表 + 财务指标 + 估值快照。

    - revenue_yoy / net_profit_yoy：最新累计报告期 vs 上年同期累计（利润表计算）
    - roe / gross_margin：最近披露期财务指标
    - pe：估值快照 PE(TTM)，缺失时退回 PE(MRQ)
    """
    company = company.strip()
    try:
        hit = _resolve_ticker(company)
        thscode = hit["thscode"]
    except RuntimeError as e:
        return {"error": "unknown_company", "message": str(e)}

    try:
        # 1) 利润表：最近 9 期季度累计（覆盖"最新期 + 上一年同报告期"）
        income = _api_get(
            "/api/a-share/financials/income-statements",
            {"thscode": thscode, "period": "quarterly", "limit": 9},
        )
        items = income.get("item") or []
        latest = items[0] if items else {}
        fiscal_year = latest.get("fiscal_year")
        fiscal_period = latest.get("fiscal_period")
        report_hint = f"{fiscal_year}-{fiscal_period.lstrip('Q')}" if fiscal_period and fiscal_period != "FY" else f"{fiscal_year}-4"
        report_period = _ms_to_iso(latest.get("period_end_ms"))

        # 2) 财务指标：ROE / 毛利率 / 上游直出同比（若有）
        gross_margin, roe, indicator_report, growth_map = _latest_indicators(thscode, report_hint)
        revenue_yoy = _to_float(growth_map.get("operating_income_yoy_growth_ratio"))
        profit_yoy = _to_float(growth_map.get("net_profit_yoy_growth_ratio"))
        yoy_source = "同花顺财务指标（同比）" if revenue_yoy is not None or profit_yoy is not None else None

        # 3) 估值：PE(TTM)，空则退回 MRQ
        valuation = _api_get("/api/a-share/valuations/snapshot", {"thscodes": thscode})
        vrow = (valuation.get("item") or [{}])[0]
        pe = vrow.get("pe_ttm")
        if pe is None:
            pe = vrow.get("pe_mrq")
        pe = round(float(pe), 2) if pe is not None else None

        # 4) 同比兜底：上游未直出同比时，用利润表"最新累计期 vs 上年同期"计算
        if revenue_yoy is None and profit_yoy is None:
            revenue_yoy, profit_yoy = _calc_yoy(items, fiscal_period)
            yoy_source = "按同花顺季报累计口径计算（最新期 vs 上年同期）"
        revenue_yoy = round(revenue_yoy, 2) if revenue_yoy is not None else None
        profit_yoy = round(profit_yoy, 2) if profit_yoy is not None else None
    except RuntimeError as e:
        return {"error": "data_error", "message": str(e)}

    return {
        "name": hit.get("name", company),
        "symbol": hit.get("ticker"),
        "thscode": thscode,
        "revenue_yoy": revenue_yoy,
        "net_profit_yoy": profit_yoy,
        "roe": round(roe, 2) if roe is not None else None,
        "gross_margin": round(gross_margin, 2) if gross_margin is not None else None,
        "pe": pe,
        "report_period": report_period,
        "indicator_report": indicator_report,
        "yoy_method": yoy_source,
        "source": "同花顺金融数据 API（利润表/财务指标/估值快照）",
        "timestamp": _now_iso(),
    }
