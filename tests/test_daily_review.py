"""报告与分享卡片的数据契约测试。

前端只负责排版，所有字段名都对着一份"约定"来（build_card 输出 → api.ts 类型 → Canvas 绘制）。
字段一旦被改名或漏掉，页面会静默变成空白/undefined，所以这里把契约钉死。
"""

import indicators as ind
import daily_review as dr

from helpers import stock

CARD_KEYS = {
    "trade_date",
    "weekday",
    "note",
    "stage",
    "confidence",
    "style",
    "summary",
    "metrics",
    "reasons",
    "sectors",
    "leaders",
    "tactics",
    "risk",
    "breadth_stale",
    "prev_trade_date",
    "source",
    "disclaimer",
}

LEADER_KEYS = {
    "name",
    "sector",
    "board",
    "seal_time",
    "seal_money",
    "limit_type",
    "features",
    "why",
    "alt_leader",
    "alt_limit_type",
    "peers",
    "laggards",
}


def limit_up_fixture() -> list:
    return [
        stock("中晶科技", "半导体硅片+订单充足", board=2, seal_time="09:32", seal_money=1.07e8),
        stock("有研硅", "半导体硅材料", pct=20.0, ticker="688432", seal_time="10:09", seal_money=2.15e8),
        stock("闽东电力", "海上风电+福建国资", board=6, seal_time="09:36", seal_money=4.3e7),
    ]


def make_snapshot(limit_up: list) -> dict:
    """按 daily_snapshot.py 的结构造一份快照（只跑纯函数，不碰网络）。"""
    return {
        "trade_date": "2026-09-16",
        "raw": {"limit_up": limit_up, "limit_down": [], "limit_break": []},
        "indicators": ind.build_indicators(
            "2026-09-16",
            limit_up,
            [],
            [],
            [],
            {},
            concept_catalog=[],
            index_snapshot=[],
            prev_snapshots=[],
        ),
    }


def llm_result() -> dict:
    """LLM 的结构化输出（形状与 daily_review 的 prompt 约定一致）。"""
    return {
        "market_phase": {"stage": "修复期", "confidence": "高", "reasons": ["涨停 3 家，情绪修复"]},
        "style": {"verdict": "连板题材", "explanation": "高度集中在少数个股"},
        "emotion_summary": "情绪从冰点修复。",
        "hot_sectors": [{"name": "半导体", "strength": "强", "logic": "材料链共振", "sustainability": "看龙头"}],
        "tactics": {"position": "3-5成", "approach": "低吸为主", "do": ["盯龙头承接"], "avoid": ["追高"]},
        "opportunities": [],
        "risks": ["高位断板风险"],
    }


def test_build_card_contract():
    snapshot = make_snapshot(limit_up_fixture())
    card = dr.build_card("2026-09-16", "", llm_result(), snapshot)

    assert set(card.keys()) == CARD_KEYS
    assert card["trade_date"] == "2026-09-16"
    assert card["weekday"] == "周三"
    assert len(card["metrics"]) == 4
    assert card["leaders"], "卡片必须带核心龙头模块"
    for leader in card["leaders"]:
        assert set(leader.keys()) == LEADER_KEYS
        assert leader["name"]
        assert leader["limit_type"] in {"10cm", "20cm", "30cm", "5cm"}
        assert leader["features"], "特征词不能为空"
        assert "同链" in leader["why"]


def test_card_leaders_use_the_same_ranking_as_indicators():
    """卡片和报告必须共用一套口径：卡片的龙头 = indicators 算出来的第一名。"""
    limit_up = limit_up_fixture()
    snapshot = make_snapshot(limit_up)
    card = dr.build_card("2026-09-16", "", llm_result(), snapshot)
    chains = ind.calc_chain_leaders(limit_up)

    for leader, chain in zip(card["leaders"], chains):
        assert leader["name"] == chain["leader"]["name"]
        assert leader["sector"] == chain["sector"]


def test_card_leaders_split_10cm_and_20cm():
    """半导体链：10cm 龙头上榜，同时给出 20cm 龙头（弹性方向）。"""
    card = dr.build_card("2026-09-16", "", llm_result(), make_snapshot(limit_up_fixture()))
    semi = next((l for l in card["leaders"] if l["name"] == "中晶科技"), None)

    assert semi is not None
    assert semi["name"] == "中晶科技"
    assert semi["limit_type"] == "10cm"
    assert semi["alt_limit_type"] == "20cm"
    assert semi["alt_leader"].startswith("有研硅")


def test_render_report_contains_all_sections():
    snapshot = make_snapshot(limit_up_fixture())
    report = dr.render_report("2026-09-16", llm_result(), snapshot, note="")

    for title in ("## 一、", "## 二、", "## 三、", "## 四、", "## 五、", "## 六、", "## 七、"):
        assert title in report
    assert "### 核心龙头" in report
    assert "特征词：" in report
    assert "### 板块点评" in report
    assert "20cm 龙头" in report or "10cm 龙头" in report


def test_render_report_keeps_date_note():
    """自动落到其他交易日时必须在报告里留痕，避免以后翻报告误以为是当天的盘面。"""
    snapshot = make_snapshot(limit_up_fixture())
    report = dr.render_report("2026-09-15", llm_result(), snapshot, note="9/15 数据未生成，已回退到 9/14")

    assert "9/15 数据未生成" in report


def test_empty_pool_does_not_break_card_or_report():
    """没有涨停股（极端行情/数据缺失）时，不能崩，也不能出现空的核心龙头小节。"""
    snapshot = make_snapshot([])
    card = dr.build_card("2026-09-16", "", llm_result(), snapshot)
    report = dr.render_report("2026-09-16", llm_result(), snapshot, note="")

    assert card["leaders"] == []
    assert "### 核心龙头" not in report
    assert "## 三、热点板块与持续性" in report
