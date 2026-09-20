"""部署入口与只读环境的契约测试。

入口文件是部署的命门：路径解析或导出名写错，线上就是 500，而本地起 uvicorn 完全正常。
只读文件系统同理——Vercel 的函数只有 /tmp 可写，落盘必须降级而不是炸掉请求。
"""

import importlib.util
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
    routes = {route.path for route in entry.app.routes if hasattr(route, "path")}

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
    import json

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    fn = config["functions"]["api/index.py"]

    assert "market/**" in fn["includeFiles"]
    assert fn["maxDuration"] <= 60  # Hobby 上限就是 60s


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
