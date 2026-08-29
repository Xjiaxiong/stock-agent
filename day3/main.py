"""Day 3 命令行入口：支持新建/继续会话，重启后仍记得上下文。

给 TS/JS 开发者的对照说明：
- input("...") 相当于 Node 里的 readline 提问（阻塞等待用户输入一行）
- print(...) 相当于 console.log(...)
- if __name__ == "__main__": 相当于"只有直接运行本文件时才执行 main()"，
  被别的文件 import 时不会误执行（类似 require.main === module 的判断）
"""

import os
import sys

# import memory = 导入同目录下的 memory.py（相当于 import * as memory from './memory'）
# from agent import run_agent = 只导入 agent.py 里的 run_agent 函数（相当于 import { runAgent } from './agent'）
import memory
from agent import run_agent


def main():
    # os.environ 相当于 process.env；.get("KEY", "") = 取不到就用空字符串
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 API Key，请先设置环境变量：")
        print("  export DEEPSEEK_API_KEY='sk-xxx'")
        sys.exit(1)  # 退出程序，退出码 1（类似 process.exit(1)）

    # 确保数据库和表存在（幂等，重复调用没副作用）
    memory.init_db()

    # 列出这个用户之前的所有会话，让用户选择继续哪一段
    conversations = memory.list_conversations()
    conversation_id = None
    if conversations:
        print("已有的会话：")
        # enumerate(conversations, 1)：返回 (序号, 元素)，序号从 1 开始
        #   for i, c in ... 相当于 JS 的 for (const [i, c] of conversations.entries())
        for i, c in enumerate(conversations, 1):
            # f"..." 是 f-string，相当于 TS 模板字符串 `${c['id']}`
            print(f"  [{i}] {c['id']}  最近更新 {c['updated_at']}")
        choice = input("选择要继续的会话编号，或直接回车新建: ").strip()
        # isdigit() 判断是否全是数字；int() 转成整数
        # 注意列表下标从 0 开始，所以用户选的 1 号对应 conversations[0]
        if choice.isdigit() and 1 <= int(choice) <= len(conversations):
            conversation_id = conversations[int(choice) - 1]["id"]

    if not conversation_id:
        conversation_id = memory.create_conversation()
        print(f"新建会话: {conversation_id}")

    # 恢复最近对话（短期记忆）：把上次的对话打印出来，让用户看到"我上次聊到哪了"
    for h in memory.load_messages(conversation_id, limit=6):
        # [h['content'][:120]] 中的 [:120] 是切片，取前 120 个字符（相当于 content.slice(0, 120)）
        print(f"\n[{h['role']}] {h['content'][:120]}")

    print("\nDay 3 Agent（带记忆）已启动。输入 q 退出。")
    while True:
        question = input("你: ").strip()
        # lower() 转小写统一判断；in ("q", "quit", "exit") 判断是否在元组里
        if question.lower() in ("q", "quit", "exit"):
            break
        if not question:
            continue
        print(run_agent(question, api_key, conversation_id))


if __name__ == "__main__":
    main()
