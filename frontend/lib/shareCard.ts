/**
 * 分享卡片：把一次复盘画成一张可以直接发出去的 PNG。
 *
 * 为什么用 Canvas 手绘而不是 html2canvas 截图：
 *   1. 零依赖；2. 不受页面 CSS 影响（Tailwind 4 的 oklch 颜色会让截图库翻车）；
 *   3. 导出的是"设计好的版式"，而不是网页长什么样。
 *
 * 版式目标："一张图讲清楚核心观点"——市场阶段 → 一句话结论 → 四个关键数字 →
 * 核心依据 → 热点板块 → 核心龙头 → 明日应对 → 风险提示。
 *
 * 排版约定（很重要，改版式时请守住）：
 *   - 所有元素都按"顶边 y + 高度"推进，块与块之间只用 `gap()` 加间距；
 *   - 每个元素都通过 drawText / drawPill / drawRect 登记一个包围盒（CardBox），
 *     所以版式可以被自动检查（见 scripts/card-layout-check 思路：渲染后做碰撞检测）；
 *   - 文字用"基线"定位，包围盒按 ascender/descender 估算，避免视觉上贴边或压字。
 */

import type { ShareCardData } from "./api";

export const CARD_WIDTH = 1080;
const PAD = 80;
const CONTENT_W = CARD_WIDTH - PAD * 2;
const MIN_HEIGHT = 1350; // 4:5，内容少时也是一张完整海报
const MEASURE_HEIGHT = 4200; // 先按这个高度量文字，量完再定真实高度
const DPR = 2; // 导出 2 倍图，放大看也清晰

const FONT_STACK =
  '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif';

const COLOR = {
  bg: "#ffffff",
  title: "#18181b",
  body: "#3f3f46",
  secondary: "#52525b",
  muted: "#9ca3af",
  border: "#e4e4e7",
  tileBg: "#fafafa",
  chipBg: "#f4f4f5",
};

/** 涨停板别标签的配色：10cm 是主线主锚，20cm/30cm 是同题材的弹性方向 */
const LIMIT_STYLE: Record<string, { bg: string; fg: string }> = {
  "10cm": { bg: "#eef2ff", fg: "#4338ca" },
  "20cm": { bg: "#fef3c7", fg: "#b45309" },
  "30cm": { bg: "#ffe4e6", fg: "#be123c" },
  "5cm": { bg: "#f4f4f5", fg: "#52525b" },
};

/** 市场阶段 → 主色（卡片上的"情绪色"） */
const STAGE_COLOR: Record<string, string> = {
  冰点期: "#475569",
  修复期: "#d97706",
  主升期: "#059669",
  分化期: "#7c3aed",
  退潮期: "#dc2626",
};

type Ctx = CanvasRenderingContext2D;

/** 画面上每个元素的包围盒（y 为顶边）。导出的图可以直接对它做重叠自检。 */
export type CardBox = {
  kind: "title" | "text" | "pill" | "tile" | "rule";
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** 文字元素的实际字号（逻辑像素），便于检查"最小字号是否够看" */
  size?: number;
};

function font(size: number, weight = 400): string {
  return `${weight} ${size}px ${FONT_STACK}`;
}

type Op = (ctx: Ctx) => void;

/** 绘制过程中的状态：游标位置 + 待执行绘制指令 + 已登记包围盒 */
type Builder = {
  ctx: Ctx;
  y: number;
  ops: Op[];
  boxes: CardBox[];
};

function gap(b: Builder, px: number) {
  b.y += px;
}

function roundRect(ctx: Ctx, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** 不能从中间劈开的字符：「09:32」「20cm」「1.07」这类数字/字母 token */
const TOKEN_CHAR = /[0-9A-Za-z:.\/%]/;
/** 优先在这些分隔符后面换行，避免把一行切成「…共达电 / 声 13:07」 */
const BREAK_AFTER = new Set(["｜", "|", "·", "›", "、", "，", " ", "\t", "：", "；", ")"]);

/**
 * 按字符宽度折行（中文没有空格，只能逐字量）。
 *
 * 两个约束，否则卡片上会出现「20c / m 龙头」「13:0 / 7」这种断词：
 *   1. 数字/字母 token 整体不拆；
 *   2. 有分隔符时优先在分隔符后断（分隔符在行尾比在行首好看）。
 */
function wrapText(ctx: Ctx, text: string, maxWidth: number, maxLines: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const ch of Array.from(text)) {
    if (ch === "\n") {
      lines.push(line);
      line = "";
      if (lines.length >= maxLines) break;
      continue;
    }
    const next = line + ch;
    if (line && ctx.measureText(next).width > maxWidth) {
      const { keep, carry } = splitLine(ctx, line, ch, maxWidth);
      // 注意：不要把行尾空格 trim 掉，fitText 用"字符总数"判断有没有被截断
      lines.push(keep);
      line = carry;
      if (lines.length >= maxLines) break;
    } else {
      line = next;
    }
  }
  if (lines.length < maxLines && line) lines.push(line);
  return lines;
}

