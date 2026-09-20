"""盘面指标计算层：把全市场原始数据压缩成客观指标。

设计原则（关键）：
- 这里只做确定性计算，不调用任何 LLM。数字必须由代码算准。
- 所有函数都是纯函数：输入原始数据，输出 dict，便于单测与复算。
- 缺失数据一律返回 None，不补零、不猜测（与后端 tools.py 同一约定）。

指标分五组：
1. 情绪周期：涨停/跌停/炸板家数、封板率、连板高度、梯队
2. 市场活跃度：成交额、涨跌家数分布
3. 资金风格：涨停股的市值/题材特征、连板延续（依赖历史快照）
4. 热点板块：从涨停原因聚类，判断板块强度与持续性（持续性依赖历史）
5. 赚钱效应：昨日涨停股今日表现（依赖历史快照）
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

# 连板天梯的板位顺序（上游固定返回这六个 key）
BOARD_KEYS = ["two_board", "three_board", "four_board", "five_board", "six_board", "seven_over"]
BOARD_LABEL = {
    "two_board": "2板",
    "three_board": "3板",
    "four_board": "4板",
    "five_board": "5板",
    "six_board": "6板",
    "seven_over": "7板及以上",
}


def _now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _ratio(numerator, denominator):
    """安全百分比；分母为 0 返回 None（不编造 0%）。"""
    if not denominator:
        return None
    return round(numerator / denominator * 100, 2)


# ---------- 1. 情绪周期 ----------


def calc_emotion(limit_up: list, limit_down: list, limit_break: list) -> dict:
    """情绪周期核心指标。"""
    # 连板计数：continue_day_cnt 为 1 表示首板，>1 表示连板
    counts = [int(x.get("continue_day_cnt") or 1) for x in limit_up]
    consecutive = [c for c in counts if c > 1]

    # 今日正处于涨停状态的股票数
    sealed = len(limit_up)
    broken = len(limit_break)
    # 封板率：封住的 / (封住 + 炸板)。衡量情绪强度，比单纯涨停家数更有意义
    seal_rate = _ratio(sealed, sealed + broken)

    # 连板梯队分布：统计每个连板高度各有多少只
    ladder_dist: dict = {}
    for c in counts:
        if c > 1:
            key = f"{c}板"
            ladder_dist[key] = ladder_dist.get(key, 0) + 1

    return {
        "limit_up_count": sealed,
        "limit_down_count": len(limit_down),
        "limit_break_count": broken,
        "seal_rate_pct": seal_rate,
        "first_board_count": len([c for c in counts if c == 1]),
        "consecutive_board_count": len(consecutive),
        "consecutive_board_ratio_pct": _ratio(len(consecutive), sealed),
        "max_consecutive_board": max(counts) if counts else 0,
        "ladder_distribution": dict(sorted(ladder_dist.items(), key=lambda kv: -int(kv[0].rstrip("板")))),
        # 连板家数占比高 = 题材性强；首板多 = 情绪修复初期
        "limit_down_ratio_pct": _ratio(len(limit_down), len(limit_down) + sealed),
    }


# ---------- 2. 市场活跃度 ----------


def calc_breadth(market_snapshot: list, as_of: str | None = None, trade_date: str | None = None) -> dict:
    """涨跌家数分布与总成交额（基于采样快照估算）。

    as_of 是快照数据的真实日期。若与 trade_date 不一致，说明这是"当前"的市场
    分布而非目标交易日的分布（历史日期无法回填），此时打上 is_stale 标记，
    下游（LLM/报告）不应把它当作该交易日的涨跌分布使用。
    """
    ups = downs = flat = 0
    limit_up_like = limit_down_like = 0
    total_turnover = 0.0
    changes = []

    for row in market_snapshot:
        pct = row.get("price_change_ratio_pct")
        if pct is None:
            continue
        pct = float(pct)
        changes.append(pct)
        total_turnover += float(row.get("turnover") or 0)
        if pct > 0:
            ups += 1
        elif pct < 0:
            downs += 1
        else:
            flat += 1
        if pct >= 9.8:
            limit_up_like += 1
        elif pct <= -9.8:
            limit_down_like += 1

    sampled = ups + downs + flat
    return {
        "as_of": as_of,
        "is_stale": bool(as_of and trade_date and as_of != trade_date),
        "sampled_stocks": sampled,
        "up_count": ups,
        "down_count": downs,
        "flat_count": flat,
        "up_ratio_pct": _ratio(ups, sampled),
        "down_ratio_pct": _ratio(downs, sampled),
        "avg_change_pct": round(sum(changes) / len(changes), 2) if changes else None,
        "est_total_turnover": round(total_turnover, 2),
        # 采样模式下按比例外推全市场家数（仅用于展示，非精确值）
        "limit_up_like_sampled": limit_up_like,
        "limit_down_like_sampled": limit_down_like,
    }


# ---------- 3. 资金风格 ----------


def calc_style(limit_up: list) -> dict:
    """从涨停股结构判断"连板题材"还是"趋势核心"风格。"""
    st_count = len([x for x in limit_up if x.get("is_st")])
    new_count = len([x for x in limit_up if x.get("is_new")])
    # 封单额（封单越大说明资金越坚决）
    seal_money = [float(x.get("seal_money") or 0) for x in limit_up]
    big_seal = len([m for m in seal_money if m >= 3e8])  # 封单 >= 3 亿

    # 涨停时间分布：早盘涨停（<=10:00）多说明资金一致性高、情绪强
    early_limit = 0
    for x in limit_up:
        t = (x.get("limit_up_time") or "").strip()
        if len(t) == 5 and t <= "10:00":
            early_limit += 1

    counts = [int(x.get("continue_day_cnt") or 1) for x in limit_up]
    high_board = len([c for c in counts if c >= 3])
    return {
        "st_limit_up_count": st_count,
        "new_stock_limit_up_count": new_count,
        "big_seal_count": big_seal,
        "early_limit_up_count": early_limit,
        "early_limit_up_ratio_pct": _ratio(early_limit, len(limit_up)),
        "high_board_count": high_board,  # 3 板及以上
    }


# ---------- 4. 热点板块（从涨停原因聚类） ----------


def _split_reason(reason: str) -> list:
    """涨停原因形如 'AI文旅+景区旅游+游船票务'，拆成独立标签。"""
    if not reason:
        return []
    parts = re.split(r"[+＋、,，/|｜]", reason)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]


def calc_hot_sectors(limit_up: list, top_n: int = 10) -> list:
    """按涨停原因标签聚类，输出热点题材排名。

    口径：
    - stocks_count：有多少只**不同的**股票挂了该标签（衡量题材广度，最重要）
    - occurrence：标签出现次数（含同一只票贡献多个概念）
    - max_board：该标签下最高连板高度（衡量龙头高度）
    score = stocks_count * 2 + max_board（广度优先，高度加成）

    注意：单只票的多个概念标签会各自成行（如"智能卫浴/适老产品"），
    因此用 stocks_count 排序能避免同一只票霸榜，但跨票的题材合并
    （如"AI文旅"与"景区旅游"其实是一条主线）需靠后续 LLM 或人工归并。
    """
    stat: dict = {}
    for row in limit_up:
        board = int(row.get("continue_day_cnt") or 1)
        # 同一只票可能有多个标签，用集合去重，保证每只票对每个标签只计一次
        tags = set(_split_reason(row.get("limit_up_reason") or ""))
        for tag in tags:
            entry = stat.setdefault(
                tag,
                {"tag": tag, "occurrence": 0, "stocks_count": 0, "max_board": 0, "stocks": [], "score": 0},
            )
            entry["occurrence"] += 1
            entry["max_board"] = max(entry["max_board"], board)
            entry["stocks_count"] += 1
            if len(entry["stocks"]) < 6:
                entry["stocks"].append({"name": row.get("name"), "board": board})

    for entry in stat.values():
        entry["score"] = round(entry["stocks_count"] * 2 + entry["max_board"], 2)
    return sorted(stat.values(), key=lambda x: (-x["score"], -x["stocks_count"]))[:top_n]


# ---------- 4b. 核心龙头（板块之间对比 + 板块内部对比） ----------

# 涨停原因里的"通用词"：它们出现在几十个互不相干的题材里，
# 拿来做"同链"合并会把不相关的票串成一条假主线（如"业绩增长"和"中报增长"）。
_GENERIC_TAG_WORDS = {
    "概念", "板块", "增长", "业绩", "中报", "半年报", "年报", "预告", "扭亏", "订单",
    "充足", "饱满", "涨价", "扩产", "扩能", "产能", "投产", "量产", "回购", "增持",
    "中标", "合作", "突破", "上市", "定增", "重组", "收购", "参股", "持股", "股权",
    "激励", "转让", "控股", "国资", "涨停", "龙头", "题材", "预期", "布局", "签约",
    "材料", "设备", "技术", "产品", "项目", "新材", "股份", "科技", "订单充足",
    "高端", "中低端", "采购", "分销", "部件", "装备", "应用", "业务", "领域", "需求",
}

# 尾盘封板的身位（首板）算跟风：这个时间点封板说明是资金跟风，不是日内引领
_LATE_SEAL_MINUTES = 13 * 60


def _seal_minutes(text) -> int:
    """'09:32' -> 572（当日分钟数）。缺失/异常给一个超大值，排在最后。"""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(text or "").strip())
    if not m:
        return 24 * 60
    return int(m.group(1)) * 60 + int(m.group(2))


_WORD_SHAPE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9]+$")


def _is_generic(key: str) -> bool:
    """关键词是否"通用"：整词命中通用词，或只是通用词的碎片（报增长 / 高端PC）。"""
    return any(word in key for word in _GENERIC_TAG_WORDS)


def _tag_keywords(tag: str) -> dict:
    """标签里的候选关键词，返回 {归一化关键词: 原始写法（用于展示）}。

    取 3~4 字子串 + 开头的 2 字词：
    - 不用所有 2 字子串：太容易撞车（"材料""设备"谁的标签里都有）；
    - 保留开头 2 字是因为同花顺标签习惯把主线写在最前面
      （光刻胶配套试剂 / 光刻机 → 共享"光刻"）。
    """
    text = str(tag or "").strip()
    out: dict = {}
    for size in (3, 4):
        for i in range(0, len(text) - size + 1):
            piece = text[i : i + size]
            if _WORD_SHAPE.match(piece):
                out.setdefault(_norm(piece), piece)
    head = text[:2]
    if len(text) >= 2 and _WORD_SHAPE.match(head):
        out.setdefault(_norm(head), head)
    out.setdefault(_norm(text), text)
    return {k: v for k, v in out.items() if not _is_generic(k)}


def _rank_chain(rows: list) -> list:
    """板块内部排序：身位 > 板别（同身位 10cm 优先）> 封板时间 > 封单额。

    身位仍然是最硬的：20cm 的 3 板（累计 68%）不会因为"板别"就排在 10cm 首板后面。
    但同身位时必须给 10cm 让路——题材梯度完整时，主板那只才是资金定价的主锚，
    20cm（创业板/科创板）是同题材的弹性补充。谁是龙头、谁是弹性，卡片上分开写。
    """
    return sorted(
        rows,
        key=lambda s: (
            -s["board"],
            _LIMIT_TIER.get(s["limit_type"], 9),
            s["seal_minutes"],
            -s["seal_money"],
        ),
    )


# 涨停板别 → 排序优先级（越小越靠前）
_LIMIT_TIER = {"10cm": 0, "5cm": 1, "20cm": 2, "30cm": 3}


def _limit_type(row: dict) -> str:
    """涨停板别：10cm（主板）/ 5cm（ST）/ 20cm（创业板、科创板）/ 30cm（北交所）。

    用当日涨幅判比用代码判可靠（接口给的 price_change_ratio_pct 就是涨停幅度），
    拿不到时才退回代码段判断。
    """
    try:
        pct = abs(float(row.get("price_change_ratio_pct")))
    except (TypeError, ValueError):
        pct = 0.0
    if row.get("is_st") and pct <= 6:
        return "5cm"
    if pct >= 25:
        return "30cm"
    if pct >= 15:
        return "20cm"
    if pct >= 8:
        return "10cm"
    code = str(row.get("ticker") or "")
    if code.startswith(("300", "301", "688", "689")):
        return "20cm"
    if code.startswith(("43", "83", "87", "92")):
        return "30cm"
    return "10cm"


def calc_chain_leaders(limit_up: list, top_n: int = 3, peers_n: int = 3) -> list:
    """核心龙头：先按"同链"合并题材标签，再在链内排序找出龙头。

    为什么要合并标签：涨停原因是按"公司自己的标签"写的，同一条产业链会被拆成
    多个标签（半导体硅片 / 半导体材料 / 半导体设备 / 半导体靶材 …），
    不合并就每只票各自成"板块"，无法比出龙头。

    口径：
    - 同链 = 两个标签共享一个非通用关键词（3 字以上子串，或开头 2 字）
    - 链内排序 = 板别（10cm 优先于 20cm/30cm）> 身位 > 封板时间 > 封单额（见 _rank_chain）
    - 同链里 10cm 和 20cm 各自出一只龙头：主板龙头定调，20cm 龙头给弹性
    - 板块之间排序 score = 最高板 * 3 + 链内涨停家数 * 2（高度优先，广度加成）
    - 一只票只归给最强的链：避免同一只票在多条链里重复当龙头

    输出（build_card 拿去做文案，前端只负责排版）：
    [{sector, score, stock_count, max_board, keywords,
      leader / peers / growth_leader / laggards,
      每只票含 name, board, board_text, seal_time, seal_money, limit_type, features}]
    """
    stocks: dict = {}
    tag_stocks: dict = {}
    for row in limit_up or []:
        name = (row.get("name") or "").replace(" ", "")
        if not name:
            continue
        board = int(row.get("continue_day_cnt") or 1)
        minutes = _seal_minutes(row.get("limit_up_time"))
        tags = _split_reason(row.get("limit_up_reason") or "")
        stocks[name] = {
            "name": name,
            "board": board,
            "board_text": "首板" if board <= 1 else f"{board}板",
            "seal_time": str(row.get("limit_up_time") or "").strip(),
            "seal_minutes": minutes,
            "seal_money": float(row.get("seal_money") or 0),
            "limit_type": _limit_type(row),
            # 特征词：同花顺给的涨停原因标签（主升题材写在最前面），
            # 卡片上用来回答"这只龙头是靠什么赚钱的"
            "features": tags[:3],
        }
        # 用 dict.fromkeys 去重但保留标签顺序：同花顺把主升题材写在最前面，
        # 而"哪个标签先出现"决定了同分链条谁先认领这只票（set 会让结果随进程变化）
        for tag in dict.fromkeys(tags):
            tag_stocks.setdefault(tag, set()).add(name)

    # 关键词 -> 挂了该关键词的标签；同时记住关键词的原始写法
    keyword_tags: dict = {}
    keyword_display: dict = {}
    for tag in tag_stocks:
        for key, display in _tag_keywords(tag).items():
            keyword_tags.setdefault(key, set()).add(tag)
            keyword_display.setdefault(key, display)

    # 一个标签只归给"最强的一条链"：
    # 打分 = 覆盖标签数 × 关键词长度（长词更具体，短词更容易串味），
    # 逐个关键词认领标签，先认领的赢，避免"服务器"把 AI 和 PCB 缝成一条巨链。
    groups: dict = {}
    claimed: set = set()
    for key in sorted(
        keyword_tags,
        key=lambda k: (-len(keyword_tags[k]) * len(k), -len(keyword_tags[k]), -len(k)),
    ):
        tags = {t for t in keyword_tags[key] if t not in claimed}
        if len(tags) < 2:
            continue
        groups[key] = tags
        claimed |= tags

    chains = []
    for key, tags in groups.items():
        sector = keyword_display.get(key) or key
        names_in_chain = {n for tag in tags for n in tag_stocks[tag]}
        rows = [stocks[n] for n in names_in_chain]
        if not rows:
            continue
        ranked = _rank_chain(rows)
        max_board = max(r["board"] for r in ranked)
        chains.append(
            {
                "sector": sector,
                "keywords": sorted(tags),
                "stock_count": len(ranked),
                "max_board": max_board,
                "score": round(max_board * 3 + len(ranked) * 2, 2),
                "ranking": ranked,
            }
        )

    # 没被任何链认领的标签各自成一条链（板块名就是标签本身）
    for tag in tag_stocks:
        if tag in claimed:
            continue
        rows = [stocks[n] for n in tag_stocks[tag]]
        if not rows:
            continue
        ranked = _rank_chain(rows)
        chains.append(
            {
                "sector": tag,
                "keywords": [tag],
                "stock_count": len(ranked),
                "max_board": max(r["board"] for r in ranked),
                "score": round(max(r["board"] for r in ranked) * 3 + len(ranked) * 2, 2),
                "ranking": ranked,
            }
        )

    # 板块之间对比：高度 + 广度决定谁排在前面
    chains.sort(key=lambda c: (-c["score"], -c["stock_count"], -c["max_board"]))

    def is_lagger(row: dict) -> bool:
        """跟风：首板且尾盘才封板（冲板晚 = 跟随资金，不是日内引领）。"""
        return row["board"] <= 1 and row["seal_minutes"] >= _LATE_SEAL_MINUTES

    out, used = [], set()
    for chain in chains:
        rows = [r for r in chain["ranking"] if r["name"] not in used]
        # 一只票只归给最强的那条链（链分高的先认领）。若这条链的龙头已经被
        # 更强的链领走，就不再单独展示它——否则会把"副将"当成龙头报出去
        # （闽东电力归了福建国资，海上风电就只剩太阳电缆，那不能叫风电龙头）。
        if not rows or rows[0]["name"] != chain["ranking"][0]["name"]:
            continue
        leader = rows[0]
        if is_lagger(leader):
            continue  # 整条链都是尾盘跟风，没有值得盯的龙头
        used.update(r["name"] for r in rows)

        # 同链分两个板别看：主线龙头之外，再单独指出另一板别的龙头
        # （题材梯度完整时，10cm 龙头定调、20cm 龙头给弹性，两个都要盯）
        main_rows = [r for r in rows if r["limit_type"] == leader["limit_type"]]
        other_rows = [r for r in rows if r["limit_type"] != leader["limit_type"]]
        alt_leader = next(
            (r for r in other_rows if r["limit_type"] in ("20cm", "30cm") and not is_lagger(r)),
            None,
        ) or next((r for r in other_rows if not is_lagger(r)), None)
        out.append(
            {
                "sector": chain["sector"],
                "keywords": chain["keywords"],
                "stock_count": len(rows),
                "max_board": max(r["board"] for r in rows),
                "score": chain["score"],
                "leader": leader,
                # 同板别里紧随其后的票（板块内部对比：谁是次强）
                "peers": [r for r in main_rows[1 : peers_n + 1] if not is_lagger(r)],
                # 另一板别的龙头
                "alt_leader": alt_leader,
                # 尾盘跟风（板块内部对比：谁只是在跟）
                "laggards": [r for r in rows[1:] if is_lagger(r)][:2],
                # 链内极值：build_card 用它写"为什么是它"
                "first_seal_time": min(rows, key=lambda r: r["seal_minutes"])["seal_time"],
                "top_seal_money": max(r["seal_money"] for r in rows),
            }
        )
        if len(out) >= top_n:
            break
    return out


# ---------- 4c. 板块强度（概念/行业指数 + 涨停原因交叉） ----------


def _norm(text: str) -> str:
    """归一化文本用于板块名匹配：去掉空白与常见分隔符，小写。"""
    if not text:
        return ""
    return re.sub(r"[\s\-_/、，,+＋|｜()（）]", "", str(text)).lower()


def calc_concept_strength(
    concept_catalog: list,
    index_snapshot: list,
    limit_up: list,
    prev_snapshots: list | None = None,
    top_n: int = 10,
) -> dict:
    """板块强度：把"板块指数涨跌"与"涨停原因聚类"交叉验证。

    为什么交叉：只看板块指数涨幅会漏掉短线题材（指数被大市值拖累）；
    只看涨停原因又会缺板块整体热度。两者叠加才接近真实主线。

    输出：
    - top_by_change：按板块指数涨跌幅排序的前 N（板块整体强度）
    - hot_concepts：板块指数涨幅为正、且板块名与当日涨停原因存在关联的题材
      （name / change_pct / limit_up_count / max_board / leader / streak_days）
    - streak_days：该题材连续出现在涨停原因里的天数（依赖历史快照，记忆层）
    """
    name_by_code = {x.get("thscode"): x.get("name") for x in concept_catalog}

    # 涨停原因标签 -> 关联的涨停股
    tag_stocks: dict = {}
    for row in limit_up:
        board = int(row.get("continue_day_cnt") or 1)
        for tag in set(_split_reason(row.get("limit_up_reason") or "")):
            tag_stocks.setdefault(tag, []).append(
                {"name": row.get("name"), "board": board, "seal_money": float(row.get("seal_money") or 0)}
            )

    # 历史快照里每天出现过的涨停原因标签（用于算持续天数）
    history_tags: list = []
    for snap in (prev_snapshots or []):
        day_tags = set()
        for row in ((snap.get("raw") or {}).get("limit_up") or []):
            day_tags.update(_split_reason(row.get("limit_up_reason") or ""))
        history_tags.append(day_tags)

    def streak_of(tag: str) -> int:
        """连续天数：从最近一天往前数，标签每天都出现才算连续。"""
        streak = 1
        for day_tags in history_tags:
            if tag in day_tags:
                streak += 1
            else:
                break
        return streak

    # 板块指数强度
    rows = []
    for item in index_snapshot:
        code = item.get("thscode")
        change = item.get("price_change_ratio_pct")
        rows.append(
            {
                "thscode": code,
                "name": name_by_code.get(code) or code,
                "change_pct": round(float(change), 2) if change is not None else None,
                "turnover": item.get("turnover"),
            }
        )
    rows = [r for r in rows if r["change_pct"] is not None]
    top_by_change = sorted(rows, key=lambda r: -r["change_pct"])[:top_n]

    # 板块名 <-> 涨停标签 关联（双向子串匹配，归一化后比较）
    hot_concepts = []
    for row in rows:
        norm_name = _norm(row["name"])
        if not norm_name or row["change_pct"] <= 0:
            continue
        matched_tags = {
            tag for tag in tag_stocks
            if norm_name in _norm(tag) or _norm(tag) in norm_name
        }
        if not matched_tags:
            continue
        stocks = [s for tag in matched_tags for s in tag_stocks[tag]]
        # 去重（同一只票可能同时匹配多个标签）
        seen, uniq = set(), []
        for s in stocks:
            if s["name"] not in seen:
                seen.add(s["name"])
                uniq.append(s)
        leader = max(uniq, key=lambda s: (s["board"], s["seal_money"])) if uniq else None
        hot_concepts.append(
            {
                "thscode": row["thscode"],
                "name": row["name"],
                "change_pct": row["change_pct"],
                "limit_up_count": len(uniq),
                "max_board": max((s["board"] for s in uniq), default=0),
                "leader": leader,
                "streak_days": max(streak_of(t) for t in matched_tags),
                "matched_tags": sorted(matched_tags),
            }
        )

    hot_concepts.sort(key=lambda x: (-x["streak_days"], -x["limit_up_count"], -x["change_pct"]))
    return {"top_by_change": top_by_change, "hot_concepts": hot_concepts[:top_n]}


# ---------- 5. 连板天梯（近 30 日趋势） ----------


def calc_ladder_trend(ladder: dict, days: int = 5) -> list:
    """从连板天梯提取最近 N 个交易日的梯队概况，用于看周期位置。

    天梯无入参、固定返回近 30 日，每天按板位给出最多 4 只代表股。
    这里只取"每天各板位数量 + 最高板"，就足够判断情绪高度是升是降。
    """
    series = []
    for day_item in (ladder.get("item") or [])[:days]:
        boards = day_item.get("boards") or {}
        dist = {}
        max_board = 0
        for key in BOARD_KEYS:
            stocks = boards.get(key) or []
            if stocks:
                dist[BOARD_LABEL[key]] = len(stocks)
                max_board = max(max_board, max(int(s.get("board_num") or 0) for s in stocks))
        series.append({"date": day_item.get("date"), "distribution": dist, "max_board": max_board})
    return series


# ---------- 历史对比（依赖上一交易日快照） ----------


def calc_yesterday_effect(prev_snapshot: dict | None, today_limit_up: list) -> dict | None:
    """赚钱效应：昨日涨停股今日的整体表现。

    A 股情绪的核心观测点——昨日涨停今天能不能赚钱，比今天涨停多少家更重要。

    实现方式：用昨日涨停名单里的代码，与今日全市场快照的涨跌幅匹配。
    """
    if not prev_snapshot:
        return None
    prev_pool = ((prev_snapshot.get("raw") or {}).get("limit_up")) or []
    if not prev_pool:
        return None
    prev_codes = {x.get("thscode"): x.get("name") for x in prev_pool if x.get("thscode")}
    today_map = {x.get("thscode"): x for x in today_limit_up}
    return {
        "prev_limit_up_count": len(prev_codes),
        "still_limit_up_count": len([c for c in prev_codes if c in today_map]),
        "still_limit_up_ratio_pct": _ratio(len([c for c in prev_codes if c in today_map]), len(prev_codes)),
    }


def calc_prev_day_comparison(prev_snapshot: dict | None, today: dict) -> dict | None:
    """与上一交易日的关键指标对比（环比变化）。"""
    if not prev_snapshot:
        return None
    prev_emotion = (prev_snapshot.get("indicators") or {}).get("emotion") or {}
    prev_breadth = (prev_snapshot.get("indicators") or {}).get("breadth") or {}
    cur_emotion = today.get("emotion") or {}
    cur_breadth = today.get("breadth") or {}

    def delta(key, cur, prev):
        if cur.get(key) is None or prev.get(key) is None:
            return None
        return round(cur[key] - prev[key], 2)

    return {
        "prev_trade_date": prev_snapshot.get("trade_date"),
        "limit_up_count_delta": delta("limit_up_count", cur_emotion, prev_emotion),
        "limit_down_count_delta": delta("limit_down_count", cur_emotion, prev_emotion),
        "limit_break_count_delta": delta("limit_break_count", cur_emotion, prev_emotion),
        "seal_rate_delta_pct": delta("seal_rate_pct", cur_emotion, prev_emotion),
        "max_board_delta": delta("max_consecutive_board", cur_emotion, prev_emotion),
        "up_ratio_delta_pct": delta("up_ratio_pct", cur_breadth, prev_breadth),
    }


# ---------- 汇总 ----------


def calc_style_verdict(emotion: dict, style: dict, breadth: dict) -> dict:
    """用确定性规则给风格一个客观初判（LLM 之后可以再解读，但基线由代码给）。

    规则是透明的启发式，不是投资建议；阈值可后续按回测调整。
    """
    reasons = []
    momentum = 0
    trend = 0

    if (emotion.get("consecutive_board_count") or 0) >= 8:
        momentum += 2
        reasons.append("连板家数较多，题材接力活跃")
    if (emotion.get("max_consecutive_board") or 0) >= 4:
        momentum += 1
        reasons.append("出现 4 板及以上高度，情绪偏强")
    if (style.get("early_limit_up_ratio_pct") or 0) >= 40:
        momentum += 1
        reasons.append("早盘封板占比高，资金一致性高")
    if (emotion.get("limit_down_count") or 0) >= 10:
        trend -= 1
        reasons.append("跌停家数偏多，存在亏钱效应")
    if (breadth.get("up_ratio_pct") or 0) >= 55:
        trend += 1
        reasons.append("上涨家数占优，普涨特征")
    if (breadth.get("up_ratio_pct") or 100) <= 35:
        trend -= 1

    if momentum >= 3 and momentum > trend:
        verdict = "连板/题材风格"
    elif trend >= 1 and trend >= momentum:
        verdict = "趋势/普涨风格"
    else:
        verdict = "风格不明/结构性行情"
    return {"verdict": verdict, "momentum_score": momentum, "trend_score": trend, "reasons": reasons}


def build_indicators(
    trade_date: str,
    limit_up: list,
    limit_down: list,
    limit_break: list,
    market_snapshot: list,
    ladder: dict,
    prev_snapshot: dict | None = None,
    concept_catalog: list | None = None,
    index_snapshot: list | None = None,
    prev_snapshots: list | None = None,
    breadth_as_of: str | None = None,
) -> dict:
    """组装当日全部指标。"""
    emotion = calc_emotion(limit_up, limit_down, limit_break)
    breadth = calc_breadth(market_snapshot, as_of=breadth_as_of, trade_date=trade_date)
    style = calc_style(limit_up)
    return {
        "trade_date": trade_date,
        "computed_at": _now_iso(),
        "emotion": emotion,
        "breadth": breadth,
        "style": style,
        "hot_sectors": calc_hot_sectors(limit_up),
        "chain_leaders": calc_chain_leaders(limit_up),
        "concept_strength": calc_concept_strength(
            concept_catalog or [], index_snapshot or [], limit_up, prev_snapshots
        ),
        "ladder_trend": calc_ladder_trend(ladder),
        "yesterday_effect": calc_yesterday_effect(prev_snapshot, limit_up),
        "prev_day_comparison": calc_prev_day_comparison(prev_snapshot, {"emotion": emotion, "breadth": breadth}),
        "style_verdict": calc_style_verdict(emotion, style, breadth),
    }
