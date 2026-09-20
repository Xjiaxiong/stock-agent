/**
 * 分享卡片：把复盘结论画成一张图片，方便直接转发。
 *
 * 这里画出来的 canvas 就是导出的 PNG（所见即所得），
 * 版式逻辑全在 lib/shareCard.ts，换版式只改那一个文件。
 */
"use client";

import { useEffect, useRef, useState } from "react";

import type { ShareCardData } from "@/lib/api";
import { cardFileName, cardToBlob, drawShareCard } from "@/lib/shareCard";

export default function ShareCard({ data }: { data: ShareCardData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawShareCard(canvas, data);
    setSize({ w: canvas.width, h: canvas.height });
    setStatus("");
  }, [data]);

  function flash(message: string) {
    setStatus(message);
    window.setTimeout(() => setStatus(""), 4000);
  }

  async function handleDownload() {
    const canvas = canvasRef.current;
    if (!canvas || busy) return;
    setBusy(true);
    try {
      const blob = await cardToBlob(canvas);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = cardFileName(data.trade_date);
      a.click();
      URL.revokeObjectURL(url);
      flash(`已保存 ${cardFileName(data.trade_date)}`);
    } catch (err) {
      flash(err instanceof Error ? err.message : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyImage() {
    const canvas = canvasRef.current;
    if (!canvas || busy) return;
    setBusy(true);
    try {
      const blob = await cardToBlob(canvas);
      if (!navigator.clipboard || typeof ClipboardItem === "undefined") {
        throw new Error("当前浏览器不支持复制图片，请用「下载图片」");
      }
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      flash("图片已复制，可直接粘贴到聊天窗口");
    } catch (err) {
      flash(err instanceof Error ? err.message : "复制失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyText() {
    const lines = [
      `${data.trade_date} 盘面复盘 · ${data.stage}${data.confidence ? `（置信度${data.confidence}）` : ""}`,
      data.summary,
      "",
      ...data.metrics.map((m) => `${m.label} ${m.value}（${m.sub}）${m.delta ? ` ${m.delta}` : ""}`),
    ];
    if (data.sectors.length) {
      lines.push("", `热点：${data.sectors.map((s) => s.name).join("、")}`);
    }
    for (const leader of data.leaders ?? []) {
      lines.push(
        `核心龙头：${leader.name}（${[leader.board, leader.sector, leader.limit_type].filter(Boolean).join(" · ")}）${leader.seal_time ? ` ${leader.seal_time} 首封` : ""}${leader.seal_money ? ` · 封单 ${leader.seal_money}` : ""}`,
      );
      if (leader.features?.length) lines.push(`  特征词：${leader.features.join(" · ")}`);
      if (leader.why) lines.push(`  ${leader.why}`);
      if (leader.peers) lines.push(`  链内 ${leader.peers}`);
      if (leader.alt_leader) {
        lines.push(`  ${leader.alt_limit_type} 龙头：${leader.alt_leader}`);
      }
    }
    if (data.tactics.position || data.tactics.approach) {
      lines.push(`明日应对：${[data.tactics.position, data.tactics.approach].filter(Boolean).join(" · ")}`);
    }
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      flash("文字版结论已复制");
    } catch {
      flash("复制失败，请手动选择文本");
    }
  }

  const buttonClass =
    "rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition hover:border-zinc-400 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">分享卡片</h2>
          <p className="text-sm text-zinc-500">
            一张图包含核心结论、关键数字、热点与明日应对，可直接发给别人
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={handleDownload} disabled={busy} className={buttonClass}>
            {busy ? "处理中…" : "下载图片"}
          </button>
          <button type="button" onClick={handleCopyImage} disabled={busy} className={buttonClass}>
            复制图片
          </button>
          <button type="button" onClick={handleCopyText} className={buttonClass}>
            复制文字
          </button>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        className="w-full max-w-2xl self-center rounded-xl border border-zinc-200 shadow-sm"
        style={{ height: "auto" }}
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-zinc-400">
          {size.w > 0 && `图片尺寸 ${size.w}×${size.h} 像素（2 倍图，长按可放大查看）`}
        </p>
        {status && <p className="text-sm text-emerald-600">{status}</p>}
      </div>
    </section>
  );
}
