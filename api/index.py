"""Vercel 后端入口：补齐包边界后导出 FastAPI 应用。

为什么需要这一层：
- Vercel 的 Python 函数只认 `api/` 目录下的文件，并且要求模块级存在 `app` 变量；
- 本项目的服务代码在 `backend/`、每日复盘链路在 `market/`，两边都靠 sys.path 互相 import，
  所以入口的职责就是把这些目录挂上搜索路径，再原样导出 `server.app`。
- `vercel.json` 用 `includeFiles` 把 `market/**` 一起打进函数；漏掉它复盘接口会退化成
  "每日复盘模块不可用"（server.py 里有这条兜底）。

本地起服务不用这个文件，继续用：
    .venv/bin/python -m uvicorn backend.server:app --port 8000
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 注意顺序：market 放前面，保证 backend/ 与 market/ 里同名模块（如果有）按预期解析
for rel in ("market", "backend"):
    path = os.path.join(ROOT, rel)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

from server import app  # noqa: E402  （Vercel 靠模块级 app 变量识别 ASGI 应用）

__all__ = ["app"]
