"""Day 2 Agent：使用 DeepSeek 原生 Function Calling。

与 Day 1 的区别：
- 工具定义通过 API 的 tools 参数传给模型（JSON Schema 约束）
- 模型原生输出 tool_calls（含 id、name、arguments），格式由 API 保证
- 工具结果通过 role="tool" + tool_call_id 回传给模型
"""

import json
import os
import sys
import time
import urllib.request

from tools import TOOLS


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
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2]


def _build_system_prompt() -> str:
    return """你是 Stock Research Agent，一个股票研究助手，可以调用工具获取数据。

工作方式：
1. 判断用户问题是否需要外部数据；需要时调用对应工具
2. 工具返回错误时，根据错误信息调整（换参数、换公司名），或向用户说明原因
3. 回答必须基于工具返回的真实数据，不要编造数字；给出关键数据和结论
4. 用中文回答
"""


def _build_tool_schemas() -> list:
    """把注册表转换成 API 需要的 tools 参数格式。"""
    schemas = []
    for tool in TOOLS:
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
        )
    return schemas


def _call_llm(messages: list, api_key: str, tools: list) -> dict:
    """调用 DeepSeek，返回完整的 message 对象（可能含 tool_calls）。"""
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
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"LLM API 错误 {e.code}: {e.read().decode('utf-8', 'ignore')}"
            ) from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == MAX_RETRIES - 1:
                reason = getattr(e, "reason", e)
                raise RuntimeError(
                    f"无法连接 LLM API（已重试 {MAX_RETRIES} 次）: {reason}"
                ) from e
            wait = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2
            print(
                f"  [!] 连接 LLM 失败，{wait}s 后重试 ({attempt + 1}/{MAX_RETRIES})",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _execute_tool(name: str, args: dict) -> str:
    """执行工具，返回 JSON 字符串。任何异常都转成结构化错误，不让循环崩溃。"""
    for tool in TOOLS:
        if tool["name"] == name:
            try:
                result = tool["function"](**args)
            except Exception as e:  # 兜底：未知异常也反馈给模型
                return json.dumps(
                    {"error": "tool_exception", "message": str(e)},
                    ensure_ascii=False,
                )
            return json.dumps(result, ensure_ascii=False)
    return json.dumps(
        {"error": "unknown_tool", "message": f"未知工具: {name}"},
        ensure_ascii=False,
    )


def run_agent(question: str, api_key: str) -> str:
    """Agent 主循环：模型原生输出 tool_calls -> 代码执行 -> 结果回传。"""
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": question},
    ]
    tools = _build_tool_schemas()

    for _ in range(MAX_ITERATIONS):
        message = _call_llm(messages, api_key, tools)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return (message.get("content") or "").strip() or "（模型未返回内容）"

        # 保留模型这条带 tool_calls 的消息（原生 Function Calling 协议要求）
        messages.append(message)
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  -> 调用工具: {name} args={args}")
            result = _execute_tool(name, args)
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result}
            )

    return "达到最大迭代次数，任务未能完成。"
