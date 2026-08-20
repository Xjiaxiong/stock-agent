"""Day 1 最小 Agent 循环。

原理：
    用户问题 -> LLM 决定是否调用工具 -> 代码执行工具 -> 结果反馈给 LLM
    -> LLM 再决定：继续调用工具，还是输出最终回答

使用 DeepSeek（OpenAI 兼容接口），只依赖 Python 标准库，无需 pip 安装。
"""

import json
import os
import re
import sys
import time
import urllib.request

from tools import TOOLS

DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MAX_ITERATIONS = 10  # 防止模型无限循环调用工具
MAX_RETRIES = 3      # 网络抖动时自动重试
RETRY_BACKOFF = [1, 2]  # 每次重试前等待的秒数


def _build_system_prompt() -> str:
    """根据工具注册表自动生成给 LLM 的系统提示词。"""
    lines = [
        "你是一个 Agent，可以调用工具获取外部信息。",
        "",
        "可用工具：",
    ]
    for tool in TOOLS:
        lines.append(f"- {tool['name']}: {tool['description']}")
        lines.append(f"  参数: {json.dumps(tool['parameters'], ensure_ascii=False)}")
    lines += [
        "",
        "规则：",
        "1. 如果需要外部信息，只输出一行 JSON，格式：",
        '   {"tool": "工具名", "args": {"参数名": "参数值"}}',
        "   除此之外不要输出任何其他内容。",
        "2. 如果不需要外部信息，直接输出最终回答。",
        "3. 工具执行失败时，根据反馈重试或向用户说明原因。",
    ]
    return "\n".join(lines)


def _call_llm(messages: list, api_key: str) -> str:
    """调用 DeepSeek Chat Completions 接口，返回模型输出的文本。

    网络连接类错误（TLS 握手失败、超时等）会重试；HTTP 层错误直接抛出。
    """
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
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
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            # 例如 401 鉴权失败、400 参数错误：重试没有意义，直接报错
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


def _parse_tool_call(content: str) -> dict | None:
    """从模型输出中提取工具调用意图，解析失败返回 None。"""
    content = content.strip()
    # 去掉 markdown 代码围栏，例如 ```json ... ```
    content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # 容错：模型偶尔在 JSON 前后夹带文字，提取第一个 {...}（支持嵌套）
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict) and isinstance(data.get("tool"), str):
        return data
    return None


def _execute_tool(name: str, args: dict) -> str:
    """根据工具名找到真实函数并执行，任何错误都以文本形式反馈给模型。"""
    for tool in TOOLS:
        if tool["name"] == name:
            try:
                result = tool["function"](**args)
            except TypeError as e:
                return f"参数错误: {e}"
            except ValueError as e:
                return f"执行失败: {e}"
            return json.dumps(result, ensure_ascii=False)
    return f"未知工具: {name}"


def run_agent(question: str, api_key: str) -> str:
    """Agent 主循环：LLM 决策 -> 执行工具 -> 反馈结果，直到得到最终回答。"""
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_ITERATIONS):
        content = _call_llm(messages, api_key)
        tool_call = _parse_tool_call(content)

        if tool_call is None:
            return content  # 模型没有调用工具，直接作为最终回答

        name = tool_call["tool"]
        args = tool_call.get("args", {})
        print(f"  -> Agent 调用工具: {name} args={args}")

        result = _execute_tool(name, args)
        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": f"工具 {name} 返回结果: {result}\n请根据结果继续，完成任务后输出最终回答。",
            }
        )

    return "达到最大迭代次数，任务未能完成。"
