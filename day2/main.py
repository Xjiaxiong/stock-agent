"""Day 2 命令行入口。用法与 Day 1 相同。"""

import os
import sys

from agent import run_agent


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 API Key，请先设置环境变量：")
        print("  export DEEPSEEK_API_KEY='sk-xxx'")
        sys.exit(1)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"你: {question}")
        print(run_agent(question, api_key))
        return

    print("Day 2 Agent（原生 Function Calling）已启动。输入 q 退出。")
    while True:
        question = input("你: ").strip()
        if question.lower() in ("q", "quit", "exit"):
            break
        if not question:
            continue
        print(run_agent(question, api_key))


if __name__ == "__main__":
    main()
