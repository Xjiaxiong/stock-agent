"""每日复盘报告（LLM 判断层）。

分工：indicators.py 负责算出客观指标，本模块只让 LLM 对指标做定性推理，
产出《每日复盘与明日计划》。LLM 不参与任何数字计算，避免幻觉。

用法（项目根目录）：
    .venv/bin/python market/daily_review.py                 # 用今天
    .venv/bin/python market/daily_review.py --date 2026-09-11
    .venv/bin/python market/daily_review.py --fresh         # 先重跑快照再复盘
    .venv/bin/python market/daily_review.py --show          # 只打印不写盘

产物：
    market/reports/{日期}.md     人类可读的复盘报告
    market/reports/{日期}.json   结构化结果（阶段/机会/手法）
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import daily_snapshot as ds  # noqa: E402
import llm_client  # noqa: E402
import verify  # noqa: E402

# 复盘存档目录。Vercel 的函数只有 /tmp 可写，所以线上用 DAILY_REPORT_DIR 指过去；
# 不配也不会崩——落盘失败会降级成警告（见 _try_save_report）。
REPORT_DIR = Path(os.environ.get("DAILY_REPORT_DIR", _HERE / "reports"))

DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def resolve_date(day: str | None = None) -> tuple[str, str]:
    """把"用户请求的日期"解析成"真正可复盘的交易日"，返回 (交易日, 说明)。

    单独包一层是为了让后端不必依赖 daily_snapshot 的内部结构（避免越层调用）。
    """
    return ds.hithink.resolve_trade_date(day)


def _load_snapshot(trade_date: str, fresh: bool) -> dict:
    """读取当日快照；不存在或 --fresh 时重新采集。"""
    path = ds.SNAPSHOT_DIR / f"{trade_date}.json"
    if path.exists() and not fresh:
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
        # 老快照可能是在"目标日数据还没生成"时写下的（那时上游会静默回退到上一交易日，
        # 快照其实是昨天甚至更早的盘面）。用写入时记录的上游最新可用交易日识别并拒绝复用。
        ready = (snapshot.get("data_source") or {}).get("latest_ready_trade_date")
        if ready and ready < trade_date:
            raise ds.hithink.DataNotReady(
                f"已保存的 {trade_date} 快照不可信：它是在上游最新交易日只有 {ready} 时生成的，"
                f"内容实际是 {ready} 的盘面。请删除 market/snapshots/{trade_date}.json 后重跑，"
                f"或等 {trade_date} 的数据生成后再来。"
            )
        return snapshot
    prev_snapshots = ds.find_prev_snapshots(trade_date, limit=10)
    raw = ds.collect(trade_date, sample_step=4)
    snapshot = ds.build_snapshot(trade_date, raw, prev_snapshots[0] if prev_snapshots else None, prev_snapshots)
    # 走统一的落盘函数：--fresh 也会同步写出简报与 latest.json；
    # 落盘失败（如 Vercel 只读文件系统）不阻断复盘
    _try_save_snapshot(snapshot)
    return snapshot


def build_brief(snapshot: dict) -> dict:
    """把快照压缩成喂给 LLM 的数据（不含全市场明细，控制体积）。"""
    i = snapshot["indicators"]
    limit_up = (snapshot.get("raw") or {}).get("limit_up") or []
    # 涨停梯队明细：按连板数降序，给 LLM 识别龙头用
    ladder_stocks = sorted(
        (
            {
                "name": x.get("name"),
                "board": int(x.get("continue_day_cnt") or 1),
                "reason": x.get("limit_up_reason"),
                "limit_up_time": x.get("limit_up_time"),
                "seal_money_yi": round(float(x.get("seal_money") or 0) / 1e8, 2),
            }
            for x in limit_up
        ),
        key=lambda x: -x["board"],
    )[:25]

    breadth = dict(i["breadth"])
    return {
        "交易日": snapshot["trade_date"],
        "情绪周期": i["emotion"],
        "市场活跃度": breadth,
        "资金风格(客观)": i["style"],
        "风格初判(规则)": i["style_verdict"],
        "热点题材(涨停原因聚类)": i["hot_sectors"],
        "板块强度(指数×涨停)": i.get("concept_strength"),
        "连板天梯近5日": i["ladder_trend"],
        "环比上一交易日": i.get("prev_day_comparison"),
        "赚钱效应": i.get("yesterday_effect"),
        "涨停梯队明细": ladder_stocks,
    }


SYSTEM_PROMPT = """你是一名资深的 A 股短线交易复盘分析师，擅长用情绪周期和板块轮动判断市场阶段。

