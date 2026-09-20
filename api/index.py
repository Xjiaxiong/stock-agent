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

from server import app as server_app  # noqa: E402


class StripInternalPrefix:
    """剥掉 Vercel rewrite 带进来的内部路径前缀，让 FastAPI 看到用户请求的真实路径。

    Vercel 把 `/(.*)` 重写到函数时，函数拿到的路径不一定是原始路径（实测遇到的就是
    全部路由 404，因为函数收到的是 rewrite 目标 `/api/index`）。这里把三种形态都兼容：

        /health            有的部署直接透传原始路径 → 原样放行
        /api/index/health  rewrite destination 带 $1 捕获 → 剥成 /health
        /api/index         没有捕获时只能落到 /（会命中 server.py 里的 404 兜底并说明原因）
    """

    PREFIX = "/api/index"

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path") or "/"
            if path == self.PREFIX or path.startswith(f"{self.PREFIX}/"):
                new_path = path[len(self.PREFIX) :] or "/"
                scope = dict(scope, path=new_path)
                if isinstance(scope.get("raw_path"), (bytes, bytearray)):
                    scope["raw_path"] = new_path.encode()
        await self.asgi_app(scope, receive, send)


app = StripInternalPrefix(server_app)

__all__ = ["app"]
