"""指标层单测。

indicators.py 是整个项目的"事实层"：报告和卡片里的数字、龙头排名都由它产出。
这里锁住三类最容易回归的口径：
  1. 情绪/广度等基础指标的计算公式；
  2. 板别（10cm / 20cm / 30cm / ST）判定；
  3. 核心龙头的同链合并、链内排序、一只票只归一条链。
"""

import indicators as ind

from helpers import chain_by_sector, chain_of, names_of, quote, stock


# ---------- 1. 情绪周期 ----------


def test_emotion_counts_and_seal_rate():
    limit_up = [
        stock("甲", "半导体硅片", board=1),
        stock("乙", "半导体设备", board=2),
        stock("丙", "风电", board=3),
    ]
    limit_break = [stock("炸板股", "风电")]
    limit_down = [stock("跌停股", "风电")]

    emo = ind.calc_emotion(limit_up, limit_down, limit_break)

    assert emo["limit_up_count"] == 3
    assert emo["limit_down_count"] == 1
    assert emo["limit_break_count"] == 1
    # 封板率 = 封住 / (封住 + 炸板)，不是"涨停 / 全市场"
    assert emo["seal_rate_pct"] == 75.0
    assert emo["first_board_count"] == 1
    assert emo["consecutive_board_count"] == 2
    assert emo["max_consecutive_board"] == 3
    assert emo["ladder_distribution"] == {"3板": 1, "2板": 1}


def test_emotion_empty_pool_does_not_crash():
    emo = ind.calc_emotion([], [], [])
    assert emo["limit_up_count"] == 0
    assert emo["max_consecutive_board"] == 0
    # 分母为 0 时 _ratio 返回 None（不编造 0%），展示层负责渲染成 "—"
    assert emo["seal_rate_pct"] is None


# ---------- 2. 市场活跃度 ----------


def test_breadth_ratio_and_avg():
    rows = [quote(10), quote(-3), quote(0), quote(2)]
    br = ind.calc_breadth(rows, as_of="2026-09-16", trade_date="2026-09-16")

    assert br["sampled_stocks"] == 4
    assert br["up_count"] == 2 and br["down_count"] == 1 and br["flat_count"] == 1
    assert br["up_ratio_pct"] == 50.0
    assert br["avg_change_pct"] == 2.25
    assert br["is_stale"] is False


def test_breadth_marks_stale_when_snapshot_is_another_day():
    """全市场快照接口只返回最新数据：日期对不上必须打 is_stale，避免张冠李戴。"""
    br = ind.calc_breadth([quote(1)], as_of="2026-09-16", trade_date="2026-09-15")
    assert br["is_stale"] is True


# ---------- 3. 板别判定 ----------


def test_limit_type_by_price_change():
    assert ind._limit_type(stock("主板", "x", pct=10.0)) == "10cm"
    assert ind._limit_type(stock("创业板", "x", pct=20.0, ticker="300123")) == "20cm"
    assert ind._limit_type(stock("北交所", "x", pct=30.0, ticker="830799")) == "30cm"
    assert ind._limit_type(stock("ST股", "x", pct=5.0, is_st=True)) == "5cm"


def test_limit_type_falls_back_to_ticker():
    """接口没给涨幅时（缺失/新上市），用代码段兜底。"""
    assert ind._limit_type(stock("科创板", "x", pct=None, ticker="688111")) == "20cm"
    assert ind._limit_type(stock("创业板", "x", pct=None, ticker="301001")) == "20cm"
    assert ind._limit_type(stock("主板", "x", pct=None, ticker="600000")) == "10cm"


# ---------- 4. 核心龙头：同链合并 ----------


def test_same_chain_tags_merge_into_one_sector():
    """半导体硅片 / 半导体设备 / 半导体材料 是同一条产业链，应该合成一条链。"""
    limit_up = [
        stock("中晶科技", "半导体硅片+订单充足", board=2, seal_time="09:32", seal_money=1.07e8),
        stock("德尔未来", "半导体设备", board=2, seal_time="10:36"),
        stock("有研硅", "半导体硅材料+硅片涨价", pct=20.0, ticker="688432", seal_time="10:09"),
    ]
    chains = ind.calc_chain_leaders(limit_up)

    chain = chain_by_sector(chains, "半导体")
    assert chain is not None, [c["sector"] for c in chains]
    assert chain["stock_count"] == 3
    assert chain["max_board"] == 2
    assert set(names_of(chain)) == {"中晶科技", "德尔未来", "有研硅"}


def test_generic_words_do_not_merge_unrelated_themes():
    """业绩增长 / 中报增长 这类通用词不能把不相干的票缝成一条假主线。"""
    limit_up = [
        stock("甲", "业绩增长", seal_money=3e8),
        stock("乙", "中报增长", seal_money=2e8),
    ]
    chains = ind.calc_chain_leaders(limit_up)

    for chain in chains:
        assert not {"甲", "乙"} <= set(names_of(chain))


# ---------- 5. 核心龙头：链内排序 ----------


def test_same_board_prefers_10cm_over_20cm():
    """题材梯度完整时，主板那只才是资金定价的主锚：同身位让 10cm 领先。"""
    limit_up = [
        stock("创业板票", "半导体硅片", board=2, pct=20.0, ticker="300123", seal_time="09:25"),
        stock("主板票", "半导体设备", board=2, seal_time="09:40"),
    ]
    chain = chain_by_sector(ind.calc_chain_leaders(limit_up), "半导体")

    assert chain["leader"]["name"] == "主板票"
    assert chain["leader"]["limit_type"] == "10cm"
    # 另一板别的龙头也单独给出来（20cm 弹性方向）
    assert chain["alt_leader"]["name"] == "创业板票"
    assert chain["alt_leader"]["limit_type"] == "20cm"


