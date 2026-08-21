"""批量运行 Day 2 的 10 个测试用例，方便填写 test-cases.md。"""

import os
import sys

from agent import run_agent

QUESTIONS = [
    "贵州茅台现在多少钱？",
    "分析一下宁德时代最近发生了什么？",
    "帮我计算 2 + 8 等于多少？",
    "最近英伟达有什么新闻？",
    "告诉我贵州茅台属于什么行业。",
    "比亚迪今天的股价是多少？涨了还是跌了？",
    "帮我搜索一下 AI 芯片行业最近动态",
    "招商银行的公司基本情况？",
    "中际旭创最近有什么新闻？",
    "计算 (3 + 5) * 2 的结果",
]


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("请先设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n===== [{i}] {question} =====")
        print(run_agent(question, api_key))


if __name__ == "__main__":
    main()
