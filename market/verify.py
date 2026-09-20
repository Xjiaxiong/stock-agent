"""事实校验：LLM 写进报告的数字，必须能在指标快照里找到。

反幻觉在提示词里写"不许编数字"是不够的——输出侧还要兜底。这里只盯
"盘面统计口径的数字"（带 家 / % / 亿 / 万 / pct 后缀的那种），逐个回快照里找；
找不到的记为可疑，写进 result["fact_check"]，并在报告末尾给一行校验结论。

刻意做成"提示"而不是"拦截"：像"2-3 板补位"这种是计划性表述，不是对今日数据的断言，
所以不纳入校验（否则全是误报）；但盘面数字比例明显偏低时，说明模型开始编数了，
这时候人必须看一眼。
"""

import re

# 盘面统计数字 + 单位：89家 / 57.14% / 1.07亿 / 4337万 / +31.86 pct
STAT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(家|%|亿|万|pct)")

# 阈值/目标型表述不是"对今日数据的断言"（"封板率回升至 60% 以上""不足 20%"），
# 命中这些前后缀就跳过，避免把计划性语言当成幻觉误报。
SOFT_PREFIX = ("不足", "超过", "高于", "低于", "至", "到", "接近", "约", "回落至", "回升至")
SOFT_SUFFIX = ("以上", "以下", "以内", "左右", "附近", "上方", "下方")

# 这些字段是"叙述"，逐字校验；其余字段（列表序号之类）不查
TEXT_FIELDS = ("emotion_summary", "summary")


def _iter_numbers(node, out: list) -> None:
    """把指标树里所有数字摊平（含 dict/list 嵌套）。"""
    if isinstance(node, dict):
        for value in node.values():
            _iter_numbers(value, out)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _iter_numbers(value, out)
    elif isinstance(node, bool):
        return
    elif isinstance(node, (int, float)):
        out.append(float(node))


def collect_allowed(indicators: dict) -> set:
    numbers: list = []
    _iter_numbers(indicators, numbers)
    allowed = set(numbers)
    # 环比字段只存了 delta，但报告里常写"昨日 X 家"（= 今日 X − delta）。
    # 这类能一步推出来的历史值要放行，否则全是误报。
    for (cur_section, cur_key), delta_key in _DELTA_PAIRS:
        current = ((indicators.get(cur_section) or {}).get(cur_key))
        delta = ((indicators.get("prev_day_comparison") or {}).get(delta_key))
        if current is None or delta is None:
            continue
        allowed.add(round(float(current) - float(delta), 2))
        allowed.add(round(float(current) + float(delta), 2))
    return allowed


# 今日指标 ↔ 环比 delta：用来还原"上一交易日"的绝对值
_DELTA_PAIRS = (
    (("emotion", "limit_up_count"), "limit_up_count_delta"),
    (("emotion", "limit_down_count"), "limit_down_count_delta"),
    (("emotion", "limit_break_count"), "limit_break_count_delta"),
    (("emotion", "seal_rate_pct"), "seal_rate_delta_pct"),
    (("emotion", "max_consecutive_board"), "max_board_delta"),
    (("breadth", "up_ratio_pct"), "up_ratio_delta_pct"),
)


def _matches(value: float, allowed: set, tol: float = 0.06) -> bool:
    if value in allowed:
        return True
    return any(abs(value - candidate) <= tol for candidate in allowed)


def _is_soft(text: str, start: int, end: int) -> bool:
    """是不是阈值/目标型表述（不算断言，直接跳过）。"""
    before = text[max(0, start - 3) : start]
    after = text[end : end + 3]
    return any(mark in before for mark in SOFT_PREFIX) or any(
        mark in after for mark in SOFT_SUFFIX
    )


def check_text(text: str, allowed: set) -> list:
    """返回这段文本里"找不到出处"的统计数字。"""
    issues = []
    text = text or ""
    for match in STAT_RE.finditer(text):
        if _is_soft(text, match.start(), match.end()):
            continue
        raw, unit = match.group(1), match.group(2)
        value = float(raw)
        if not _matches(value, allowed):
            issues.append(f"{raw}{unit}")
    return issues


def _texts_of(result: dict) -> list:
    """捞出所有需要校验的叙述文本。"""
    texts = [str(result.get(field) or "") for field in TEXT_FIELDS]
    phase = result.get("market_phase") or {}
    texts += [str(x) for x in (phase.get("reasons") or [])]
    texts.append(str((result.get("style") or {}).get("explanation") or ""))
    for sector in result.get("hot_sectors") or []:
        texts.append(str(sector.get("logic") or ""))
        texts.append(str(sector.get("sustainability") or ""))
    for item in result.get("opportunities") or []:
        texts += [str(item.get(k) or "") for k in ("logic", "entry_signal", "invalidation", "risk")]
    texts += [str(x) for x in (result.get("risks") or [])]
    tactics = result.get("tactics") or {}
    texts += [str(x) for x in (tactics.get("do") or [])]
    texts += [str(x) for x in (tactics.get("avoid") or [])]
    return [t for t in texts if t]


def verify_result(result: dict, indicators: dict, max_issues: int = 5) -> dict:
    """校验 LLM 结果里的统计数字，返回 {checked, matched, ratio, issues}。"""
    allowed = collect_allowed(indicators or {})
    texts = _texts_of(result or {})
    checked = matched = 0
    issues: list = []
    for text in texts:
        for match in STAT_RE.finditer(text):
            if _is_soft(text, match.start(), match.end()):
                continue
            raw, unit = match.group(1), match.group(2)
            checked += 1
            if _matches(float(raw), allowed):
                matched += 1
            elif len(issues) < max_issues:
                issues.append(f"{raw}{unit}")
    return {
        "checked": checked,
        "matched": matched,
        "ratio_pct": round(matched / checked * 100, 1) if checked else None,
        "issues": issues,
    }


def format_note(fact_check: dict) -> str:
    """报告末尾那行校验结论。"""
    if not fact_check or not fact_check.get("checked"):
        return ""
    ratio = fact_check.get("ratio_pct")
    note = (
        f"数字校验：正文 {fact_check['checked']} 处统计数字，"
        f"{fact_check['matched']} 处可在指标快照中复现（{ratio}%）"
    )
    issues = fact_check.get("issues") or []
    if issues:
        note += "；存疑：" + "、".join(issues)
    return note