严格要求：
1. 只能基于用户提供的客观指标推理，禁止编造未给出的数字、事件、新闻或个股消息。
2. 如果某项数据缺失或标记为 stale（历史不可回填），必须明确说明"该项数据不可用"，不得臆测。
3. 不做个股买卖推荐；只输出"观察方向、判断依据、应对策略、触发/失效条件"。
4. 语言精炼、结论明确，避免模棱两可。
5. 只输出 JSON，不要任何多余文字或代码围栏。"""


USER_TEMPLATE = """下面是今日 A 股盘面的**客观统计数据**（由程序计算，未做主观加工）。

请据此输出一份每日复盘判断，JSON 结构如下：
{{
  "market_phase": {{
    "stage": "冰点期/修复期/主升期/分化期/退潮期 之一",
    "confidence": "高/中/低",
    "reasons": ["依据1", "依据2", "依据3"]
  }},
  "emotion_summary": "一段话总结今日情绪与赚钱效应",
  "hot_sectors": [
    {{"name": "板块名", "strength": "强/中/弱", "sustainability": "持续性判断(1-2句)", "logic": "驱动逻辑"}}
  ],
  "style": {{"verdict": "连板题材/趋势核心/均衡/结构性", "explanation": "判断依据"}},
  "opportunities": [
    {{"direction": "机会方向", "logic": "为什么是机会", "entry_signal": "触发条件", "invalidation": "失效条件", "risk": "主要风险"}}
  ],
  "tactics": {{
    "position": "建议仓位（如 3-5 成）",
    "approach": "主要操作手法（如低吸/打板/接力/观望）",
    "do": ["该做的1", "该做的2"],
    "avoid": ["该避免的1", "该避免的2"]
  }},
  "risks": ["风险1", "风险2", "风险3"],
  "summary": "一句话结论：明天该怎么应对"
}}

硬性要求：
- market_phase.stage 必须是五个阶段之一；判断要有数据支撑（封板率、涨停家数、赚钱效应、最高板等）。
- hot_sectors 最多 5 个，必须来源于数据里给出的题材/板块，不要自创。
- opportunities 最多 3 个，只描述方向与策略，不给具体买卖点。
- 若"市场活跃度.is_stale" 为 true，请在 emotion_summary 里说明涨跌分布数据不属于该交易日。

