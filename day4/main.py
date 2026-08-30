"""Day 4 命令行入口：输入公司名，跑完整 ResearchGraph，输出研究报告。

运行方式：cd day4 && ../.venv/bin/python main.py
"""

from graph import build_graph


def main():
    company = input("输入要研究的公司（例如 贵州茅台）: ").strip()
    if not company:
        print("公司名不能为空")
        return

    graph = build_graph()
    # thread_id 是 Checkpoint 的"存档槽位"，同一个 id 的多次运行会共用存档
    result = graph.invoke(
        {"symbol": company},
        config={"configurable": {"thread_id": "day4-demo"}},
    )

    if result.get("error"):
        print("\n[执行失败] ", result["error"])
        return

    print("\n" + result.get("report", ""))


if __name__ == "__main__":
    main()
