/**
 * /analysis 页面 —— Stock Research Agent 的前端入口。
 *
 * 交互流程：
 *   1. 输入公司名，点「开始研究」
 *   2. 向后端发 POST，SSE 流式接收进度
 *   3. 进度列表逐个打勾（✓/●/○）
 *   4. 收到 report 事件 -> 渲染 Markdown 报告
 *   5. 收到 error 事件 -> 显示红色错误提示
 *
 * 这是你重点"读 + 改"的文件。想改交互或布局，都从这里下手。
 */
"use client";

import { useRef, useState } from "react";

import AgentProgress from "@/components/AgentProgress";
import ReportView from "@/components/ReportView";
import { STEPS, streamAnalysis, type AnalysisEvent } from "@/lib/api";

type StepStatus = "done" | "running" | "pending";

export default function AnalysisPage() {
  const [company, setCompany] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState("");
  const [error, setError] = useState("");
  const [doneNodes, setDoneNodes] = useState<string[]>([]);
  const [runningNode, setRunningNode] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /** 根据后端事件更新进度状态 */
  function handleEvent(event: AnalysisEvent) {
    if (event.type === "progress") {
      // 该节点完成了：加入 done 集合，下一个节点进入 running
      setDoneNodes((prev) => (prev.includes(event.node) ? prev : [...prev, event.node]));
      const idx = STEPS.findIndex((s) => s.node === event.node);
      setRunningNode(idx >= 0 && idx < STEPS.length - 1 ? STEPS[idx + 1].node : null);
    } else if (event.type === "report") {
      setReport(event.report);
      setRunningNode(null);
      setLoading(false);
    } else if (event.type === "error") {
      setError(event.message);
      setRunningNode(null);
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = company.trim();
    if (!name || loading) return;

    // 重置上一轮的状态
    setReport("");
    setError("");
    setDoneNodes([]);
    setRunningNode(STEPS[0]?.node ?? null);
    setLoading(true);

    // 支持中途取消（点别的操作时中止上一次请求）
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAnalysis(name, handleEvent, controller.signal);
    } catch (err) {
      // AbortError 是用户主动取消，不提示
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof Error ? err.message : String(err));
      }
      setRunningNode(null);
      setLoading(false);
    }
  }

  /** 组装给进度组件的步骤状态列表 */
  const steps = STEPS.map((s) => ({
    ...s,
    status: (doneNodes.includes(s.node)
      ? "done"
      : runningNode === s.node
        ? "running"
        : "pending") as StepStatus,
  }));

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900">
          股票研究 Agent
        </h1>
        <p className="mt-2 text-zinc-500">
          输入公司名称，Agent 将自动获取行情、新闻、财务数据并生成研究报告。
          （当前为模拟数据演示）
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="例如：贵州茅台"
          className="flex-1 rounded-lg border border-zinc-300 px-4 py-2.5 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
        <button
          type="submit"
          disabled={loading || !company.trim()}
          className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "研究中…" : "开始研究"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          研究失败：{error}
        </div>
      )}

      {(loading || doneNodes.length > 0) && (
        <AgentProgress steps={steps} />
      )}

      {report && <ReportView report={report} />}
    </main>
  );
}