数据：
{data}"""


def _call_llm(messages: list, max_tokens: int = 3000) -> str:
    """调用 LLM（走共享客户端：统一重试 + 记用量日志）。"""
    return llm_client.call(messages, source="daily_review", max_tokens=max_tokens, timeout=180)


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def render_report(trade_date: str, result: dict, snapshot: dict, note: str = "") -> str:
    """把 LLM 的结构化结果渲染成 Markdown 报告。"""
    phase = result.get("market_phase") or {}
    style = result.get("style") or {}
    tactics = result.get("tactics") or {}
    i = snapshot["indicators"]

    lines = [f"# 每日复盘与明日计划 · {trade_date}", ""]
    if note:
        # 自动落到其他交易日时必须在报告里留痕，避免以后翻报告时误以为是当天的盘面
        lines += [f"> 数据日期说明：{note}", ""]
    lines += [
        f"**市场阶段：{phase.get('stage', '—')}**（置信度 {phase.get('confidence', '—')}）",
        "",
    ]
    for r in phase.get("reasons", []):
        lines.append(f"- {r}")

    lines += ["", "## 一、情绪与赚钱效应", "", result.get("emotion_summary", "—")]

    lines += ["", "## 二、今日盘面数据（客观统计）", ""]
    emo, br = i["emotion"], i["breadth"]
    lines += [
        f"- 涨停 {emo['limit_up_count']} 家（首板 {emo['first_board_count']}、连板 {emo['consecutive_board_count']}）"
        f" ｜ 跌停 {emo['limit_down_count']} ｜ 炸板 {emo['limit_break_count']}",
        f"- 封板率 {_pct_text(emo.get('seal_rate_pct'))} ｜ 最高 {emo['max_consecutive_board']} 板"
        f" ｜ 连板梯队：" + ("、".join(f"{k}{v}只" for k, v in emo["ladder_distribution"].items()) or "无"),
        f"- 上涨占比 {_pct_text(br.get('up_ratio_pct'))}（数据日期 {br.get('as_of')}）"
        f" ｜ 平均涨跌幅 {_pct_text(br.get('avg_change_pct'))}",
    ]
    if i.get("yesterday_effect"):
        ye = i["yesterday_effect"]
        lines.append(
            f"- 赚钱效应：昨日涨停 {ye['prev_limit_up_count']} 家，今日仍涨停 {ye['still_limit_up_count']} 家"
            f"（延续率 {ye['still_limit_up_ratio_pct']}%）"
        )
    if i.get("prev_day_comparison"):
        pc = i["prev_day_comparison"]
        lines.append(
            f"- 环比 {pc['prev_trade_date']}：涨停 {pc['limit_up_count_delta']:+}"
            f" ｜ 炸板 {pc['limit_break_count_delta']:+}"
            f" ｜ 最高板 {pc['max_board_delta']:+}"
        )

    lines += ["", "## 三、热点板块与持续性", ""]
    strength = (i.get("concept_strength") or {}).get("hot_concepts") or []
    if strength:
        lines += ["| 板块 | 指数涨幅 | 涨停数 | 最高板 | 连续天数 | 龙头 |", "|---|---|---|---|---|---|"]
        for c in strength[:8]:
            leader = (c.get("leader") or {}).get("name") or "—"
            lines.append(
                f"| {c['name']} | {c['change_pct']}% | {c['limit_up_count']} | {c['max_board']} | "
                f"{c['streak_days']} 天 | {leader} |"
            )
    else:
        lines += ["- 今日无板块指数与涨停共振的题材"]

    # 核心龙头：报告里也要能一眼看到"该盯谁"，口径与分享卡片完全一致
    leaders = _chain_leaders(result, snapshot)
    if leaders:
        lines += [
            "",
            "### 核心龙头",
            "",
            "> 排序口径：板块之间按 最高板 × 3 + 链内涨停家数 × 2；板块内部按 身位 > 板别（同身位 10cm 优先于 20cm）> 首封时间 > 封单额。",
            "",
        ]
        for leader in leaders:
            head = " · ".join(
                x
                for x in (leader.get("sector"), leader.get("board"), leader.get("limit_type"))
                if x
            )
            facts = [f"{leader['seal_time']} 首封" if leader.get("seal_time") else ""]
            if leader.get("seal_money"):
                facts.append(f"封单 {leader['seal_money']}")
            if leader.get("why"):
                facts.append(leader["why"])
            lines.append(
                f"- **{leader['name']}**（{head}）：" + " · ".join(x for x in facts if x)
            )
            if leader.get("features"):
                lines.append(f"  - 特征词：{' / '.join(leader['features'])}")
            if leader.get("peers"):
                lines.append(f"  - 链内次强：{leader['peers']}")
            if leader.get("alt_leader"):
                lines.append(
                    f"  - {leader.get('alt_limit_type') or '另一板别'} 龙头：{leader['alt_leader']}"
                )
            if leader.get("laggards"):
                lines.append(f"  - 尾盘跟风：{leader['laggards']}")
        # 后面接的是 LLM 的板块点评，给个小标题，免得看起来像上一条龙头的子项
        lines += ["", "### 板块点评", ""]

    for s in result.get("hot_sectors", []):
        lines.append(
            f"- **{s.get('name')}**（{s.get('strength')}）：{s.get('logic')} — 持续性：{s.get('sustainability')}"
        )

    lines += ["", "## 四、市场风格", ""]
    lines.append(f"**{style.get('verdict', '—')}**：{style.get('explanation', '—')}")
    verdict = i.get("style_verdict") or {}
    lines.append(f"（规则初判：{verdict.get('verdict')}，题材分 {verdict.get('momentum_score')} / 趋势分 {verdict.get('trend_score')}）")

    lines += ["", "## 五、机会点", ""]
    for idx, op in enumerate(result.get("opportunities", []), 1):
        lines += [
            f"**{idx}. {op.get('direction')}**",
            f"- 逻辑：{op.get('logic')}",
            f"- 触发条件：{op.get('entry_signal')}",
            f"- 失效条件：{op.get('invalidation')}",
            f"- 风险：{op.get('risk')}",
            "",
        ]

    lines += ["## 六、操作手法与仓位", ""]
    lines += [
        f"- 建议仓位：{tactics.get('position', '—')}",
        f"- 主要手法：{tactics.get('approach', '—')}",
    ]
    for d in tactics.get("do", []):
        lines.append(f"- ✅ {d}")
    for a in tactics.get("avoid", []):
        lines.append(f"- ⚠️ {a}")

    lines += ["", "## 七、风险提示", ""]
    for r in result.get("risks", []):
        lines.append(f"- {r}")

    lines += ["", "## 八、结论", "", result.get("summary", "—"), ""]
    lines += [
        "---",
        "",
        "> 数据来源：同花顺金融数据 API（真实数据）+ 客观指标计算。",
    ]
    check_note = verify.format_note(result.get("fact_check") or {})
    if check_note:
        lines.append(f"> {check_note}")
    lines.append("> 本报告由 LLM 基于统计数据生成，仅供个人研究，不构成投资建议。")
    return "\n".join(lines)


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _weekday_cn(day: str) -> str:
    try:
        return WEEKDAYS[datetime.strptime(day, "%Y-%m-%d").weekday()]
    except ValueError:
        return ""


def _delta_text(value, unit: str = "") -> str:
    """环比数值（'-23 家' / '+7.57 pct'）；没有对比基准时返回空串。

    不带"环比"前缀：四个数字共用一句"对比 09-14"的说明，避免重复四遍。
    """
    if value is None:
        return ""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:g}{unit}"


def _money_text(value) -> str:
    """封单额：1.07 亿 / 8600 万。卡片上不写小数位过多的原始数字。"""
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if amount <= 0:
        return ""
    if amount >= 1e8:
        return f"{amount / 1e8:.2f} 亿"
    return f"{amount / 1e4:.0f} 万"


def _pct_text(value, unit: str = "%") -> str:
    """百分比文案。None 表示"分母为 0、没有有效样本"（_ratio 的口径），显示 — 而不是 0%。"""
    if value is None:
        return "—"
    return f"{value:g}{unit}"


def _chain_leaders(result: dict, snapshot: dict, limit: int = 3) -> list:
    """核心龙头：给卡片的"该盯谁"模块。

    数据全部来自 indicators.calc_chain_leaders（客观排序），这里只负责写成一句话。
    为什么是它 → 用链内极值反推，避免让 LLM 编理由。
    """
    ind = result.get("indicators") or snapshot.get("indicators") or {}
    raw_limit_up = (snapshot.get("raw") or {}).get("limit_up") or []
    chains = None
    # 有原始涨停池就现场算：快照里的 chain_leaders 可能是旧口径存的，
    # 直接拿来用会让卡片和报告口径不一致（出现过一次）。
    if raw_limit_up:
        try:
            import indicators as _indicators

            chains = _indicators.calc_chain_leaders(raw_limit_up)
        except Exception:
            chains = None
    if chains is None:
        chains = ind.get("chain_leaders") or []

    out = []
    for chain in (chains or [])[:limit]:
        leader = chain.get("leader") or {}
        if not leader.get("name"):
            continue
        why = []
        if leader.get("board") and leader.get("board") >= chain.get("max_board", 0):
            why.append("身位最高")
        if leader.get("seal_time") and leader.get("seal_time") == chain.get("first_seal_time"):
            why.append("封板最早")
        if leader.get("seal_money") and leader.get("seal_money") >= (chain.get("top_seal_money") or 0):
            why.append("封单最大")
        why.append(f"同链 {chain.get('stock_count', 0)} 只涨停")

        peers = " › ".join(
            f"{p['name']} {p['board_text']}/{p['seal_time']}"
            for p in (chain.get("peers") or [])[:3]
            if p.get("name")
        )
        laggards = "、".join(
            f"{p['name']} {p['seal_time']}"
            for p in (chain.get("laggards") or [])[:2]
            if p.get("name")
        )
        alt = chain.get("alt_leader") or {}
        out.append(
            {
                "name": leader["name"],
                "sector": chain.get("sector") or "",
                "board": leader.get("board_text") or "",
                "seal_time": leader.get("seal_time") or "",
                "seal_money": _money_text(leader.get("seal_money")),
                "limit_type": leader.get("limit_type") or "",
                # 特征词：这只龙头靠什么赚钱（同花顺涨停原因的前几个标签）
                "features": list(leader.get("features") or []),
                # 另一板别的龙头：10cm 主线 + 20cm 弹性
                "alt_leader": (
                    f"{alt['name']} {alt['board_text']}/{alt['seal_time']}"
                    if alt.get("name")
                    else ""
                ),
                "alt_limit_type": alt.get("limit_type") or "",
                "why": " · ".join(why),
                "peers": peers,
                "laggards": laggards,
            }
        )
    return out


def build_card(trade_date: str, note: str, result: dict, snapshot: dict) -> dict:
    """把复盘结果压成"一张图能讲清楚"的结构化数据，供前端画分享卡片。

    分工：这里只负责"选内容 + 定文案"（哪些数字、哪几条结论、什么口径），
    排版全部交给前端。这样以后换版式、加导出格式都不用再动数据层。
    """
    ind = snapshot["indicators"]
    emo, br = ind["emotion"], ind["breadth"]
    phase = result.get("market_phase") or {}
    tactics = result.get("tactics") or {}
    prev = ind.get("prev_day_comparison") or {}

    metrics = [
        {
            "label": "涨停",
            "value": str(emo["limit_up_count"]),
            "sub": f"首板 {emo['first_board_count']} · 连板 {emo['consecutive_board_count']}",
            "delta": _delta_text(prev.get("limit_up_count_delta"), " 家"),
        },
        {
            "label": "跌停",
            "value": str(emo["limit_down_count"]),
            "sub": f"炸板 {emo['limit_break_count']}",
            "delta": _delta_text(prev.get("limit_down_count_delta"), " 家"),
        },
        {
            "label": "封板率",
            "value": _pct_text(emo.get("seal_rate_pct")),
            "sub": f"最高 {emo['max_consecutive_board']} 板",
            "delta": _delta_text(prev.get("seal_rate_delta_pct"), " pct"),
        },
        {
            "label": "上涨占比",
            "value": _pct_text(br.get("up_ratio_pct")),
            "sub": f"平均 {_pct_text(br.get('avg_change_pct'))}",
            "delta": _delta_text(prev.get("up_ratio_delta_pct"), " pct"),
        },
    ]

    return {
        "trade_date": trade_date,
        "weekday": _weekday_cn(trade_date),
        "note": note,
        "stage": phase.get("stage") or "—",
        "confidence": phase.get("confidence") or "",
        "style": (result.get("style") or {}).get("verdict")
        or (ind.get("style_verdict") or {}).get("verdict")
        or "",
        "summary": result.get("summary") or "",
        "metrics": metrics,
        "reasons": [str(r) for r in (phase.get("reasons") or [])[:3]],
        "sectors": [
            {"name": s.get("name") or "", "strength": s.get("strength") or ""}
            for s in (result.get("hot_sectors") or [])[:3]
        ],
        # 核心龙头：热点板块下面一行"该盯谁"，由板块间对比 + 板块内对比算出来
        "leaders": _chain_leaders(result, snapshot),
        "tactics": {
            "position": tactics.get("position") or "",
            "approach": tactics.get("approach") or "",
            "do": [str(x) for x in (tactics.get("do") or [])[:2]],
        },
        "risk": (result.get("risks") or [""])[0],
        "breadth_stale": bool(br.get("is_stale")),
        "prev_trade_date": prev.get("prev_trade_date") or "",
        "source": "同花顺金融数据 API · 指标由程序计算",
        "disclaimer": "仅供个人研究，不构成投资建议",
    }


def save_report(payload: dict) -> Path:
    """把复盘结果落盘到 reports/{交易日}.md 与 .json（前端点击也会走这里存档）。"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    trade_date = payload["trade_date"]
    md_path = REPORT_DIR / f"{trade_date}.md"
    json_path = REPORT_DIR / f"{trade_date}.json"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(payload["report"])
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return md_path