/** 决定这一行从哪儿断开：返回留在本行的 keep 和挪到下一行的 carry */
function splitLine(
  ctx: Ctx,
  line: string,
  ch: string,
  maxWidth: number,
): { keep: string; carry: string } {
  // 优先在分隔符后断开，但只在"断出来的尾巴很短"时——否则会白白浪费半行，
  // 让本来能排下的句子被迫降字号（折行质量要服务于"不缩字号 + 不断词"）。
  for (let i = line.length - 1; i >= 0; i--) {
    if (!BREAK_AFTER.has(line[i])) continue;
    const tail = line.slice(i + 1) + ch;
    if (ctx.measureText(tail).width <= maxWidth * 0.3) {
      return { keep: line.slice(0, i + 1), carry: tail };
    }
    break; // 只看最后一个分隔符，它都不合适就不用再往前找
  }
  // 其次：数字/字母 token 整体挪到下一行（「20cm」「09:32」不能被劈开）
  if (TOKEN_CHAR.test(ch)) {
    let i = line.length;
    while (i > 0 && TOKEN_CHAR.test(line[i - 1])) i--;
    const keep = line.slice(0, i);
    if (keep) return { keep, carry: line.slice(i) + ch };
  }
  return { keep: line, carry: ch };
}

/** 逐级缩小字号，尽量把整段话放进 maxLines 行；实在放不下才截断并补省略号 */
function fitText(
  ctx: Ctx,
  text: string,
  maxWidth: number,
  maxLines: number,
  sizes: number[],
  weight = 400,
): { lines: string[]; size: number } {
  const plain = text.replace(/\n/g, "");
  for (const size of sizes) {
    ctx.font = font(size, weight);
    const lines = wrapText(ctx, text, maxWidth, maxLines);
    if (lines.join("").length >= plain.length) return { lines, size };
  }
  const size = sizes[sizes.length - 1];
  ctx.font = font(size, weight);
  const lines = wrapText(ctx, text, maxWidth, maxLines);
  if (lines.length) {
    let last = lines[lines.length - 1];
    while (last && ctx.measureText(`${last}…`).width > maxWidth) last = last.slice(0, -1);
    lines[lines.length - 1] = `${last}…`;
  }
  return { lines, size };
}

/**
 * 画一行文字，并登记包围盒。
 * @param baseline 文字基线 y（canvas 的默认 textBaseline）
 */
function drawText(
  b: Builder,
  {
    text,
    x,
    baseline,
    size,
    weight = 400,
    color = COLOR.body,
    align = "left" as CanvasTextAlign,
    label = "text",
  }: {
    text: string;
    x: number;
    baseline: number;
    size: number;
    weight?: number;
    color?: string;
    align?: CanvasTextAlign;
    label?: string;
  },
) {
  b.ctx.font = font(size, weight);
  const metrics = b.ctx.measureText(text);
  const w = metrics.width;
  const left = align === "right" ? x - w : align === "center" ? x - w / 2 : x;
  // 用浏览器给的"真实墨迹范围"登记包围盒（拿不到就退回保守估算），
  // 这样自动检查出来的重叠就是肉眼真的会看到的压字。
  const ascent = metrics.actualBoundingBoxAscent || size * 0.86;
  const descent = metrics.actualBoundingBoxDescent || size * 0.16;
  b.boxes.push({
    kind: "text",
    label,
    x: left,
    y: baseline - ascent,
    w,
    h: ascent + descent,
    size,
  });
  b.ops.push((c) => {
    c.fillStyle = color;
    c.font = font(size, weight);
    c.textAlign = align;
    c.fillText(text, x, baseline);
    c.textAlign = "left";
  });
}

