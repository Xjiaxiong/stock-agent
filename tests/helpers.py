"""测试用的数据构造工具：字段与同花顺涨停池保持一致。"""


def stock(
    name: str,
    reason: str,
    board: int = 1,
    seal_time: str = "09:35",
    pct: float = 10.0,
    seal_money: float = 1e8,
    ticker: str = "000001",
    is_st: bool = False,
) -> dict:
    """造一条涨停股记录（只保留被测代码用到的字段）。"""
    return {
        "thscode": f"{ticker}.SZ",
        "ticker": ticker,
        "name": name,
        "is_st": is_st,
        "is_new": False,
        "last_price": 10.0,
        "price_change_ratio_pct": pct,
        "limit_up_time": seal_time,
        "limit_up_reason": reason,
        "continue_day_cnt": board,
        "seal_money": seal_money,
        "max_seal_money": seal_money,
    }


def quote(pct: float, turnover: float = 1e7) -> dict:
    """造一条全市场快照记录（测涨跌分布用）。"""
    return {"thscode": "000001.SZ", "price_change_ratio_pct": pct, "turnover": turnover}


def chain_by_sector(chains: list, sector: str) -> dict | None:
    return next((c for c in chains if c["sector"] == sector), None)


def chain_of(chains: list, leader_name: str) -> dict | None:
    """按龙头名找链。

    板块名是从涨停原因里抽出来的共享关键词（数据说了算），会随当天标签变体变化
    （"半导体硅片 + 半导体硅材料"可能抽成"半导体硅"），所以测试断言行为而不是标签。
    """
    return next((c for c in chains if c["leader"]["name"] == leader_name), None)


def names_of(chain: dict) -> list:
    """链上出现过的人名（龙头 + 次强 + 另一板别龙头 + 跟风）。"""
    rows = [chain["leader"], *(chain.get("peers") or [])]
    if chain.get("alt_leader"):
        rows.append(chain["alt_leader"])
    rows += chain.get("laggards") or []
    return [r["name"] for r in rows]