def _try_save_snapshot(snapshot: dict) -> None:
    """落盘快照；只读文件系统（Vercel）上退化成警告，不阻断本次复盘。

    代价是拿不到历史留档与环比，但"这一次复盘"本身不受影响——
    对线上部署来说，能出结论比能存档重要。
    """
    try:
        ds.save_snapshot(snapshot, ds.render_brief(snapshot))
    except OSError as exc:
        print(f"警告：快照落盘失败（{exc}），本次复盘继续，仅影响历史留档与环比")


def _try_save_report(payload: dict) -> str:
    """落盘复盘存档；失败只警告，返回空字符串（前端拿到的报告不受影响）。"""
    try:
        return str(save_report(payload))
    except OSError as exc:
        print(f"警告：复盘存档写入失败（{exc}），本次仍正常返回报告")
        return ""


def iter_review(trade_date: str, fresh: bool = False, save: bool = True):
    """生成器：逐步产出 (阶段名, 中文说明) 进度，最后产出 ("report", 结果 dict)。

    让后端可以用 SSE 推送真实进度（而不是一次性发完所有进度再长时间等待）。
    """
    # 用户点"复盘"通常指的是当天，但当天数据要到收盘后才有：先解析成真正可复盘的交易日，
    # 把"用了哪一天、为什么"提前告诉调用方（第一条 meta 事件），再开始采集。
    trade_date, note = ds.hithink.resolve_trade_date(trade_date)
    yield ("meta", {"trade_date": trade_date, "note": note})

    yield ("snapshot", "采集盘面数据（涨停/跌停/炸板/板块）")
    snapshot = _load_snapshot(trade_date, fresh)

    yield ("indicators", "计算情绪、题材与板块强度指标")
    brief = build_brief(snapshot)

    yield ("review", "调用 LLM 生成复盘判断")
    content = _call_llm(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                data=json.dumps(brief, ensure_ascii=False, indent=1))},
        ]
    )
    result = _parse_json(content)
    if not result:
        raise RuntimeError("LLM 返回无法解析为 JSON：" + content[:300])
    # 输出侧兜底：把 LLM 写的统计数字逐个回指标快照里对一遍（编的数字会在这里露出来）
    result["fact_check"] = verify.verify_result(result, snapshot["indicators"])

    payload = {
        "trade_date": trade_date,
        "note": note,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result": result,
        "indicators": snapshot["indicators"],
        "report": render_report(trade_date, result, snapshot, note=note),
        # 给前端"分享卡片/摘要条"用的精简结构化数据
        "card": build_card(trade_date, note, result, snapshot),
    }
    if save:
        # 不管是 CLI 还是前端点击，复盘结果都留档，方便日后回看/对比
        payload["saved_to"] = _try_save_report(payload)
    yield ("report", payload)


