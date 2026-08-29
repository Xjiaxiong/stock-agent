"""Day 3 Agent：原生 Function Calling + 记忆（短期对话历史 + 长期记忆注入）。

整体流程（每回答用户一句，走一遍这个流程）：
  1. 从 SQLite 加载最近对话历史（短期记忆）和长期记忆
  2. 组装 messages：system（含记忆背景） + 历史 + 用户新问题
  3. 循环调用 LLM：模型要么输出 tool_calls（继续），要么输出最终回答（结束）
  4. 把这一轮 user/assistant 消息写回 SQLite，并抽取长期记忆

给 TS/JS 开发者的对照说明：
- json.dumps(x) = JSON.stringify(x)；json.loads(s) = JSON.parse(s)
- **args 在函数调用里 = 展开运算符：fn(...args) 等价于 fn(...args)（Python 是 ** 解包字典）
- messages.extend(history) = messages.push(...history)
- 本文件没有类型标注之外的"接口"，TOOLS 注册表就是工具清单（类似一个配置数组）
"""

import json
import os
import sys
import time
import urllib.request

# import memory：导入同目录 memory.py（SQLite 操作都在那）
import memory
from tools import TOOLS  # TOOLS = 5 个工具的注册表（name/description/parameters/function）


def _load_dotenv() -> None:
    """从当前目录向上查找 .env（项目根目录共享一份配置）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        env_path = os.path.join(current, ".env")
        if os.path.exists(env_path):
            # with open(...) as f：打开文件，退出 with 自动关闭（类似 try/finally close）
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和 # 开头的注释；"=" not in line 跳过没有等号的行
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    # partition("=") 按第一个 = 切成 (key, "=", value) 三元组，_ 表示丢弃
                    key, _, value = line.partition("=")
                    # strip('"') 去掉值两端的引号；setdefault = 已有环境变量时不覆盖
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return
        parent = os.path.dirname(current)
        if parent == current:  # 已经到文件系统根目录，没有再上一层了
            break
        current = parent


_load_dotenv()

# 模块级常量（相当于 TS 文件顶部的 const），可在环境变量里覆盖默认值
DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MAX_ITERATIONS = 10  # Agent 循环最大轮数，防止模型无限调用工具
MAX_RETRIES = 3      # 网络抖动时自动重试次数
RETRY_BACKOFF = [1, 2]  # 每次重试前等待的秒数（递增退避）


def _build_system_prompt(mem: dict) -> str:
    """系统提示词；如果有长期记忆，注入为"已知背景"。"""
    lines = [
        "你是 Stock Research Agent，一个股票研究助手，可以调用工具获取数据。",
        "",
        "工作方式：",
        "1. 判断用户问题是否需要外部数据；需要时调用对应工具",
        "2. 工具返回错误时，根据错误信息调整（换参数、换公司名），或向用户说明原因",
        "3. 回答必须基于工具返回的真实数据，不要编造数字；给出关键数据和结论",
        "4. 用中文回答",
    ]
    if mem:
        # join + 字典推导式：把 {"关注的股票": "贵州茅台"} 拼成
        # "关注的股票: 贵州茅台"，再 "；".join 合并多条记忆
        background = "；".join(f"{k}: {v}" for k, v in mem.items())
        lines += ["", f"已知背景（跨会话长期记忆）：{background}"]
    return "\n".join(lines)  # 用换行把列表拼成一段文本


def _build_tool_schemas() -> list:
    """把注册表转换成 DeepSeek API 要求的 tools 参数格式。"""
    schemas = []
    for tool in TOOLS:
        # 每个工具从 {"name", "description", "parameters", "function"} 转成
        # {"type": "function", "function": {name, description, parameters}}
        # function 字段是给模型的"说明书"，真正执行时再用 name 去 TOOLS 里找
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
    # 请求体（相当于 fetch 的 body）：messages 是对话，tools 是工具清单
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",  # auto = 让模型自己决定是否调用工具
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    # urllib.request 是 Python 标准库里的 HTTP 客户端（相当于 fetch，但 API 更底层）
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),  # JSON.stringify(payload)，再编码成 bytes
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",  # 相当于 headers: { Authorization: `Bearer ${apiKey}` }
        },
        method="POST",
    )
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                # resp.read() 拿 bytes，decode("utf-8") 转字符串，json.loads 解析成 dict
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            # HTTP 层错误（4xx/5xx）：比如 401 key 错误、400 参数错误，重试没意义，直接抛异常
            raise RuntimeError(
                f"LLM API 错误 {e.code}: {e.read().decode('utf-8', 'ignore')}"
            ) from e
        except (urllib.error.URLError, TimeoutError) as e:
            # 网络层错误（TLS 握手失败、超时）：抖动常见，重试几次
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
            time.sleep(wait)  # 暂停 wait 秒再试
    raise RuntimeError("unreachable")  # 正常不会走到这里（for 循环必然 return 或抛异常）


def _execute_tool(name: str, args: dict) -> str:
    """执行工具，返回 JSON 字符串。任何异常都转成结构化错误，不让循环崩溃。"""
    for tool in TOOLS:
        if tool["name"] == name:
            try:
                # **args = 把字典展开成关键字参数：{"expression": "2 + 8"} 会变成
                # calculate(expression="2 + 8")，等价于 JS 的 fn(...args)（对象展开）
                result = tool["function"](**args)
            except Exception as e:  # 兜底：未知异常也反馈给模型，而不是让程序崩溃
                return json.dumps(
                    {"error": "tool_exception", "message": str(e)},
                    ensure_ascii=False,  # ensure_ascii=False 让中文原样输出，不转成 \uXXXX
                )
            return json.dumps(result, ensure_ascii=False)
    return json.dumps(
        {"error": "unknown_tool", "message": f"未知工具: {name}"},
        ensure_ascii=False,
    )


def _update_memory(conversation_id: str, user_message: str) -> None:
    """从用户消息中抽取事实，写入长期记忆表。

    TODO(用户): 实现你的版本
    提示：
    1. 遍历 tools.py 里 _MOCK_STOCK / _MOCK_COMPANY_INFO 的公司名
    2. 如果用户消息里提到了某个公司，用 memory.set_memory(conversation_id, "关注的股票", 公司名) 记下来
    3. 这样重启后系统提示词会带上"已知背景：关注的股票: 贵州茅台"，模型就能理解"刚才那家公司"
    """

    from tools import _MOCK_STOCK, _MOCK_COMPANY_INFO
    # 合并两份字典的公司名（set 去重）
    companies = set(_MOCK_STOCK) | set(_MOCK_COMPANY_INFO)
    for company in companies:
        # 如果用户这句话里出现了这家公司的名字
        if company in user_message:
            memory.set_memory(conversation_id, "关注的股票", company)
            break  # 只记一家就够了；想记多家可以改逻辑


def run_agent(question: str, api_key: str, conversation_id: str) -> str:
    """带记忆的 Agent 主循环。"""
    # 1. 读取记忆：历史消息（短期）+ memory 表（长期）
    history = memory.load_messages(conversation_id)
    mem = memory.load_memory(conversation_id)

    # 2. 组装发给模型的 messages：
    #    system（角色设定 + 记忆背景） + 历史对话 + 当前问题
    messages = [{"role": "system", "content": _build_system_prompt(mem)}]
    messages.extend(history)  # 相当于 messages.push(...history)
    messages.append({"role": "user", "content": question})

    # 3. Agent 循环（和 Day 2 相同）：模型说调工具就调，说完了就结束
    tools = _build_tool_schemas()
    for _ in range(MAX_ITERATIONS):
        message = _call_llm(messages, api_key, tools)
        tool_calls = message.get("tool_calls")  # dict.get = 取不到返回 None（不抛异常）

        if not tool_calls:
            # 模型没有要求调用工具 -> 这就是最终回答，结束循环
            final = (message.get("content") or "").strip() or "（模型未返回内容）"
            break

        # 协议要求：把模型这条带 tool_calls 的消息原样加回对话（不能省略）
        messages.append(message)
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}  # arguments 解析失败就当作没有参数，让工具自己报错
            print(f"  -> 调用工具: {name} args={args}")
            result = _execute_tool(name, args)
            # 工具结果用 role="tool" + tool_call_id 回传，模型靠 id 知道对应哪次调用
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result}
            )
    else:
        # for 循环正常走完（没 break）才会进 else：说明达到最大轮数
        final = "达到最大迭代次数，任务未能完成。"

    # 4. 持久化这一轮对话（短期记忆来源），下次启动还能恢复
    memory.append_message(conversation_id, "user", question)
    memory.append_message(conversation_id, "assistant", final)
    # 5. 从用户消息里抽取事实写入长期记忆（由用户实现）
    _update_memory(conversation_id, question)
    return final