def test_higher_board_still_wins_over_board_tier():
    """身位优先：20cm 的 3 板不该排在 10cm 首板后面。"""
    limit_up = [
        stock("创业板三板", "半导体硅片", board=3, pct=20.0, ticker="300123", seal_time="10:30"),
        stock("主板首板", "半导体设备", seal_time="09:30"),
    ]
    chain = chain_by_sector(ind.calc_chain_leaders(limit_up), "半导体")

    assert chain["leader"]["name"] == "创业板三板"
    assert chain["alt_leader"]["name"] == "主板首板"
    assert chain["alt_leader"]["limit_type"] == "10cm"


def test_late_first_board_chain_has_no_leader():
    """尾盘才封的首板是跟风资金；整条链都这样时不该报成龙头。"""
    limit_up = [
        stock("跟风甲", "冷门概念", seal_time="13:05"),
        stock("跟风乙", "冷门概念", seal_time="14:20"),
    ]
    chains = ind.calc_chain_leaders(limit_up)

    assert all(c["sector"] != "冷门概念" for c in chains)


def test_laggard_listed_on_an_otherwise_strong_chain():
    limit_up = [
        stock("龙头股", "半导体硅片", board=2, seal_time="09:32"),
        stock("跟风股", "半导体设备", seal_time="13:12"),
    ]
    chain = chain_by_sector(ind.calc_chain_leaders(limit_up), "半导体")

    assert chain["leader"]["name"] == "龙头股"
    assert [r["name"] for r in chain["laggards"]] == ["跟风股"]
    assert all(r["name"] != "跟风股" for r in chain["peers"])


def test_features_carry_limit_up_reason():
    """特征词就是同花顺涨停原因标签，卡片/报告上用来回答"靠什么涨"。"""
    limit_up = [stock("中晶科技", "半导体硅片+订单充足+股权激励", board=2, seal_time="09:32")]
    chain = chain_of(ind.calc_chain_leaders(limit_up), "中晶科技")

    assert chain is not None
    assert chain["leader"]["features"] == ["半导体硅片", "订单充足", "股权激励"]


# ---------- 6. 一只票只归一条链 ----------


def test_stock_belongs_to_single_strongest_chain():
    """同一只票挂多个题材时，只能出现在最强的那条链里，避免重复当龙头。"""
    limit_up = [
        stock("跨题材股", "半导体硅片+光刻胶配套试剂", board=2, seal_time="09:30"),
        stock("半导体票", "半导体设备", seal_time="10:00"),
        stock("光刻机票", "光刻机", seal_time="10:10"),
    ]
    chains = ind.calc_chain_leaders(limit_up)

    appearances = [name for chain in chains for name in names_of(chain)]
    assert appearances.count("跨题材股") == 1
    # 光刻链的龙头被别人领走，就不再单独展示（不能把副将当龙头）
    assert chain_by_sector(chains, "光刻") is None


# ---------- 7. 题材广度 ----------


def test_hot_sectors_rank_by_breadth_then_height():
    limit_up = [
        stock("甲", "光通信"),
        stock("乙", "光通信"),
        stock("丙", "光通信"),
        stock("丁", "固态电池", board=4),
    ]
    sectors = {s["tag"]: s for s in ind.calc_hot_sectors(limit_up)}

    assert sectors["光通信"]["stocks_count"] == 3
    assert sectors["固态电池"]["max_board"] == 4
    # 广度优先：3 只票的题材排在 1 只票的高标题材前面
    assert sectors["光通信"]["score"] > sectors["固态电池"]["score"]


# ---------- 8. 跨日对比 ----------


def test_prev_day_comparison_and_yesterday_effect():
    # 赚钱效应按 thscode 匹配，测试数据要给不同代码
    today = [stock("甲", "半导体硅片", ticker="000001"), stock("乙", "半导体设备", ticker="000002", board=2)]
    prev_limit_up = [
        stock("甲", "x", ticker="000001"),
        stock("乙", "x", ticker="000002"),
        stock("丙", "x", ticker="000003"),
    ]
    prev_snapshot = {
        "trade_date": "2026-09-15",
        "indicators": {
            "emotion": ind.calc_emotion(prev_limit_up, [], []),
            "breadth": ind.calc_breadth([quote(1), quote(-1)], as_of="2026-09-15", trade_date="2026-09-15"),
        },
        "raw": {"limit_up": prev_limit_up},
    }
    today_emotion = ind.calc_emotion(today, [], [])
    today_breadth = ind.calc_breadth([quote(2)], as_of="2026-09-16", trade_date="2026-09-16")

    compare = ind.calc_prev_day_comparison(
        prev_snapshot, {"emotion": today_emotion, "breadth": today_breadth}
    )
    effect = ind.calc_yesterday_effect(prev_snapshot, today)

    assert compare["prev_trade_date"] == "2026-09-15"
    assert compare["limit_up_count_delta"] == -1
    assert effect["prev_limit_up_count"] == 3
    assert effect["still_limit_up_count"] == 2
    assert effect["still_limit_up_ratio_pct"] == round(2 / 3 * 100, 2)