/** 画一个圆角标签（阶段 chip / 板块 chip），返回它的宽度 */
function drawPill(
  b: Builder,
  {
    text,
    x,
    top,
    size,
    weight = 600,
    height,
    padX = 28,
    bg,
    color,
    label = "pill",
  }: {
    text: string;
    x: number;
    top: number;
    size: number;
    weight?: number;
    height: number;
    padX?: number;
    bg: string;
    color: string;
    label?: string;
  },
): number {
  b.ctx.font = font(size, weight);
  const textMetrics = b.ctx.measureText(text);
  const w = textMetrics.width + padX * 2;
  b.boxes.push({ kind: "pill", label, x, y: top, w, h: height });
  const ascent = textMetrics.actualBoundingBoxAscent || size * 0.86;
  const descent = textMetrics.actualBoundingBoxDescent || size * 0.16;
  b.boxes.push({
    kind: "text",
    label: `${label}:text`,
    x: x + padX,
    y: top + height / 2 + size * 0.35 - ascent,
    w: w - padX * 2,
    h: ascent + descent,
    size,
  });
  b.ops.push((c) => {
    c.fillStyle = bg;
    roundRect(c, x, top, w, height, Math.min(18, height / 3));
    c.fill();
    c.fillStyle = color;
    c.font = font(size, weight);
    c.fillText(text, x + padX, top + height / 2 + size * 0.35);
  });
  return w;
}

/**
 * 画一个卡片式数字块。
 *
 * 三行文字都做"单行自适应"：格子窄（4 个并排约 215px），而数值可能是 "19.48%"、
 * 说明可能是 "首板 25 · 连板 7"，字号写死就会溢出格子——这正是老版本看起来
 * "排版错乱"的原因之一。
 */
function drawTile(
  b: Builder,
  {
    x,
    top,
    w,
    h,
    label,
    value,
    sub,
  }: { x: number; top: number; w: number; h: number; label: string; value: string; sub: string },
) {
  const innerPad = 24;
  const innerW = w - innerPad * 2;
  b.boxes.push({ kind: "tile", label: `tile:${label}`, x, y: top, w, h });
  b.ops.push((c) => {
    c.fillStyle = COLOR.tileBg;
    roundRect(c, x, top, w, h, 18);
    c.fill();
    c.strokeStyle = COLOR.border;
    c.lineWidth = 2;
    c.stroke();
  });

  const labelFit = fitText(b.ctx, label, innerW, 1, [25, 23, 21]);
  drawText(b, {
    text: labelFit.lines[0] ?? label,
    x: x + innerPad,
    baseline: top + 44,
    size: labelFit.size,
    color: COLOR.muted,
    label: `tile:${label}:label`,
  });

  const valueFit = fitText(b.ctx, value, innerW, 1, [56, 50, 46, 42, 38]);
  drawText(b, {
    text: valueFit.lines[0] ?? value,
    x: x + innerPad,
    baseline: top + 112,
    size: valueFit.size,
    weight: 700,
    color: COLOR.title,
    label: `tile:${label}:value`,
  });

  const subFit = fitText(b.ctx, sub, innerW, 1, [24, 22, 20, 18]);
  drawText(b, {
    text: subFit.lines[0] ?? sub,
    x: x + innerPad,
    baseline: top + 152,
    size: subFit.size,
    color: COLOR.muted,
    label: `tile:${label}:sub`,
  });
}

function drawRule(b: Builder, y: number, label: string) {
  b.boxes.push({ kind: "rule", label, x: PAD, y: y - 1, w: CONTENT_W, h: 2 });
  b.ops.push((c) => {
    c.strokeStyle = COLOR.border;
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(PAD, y);
    c.lineTo(CARD_WIDTH - PAD, y);
    c.stroke();
  });
}

/**
 * 把数据画到 canvas 上（同步），返回所有元素的包围盒（便于自动检查排版）。
 * 画完即可用 cardToBlob() 导出 PNG。
 */
