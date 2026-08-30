"""Day 4 ResearchGraph：用 LangGraph 把股票研究做成固定 Workflow。

流程：
    START
      ↓
    stock（获取行情）── 条件边：symbol 无效 → error
      ↓
    news（获取新闻）── 条件边：新闻 < 3 条 → search_more
      ↓
    financial（获取财务）
      ↓
    analysis（分析）
      ↓
    risk（风险检查）
      ↓
    report（生成报告）→ END

给 TS/JS 开发者的对照：
- State 相当于 Redux store / 全局变量：每个节点读它、改它
- 每个 Node 函数相当于一个 reducer：输入 state，返回"要更新的字段"
- 普通 Edge 相当于固定的执行顺序；Conditional Edge 相当于 router

运行方式：cd day4 && ../.venv/bin/python main.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from tools import get_financial_data, get_stock_news, get_stock_price


# ---------- State（相当于 Redux store 的类型定义） ----------


class ResearchState(TypedDict):
    symbol: str          # 用户输入的公司名，例如 "贵州茅台"
    stock_data: dict     # stock 节点写入：行情
    news: list           # news / search_more 节点写入：新闻列表
    financial_data: dict # financial 节点写入：财务数据
    analysis: dict       # analysis 节点写入：分析结果
    risks: dict          # risk 节点写入：风险
    report: str          # report 节点写入：最终报告
    error: str           # 出错时写入错误信息


# ---------- 节点（每个节点 = 一个函数，返回要更新到 State 的字段） ----------


def stock_node(state: ResearchState) -> dict:
    """获取行情：调 get_stock_price，成功写 stock_data，失败写 error。"""
    print("  -> 节点: stock（获取行情）")
    result = get_stock_price(state["symbol"])
    if "error" in result:
        return {"error": result["message"]}
    return {"stock_data": result}


def news_node(state: ResearchState) -> dict:
    """获取新闻：调 get_stock_news，结果写进 news 列表。"""
    print("  -> 节点: news（获取新闻）")
    result = get_stock_news(state["symbol"])
    if "error" in result:
        return {"news": []}
    return {"news": result["news"]}


def financial_node(state: ResearchState) -> dict:
    """获取财务数据：成功写 financial_data，失败用空 dict 继续。"""
    print("  -> 节点: financial（获取财务数据）")
    result = get_financial_data(state["symbol"])
    if "error" in result:
        return {"financial_data": {}}
    return {"financial_data": result}


def search_more_node(state: ResearchState) -> dict:
    """新闻不足时的补救节点：追加两条模拟新闻，凑够数量再继续。"""
    print("  -> 节点: search_more（新闻不足，补充搜索）")
    company = state["symbol"]
    extra = [
        {
            "title": f"补充搜索：{company} 近期市场观点",
            "date": "2026-08-21",
            "source": "模拟搜索",
            "summary": "市场对该公司近期表现的综合观点（模拟数据）。",
        },
        {
            "title": f"补充搜索：{company} 行业动态",
            "date": "2026-08-22",
            "source": "模拟搜索",
            "summary": "所属行业最新动态汇总（模拟数据）。",
        },
    ]
    return {"news": state["news"] + extra}


def analysis_node(state: ResearchState) -> dict:
    """分析：把行情、新闻、财务拼成结构化的分析结论。"""
    print("  -> 节点: analysis（分析）")
    name = state["symbol"]
    stock = state.get("stock_data") or {}
    news = state.get("news") or []
    fin = state.get("financial_data") or {}

    highlights = []
    if stock:
        highlights.append(
            f"最新股价 {stock['price']} 元，涨跌幅 {stock['change_percent']}%"
        )
    if fin:
        highlights.append(
            f"营收同比 {fin['revenue_yoy']}%，净利润同比 {fin['net_profit_yoy']}%，ROE {fin['roe']}%"
        )
    if news:
        highlights.append(f"近期新闻 {len(news)} 条，最新一条：{news[0]['title']}")

    return {
        "analysis": {
            "company": name,
            "summary": f"{name} 基本面与市场表现综合分析（数据为模拟）",
            "highlights": highlights,
        }
    }


def risk_node(state: ResearchState) -> dict:
    """风险检查：基于已有信息给出风险点（模板化，Day 6 会升级为 LLM 生成）。"""
    print("  -> 节点: risk（风险检查）")
    name = state["symbol"]
    risks = [
        "市场波动风险：股价受大盘与情绪影响，短期波动可能放大",
        "行业政策风险：政策变化可能影响行业景气度",
        "业绩不及预期风险：若实际业绩低于市场预期，估值可能承压",
    ]
    return {"risks": {"company": name, "risks": risks}}


def report_node(state: ResearchState) -> dict:
    """生成报告：把 State 里所有中间结果组装成 Markdown 报告。"""
    print("  -> 节点: report（生成报告）")
    name = state["symbol"]
    stock = state.get("stock_data") or {}
    news = state.get("news") or []
    fin = state.get("financial_data") or {}
    analysis = state.get("analysis") or {}
    risks = state.get("risks") or {}

    lines = [f"# {name} 研究报告", ""]

    lines += ["## 1. 最新行情", ""]
    if stock:
        lines += [
            f"- 股票代码：{stock['symbol']}",
            f"- 最新价：{stock['price']} 元（{stock['change']:+.2f}，{stock['change_percent']:+.2f}%）",
            f"- 数据时间：{stock['timestamp']}",
        ]
    else:
        lines += ["- 无行情数据"]

    lines += ["", "## 2. 近期新闻", ""]
    for item in news:
        lines.append(f"- **{item['title']}**（{item['date']} · {item['source']}）")
        lines.append(f"  {item['summary']}")
    if not news:
        lines += ["- 暂无新闻"]

    lines += ["", "## 3. 基本面", ""]
    if fin:
        lines += [
            f"- 营收同比：{fin['revenue_yoy']}%",
            f"- 净利润同比：{fin['net_profit_yoy']}%",
            f"- ROE：{fin['roe']}%",
            f"- 毛利率：{fin['gross_margin']}%",
            f"- 市盈率：{fin['pe']}",
        ]
    else:
        lines += ["- 暂无财务数据"]

    lines += ["", "## 4. 分析", ""]
    for h in analysis.get("highlights", []):
        lines.append(f"- {h}")

    lines += ["", "## 5. 风险", ""]
    for r in risks.get("risks", []):
        lines.append(f"- {r}")

    lines += ["", "---", "*报告由 Day 4 ResearchGraph 自动生成（数据为模拟）*"]
    return {"report": "\n".join(lines)}


def error_node(state: ResearchState) -> dict:
    """出错节点：打印错误信息，直接结束流程。"""
    print("  -> 节点: error（错误处理）")
    print(f"  [!] {state.get('error', '未知错误')}")
    return {"error": state.get("error", "未知错误")}


# ---------- 条件边（router 函数：读 State，返回下一个节点名） ----------


def route_after_stock(state: ResearchState) -> str:
    """stock 节点之后：有 error 就去 error，否则去 news。"""
    if state.get("error"):
        return "error"
    return "news"


def route_after_news(state: ResearchState) -> str:
    """news 节点之后：新闻不足 3 条就去 search_more，否则直接去 financial。"""
    if len(state.get("news") or []) < 3:
        return "search_more"
    return "financial"


# ---------- 建图 ----------


def build_graph():
    """把节点和边组装成一张可执行的图。"""
    graph = StateGraph(ResearchState)

    # 注册所有节点（节点名 -> 函数）
    graph.add_node("stock", stock_node)
    graph.add_node("news", news_node)
    graph.add_node("search_more", search_more_node)
    graph.add_node("financial", financial_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("risk", risk_node)
    graph.add_node("report", report_node)
    graph.add_node("error", error_node)

    # 固定边：START 出发，按顺序连接
    graph.add_edge(START, "stock")

    # 条件边：返回值决定去哪个节点（映射表：返回值 -> 节点名）
    graph.add_conditional_edges(
        "stock",
        route_after_stock,
        {"news": "news", "error": "error"},
    )
    graph.add_conditional_edges(
        "news",
        route_after_news,
        {"search_more": "search_more", "financial": "financial"},
    )

    graph.add_edge("search_more", "financial")
    graph.add_edge("financial", "analysis")
    graph.add_edge("analysis", "risk")
    graph.add_edge("risk", "report")
    graph.add_edge("report", END)
    graph.add_edge("error", END)

    # MemorySaver：把每一步的 State 存成 Checkpoint（存档点）。
    # invoke 时传 thread_id 才能命中存档；这是 Day 4 理论里 Checkpoint 的实际载体
    return graph.compile(checkpointer=MemorySaver())
