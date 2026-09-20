"""每日盘面快照：取数 -> 计算指标 -> 落盘 -> 生成可读文本。

这是"每日复盘 Agent"的第一步，完全不涉及 LLM：
用同花顺真实数据算出当天的客观盘面指标，并保存成历史快照。

用法（在项目根目录执行）：
    .venv/bin/python market/daily_snapshot.py                      # 用今天
    .venv/bin/python market/daily_snapshot.py --date 2026-09-11    # 指定交易日
    .venv/bin/python market/daily_snapshot.py --full               # 全市场采样（更慢更准）
    .venv/bin/python market/daily_snapshot.py --show               # 只打印不写盘

产物：
    market/snapshots/{交易日}.json   完整快照（原始数据 + 指标）
    market/snapshots/latest.json     最新一份快照
    market/snapshots/{交易日}.md     人类可读的盘面简报
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 让脚本既能在项目根目录跑，也能在 market 目录里跑
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from data import hithink  # noqa: E402
import indicators as ind  # noqa: E402

SNAPSHOT_DIR = Path(os.environ.get("MARKET_DATA_DIR", _HERE / "snapshots"))


def find_prev_snapshot(trade_date: str) -> dict | None:
    """找上一份已保存的快照（用于环比与赚钱效应）。"""
    snaps = find_prev_snapshots(trade_date, limit=1)
    return snaps[0] if snaps else None


def find_prev_snapshots(trade_date: str, limit: int = 10) -> list:
    """找最近若干份已保存的快照（用于环比、赚钱效应、题材持续天数）。"""
    if not SNAPSHOT_DIR.exists():
        return []
    files = sorted(
        [p for p in SNAPSHOT_DIR.glob("*.json") if p.stem[:4].isdigit() and p.stem < trade_date],
        reverse=True,
    )[:limit]
    out = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def collect(trade_date: str, sample_step: int) -> dict:
    """按顺序取回当日全部原始数据。

    第一步先取连板天梯并校验"目标日数据是否已生成"：涨停池在数据未生成时会
    静默回退到上一交易日，不先校验就会把昨天的盘面写成今天的快照。
    """
    print(f"[1/6] 连板天梯（近 30 日，同时校验目标日数据是否已生成） ...")
    ladder = hithink.fetch_limit_up_ladder()
    hithink.ensure_data_ready(trade_date, ladder=ladder)
    latest_ready = hithink.latest_ready_trade_date(ladder)
    print(f"      天数 {len(ladder.get('item') or [])}")

    print(f"[2/6] 涨停池 ...")
    limit_up = hithink.fetch_limit_up_pool(trade_date)
    print(f"      涨停/连板 {len(limit_up)} 只")

    print(f"[3/6] 跌停池 ...")
    limit_down = hithink.fetch_limit_down_pool(trade_date)
    print(f"      跌停 {len(limit_down)} 只")

    print(f"[4/6] 炸板池 ...")
    limit_break = hithink.fetch_limit_break_pool(trade_date)
    print(f"      炸板 {len(limit_break)} 只")

    print(f"[5/6] 全市场快照（采样步长 {sample_step}） ...")
    snapshot, snapshot_as_of = hithink.fetch_market_snapshot(sample_step=sample_step)
    print(f"      采样 {len(snapshot)} 只（数据日期 {snapshot_as_of}）")

    # 全市场接口只返回"最新"行情，接口带回的时间戳是**墙钟时间**：凌晨跑时已经跨天，
    # 会把昨天收盘的数据标成今天。真正代表这份分布的是"上游最新可用交易日"。
    breadth_as_of = latest_ready or snapshot_as_of

    print(f"[6/6] 概念板块清单与快照（板块强度） ...")
    catalog = hithink.fetch_index_catalog("cn_concept")
    index_snapshot = hithink.fetch_index_snapshot([x["thscode"] for x in catalog])
    print(f"      概念 {len(catalog)} 个，快照 {len(index_snapshot)} 条")
    return {
        "limit_up": limit_up,
        "limit_down": limit_down,
        "limit_break": limit_break,
        "ladder": ladder,
        "market_snapshot": snapshot,
        "market_snapshot_as_of": breadth_as_of,
        "market_snapshot_ts": snapshot_as_of,
        "concept_catalog": catalog,
        "index_snapshot": index_snapshot,
        # 取数时上游最新可用交易日：写进快照用于日后识别"是否在数据未生成时写的"
        "latest_ready_trade_date": latest_ready,
    }


def build_snapshot(trade_date: str, raw: dict, prev: dict | None, prev_snapshots: list | None = None) -> dict:
    """组装完整快照：原始数据 + 指标。"""
    indicators = ind.build_indicators(
        trade_date=trade_date,
        limit_up=raw["limit_up"],
        limit_down=raw["limit_down"],
        limit_break=raw["limit_break"],
        market_snapshot=raw["market_snapshot"],
        ladder=raw["ladder"],
        prev_snapshot=prev,
        concept_catalog=raw.get("concept_catalog"),
        index_snapshot=raw.get("index_snapshot"),
        prev_snapshots=prev_snapshots,
        breadth_as_of=raw.get("market_snapshot_as_of"),
    )
    return {
        "trade_date": trade_date,
        "generated_at": ind._now_iso(),
        # 数据来源与就绪状态（供上层判断这份快照是否可信）
        "data_source": {
            "provider": "hithink",
            "latest_ready_trade_date": raw.get("latest_ready_trade_date"),
            # 上游接口自带的墙钟时间戳（仅作排查用，判断数据归属请用上面那个字段）
            "market_snapshot_ts": raw.get("market_snapshot_ts"),
        },
        "indicators": indicators,
        "raw": {
            "limit_up": raw["limit_up"],
            "limit_down": raw["limit_down"],
            "limit_break": raw["limit_break"],
            "ladder_window": (raw["ladder"].get("window") or {}),
            # 全市场采样数据体积较大，只保留必要字段
            "market_snapshot": [
                {
                    "thscode": r.get("thscode"),
                    "price_change_ratio_pct": r.get("price_change_ratio_pct"),
                    "turnover": r.get("turnover"),
                }
                for r in raw["market_snapshot"]
            ],
        },
    }


def _fmt(value, suffix="", none_text="—"):
    if value is None:
        return none_text
    if isinstance(value, float):
        value = f"{value:g}"
    return f"{value}{suffix}"


def save_snapshot(snapshot: dict, brief: str | None = None) -> Path:
    """落盘一份快照：{日期}.json（必需）、{日期}.md（可选）、latest.json。

    统一在取数层写盘，避免"CLI 跑出来有简报、复盘 --fresh 跑出来只有 json"的不一致。
    latest.json 只在日期不倒退时更新：补跑历史交易日不应把最新指针指回过去。
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    trade_date = snapshot["trade_date"]
    out_json = SNAPSHOT_DIR / f"{trade_date}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    if brief is not None:
        with open(SNAPSHOT_DIR / f"{trade_date}.md", "w", encoding="utf-8") as f:
            f.write(brief)

    latest_path = SNAPSHOT_DIR / "latest.json"
    current = ""
    if latest_path.exists():
        try:
            with open(latest_path, encoding="utf-8") as f:
                current = json.load(f).get("trade_date") or ""
        except (OSError, ValueError):  # 损坏的 latest 不该阻断本次落盘
            current = ""
    if trade_date >= current:
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=1)
    return out_json


