/**
 * /daily 页面 —— 每日盘面复盘。
 *
 * 与 /analysis（单股研究）的区别：
 *   - 输入是"交易日"，不是公司名（留空 = 今天）
 *   - 后端先算全市场客观指标，再让 LLM 做判断
 *   - 输出《每日复盘与明日计划》：市场阶段 / 热点板块 / 风格 / 机会点 / 操作手法
 *
 * 进度事件语义：progress = 该阶段**开始**（采集数据很慢，先告知正在做什么），
 * 所以收到 progress(node) 时，node 之前的步骤算完成，node 自己算进行中。
 */
"use client";

import { useEffect, useRef, useState } from "react";

import AgentProgress from "@/components/AgentProgress";
import ReportView from "@/components/ReportView";
import ShareCard from "@/components/ShareCard";
import {
  DAILY_STEPS,
  fetchLatestTradeDate,
  streamDailyReview,
  type DailyReviewEvent,
  type ShareCardData,
} from "@/lib/api";

type StepStatus = "done" | "running" | "pending";

/** 今天的日期字符串 YYYY-MM-DD（按本地时区） */
function todayString(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export default function DailyPage() {
  const [date, setDate] = useState(todayString());
  const [fresh, setFresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState("");
  /** 结构化摘要（画分享卡片用） */
  const [card, setCard] = useState<ShareCardData | null>(null);
  const [error, setError] = useState("");
  /** 本次复盘实际使用的数据日期（可能与输入框不同：今天数据没生成时会落到最近交易日） */
  const [dataDate, setDataDate] = useState("");
  /** 日期被自动调整时的说明文案 */
  const [dateNote, setDateNote] = useState("");
  const [startedNodes, setStartedNodes] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  // 进入页面就问后端"现在能复盘哪一天"：9/15 早上 9 点前会拿到 9/14，
  // 而不是把日期框默认填成还没数据的今天。
  useEffect(() => {
    const controller = new AbortController();
    fetchLatestTradeDate(controller.signal)
      .then((info) => {
        if (!info.trade_date) return;
        setDate(info.trade_date);
        setDataDate(info.trade_date);
        setDateNote(info.note);
      })
      .catch(() => {
        // 拿不到就保持默认（今天），点复盘时后端仍会自己解析
      });
    return () => controller.abort();
  }, []);

  function handleEvent(event: DailyReviewEvent) {
    if (event.type === "meta") {
      // 后端在采集开始前就告诉我们实际用了哪一天
      setDataDate(event.trade_date);
      setDateNote(event.note);
    } else if (event.type === "progress") {
      // 记录"已开始过的阶段"；最后一个开始的就是正在跑的
      setStartedNodes((prev) => (prev.includes(event.node) ? prev : [...prev, event.node]));
    } else if (event.type === "report") {
      setReport(event.report);
      setCard(event.card);
      setDataDate(event.trade_date);
      setDateNote(event.note);
      setLoading(false);
    } else if (event.type === "error") {
      setError(event.message);
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    setReport("");
    setCard(null);
    setError("");
    setStartedNodes([]);
    setLoading(true);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamDailyReview(date, handleEvent, controller.signal, fresh);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof Error ? err.message : String(err));
      }
      setLoading(false);
    }
  }

  const lastStarted = startedNodes[startedNodes.length - 1];
  const steps = DAILY_STEPS.map((s) => {
    const started = startedNodes.includes(s.node);
    const status: StepStatus = loading
      ? s.node === lastStarted
        ? "running"
        : started
          ? "done"
          : "pending"
      : started
        ? "done"
        : "pending";
    return { ...s, status };
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900">
          每日盘面复盘
        </h1>
        <p className="mt-2 text-zinc-500">
          基于同花顺真实盘面数据，自动计算情绪与板块指标，再由 LLM 判断市场阶段、
          热点板块与明日应对策略。（仅供个人研究，不构成投资建议）
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
        <input
          type="date"
          value={date}
          onChange={(e) => {
            setDate(e.target.value);
            setDateNote(""); // 手动改了日期，之前的自动调整说明就作废
          }}
          className="rounded-lg border border-zinc-300 px-4 py-2.5 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
        <label className="flex items-center gap-2 text-sm text-zinc-600">
          <input
            type="checkbox"
            checked={fresh}
            onChange={(e) => setFresh(e.target.checked)}
          />
          重新采集快照
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "复盘生成中…" : "生成复盘"}
        </button>
      </form>

      {(dataDate || dateNote) && (
        <p className="text-sm text-zinc-600">
          {dataDate && (
            <>
              本次复盘数据日期：
              <span className="font-medium text-zinc-900">{dataDate}</span>
            </>
          )}
          {dateNote && <span className="text-amber-600">（{dateNote}）</span>}
        </p>
      )}

      <p className="text-xs text-zinc-400">
        提示：采集盘面数据需要调用十余次同花顺接口，通常 20~40 秒；若不勾选「重新采集快照」，
        则会复用当天已保存的快照，速度快很多。
      </p>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          复盘失败：{error}
        </div>
      )}

      {(loading || startedNodes.length > 0) && <AgentProgress steps={steps} />}

      {card && <ShareCard data={card} />}

      {report && <ReportView report={report} />}
    </main>
  );
}
