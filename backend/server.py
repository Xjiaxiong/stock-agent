"""Day 6 后端 API：POST /api/analysis，SSE 流式返回 Agent 进度和最终报告。

运行：cd 项目根目录 && .venv/bin/python -m uvicorn backend.server:app --port 8000
"""

import json
import os
import sys
import uuid

# 把 backend 目录加入模块搜索路径（原因同 graph.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph import build_graph

app = FastAPI(title="Stock Research Agent API")

# 允许前端 localhost:3000 跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
