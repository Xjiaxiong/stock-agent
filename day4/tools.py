"""Day 3 工具集：5 个工具，每个都带 JSON Schema 和错误处理（从 Day 2 复用）。

给 TS/JS 开发者的对照说明：
- 这里的每个工具函数都相当于一个 backend 接口：输入参数、返回结构化 JSON
- 每个工具"失败时返回 {"error": ..., "message": ...}"，而不是抛异常——
  这样错误能通过 tool 消息回传给模型，由模型决定怎么处理
- TOOLS 注册表在最下面：一个数组，包含工具名、描述、参数 Schema 和真实函数引用
"""

# ast 是 Python 内置的"解析代码为语法树"的库。
# 我们用 ast 而不是 eval() 来算表达式，是因为 eval 能执行任意代码（安全风险），
# 而 ast 只允许我们白名单里的运算（类似只允许有限的 AST 节点）
import ast
import operator
from datetime import datetime


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
        # ast.parse(expression, mode="eval")：把字符串解析成语法树
        # _safe_eval 递归遍历这棵树，只放行数字和 + - * / 运算
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
        # 关键模式：查不到不抛异常，而是返回结构化错误。
        # 这个 dict 会以 JSON 字符串形式回传给模型，模型能看到原因并自行调整
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
        {
            "title": "茅台推出国际化新动作，海外市场布局加速",
            "date": "2026-08-20",
            "source": "上证报",
            "summary": "公司加快东南亚市场渠道建设，国际化战略进入落地期。",
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
    "比亚迪": [
        {
            "title": "比亚迪发布第五代 DM 技术",
            "date": "2026-08-10",
            "source": "财联社",
            "summary": "新混动系统油耗进一步降低，上市后订单反响热烈。",
        },
        {
            "title": "比亚迪海外销量创单月新高",
            "date": "2026-08-16",
            "source": "证券时报",
            "summary": "东南亚与拉美市场贡献主要增量，海外单月销量突破 8 万辆。",
        },
    ],
    "招商银行": [
        {
            "title": "招商银行发布中期业绩，零售业务韧性凸显",
            "date": "2026-08-12",
            "source": "上证报",
            "summary": "上半年净利润保持正增长，零售客户 AUM 持续提升。",
        },
        {
            "title": "机构：银行板块估值修复仍有空间",
            "date": "2026-08-18",
            "source": "中证报",
            "summary": "多家券商认为高股息银行股在震荡市中配置价值突出。",
        },
    ],
    "中际旭创": [
        {
            "title": "中际旭创 800G 光模块出货放量",
            "date": "2026-08-11",
            "source": "财联社",
            "summary": "AI 数据中心需求带动高速光模块订单快速增长。",
        },
        {
            "title": "中际旭创拟扩产 1.6T 光模块产线",
            "date": "2026-08-19",
            "source": "证券时报",
            "summary": "公司公告新增产能投资，瞄准下一代数据中心网络。",
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


# ---------- 工具：财务数据（模拟） ----------

_MOCK_FINANCIAL = {
    "贵州茅台": {"revenue_yoy": 15.2, "net_profit_yoy": 16.8, "roe": 31.5, "gross_margin": 91.8, "pe": 24.5},
    "宁德时代": {"revenue_yoy": 8.6, "net_profit_yoy": 12.4, "roe": 18.9, "gross_margin": 24.2, "pe": 22.1},
    "比亚迪": {"revenue_yoy": 21.3, "net_profit_yoy": 18.5, "roe": 20.6, "gross_margin": 20.8, "pe": 19.8},
    "招商银行": {"revenue_yoy": 2.4, "net_profit_yoy": 4.1, "roe": 14.7, "gross_margin": 0, "pe": 6.2},
    "中际旭创": {"revenue_yoy": 88.6, "net_profit_yoy": 112.3, "roe": 25.1, "gross_margin": 33.4, "pe": 28.7},
    "英伟达": {"revenue_yoy": 94.2, "net_profit_yoy": 101.5, "roe": 58.3, "gross_margin": 73.6, "pe": 45.3},
}


def get_financial_data(company: str) -> dict:
    """查询指定公司的财务数据（模拟数据）。"""
    company = company.strip()
    if company not in _MOCK_FINANCIAL:
        return {
            "error": "unknown_company",
            "message": f"暂无 {company} 的财务数据，支持: {', '.join(_MOCK_FINANCIAL)}",
        }
    data = _MOCK_FINANCIAL[company]
    return {
        "name": company,
        "revenue_yoy": data["revenue_yoy"],
        "net_profit_yoy": data["net_profit_yoy"],
        "roe": data["roe"],
        "gross_margin": data["gross_margin"],
        "pe": data["pe"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- 工具注册表（含 JSON Schema） ----------
# 这是 Agent 与"外部能力"之间的桥：
# - agent.py 的 _build_tool_schemas() 从这里生成给 API 的 tools 参数
# - agent.py 的 _execute_tool() 根据 name 在这里找到真正的函数并执行

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
    {
        "name": "get_financial_data",
        "description": "查询指定公司的财务数据（营收增速、净利润增速、ROE、毛利率、市盈率）。",
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
        "function": get_financial_data,
    },
]
