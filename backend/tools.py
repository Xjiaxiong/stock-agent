"""Day 6 产品版工具层：行情 / 公司信息 / 新闻 / 财务（模拟数据）。

和 Day 4/5 的区别：这是给"产品"用的工具集合，字段稳定、错误结构化，
之后接真实数据源时只需替换函数内部实现，接口保持不变。
"""

from datetime import datetime


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

_MOCK_STOCK = {
    "贵州茅台": {"price": 1680.50, "change": 12.80, "change_percent": 0.77},
    "宁德时代": {"price": 256.30, "change": -3.20, "change_percent": -1.23},
    "比亚迪": {"price": 245.80, "change": 5.60, "change_percent": 2.33},
    "招商银行": {"price": 36.42, "change": 0.18, "change_percent": 0.50},
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

_MOCK_FINANCIAL = {
    "贵州茅台": {"revenue_yoy": 15.2, "net_profit_yoy": 16.8, "roe": 31.5, "gross_margin": 91.8, "pe": 24.5},
    "宁德时代": {"revenue_yoy": 8.6, "net_profit_yoy": 12.4, "roe": 18.9, "gross_margin": 24.2, "pe": 22.1},
    "比亚迪": {"revenue_yoy": 21.3, "net_profit_yoy": 18.5, "roe": 20.6, "gross_margin": 20.8, "pe": 19.8},
    "招商银行": {"revenue_yoy": 2.4, "net_profit_yoy": 4.1, "roe": 14.7, "gross_margin": 0, "pe": 6.2},
}


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_company_info(company: str) -> dict:
    company = company.strip()
    if company not in _MOCK_COMPANY:
        return {"error": "unknown_company",
                "message": f"暂无 {company} 的公司信息，支持: {', '.join(_MOCK_COMPANY)}"}
    return {"name": company, **_MOCK_COMPANY[company], "timestamp": _ts()}


def get_stock_price(company: str) -> dict:
    company = company.strip()
    if company not in _MOCK_STOCK:
        return {"error": "unknown_company",
                "message": f"暂无 {company} 的行情数据，支持: {', '.join(_MOCK_STOCK)}"}
    data = _MOCK_STOCK[company]
    return {
        "name": company, "symbol": _MOCK_COMPANY[company]["symbol"],
        "price": data["price"], "change": data["change"],
        "change_percent": data["change_percent"], "timestamp": _ts(),
    }


def get_stock_news(company: str) -> dict:
    company = company.strip()
    if company not in _MOCK_NEWS:
        return {"error": "unknown_company",
                "message": f"暂无 {company} 的新闻数据，支持: {', '.join(_MOCK_NEWS)}"}
    return {"company": company, "news": _MOCK_NEWS[company], "timestamp": _ts()}


def get_financial_data(company: str) -> dict:
    company = company.strip()
    if company not in _MOCK_FINANCIAL:
        return {"error": "unknown_company",
                "message": f"暂无 {company} 的财务数据，支持: {', '.join(_MOCK_FINANCIAL)}"}
    return {"name": company, **_MOCK_FINANCIAL[company], "timestamp": _ts()}
