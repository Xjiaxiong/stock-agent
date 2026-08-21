"""Day 2 工具集：5 个工具，每个都带 JSON Schema 和错误处理。

注意：与 Day 1 不同的是，这里的每个工具都定义了 parameters（JSON Schema），
供 DeepSeek 原生 Function Calling 使用。
"""

import ast
import operator
from datetime import datetime, timedelta


# ---------- Calculator ----------

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def _safe_eval(node):
    """递归求值 AST 节点，只接受数字、四则运算、括号和取负。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    raise ValueError("表达式只能包含数字和 + - * / 运算")


def calculate(expression: str) -> dict:
    """计算简单四则运算，例如 '2 + 8'。"""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        return {
            "expression": expression.strip(),
            "result": result,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        return {
            "error": "invalid_expression",
            "message": f"无法计算 '{expression}': {e}",
        }


# ---------- 模拟数据 ----------

_MOCK_STOCK = {
    "贵州茅台": {"symbol": "600519", "price": 1680.50, "change": 12.80, "change_percent": 0.77},
    "宁德时代": {"symbol": "300750", "price": 256.30, "change": -3.20, "change_percent": -1.23},
    "比亚迪": {"symbol": "002594", "price": 245.80, "change": 5.60, "change_percent": 2.33},
    "招商银行": {"symbol": "600036", "price": 36.42, "change": 0.18, "change_percent": 0.50},
    "中际旭创": {"symbol": "300308", "price": 128.40, "change": 3.20, "change_percent": 2.56},
    "英伟达": {"symbol": "NVDA", "price": 131.20, "change": -1.85, "change_percent": -1.39},
}

_MOCK_COMPANY_INFO = {
    "贵州茅台": {
        "symbol": "600519", "industry": "白酒", "exchange": "上交所",
        "listing_date": "2001-08-27",
        "description": "中国高端白酒龙头企业，主打产品为飞天茅台系列。",
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
    "中际旭创": {
        "symbol": "300308", "industry": "光模块", "exchange": "深交所",
        "listing_date": "2012-04-10",
        "description": "全球光模块龙头，受益于 AI 数据中心需求。",
    },
    "英伟达": {
        "symbol": "NVDA", "industry": "半导体/AI 芯片", "exchange": "NASDAQ",
        "listing_date": "1999-01-22",
        "description": "全球 AI 算力芯片龙头，GPU 市场份额领先。",
    },
}


# ---------- 工具：股票行情 ----------

def get_stock_price(company: str) -> dict:
    """查询指定公司的最新股票行情（模拟数据）。"""
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


# ---------- 工具：公司信息 ----------

def get_company_info(company: str) -> dict:
    """查询指定公司的基本信息（模拟数据）。"""
    company = company.strip()
    if company not in _MOCK_COMPANY_INFO:
        return {
            "error": "unknown_company",
            "message": f"暂无 {company} 的公司信息，支持: {', '.join(_MOCK_COMPANY_INFO)}",
        }
    return {
        "name": company,
        **_MOCK_COMPANY_INFO[company],
    }


# ---------- 工具：网络搜索（模拟） ----------

def search_web(query: str) -> dict:
    """模拟网络搜索，返回与查询相关的 3 条结果。"""
    query = query.strip()
    if not query:
        return {"error": "empty_query", "message": "搜索关键词不能为空"}
    return {
        "query": query,
        "results": [
            {
                "title": f"【模拟】{query} - 最新动态",
                "url": f"https://example.com/news/{query}",
                "snippet": f"关于「{query}」的最新报道摘要，内容为模拟数据。",
            },
            {
                "title": f"【模拟】{query} 行业分析",
                "url": f"https://example.com/analysis/{query}",
                "snippet": f"从行业角度分析「{query}」的现状与趋势，内容为模拟数据。",
            },
            {
                "title": f"【模拟】{query} 市场观点",
                "url": f"https://example.com/opinion/{query}",
                "snippet": f"市场对「{query}」的近期观点汇总，内容为模拟数据。",
            },
        ],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- 工具：公司新闻（由你实现） ----------

_MOCK_NEWS = {
    "贵州茅台": [
        {
            "title": "贵州茅台发布半年报，营收保持稳健增长",
            "date": "2026-08-15",
            "source": "证券时报",
            "summary": "公司上半年实现营收同比增长约 15%，直销渠道占比继续提升。",
        },
        {
            "title": "飞天茅台批价企稳，机构看好中秋旺季",
            "date": "2026-08-18",
            "source": "财联社",
            "summary": "近期飞天茅台批价小幅回升，多家券商认为中秋国庆旺季有望带动需求。",
        },
    ],
    "宁德时代": [
        {
            "title": "宁德时代发布新一代储能电池",
            "date": "2026-08-12",
            "source": "上证报",
            "summary": "新一代储能电芯能量密度提升 20%，预计明年量产。",
        },
        {
            "title": "宁德时代海外工厂产能爬坡顺利",
            "date": "2026-08-17",
            "source": "财联社",
            "summary": "公司欧洲基地产能利用率持续提升，海外收入占比增加。",
        },
    ],
    "英伟达": [
        {
            "title": "英伟达新一代 AI 芯片订单超预期",
            "date": "2026-08-14",
            "source": "路透社",
            "summary": "数据中心客户对新一代 GPU 需求强劲，供应链持续紧张。",
        },
        {
            "title": "英伟达市值再创新高",
            "date": "2026-08-19",
            "source": "CNBC",
            "summary": "受 AI 算力需求推动，公司股价近期创历史新高。",
        },
    ],
}


def get_stock_news(company: str) -> dict:
    """查询指定公司最近的新闻（模拟数据）。"""
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


# ---------- 工具注册表（含 JSON Schema） ----------

TOOLS = [
    {
        "name": "calculate",
        "description": "计算简单的四则运算表达式，例如 '2 + 8'。用户提出数学计算时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "算术表达式字符串，例如 '2 + 8'",
                }
            },
            "required": ["expression"],
        },
        "function": calculate,
    },
    {
        "name": "get_stock_price",
        "description": "查询指定公司的最新股票行情，包括价格、涨跌幅。",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "公司名称，例如 '贵州茅台'",
                }
            },
            "required": ["company"],
        },
        "function": get_stock_price,
    },
    {
        "name": "get_stock_news",
        "description": "查询指定公司最近的新闻标题和摘要。",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "公司名称，例如 '贵州茅台'",
                }
            },
            "required": ["company"],
        },
        "function": get_stock_news,
    },
    {
        "name": "get_company_info",
        "description": "查询指定公司的基本信息，如行业、上市交易所、简介。",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "公司名称，例如 '贵州茅台'",
                }
            },
            "required": ["company"],
        },
        "function": get_company_info,
    },
    {
        "name": "search_web",
        "description": "模拟网络搜索，返回与关键词相关的网页结果列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，例如 'AI 芯片行业动态'",
                }
            },
            "required": ["query"],
        },
        "function": search_web,
    },
]