def render_brief(snapshot: dict) -> str:
    """把指标渲染成一段人类可读的盘面简报（不经过 LLM，纯模板）。"""
    i = snapshot["indicators"]
    emo, br, st = i["emotion"], i["breadth"], i["style"]
    lines = [f"# 盘面简报 {snapshot['trade_date']}", ""]

    lines += ["## 一、情绪周期", ""]
    lines += [
        f"- 涨停 {emo['limit_up_count']} 家（首板 {emo['first_board_count']}、连板 {emo['consecutive_board_count']}）"
        f" ｜ 跌停 {emo['limit_down_count']} 家 ｜ 炸板 {emo['limit_break_count']} 家",
        f"- 封板率：{_fmt(emo['seal_rate_pct'], '%')}"
        f" ｜ 连板占比：{_fmt(emo['consecutive_board_ratio_pct'], '%')}"
        f" ｜ 最高连板：{_fmt(emo['max_consecutive_board'], '板')}",
    ]
    if emo["ladder_distribution"]:
        dist = "、".join(f"{k} {v}只" for k, v in emo["ladder_distribution"].items())
        lines.append(f"- 连板梯队：{dist}")

    lines += ["", "## 二、市场活跃度", ""]
    lines += [
        f"- 上涨 {br['up_count']} / 下跌 {br['down_count']}（采样 {br['sampled_stocks']} 只）",
        f"- 上涨占比：{_fmt(br['up_ratio_pct'], '%')} ｜ 平均涨跌幅：{_fmt(br['avg_change_pct'], '%')}",
        f"- 采样成交额：{_fmt(round(br['est_total_turnover'] / 1e8, 1), ' 亿')}",
    ]
    if br.get("is_stale"):
        lines.append(
            f"- ⚠️ 该分布的数据日期为 {br.get('as_of')}，并非 {snapshot['trade_date']}"
            f"（全市场快照接口不支持历史日期），**不可当作该交易日的涨跌分布**"
        )

    lines += ["", "## 三、热点题材（按涨停原因聚类）", ""]
    for idx, sector in enumerate(i["hot_sectors"][:8], 1):
        stocks = "、".join(f"{s['name']}({s['board']}板)" for s in sector["stocks"][:4])
        lines.append(
            f"{idx}. **{sector['tag']}** — {sector['stocks_count']} 只涨停，最高 {sector['max_board']} 板，强度 {sector['score']}"
        )
        if stocks:
            lines.append(f"   代表股：{stocks}")

    strength = i.get("concept_strength") or {}
    if strength.get("hot_concepts"):
        lines += ["", "## 三·补、板块强度（指数 × 涨停交叉）", ""]
        for idx, c in enumerate(strength["hot_concepts"][:6], 1):
            leader = c.get("leader") or {}
            lines.append(
                f"{idx}. **{c['name']}** — 指数 {_fmt(c['change_pct'], '%')}"
                f" ｜ 涨停 {c['limit_up_count']} 只 ｜ 最高 {c['max_board']} 板"
                f" ｜ 题材连续 {c['streak_days']} 天"
            )
            if leader.get("name"):
                lines.append(f"   龙头：{leader['name']}（{leader.get('board')}板）")

    if strength.get("top_by_change"):
        top = "、".join(f"{x['name']}({_fmt(x['change_pct'], '%')})" for x in strength["top_by_change"][:6])
        lines += ["", f"板块指数涨幅前列：{top}"]

    lines += ["", "## 四、资金风格", ""]
    verdict = i["style_verdict"]
    lines += [
        f"- 初判：**{verdict['verdict']}**（题材分 {verdict['momentum_score']} / 趋势分 {verdict['trend_score']}）",
        f"- 早盘封板占比：{_fmt(st['early_limit_up_ratio_pct'], '%')}"
        f" ｜ 大封单(≥3亿) {st['big_seal_count']} 家 ｜ 3板及以上 {st['high_board_count']} 家",
    ]
    for reason in verdict["reasons"]:
        lines.append(f"- {reason}")

    lines += ["", "## 五、连板天梯（近 5 日）", ""]
    for day in i["ladder_trend"]:
        dist = "、".join(f"{k} {v}" for k, v in day["distribution"].items()) or "无"
        lines.append(f"- {day['date']}：最高 {day['max_board']} 板 ｜ {dist}")

    if i.get("prev_day_comparison"):
        pc = i["prev_day_comparison"]
        lines += ["", "## 六、环比上一交易日", ""]
        lines += [
            f"- 对比日：{pc['prev_trade_date']}",
            f"- 涨停家数变化：{_fmt(pc['limit_up_count_delta'])}"
            f" ｜ 炸板家数变化：{_fmt(pc['limit_break_count_delta'])}"
            f" ｜ 封板率变化：{_fmt(pc['seal_rate_delta_pct'], '%')}"
            f" ｜ 最高板变化：{_fmt(pc['max_board_delta'])}",
        ]
    if i.get("yesterday_effect"):
        ye = i["yesterday_effect"]
        lines += ["", "## 七、赚钱效应（昨日涨停今日表现）", ""]
        lines += [
            f"- 昨日涨停 {ye['prev_limit_up_count']} 家，今日仍涨停 {ye['still_limit_up_count']} 家"
            f"（延续率 {_fmt(ye['still_limit_up_ratio_pct'], '%')}）",
        ]

    lines += ["", "---", "", "> 数据来源：同花顺金融数据 API（真实数据）。本简报为客观指标统计，不构成投资建议。"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="每日盘面快照（同花顺真实数据）")
    parser.add_argument("--date", default=None, help="交易日 YYYY-MM-DD，默认今天")
    parser.add_argument("--full", action="store_true", help="全市场全量采样（更慢）")
    parser.add_argument("--show", action="store_true", help="只打印简报，不写文件")
    args = parser.parse_args()

    try:
        trade_date, date_note = hithink.resolve_trade_date(args.date)
    except hithink.DataNotReady as exc:
        print(f"✗ {exc}")
        raise SystemExit(2)
    sample_step = 1 if args.full else 4

    print(f"=== 盘面快照 {trade_date} ===")
    if date_note:
        print(f"提示：{date_note}")
    prev_snapshots = find_prev_snapshots(trade_date, limit=10)
    prev = prev_snapshots[0] if prev_snapshots else None
    if prev:
        print(f"上一份快照：{prev.get('trade_date')}（已存 {len(prev_snapshots)} 份历史，用于环比/持续天数）")
    try:
        raw = collect(trade_date, sample_step)
    except hithink.DataNotReady as exc:
        # 宁可什么都不写，也不要落一份错日期的快照
        print(f"\n✗ 无法生成 {trade_date} 的盘面快照：{exc}")
        print("  本模块只处理「已收盘且上游数据已生成」的交易日。")
        raise SystemExit(2)
    snapshot = build_snapshot(trade_date, raw, prev, prev_snapshots)

    brief = render_brief(snapshot)
    print()
    print(brief)

    if not args.show:
        out_json = save_snapshot(snapshot, brief)
        print()
        print(f"已保存：{out_json}")
        print(f"已保存：{out_json.with_suffix('.md')}")


if __name__ == "__main__":
    main()
