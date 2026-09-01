"""Day 5 MCP Server：把股票工具包装成 MCP 服务。

运行：cd mcp-server && ../.venv/bin/python server.py
（默认 stdio 传输：通过标准输入输出和客户端通信，客户端会自动启动它）

给 TS/JS 开发者的对照：
- @mcp.tool() 装饰器 = 注册一个工具，相当于把函数声明成"对外接口"
- 函数签名（参数名 + 类型 + 默认值）+ 文档字符串 = 自动生成给客户端的 Schema
- FastMCP 内部帮你处理了 JSON-RPC 协议，你只需要写普通函数
"""

from datetime import datetime

from mcp.server.fastmcp import FastMCP

# 创建 MCP Server 实例；名字会出现在客户端发现的 Server 信息里
mcp = FastMCP("stock-agent")


# ---------- 模拟数据 ----------

_MOCK_STOCK = {
    "贵州茅台": {"symbol": "600519", "price": 1680.50, "change": 12.80, "change_percent": 0.77},
    "宁德时代": {"symbol": "300750", "price": 256.30, "change": -3.20, "change_percent": -1.23},
    "比亚迪": {"symbol": "002594", "price": 245.80, "change": 5.60, "change_percent": 2.33},
    "英伟达": {"symbol": "NVDA", "price": 131.20, "change": -1.85, "change_percent": -1.39},
}

_MOCK_NEWS = {
    "贵州茅台": [
        {"title": "贵州茅台发布半年报，营收保持稳健增长", "date": "2026-08-15", "source": "证券时报",
         "summary": "公司上半年实现营收同比增长约 15%。"},
        {"title": "飞天茅台批价企稳，机构看好中秋旺季", "date": "2026-08-18", "source": "财联社",
         "summary": "多家券商认为中秋国庆旺季有望带动需求。"},
    ],
    "宁德时代": [
        {"title": "宁德时代发布新一代储能电池", "date": "2026-08-12", "source": "上证报",
         "summary": "新一代储能电芯能量密度提升 20%。"},
        {"title": "宁德时代海外工厂产能爬坡顺利", "date": "2026-08-17", "source": "财联社",
         "summary": "欧洲基地产能利用率持续提升。"},
    ],
    "比亚迪": [
        {"title": "比亚迪发布第五代 DM 技术", "date": "2026-08-10", "source": "财联社",
         "summary": "新混动系统油耗进一步降低。"},
    ],
    "英伟达": [
        {"title": "英伟达新一代 AI 芯片订单超预期", "date": "2026-08-14", "source": "路透社",
         "summary": "数据中心客户对新一代 GPU 需求强劲。"},
        {"title": "英伟达市值再创新高", "date": "2026-08-19", "source": "CNBC",
         "summary": "受 AI 算力需求推动，股价创历史新高。"},
    ],
}

_MOCK_COMPANY_INFO = {
    "贵州茅台": {"symbol": "600519", "industry": "白酒", "exchange": "上交所",
                 "listing_date": "2001-08-27", "description": "中国高端白酒龙头企业。"},
    "宁德时代": {"symbol": "300750", "industry": "动力电池", "exchange": "深交所",
                  "listing_date": "2018-06-11", "description": "全球领先的动力电池制造商。"},
    "比亚迪": {"symbol": "002594", "industry": "新能源汽车", "exchange": "深交所",
                "listing_date": "2011-06-30", "description": "覆盖新能源车、电池的综合制造商。"},
    "英伟达": {"symbol": "NVDA", "industry": "半导体/AI 芯片", "exchange": "NASDAQ",
                "listing_date": "1999-01-22", "description": "全球 AI 算力芯片龙头。"},
}


# ---------- MCP 工具 ----------


@mcp.tool()
def get_stock_price(company: str) -> dict:
    """查询指定公司的最新股票行情（模拟数据）。

    Args:
        company: 公司名称，例如 "贵州茅台"
    """
    company = company.strip()
    if company not in _MOCK_STOCK:
        return {
            "error": "unknown_company",
            "message": f"暂无 {company} 的行情数据，支持: {', '.join(_MOCK_STOCK)}",
        }
    data = _MOCK_STOCK[company]
    return {
        "symbol": data["symbol"],
        "name": company,
        "price": data["price"],
        "change": data["change"],
        "change_percent": data["change_percent"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


@mcp.tool()
def get_stock_news(company: str) -> dict:
    """查询指定公司最近的新闻（模拟数据）。

    Args:
        company: 公司名称，例如 "贵州茅台"
    """
    company = company.strip()
    if company not in _MOCK_NEWS:
        return {
            "error": "unknown_company",
            "message": f"暂无 {company} 的新闻数据，支持: {', '.join(_MOCK_NEWS)}",
        }
    return {
        "company": company,
        "news": _MOCK_NEWS[company],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


@mcp.tool()
def get_company_info(company: str) -> dict:
    """查询指定公司的基本信息（模拟数据）。

    Args:
        company: 公司名称，例如 "贵州茅台"
    """
    company = company.strip()
    if company not in _MOCK_COMPANY_INFO:
        return {
            "error": "unknown_company",
            "message": f"暂无 {company} 的公司信息，支持: {', '.join(_MOCK_COMPANY_INFO)}",
        }
    data = _MOCK_COMPANY_INFO[company]
    return {
        "name": company,
        "symbol": data["symbol"],
        "industry": data["industry"],
        "exchange": data["exchange"],
        "listing_date": data["listing_date"],
        "description": data["description"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    # 默认 transport="stdio"：通过 stdin/stdout 与 MCP Client 通信
    mcp.run()