export function drawShareCard(canvas: HTMLCanvasElement, data: ShareCardData): CardBox[] {
  // 先用一个足够高的画布量文字，量完再定真实高度、正式画一遍
  canvas.width = CARD_WIDTH * DPR;
  canvas.height = MEASURE_HEIGHT * DPR;
  const initialCtx = canvas.getContext("2d");
  if (!initialCtx) return [];
  initialCtx.setTransform(DPR, 0, 0, DPR, 0, 0);
  initialCtx.textBaseline = "alphabetic";

  const accent = STAGE_COLOR[data.stage] ?? "#3f3f46";
  const b: Builder = { ctx: initialCtx, y: 0, ops: [], boxes: [] };

  // ---------- 顶部：标题 + 日期 ----------
  const titleBaseline = 128;
  drawText(b, {
    text: "每日盘面复盘",
    x: PAD,
    baseline: titleBaseline,
    size: 52,
    weight: 700,
    color: COLOR.title,
    label: "header:title",
  });
  drawText(b, {
    text: `${data.trade_date} ${data.weekday}`.trim(),
    x: CARD_WIDTH - PAD,
    baseline: titleBaseline,
    size: 30,
    color: COLOR.muted,
    align: "right",
    label: "header:date",
  });
  b.y = titleBaseline + 40;
  drawRule(b, b.y, "header:rule");

  // ---------- 市场阶段 chip + 置信度/风格 ----------
  gap(b, 48);
  const chipTop = b.y;
  const chipH = 76;
  const chipW = drawPill(b, {
    text: data.stage,
    x: PAD,
    top: chipTop,
    size: 38,
    weight: 700,
    height: chipH,
    padX: 34,
    bg: accent,
    color: "#ffffff",
    label: "stage",
  });
  const stageMeta = [
    data.confidence ? `置信度 ${data.confidence}` : "",
    data.style ? `风格 ${data.style}` : "",
  ]
    .filter(Boolean)
    .join("  ·  ");
  if (stageMeta) {
    drawText(b, {
      text: stageMeta,
      x: PAD + chipW + 28,
      baseline: chipTop + chipH / 2 + 11,
      size: 30,
      color: COLOR.secondary,
      label: "stage:meta",
    });
  }
  b.y = chipTop + chipH;

  // ---------- 一句话结论（卡片主角） ----------
  if (data.summary) {
    gap(b, 56);
    const blockTop = b.y;
    const summary = fitText(b.ctx, data.summary, CONTENT_W, 3, [46, 42, 38, 34], 700);
    const lineH = Math.round(summary.size * 1.45);
    summary.lines.forEach((line, idx) => {
      drawText(b, {
        text: line,
        x: PAD,
        baseline: blockTop + Math.round(summary.size * 0.86) + idx * lineH,
        size: summary.size,
        weight: 700,
        color: COLOR.title,
        label: `summary:${idx}`,
      });
    });
    b.y = blockTop + (summary.lines.length - 1) * lineH + Math.round(summary.size * 1.02);
  }

  // ---------- 四个关键数字 ----------
  if (data.metrics.length) {
    gap(b, 52);
    const tileTop = b.y;
    const tileGap = 20;
    const tileW = (CONTENT_W - tileGap * 3) / 4;
    const tileH = 176;
    data.metrics.slice(0, 4).forEach((metric, idx) => {
      drawTile(b, {
        x: PAD + idx * (tileW + tileGap),
        top: tileTop,
        w: tileW,
        h: tileH,
        label: metric.label,
        value: metric.value,
        sub: metric.sub,
      });
    });
    b.y = tileTop + tileH;

    const deltas = data.metrics
      .slice(0, 4)
      .map((m) => m.delta)
      .filter(Boolean);
    if (deltas.length) {
      gap(b, 46);
      // 四个数字共用一句说明，避免"环比…环比…环比…"重复；整行自适应宽度
      const parts = data.metrics
        .slice(0, 4)
        .filter((m) => m.delta)
        .map((m) => `${m.label} ${m.delta}`);
      const line =
        (data.prev_trade_date ? `对比 ${data.prev_trade_date}：` : "") + parts.join(" ｜ ");
      const item = fitText(b.ctx, line, CONTENT_W, 1, [26, 24, 22, 20]);
      drawText(b, {
        text: item.lines[0] ?? line,
        x: PAD,
        baseline: b.y + Math.round(item.size * 0.86),
        size: item.size,
        color: COLOR.secondary,
        label: "metrics:delta",
      });
      b.y += Math.round(item.size * 1.02);
    }
  }

  /** 小标题：色条 + 文字，返回后游标停在"正文该开始的位置" */
  const section = (title: string) => {
    gap(b, 64);
    const baseline = b.y;
    b.boxes.push({ kind: "rule", label: `section:${title}:bar`, x: PAD, y: baseline - 26, w: 8, h: 34 });
    b.ops.push((c) => {
      c.fillStyle = accent;
      roundRect(c, PAD, baseline - 26, 8, 34, 4);
      c.fill();
      c.fillStyle = COLOR.title;
      c.font = font(34, 700);
      c.fillText(title, PAD + 26, baseline);
    });
    b.ctx.font = font(34, 700);
    b.boxes.push({
      kind: "text",
      label: `section:${title}`,
      x: PAD + 26,
      y: baseline - 34 * 0.86,
      w: b.ctx.measureText(title).width,
      h: 34 * 1.02,
      size: 34,
    });
    b.y = baseline + 44;
  };

  // ---------- 核心依据 ----------
  if (data.reasons.length) {
    section("核心依据");
    data.reasons.forEach((reason, idx) => {
      // 核心依据允许 3 行：这些句子是"为什么这么判断"的关键，宁可卡片长一点也别截断
      const item = fitText(b.ctx, reason, CONTENT_W - 44, 3, [31, 28, 25]);
      const lineH = Math.round(item.size * 1.5);
      const itemTop = b.y;
      item.lines.forEach((line, i) => {
        const baseline = itemTop + Math.round(item.size * 0.86) + i * lineH;
        if (i === 0) {
          drawText(b, {
            text: `${idx + 1}.`,
            x: PAD,
            baseline,
            size: item.size,
            color: COLOR.muted,
            label: `reason:${idx}:no`,
          });
        }
        drawText(b, {
          text: line,
          x: PAD + 44,
          baseline,
          size: item.size,
          color: COLOR.body,
          label: `reason:${idx}:${i}`,
        });
      });
      b.y = itemTop + (item.lines.length - 1) * lineH + Math.round(item.size * 1.02) + 18;
    });
  }

  // ---------- 热点板块 ----------
  if (data.sectors.length) {
    section("热点板块");
    const pillH = 60;
    const rowGap = 16;
    let x = PAD;
    let top = b.y;
    data.sectors.forEach((sector) => {
      const text = `${sector.name}${sector.strength ? ` · ${sector.strength}` : ""}`;
      b.ctx.font = font(28, 600);
      const w = b.ctx.measureText(text).width + 52;
      if (x + w > CARD_WIDTH - PAD) {
        x = PAD;
        top += pillH + rowGap;
      }
      drawPill(b, {
        text,
        x,
        top,
        size: 28,
        height: pillH,
        padX: 26,
        bg: COLOR.chipBg,
        color: COLOR.title,
        label: `sector:${sector.name}`,
      });
      x += w + 18;
    });
    b.y = top + pillH;
  }

  // ---------- 核心龙头（该盯谁）----------
  // 放在热点板块下面：先告诉用户"钱在哪个方向"，再告诉用户"方向里盯哪只"。
  // 每只龙头一张浅灰面板：名称 + 身位/板块标签 / 客观数据 + 为什么是它 / 链内梯队。
  const leaders = data.leaders ?? [];
  if (leaders.length) {
    section("核心龙头");
    const padIn = 28;
    const rowH = 48;
    const panelGap = 18;
    leaders.forEach((leader, idx) => {
      const top = b.y;
      const facts = [
        leader.seal_time ? `${leader.seal_time} 首封` : "",
        leader.seal_money ? `封单 ${leader.seal_money}` : "",
        leader.why,
      ]
        .filter(Boolean)
        .join(" · ");
      const factsFit = fitText(b.ctx, facts, CONTENT_W - padIn * 2, 2, [26, 24, 22]);
      const factsLineH = Math.round(factsFit.size * 1.5);
      // 特征词：这只龙头靠什么涨（同花顺涨停原因标签），单开一行，方便直接抄进笔记
      const features = (leader.features ?? []).join(" · ");
      const featureLabel = "特征词";
      const featureSize = 26;
      b.ctx.font = font(featureSize, 600);
      const featureOffset = b.ctx.measureText(featureLabel).width + 14;
      const featureFit = features
        ? fitText(b.ctx, features, CONTENT_W - padIn * 2 - featureOffset, 2, [26, 24, 22], 600)
        : null;
      const featureLineH = featureFit ? Math.round(featureFit.size * 1.5) : 0;
      const chainText = [
        leader.peers ? `链内 ${leader.peers}` : "",
        leader.alt_leader ? `${leader.alt_limit_type} 龙头 ${leader.alt_leader}` : "",
        leader.laggards ? `跟风 ${leader.laggards}` : "",
      ]
        .filter(Boolean)
        .join(" ｜ ");
      const chainFit = chainText
        ? fitText(b.ctx, chainText, CONTENT_W - padIn * 2, 2, [24, 22, 20])
        : null;
      const chainLineH = chainFit ? Math.round(chainFit.size * 1.5) : 0;
      const height =
        padIn +
        rowH +
        (featureFit ? featureFit.lines.length * featureLineH + 8 : 0) +
        factsFit.lines.length * factsLineH +
        (chainFit ? 12 + chainFit.lines.length * chainLineH : 0) +
        padIn;

      b.boxes.push({ kind: "tile", label: `leader:${leader.name}`, x: PAD, y: top, w: CONTENT_W, h: height });
      b.ops.push((c) => {
        c.fillStyle = COLOR.tileBg;
        roundRect(c, PAD, top, CONTENT_W, height, 18);
        c.fill();
      });

      // 第一行：股票名 + 身位 + 板块
      const chipTop = top + padIn;
      const chipH = 46;
      const nameSize = 36;
      drawText(b, {
        text: leader.name,
        x: PAD + padIn,
        baseline: chipTop + chipH / 2 + nameSize * 0.35,
        size: nameSize,
        weight: 700,
        color: COLOR.title,
        label: `leader:${leader.name}:name`,
      });
      b.ctx.font = font(nameSize, 700);
      let x = PAD + padIn + b.ctx.measureText(leader.name).width + 20;
      if (leader.board) {
        x +=
          drawPill(b, {
            text: leader.board,
            x,
            top: chipTop,
            size: 24,
            height: chipH,
            padX: 18,
            bg: accent,
            color: "#ffffff",
            label: `leader:${leader.name}:board`,
          }) + 10;
      }
      if (leader.sector) {
        x +=
          drawPill(b, {
            text: leader.sector,
            x,
            top: chipTop,
            size: 24,
            height: chipH,
            padX: 18,
            bg: COLOR.chipBg,
            color: COLOR.body,
            label: `leader:${leader.name}:sector`,
          }) + 10;
      }
      // 板别：10cm 主线锚 / 20cm 弹性，一眼区分
      const limitStyle = LIMIT_STYLE[leader.limit_type];
      if (leader.limit_type && limitStyle) {
        drawPill(b, {
          text: leader.limit_type,
          x,
          top: chipTop,
          size: 22,
          height: chipH,
          padX: 16,
          bg: limitStyle.bg,
          color: limitStyle.fg,
          label: `leader:${leader.name}:limit`,
        });
      }

      // 第二行：特征词
      let cursor = chipTop + rowH;
      if (featureFit) {
        featureFit.lines.forEach((line, i) => {
          const baseline = cursor + Math.round(featureFit.size * 0.86) + i * featureLineH;
          if (i === 0) {
            drawText(b, {
              text: featureLabel,
              x: PAD + padIn,
              baseline,
              size: featureSize,
              weight: 600,
              color: COLOR.muted,
              label: `leader:${leader.name}:feature-label`,
            });
          }
          drawText(b, {
            text: line,
            x: PAD + padIn + featureOffset,
            baseline,
            size: featureFit.size,
            weight: 600,
            color: COLOR.body,
            label: `leader:${leader.name}:feature:${i}`,
          });
        });
        cursor += featureFit.lines.length * featureLineH + 8;
      }

      // 第三行：客观数据 + 为什么是它
      const factsTop = cursor;
      factsFit.lines.forEach((line, i) => {
        drawText(b, {
          text: line,
          x: PAD + padIn,
          baseline: factsTop + Math.round(factsFit.size * 0.86) + i * factsLineH,
          size: factsFit.size,
          color: COLOR.secondary,
          label: `leader:${leader.name}:facts:${i}`,
        });
      });

      // 第三行：链内梯队（次强 / 跟风）——板块内部对比的结果
      if (chainFit) {
        const chainTop = factsTop + factsFit.lines.length * factsLineH + 12;
        chainFit.lines.forEach((line, i) => {
          drawText(b, {
            text: line,
            x: PAD + padIn,
            baseline: chainTop + Math.round(chainFit.size * 0.86) + i * chainLineH,
            size: chainFit.size,
            color: COLOR.muted,
            label: `leader:${leader.name}:chain:${i}`,
          });
        });
      }

      b.y = top + height + (idx < leaders.length - 1 ? panelGap : 0);
    });
  }

  // ---------- 明日应对 ----------
  if (data.tactics.position || data.tactics.approach || data.tactics.do.length) {
    section("明日应对");
    const head = [data.tactics.position, data.tactics.approach].filter(Boolean).join("  ·  ");
    if (head) {
      const item = fitText(b.ctx, head, CONTENT_W, 2, [30, 27], 600);
      const lineH = Math.round(item.size * 1.5);
      const itemTop = b.y;
      item.lines.forEach((line, i) => {
        drawText(b, {
          text: line,
          x: PAD,
          baseline: itemTop + Math.round(item.size * 0.86) + i * lineH,
          size: item.size,
          weight: 600,
          color: COLOR.title,
          label: `tactics:head:${i}`,
        });
      });
      b.y = itemTop + (item.lines.length - 1) * lineH + Math.round(item.size * 1.02) + 16;
    }
    data.tactics.do.forEach((bullet, idx) => {
      const item = fitText(b.ctx, bullet, CONTENT_W - 40, 2, [28, 25]);
      const lineH = Math.round(item.size * 1.5);
      const itemTop = b.y;
      item.lines.forEach((line, i) => {
        const baseline = itemTop + Math.round(item.size * 0.86) + i * lineH;
        if (i === 0) {
          drawText(b, {
            text: "·",
            x: PAD + 8,
            baseline,
            size: item.size,
            color: COLOR.muted,
            label: `tactics:do:${idx}:dot`,
          });
        }
        drawText(b, {
          text: line,
          x: PAD + 40,
          baseline,
          size: item.size,
          color: COLOR.secondary,
          label: `tactics:do:${idx}:${i}`,
        });
      });
      b.y = itemTop + (item.lines.length - 1) * lineH + Math.round(item.size * 1.02) + 16;
    });
  }

  // ---------- 风险提示 + 页脚 ----------
  if (data.risk) {
    const item = fitText(b.ctx, `风险提示：${data.risk}`, CONTENT_W, 2, [26, 23]);
    const lineH = Math.round(item.size * 1.5);
    const itemTop = b.y + 26;
    item.lines.forEach((line, i) => {
      drawText(b, {
        text: line,
        x: PAD,
        baseline: itemTop + Math.round(item.size * 0.86) + i * lineH,
        size: item.size,
        color: COLOR.secondary,
        label: `risk:${i}`,
      });
    });
    b.y = itemTop + (item.lines.length - 1) * lineH + Math.round(item.size * 1.02);
  }

  const footerRuleY = b.y + 52;
  drawRule(b, footerRuleY, "footer:rule");
  drawText(b, {
    text: data.source,
    x: PAD,
    baseline: footerRuleY + 44,
    size: 24,
    color: COLOR.muted,
    label: "footer:source",
  });
  drawText(b, {
    text: data.disclaimer,
    x: CARD_WIDTH - PAD,
    baseline: footerRuleY + 44,
    size: 24,
    color: COLOR.muted,
    align: "right",
    label: "footer:disclaimer",
  });
  const bottom = footerRuleY + 44 + 24;
  const finalHeight = Math.round(Math.max(MIN_HEIGHT, bottom + PAD * 0.7));

  // ---------- 高度定稿后正式画一遍 ----------
  canvas.height = finalHeight * DPR;
  const finalCtx = canvas.getContext("2d");
  if (!finalCtx) return b.boxes;
  finalCtx.setTransform(DPR, 0, 0, DPR, 0, 0);
  finalCtx.textBaseline = "alphabetic";
  finalCtx.fillStyle = COLOR.bg;
  finalCtx.fillRect(0, 0, CARD_WIDTH, finalHeight);
  for (const op of b.ops) op(finalCtx);

  return b.boxes;
}

/** canvas → PNG Blob（导出的是 2 倍图） */
export function cardToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("导出图片失败"));
    }, "image/png");
  });
}

/** 建议的分享文件名：每日复盘_2026-09-15.png */
export function cardFileName(tradeDate: string): string {
  return `每日复盘_${tradeDate || "未知日期"}.png`;
}
