/**
 * 与后端 API 通信的工具函数。
 *
 * 后端是 FastAPI（Python），跑在 http://localhost:8000，
 * 接口用 SSE（Server-Sent Events）流式返回：
 *   每次节点完成 -> 一条 progress 事件
 *   报告生成完  -> 一条 report 事件
 *   出错了      -> 一条 error 事件
 *
 * 注意：这里用 fetch + 手动解析 SSE，而不是 EventSource，
 * 因为 EventSource 只支持 GET，而我们的接口是 POST。
 */

/** 后端可能推送的事件类型（和后端 server.py 保持一致） */
export type AnalysisEvent =
  | { type: "progress"; node: string; label: string }
  | { type: "report"; report: string }
  | { type: "error"; message: string };

/** Agent 执行步骤的定义（顺序 = 展示顺序，需和后端节点顺序一致） */
export const STEPS: { node: string; label: string }[] = [
  { node: "company", label: "获取公司概况" },
  { node: "stock", label: "获取股票行情" },
  { node: "news", label: "获取近期新闻" },
  { node: "financial", label: "获取财务数据" },
  { node: "analysis", label: "基本面分析" },
  { node: "risk", label: "风险分析" },
  { node: "report", label: "生成研究报告" },
];

/**
 * 后端地址：
 * - 本地开发默认 http://localhost:8000
 * - 部署到 Vercel 时配 NEXT_PUBLIC_API_URL=https://你的后端域名
 *   （后端 CORS 也要把前端域名加进 CORS_ORIGINS）
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * 发起研究请求并流式接收事件。
 *
 * @param company 公司名，例如 "贵州茅台"
 * @param onEvent 每收到一个事件就回调一次（用于更新 UI 状态）
 * @param signal  AbortController 的信号，用于取消请求
 */
export async function streamAnalysis(
  company: string,
  onEvent: (event: AnalysisEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`请求失败：HTTP ${res.status}`);
  }

  // 逐块读取响应流（SSE 本质是一行行 text/event-stream）
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 消息之间用空行分隔；把完整的消息切出来解析
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? ""; // 最后一段可能不完整，留到下一轮

    for (const msg of messages) {
      const dataLine = msg
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      try {
        onEvent(JSON.parse(dataLine.slice(5).trim()));
      } catch {
        // 单条消息解析失败不影响整体流程，忽略即可
      }
    }
  }
}
