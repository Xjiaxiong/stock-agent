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

/** 分享卡片/摘要条需要的结构化数据（后端 build_card 生成，前端只负责排版） */
export type ShareMetric = {
  label: string;
  value: string;
  sub: string;
  delta: string;
};

/** 核心龙头：卡片上"该盯谁"那一条（后端按板块间 + 板块内对比算出来） */
export type ShareLeader = {
  /** 股票名 */
  name: string;
  /** 所属板块/产业链（同花顺涨停原因聚类后的名字） */
  sector: string;
  /** 身位：2板 / 首板 */
  board: string;
  /** 涨停板别：10cm（主板）/ 20cm（创业板、科创板）/ 30cm（北交所）/ 5cm（ST） */
  limit_type: string;
  /** 首封时间 09:32 */
  seal_time: string;
  /** 封单额 1.07 亿 */
  seal_money: string;
  /** 赚钱特征词：这只龙头靠什么涨（涨停原因标签） */
  features: string[];
  /** 为什么是它：身位最高 · 封板最早 · 同链 9 只涨停 */
  why: string;
  /** 同链另一板别的龙头：名称 身位/时间 */
  alt_leader: string;
  /** 另一板别的板别标签：20cm / 10cm */
  alt_limit_type: string;
  /** 链内紧随其后的票：名称 身位/时间 › … */
  peers: string;
  /** 尾盘跟风的票 */
  laggards: string;
};

export type ShareCardData = {
  trade_date: string;
  weekday: string;
  note: string;
  stage: string;
  confidence: string;
  style: string;
  summary: string;
  metrics: ShareMetric[];
  reasons: string[];
  sectors: { name: string; strength: string }[];
  /** 核心龙头（热点板块下面那一块） */
  leaders: ShareLeader[];
  tactics: { position: string; approach: string; do: string[] };
  risk: string;
  breadth_stale: boolean;
  prev_trade_date: string;
  source: string;
  disclaimer: string;
};

/** 每日复盘的事件类型（后端 /api/daily-review） */
export type DailyReviewEvent =
  | { type: "meta"; trade_date: string; note: string }
  | { type: "progress"; node: string; label: string }
  | {
      type: "report";
      report: string;
      trade_date: string;
      note: string;
      card: ShareCardData;
    }
  | { type: "error"; message: string };

/** 当前可复盘的最新交易日（后端 /api/daily-review/latest） */
export type LatestTradeDate = {
  trade_date: string;
  note: string;
  today?: string;
};

/**
 * 每日复盘的阶段定义。
 *
 * 注意：复盘接口的 progress 事件语义是"该阶段**开始**"（不是完成），
 * 因为采集盘面数据本身很慢，需要先告诉用户正在做什么。
 */
export const DAILY_STEPS: { node: string; label: string }[] = [
  { node: "snapshot", label: "采集盘面数据" },
  { node: "indicators", label: "计算情绪与板块指标" },
  { node: "review", label: "生成复盘判断" },
];

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
// 去掉末尾多余的 "/"，防止拼出 https://xxx.vercel.app//api/analysis 这类双斜杠
const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

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
  await readSSE<AnalysisEvent>(res, onEvent);
}


/**
 * 读取 SSE 响应流并逐条回调。
 * 抽出来给研究接口与复盘接口共用，避免重复实现解析逻辑。
 */
async function readSSE<T>(
  res: Response,
  onEvent: (event: T) => void,
): Promise<void> {
  if (!res.ok || !res.body) {
    throw new Error(`请求失败：HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? "";
    for (const msg of messages) {
      const dataLine = msg.split("\n").find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      try {
        onEvent(JSON.parse(dataLine.slice(5).trim()) as T);
      } catch {
        // 单条消息解析失败不影响整体流程
      }
    }
  }
}

/**
 * 查询当前可以复盘的最新交易日。
 *
 * 为什么需要：用户点复盘时通常是"今天"，但今天的盘面数据要到收盘后才有。
 * 这里拿到的是后端解析后的真实交易日（例如 9/15 早上会返回 9/14），
 * 用它预填日期输入框，避免默认填成一个还没有数据的日期。
 */
export async function fetchLatestTradeDate(
  signal?: AbortSignal,
): Promise<LatestTradeDate> {
  const res = await fetch(`${API_BASE}/api/daily-review/latest`, { signal });
  if (!res.ok) throw new Error(`请求失败：HTTP ${res.status}`);
  return (await res.json()) as LatestTradeDate;
}

/**
 * 发起每日复盘请求（POST /api/daily-review）并流式接收进度。
 *
 * @param date  交易日 YYYY-MM-DD；留空表示"最近可用交易日"
 * @param fresh 是否强制重新采集盘面快照
 */
export async function streamDailyReview(
  date: string,
  onEvent: (event: DailyReviewEvent) => void,
  signal?: AbortSignal,
  fresh = false,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/daily-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: date || null, fresh }),
    signal,
  });
  await readSSE<DailyReviewEvent>(res, onEvent);
}
