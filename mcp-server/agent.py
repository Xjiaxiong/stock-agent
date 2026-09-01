"""Day 5 MCP Agent：通过 MCP 发现工具，再交给 DeepSeek 原生 Function Calling 使用。

链路：
    Agent
      ↓ 启动 MCP Client，连接 server.py
      ↓ list_tools() 发现工具（运行时！不是写死在代码里）
      ↓ 把工具转成 Function Calling 的 tools 参数
      ↓ DeepSeek 选择工具 → MCP call_tool 执行 → 结果回传
      ↓ 循环直到最终回答

运行：cd mcp-server && ../.venv/bin/python agent.py "贵州茅台现在多少钱？"
"""

import asyncio
import json
import os
import sys
import time
import urllib.request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


def _load_dotenv() -> None:
    """从当前目录向上查找 .env（项目根目录共享一份配置）。"""
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
MAX_ITERATIONS = 10


def _call_llm(messages: list, api_key: str, tools: list) -> dict:
    """调用 DeepSeek（复用 Day 2 的写法）。"""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"LLM API 错误 {e.code}: {e.read().decode('utf-8', 'ignore')}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 LLM API: {e.reason}") from e


def _mcp_tool_to_schema(tool) -> dict:
    """把 MCP 发现的工具转成 DeepSeek Function Calling 需要的 tools 参数。"""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        },
    }


async def run_agent(question: str, api_key: str) -> str:
    server_params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 第 1 步：运行时发现 MCP 工具（不是写死的！）
            discovered = await session.list_tools()
            tools = [_mcp_tool_to_schema(t) for t in discovered.tools]
            print(f"  [MCP] 发现 {len(tools)} 个工具: {[t['function']['name'] for t in tools]}")

            messages = [
                {
                    "role": "system",
                    "content": "你是 Stock Research Agent。需要外部数据时调用工具，"
                    "回答基于工具返回的真实数据，用中文回答。",
                },
                {"role": "user", "content": question},
            ]

            for _ in range(MAX_ITERATIONS):
                message = _call_llm(messages, api_key, tools)
                tool_calls = message.get("tool_calls")
                if not tool_calls:
                    return (message.get("content") or "").strip()

                messages.append(message)
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    print(f"  -> 调用 MCP 工具: {name} args={args}")

                    # 第 2 步：通过 MCP Client 执行工具（跨进程调用 server.py）
                    result = await session.call_tool(name, args)
                    text = "\n".join(
                        getattr(item, "text", "") for item in result.content
                    )
                    messages.append(
                        {"role": "tool", "tool_call_id": tc["id"], "content": text}
                    )

            return "达到最大迭代次数，任务未能完成。"


if __name__ == "__main__":
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 DEEPSEEK_API_KEY（请在项目根目录 .env 中配置）")
        sys.exit(1)
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "查询贵州茅台行情"
    print(f"你: {question}")
    print(asyncio.run(run_agent(question, api_key)))