def generate_review(trade_date: str, fresh: bool = False, save: bool = True) -> dict:
    """非流式入口（CLI/脚本用）：跑完整个流程，返回最终结果 dict。"""
    for stage, payload in iter_review(trade_date, fresh, save=save):
        if stage == "report":
            return payload
    raise RuntimeError("复盘流程未产出报告")


def main() -> None:
    parser = argparse.ArgumentParser(description="每日复盘报告（LLM）")
    parser.add_argument("--date", default=None, help="交易日 YYYY-MM-DD，默认今天")
    parser.add_argument("--fresh", action="store_true", help="重新采集快照")
    parser.add_argument("--show", action="store_true", help="只打印不写盘")
    args = parser.parse_args()

    requested = args.date or ds.hithink.today_str()
    print(f"=== 每日复盘 {requested} ===")
    print("采集快照 + 调用 LLM 生成复盘判断 ...")
    try:
        payload = generate_review(requested, fresh=args.fresh, save=not args.show)
    except ds.hithink.DataNotReady as exc:
        # 数据未就绪 / 快照不可信：直接说清楚，不要吐 traceback
        print(f"\n✗ 无法生成 {requested} 的复盘：{exc}")
        raise SystemExit(2)
    trade_date = payload["trade_date"]
    if payload.get("note"):
        print(f"提示：{payload['note']}")
    report = payload["report"]
    print()
    print(report)

    if not args.show:
        print()
        print(f"已保存：{payload.get('saved_to') or (REPORT_DIR / f'{trade_date}.md')}")


if __name__ == "__main__":
    main()
