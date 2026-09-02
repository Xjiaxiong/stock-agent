"""Day 6 产品版 ResearchGraph。

与 Day 4 的区别：
- analysis / risk 两个节点调用 DeepSeek 生成（不再是模板拼装）
- report 节点把 State 里的数据和 LLM 分析结果组装成 10 章节 Markdown
- server.py 用 graph.stream() 逐节点推送进度（SSE），前端实时显示
"""

import json
import os
import re
import sys
import time
import urllib.request
from typing import TypedDict

# 把 backend 目录加入模块搜索路径，
# 这样无论从项目根目录跑 uvicorn 还是直接运行本文件，都能 import 到 tools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from tools import (
    get_company_info,
    get_financial_data,
    get_stock_news,
    get_stock_price,
)


def _load_dotenv() -> None:
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

DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


class ResearchState(TypedDict):
    symbol: str
    company_info: dict
    stock_data: dict
    news: list
    financial_data: dict
    analysis: dict
    risks: dict
    report: str
    error: str


# ---------- LLM 工具函数 ----------


def _call_llm(messages: list, max_tokens: int = 2000) -> str:
    """调用 DeepSeek，返回文本（带 2 次重试）。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在项目根目录 .env 中配置")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"LLM 调用失败: {last_error}")


def _parse_json(text: str) -> dict:
    """解析 LLM 输出的 JSON（容忍代码围栏和前后夹带文字）。"""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


# ---------- 数据节点（用工具，不花 LLM 钱） ----------


def company_node(state: ResearchState) -> dict:
    print("  -> 节点: company")
    result = get_company_info(state["symbol"])
    if "error" in result:
        return {"error": result["message"]}
    return {"company_info": result}


def stock_node(state: ResearchState) -> dict:
    print("  -> 节点: stock")
    result = get_stock_price(state["symbol"])
    if "error" in result:
        return {"error": result["message"]}
    return {"stock_data": result}


def news_node(state: ResearchState) -> dict:
    print("  -> 节点: news")
    result = get_stock_news(state["symbol"])
    if "error" in result:
        return {"news": []}
    return {"news": result["news"]}


def financial_node(state: ResearchState) -> dict:
    print("  -> 节点: financial")
    result = get_financial_data(state["symbol"])
    if "error" in result:
        return {"financial_data": {}}
    return {"financial_data": result}


# ---------- 分析节点（调 LLM） ----------


def _data_brief(state: ResearchState) -> str:
    """把 State 里的数据压缩成给 LLM 的一段文字。"""
    return json.dumps(
        {
            "公司": state["symbol"],
            "公司信息": state.get("company_info", {}),
            "行情": state.get("stock_data", {}),
            "新闻": state.get("news", []),
            "财务": state.get("financial_data", {}),
        },
        ensure_ascii=False,
    )


def analysis_node(state: ResearchState) -> dict:
    print("  -> 节点: analysis（LLM）")
    prompt = f"""你是股票基本面分析师。基于以下数据（模拟数据），输出 JSON：
{{
  "summary": "一段综合总结",
  "fundamentals": ["基本面要点1", "要点2"],
  "technical": ["技术面要点1", "要点2"],
  "sentiment": ["市场情绪要点1", "要点2"],
  "catalysts": ["潜在催化剂1", "催化剂2"]
}}
只输出 JSON，不要多余文字。

数据：{_data_brief(state)}"""
    content = _call_llm(
        [{"role": "system", "content": "你是严谨的股票研究分析师，只根据给定数据分析，不编造。"},
         {"role": "user", "content": prompt}]
    )
    parsed = _parse_json(content)
    if not parsed:
        raise RuntimeError("分析节点未能解析 LLM 输出")
    return {"analysis": parsed}


def risk_node(state: ResearchState) -> dict:
    print("  -> 节点: risk（LLM）")
    analysis = state.get("analysis", {})
    prompt = f"""你是风险分析师。基于以下信息，列出 3~5 条风险，输出 JSON：
{{"risks": ["风险1", "风险2"]}}
只输出 JSON。

