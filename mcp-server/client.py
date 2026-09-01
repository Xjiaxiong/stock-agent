"""Day 5 MCP Client：连接 Server、发现工具、调用工具。

运行：cd mcp-server && ../.venv/bin/python client.py
（不需要 API key，纯离线演示 MCP 协议本身）
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# server.py 的绝对路径（无论从哪个目录运行都能找到）
SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


async def main():
    # StdioServerParameters：告诉客户端"用什么命令启动 server"
    # sys.executable = 当前 Python 解释器（保证用的是 .venv 里的）
    server_params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])

    # stdio_client 启动子进程（server.py），返回一对读写流
    async with stdio_client(server_params) as (read, write):
        # ClientSession 封装了 MCP 协议的握手、请求、响应
        async with ClientSession(read, write) as session:
            await session.initialize()  # 完成 MCP 握手

            # ---------- 第 1 步：发现工具 ----------
            tools = await session.list_tools()
            print(f"发现 {len(tools.tools)} 个工具：")
            for t in tools.tools:
                props = list(t.inputSchema.get("properties", {}).keys())
                print(f"  - {t.name}  参数: {props}")

            # ---------- 第 2 步：调用工具 ----------
            for name, args in [
                ("get_stock_price", {"company": "贵州茅台"}),
                ("get_stock_news", {"company": "宁德时代"}),
                ("get_company_info", {"company": "比亚迪"}),
            ]:
                print(f"\n调用 {name} {args}")
                result = await session.call_tool(name, args)
                for item in result.content:
                    print("  ", item.text)


if __name__ == "__main__":
    asyncio.run(main())
