"""部署入口与只读环境的契约测试。

入口文件是部署的命门：路径解析或导出名写错，线上就是 500，而本地起 uvicorn 完全正常。
只读文件系统同理——Vercel 的函数只有 /tmp 可写，落盘必须降级而不是炸掉请求。
"""

import importlib.util
import json
import sys
from pathlib import Path

import daily_review as dr
import daily_snapshot as ds

ROOT = Path(__file__).resolve().parents[1]


def load_entry():
    """按 Vercel 的方式加载 api/index.py（不依赖 cwd）。"""
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["vercel_entry"] = module
    spec.loader.exec_module(module)
    return module


def test_entry_exposes_fastapi_app_with_all_routes():
    entry = load_entry()
    # 入口外面可能包了中间件（剥 rewrite 前缀那层），逐层剥到 FastAPI 应用
    inner = entry.app
    while not hasattr(inner, "routes"):
        inner = inner.asgi_app
    routes = {route.path for route in inner.routes if hasattr(route, "path")}

    assert {
        "/health",
        "/api/analysis",
        "/api/daily-review",
        "/api/daily-review/latest",
        "/api/metrics",
    } <= routes


def test_entry_makes_market_importable():
    """入口必须把 market/ 挂上搜索路径，否则复盘接口会退化成"模块不可用"。"""
    load_entry()

    assert "daily_review" in sys.modules
    assert sys.modules["daily_review"] is dr


def test_vercel_json_bundles_market_into_function():
    """vercel.json 里的 includeFiles 一旦漏掉，线上复盘接口会直接不可用。"""
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    fn = config["functions"]["api/index.py"]

    assert "market/**" in fn["includeFiles"]
    assert fn["maxDuration"] <= 60  # Hobby 上限就是 60s


def test_vercel_rewrite_keeps_original_path():
    """rewrite 目标必须带 $1 捕获，否则函数拿不到原始路径，所有接口都会 404。"""
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    destination = config["rewrites"][0]["destination"]

    assert destination.endswith("$1"), destination


def test_entry_strips_internal_rewrite_prefix():
    """函数收到的路径三种形态都要能归一化成真实路由。"""
    import asyncio

    entry = load_entry()
    seen = []

    async def downstream(scope, receive, send):
        seen.append(scope["path"])

    wrapper = entry.StripInternalPrefix(downstream)
    for incoming in ("/health", "/api/index/health", "/api/index", "/api/index/api/daily-review"):
        asyncio.run(wrapper({"type": "http", "path": incoming}, None, None))

    assert seen == ["/health", "/health", "/", "/api/daily-review"]


def test_report_save_failure_does_not_raise(monkeypatch):
    """只读文件系统（Vercel）下存档写不进去，也不能把整次复盘带崩。"""

    def boom(payload):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(dr, "save_report", boom)
    assert dr._try_save_report({"trade_date": "2026-09-18", "report": "x"}) == ""


def test_snapshot_save_failure_does_not_raise(monkeypatch):
    """只读文件系统下 mkdir/write 抛 PermissionError，复盘流程要继续往下走。"""

    def boom(*args, **kwargs):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(ds, "render_brief", lambda snapshot: "")
    monkeypatch.setattr(ds, "save_snapshot", boom)

    dr._try_save_snapshot({"trade_date": "2026-09-18"})  # 不抛异常即通过


def test_report_dir_can_be_overridden_by_env(monkeypatch):
    """线上把存档指到 /tmp，避免写只读目录。"""
    import importlib

    monkeypatch.setenv("DAILY_REPORT_DIR", "/tmp/reports")
    reloaded = importlib.reload(dr)
    try:
        assert str(reloaded.REPORT_DIR) == "/tmp/reports"
    finally:
        monkeypatch.delenv("DAILY_REPORT_DIR", raising=False)
        importlib.reload(dr)


# ---------- market/ 打包与线上排障 ----------


def load_server():
    sys.path.insert(0, str(ROOT))
    import backend.server as server  # noqa: PLC0415

    return server


def test_health_exposes_market_diagnostics():
    """云端"复盘不可用"时，先看 /health 里的 market 解析结果。"""
    from fastapi.testclient import TestClient

    server = load_server()
    body = TestClient(server.app).get("/health").json()

    assert body["status"] == "ok"
    market = body["market"]
    assert market["available"] is True  # 本地仓库里 market/ 一定在
    assert market["resolved_dir"].endswith("market")
    assert market["entry_file"].endswith("server.py")
    assert any(item["exists"] for item in market["candidates"])


def test_diagnostics_endpoint_available():
    from fastapi.testclient import TestClient

    server = load_server()
    response = TestClient(server.app).get("/api/diagnostics")

    assert response.status_code == 200
    assert "candidates" in response.json()["market"]


def test_unknown_route_echoes_received_path():
    """Vercel 上整站 404 时，兜底路由要告诉运维"函数到底收到了哪条路径"。"""
    from fastapi.testclient import TestClient

    server = load_server()
    body = TestClient(server.app).get("/nope").json()

    assert body["received_path"] == "/nope"
    assert "Vercel" in body["hint"]


def test_market_dir_env_takes_priority(monkeypatch):
    server = load_server()
    monkeypatch.setenv("MARKET_DIR", "/tmp/whatever-market")

    assert server._market_candidates()[0] == "/tmp/whatever-market"


def test_daily_review_error_carries_diagnostics(monkeypatch):
    """线上报错必须自带"在哪、找过哪些路径"，否则只能靠猜。"""
    server = load_server()
    monkeypatch.setattr(server, "MARKET_AVAILABLE", False)
    monkeypatch.setattr(server, "MARKET_IMPORT_ERROR", "No module named 'daily_review'")

    event = list(server.run_daily_review("2026-09-18", False))[0]
    payload = json.loads(event.removeprefix("data: ").strip())

    assert payload["type"] == "error"
    assert "No module named 'daily_review'" in payload["message"]
    assert "查过的 market 目录" in payload["message"]
    assert "入口" in payload["message"]
