"""Day 1 的三个工具：计算器、天气、股票行情（先用模拟数据）。"""

import ast
import operator
from datetime import datetime


# ---------- Calculator ----------

# 只允许这些运算，杜绝任意代码执行（不用 eval）
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
    """计算简单四则运算，例如 '2 + 8'，返回结构化结果。"""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        return {
            "expression": expression.strip(),
            "result": result,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        raise ValueError(f"无法计算 '{expression}': {e}") from e


# ---------- Weather ----------

_WEATHER_DATA = {
    "上海": {"temperature": 28, "condition": "多云", "humidity": 72},
    "北京": {"temperature": 25, "condition": "晴", "humidity": 40},
    "深圳": {"temperature": 31, "condition": "阵雨", "humidity": 85},
    "广州": {"temperature": 30, "condition": "多云", "humidity": 80},
}


def get_weather(city: str) -> dict:
    """返回指定城市的模拟天气。"""
    city = city.strip()
    if city not in _WEATHER_DATA:
        raise ValueError(
            f"暂无 {city} 的天气数据，支持的城市: {', '.join(_WEATHER_DATA)}"
        )
    data = _WEATHER_DATA[city]
    return {
        "city": city,
        "temperature": data["temperature"],
        "condition": data["condition"],
        "humidity": data["humidity"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- Stock ----------

_STOCK_DATA = {
    "贵州茅台": {"symbol": "600519", "price": 1680.50, "change": 12.80, "change_percent": 0.77},
    "宁德时代": {"symbol": "300750", "price": 256.30, "change": -3.20, "change_percent": -1.23},
    "比亚迪": {"symbol": "002594", "price": 245.80, "change": 5.60, "change_percent": 2.33},
    "招商银行": {"symbol": "600036", "price": 36.42, "change": 0.18, "change_percent": 0.50},
}


def get_stock_price(company: str) -> dict:
    """返回指定公司的模拟股票行情。"""
    company = company.strip()
    if company not in _STOCK_DATA:
        raise ValueError(
            f"暂无 {company} 的行情数据，支持: {', '.join(_STOCK_DATA)}"
        )
    data = _STOCK_DATA[company]
    return {
        "symbol": data["symbol"],
        "name": company,
        "price": data["price"],
        "change": data["change"],
        "change_percent": data["change_percent"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- 工具注册表 ----------

# Agent 循环会读取这个注册表：生成给 LLM 的工具说明 + 根据名字找到真实函数
TOOLS = [
    {
        "name": "calculate",
        "description": "计算简单的四则运算表达式，例如 '2 + 8'。用户提出数学计算时调用。",
        "parameters": {"expression": "算术表达式字符串，例如 '2 + 8'"},
        "function": calculate,
    },
    {
        "name": "get_weather",
        "description": "查询指定城市的当前天气。",
        "parameters": {"city": "城市名称，例如 '上海'"},
        "function": get_weather,
    },
    {
        "name": "get_stock_price",
        "description": "查询指定公司的最新股票行情。",
        "parameters": {"company": "公司名称，例如 '贵州茅台'"},
        "function": get_stock_price,
    },
]