公司：{state['symbol']}
数据：{_data_brief(state)}
已有分析：{json.dumps(analysis, ensure_ascii=False)}"""
    content = _call_llm(
        [{"role": "system", "content": "你是谨慎的风险分析师，指出真实风险，不夸大不编造。"},
         {"role": "user", "content": prompt}]
    )
    parsed = _parse_json(content)
    if not parsed:
        raise RuntimeError("风险节点未能解析 LLM 输出")
    return {"risks": parsed}


# ---------- 报告节点（模板组装，保证 10 章节结构） ----------


def report_node(state: ResearchState) -> dict:
    print("  -> 节点: report")
    name = state["symbol"]
    info = state.get("company_info", {})
    stock = state.get("stock_data", {})
    news = state.get("news", [])
    fin = state.get("financial_data", {})
    analysis = state.get("analysis", {})
    risks = state.get("risks", {}).get("risks", [])

    lines = [f"# {name} 研究报告", ""]

    lines += ["## 1. 公司概况", ""]
    lines += [
        f"- 股票代码：{info.get('symbol', '-')}",
        f"- 行业：{info.get('industry', '-')}",
        f"- 上市地点：{info.get('exchange', '-')}（{info.get('listing_date', '-')}上市）",
        f"- 简介：{info.get('description', '-')}",
    ]

    lines += ["", "## 2. 最新行情", ""]
    if stock:
        lines += [
            f"- 最新价：{stock['price']} 元（{stock['change']:+.2f}，{stock['change_percent']:+.2f}%）",
            f"- 数据时间：{stock['timestamp']}",
        ]
    else:
        lines += ["- 无行情数据"]

    lines += ["", "## 3. 近期新闻", ""]
    for item in news:
        lines.append(f"- **{item['title']}**（{item['date']} · {item['source']}）")
        lines.append(f"  {item['summary']}")
    if not news:
        lines += ["- 暂无新闻"]

    lines += ["", "## 4. 基本面", ""]
    if fin:
        lines += [
            f"- 营收同比：{fin['revenue_yoy']}%",
            f"- 净利润同比：{fin['net_profit_yoy']}%",
            f"- ROE：{fin['roe']}% ｜ 毛利率：{fin['gross_margin']}% ｜ 市盈率：{fin['pe']}",
        ]
    for p in analysis.get("fundamentals", []):
        lines.append(f"- {p}")

    lines += ["", "## 5. 技术面", ""]
    for p in analysis.get("technical", []):
        lines.append(f"- {p}")
    if not analysis.get("technical"):
        lines += ["- 暂无技术面数据"]

    lines += ["", "## 6. 市场情绪", ""]
    for p in analysis.get("sentiment", []):
        lines.append(f"- {p}")

    lines += ["", "## 7. 潜在催化剂", ""]
    for p in analysis.get("catalysts", []):
        lines.append(f"- {p}")

    lines += ["", "## 8. 潜在风险", ""]
    for r in risks:
        lines.append(f"- {r}")

    lines += ["", "## 9. 信息来源", ""]
    lines += ["- 行情/新闻/财务/公司信息：模拟数据（产品演示用，后续接真实数据源）"]
    if news:
        srcs = sorted({item["source"] for item in news})
        lines.append(f"- 新闻来源：{'、'.join(srcs)}")
    lines += ["", "## 10. Agent 总结", ""]
    lines.append(analysis.get("summary", "综合分析完成（模拟数据）。"))
    lines.append("")
    lines.append("> 免责声明：本报告基于模拟数据自动生成，不构成投资建议。")

    return {"report": "\n".join(lines)}


def error_node(state: ResearchState) -> dict:
    print("  -> 节点: error")
    return {"error": state.get("error", "未知错误")}


# ---------- 条件边 ----------


def route_after_company(state: ResearchState) -> str:
    return "error" if state.get("error") else "stock"


def route_after_news(state: ResearchState) -> str:
    return "financial"  # 产品版不再需要 search_more，保持图简单


# ---------- 建图 ----------


def build_graph():
    graph = StateGraph(ResearchState)
    for name, fn in [
        ("company", company_node),
        ("stock", stock_node),
        ("news", news_node),
        ("financial", financial_node),
        ("analysis", analysis_node),
        ("risk", risk_node),
        ("report", report_node),
        ("error", error_node),
    ]:
        graph.add_node(name, fn)

    graph.add_edge(START, "company")
    graph.add_conditional_edges("company", route_after_company, {"stock": "stock", "error": "error"})
    graph.add_edge("stock", "news")
    graph.add_edge("news", "financial")
    graph.add_edge("financial", "analysis")
    graph.add_edge("analysis", "risk")
    graph.add_edge("risk", "report")
    graph.add_edge("report", END)
    graph.add_edge("error", END)
    return graph.compile(checkpointer=MemorySaver())
