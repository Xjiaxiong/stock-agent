"""Day 6 后端 API：POST /api/analysis，SSE 流式返回 Agent 进度和最终报告。

运行：cd 项目根目录 && .venv/bin/python -m uvicorn backend.server:app --port 8000
"""

import json
import os
import sys
import uuid
from datetime import datetime

# 把 backend 目录加入模块搜索路径（原因同 graph.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 每日复盘模块在仓库根目录的 market/ 下（与 backend/ 平级）。
# 本地运行一定有；若某部署环境没把 market/ 打包进去，则接口返回明确错误而不影响其他功能。
_MARKET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market"
)
if os.path.isdir(_MARKET_DIR) and _MARKET_DIR not in sys.path:
    sys.path.insert(0, _MARKET_DIR)

try:
    import daily_review as market_review

    MARKET_AVAILABLE = True
    MARKET_IMPORT_ERROR = ""
except Exception as _exc:  # pragma: no cover - 仅在缺模块的部署环境触发
    MARKET_AVAILABLE = False
    MARKET_IMPORT_ERROR = str(_exc)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph import build_graph

app = FastAPI(title="Stock Research Agent API")

# 允许跨域的前端来源：本地默认 localhost:3000；
# 部署后通过环境变量 CORS_ORIGINS 配置（逗号分隔多个来源，如 https://xx.vercel.app）
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 节点名 -> 前端展示的中文进度文案
NODE_LABELS = {
    "company": "获取公司概况",
    "stock": "获取股票行情",
    "news": "获取近期新闻",
    "financial": "获取财务数据",
    "analysis": "基本面分析",
    "risk": "风险分析",
    "report": "生成研究报告",
    "error": "处理错误",
}


class AnalysisRequest(BaseModel):
    company: str


def _sse(event: dict) -> str:
    """把事件 dict 转成 SSE 格式：data: {json}\n\n"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def run_analysis(company: str):
    """同步生成器：跑图，逐节点产出 SSE 事件。"""
    graph = build_graph()
    try:
        # graph.stream(stream_mode="updates")：每完成一个节点就 yield 一次
        for update in graph.stream(
            {"symbol": company},
            config={"configurable": {"thread_id": uuid.uuid4().hex[:12]}},
            stream_mode="updates",
        ):
            for node_name, state_update in update.items():
                if node_name == "error":
                    yield _sse(
                        {"type": "error", "message": state_update.get("error", "未知错误")}
                    )
                    return
                if node_name in NODE_LABELS:
                    yield _sse(
                        {"type": "progress", "node": node_name, "label": NODE_LABELS[node_name]}
                    )
                if node_name == "report":
                    yield _sse({"type": "report", "report": state_update.get("report", "")})
                    return
    except Exception as e:
        yield _sse({"type": "error", "message": f"分析失败：{e}"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics")
def metrics():
    """LLM 调用观测：次数、成功率、耗时、token（读 market/logs/llm-usage.jsonl）。

    为什么要有：复盘/研究都会调 LLM，变慢、报错、token 暴涨时需要能定位到具体哪一次，
    而不是只看一句"调用失败"。
    """
    if not MARKET_AVAILABLE:
        return {"available": False, "reason": MARKET_IMPORT_ERROR}
    try:
        import llm_client

        return {"available": True, **llm_client.summary()}
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc)}


class DailyReviewRequest(BaseModel):
    date: str | None = None  # 交易日 YYYY-MM-DD，缺省用今天
    fresh: bool = False  # 是否重新采集盘面快照


def run_daily_review(trade_date: str, fresh: bool):
    """同步生成器：逐步产出复盘进度与最终报告。"""
    if not MARKET_AVAILABLE:
        yield _sse({
            "type": "error",
            "message": f"每日复盘模块不可用（该部署未包含 market/ 目录）：{MARKET_IMPORT_ERROR}",
        })
        return
    try:
        # iter_review 每完成一个阶段就产出一条事件，节点完成后才推送该节点的进度
        for stage, payload in market_review.iter_review(trade_date, fresh=fresh):
            if stage == "report":
                yield _sse({
                    "type": "report",
                    "report": payload["report"],
                    "trade_date": payload["trade_date"],
                    "note": payload.get("note", ""),
                    # 结构化摘要：前端用它画"关键结论"摘要条和分享卡片
                    "card": payload.get("card") or {},
                })
            elif stage == "meta":
                # 让前端在采集开始前就知道"这次复盘实际用的是哪一天的数据"
                yield _sse({
                    "type": "meta",
                    "trade_date": payload["trade_date"],
                    "note": payload.get("note", ""),
                })
            else:
                yield _sse({"type": "progress", "node": stage, "label": payload})
    except Exception as e:
        yield _sse({"type": "error", "message": f"复盘失败：{e}"})


@app.get("/api/daily-review/latest")
def latest_trade_date():
    """当前可以复盘的最新交易日（前端用它预填日期，避免默认填成还没数据的今天）。

    9/15 早上 9 点前点复盘：这里返回 9/14，并说明原因。
    """
    if not MARKET_AVAILABLE:
        return {
            "trade_date": "",
            "note": f"每日复盘模块不可用（该部署未包含 market/ 目录）：{MARKET_IMPORT_ERROR}",
        }
    try:
        trade_date, note = market_review.resolve_date(None)
        return {
            "trade_date": trade_date,
            "note": note,
            "today": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"trade_date": "", "note": f"无法获取最新交易日：{e}"}


@app.post("/api/analysis")
def analysis(req: AnalysisRequest):
    company = req.company.strip()
    if not company:
        return {"type": "error", "message": "公司名不能为空"}
    return StreamingResponse(
        run_analysis(company),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/daily-review")
def daily_review(req: DailyReviewRequest):
    trade_date = (req.date or "").strip() or datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        run_daily_review(trade_date, req.fresh),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
