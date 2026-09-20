"""同花顺金融数据 API 的盘面取数层。

这一层只负责"把原始数据取回来"，不做任何业务判断：
- 统一鉴权（X-api-key，读项目根目录 .env 的 HITHINK_FINANCE_API_KEY）
- 统一分页（涨停池/跌停池/炸板池/全市场快照都可能多页）
- 统一日期（毫秒时间戳，Asia/Shanghai 零点）
- 统一错误（业务错误码转成带上下文的 RuntimeError）

上层 indicators.py 只消费这里返回的原始列表，保持"取数 / 计算"分离。
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE_URL = "https://fuyao.aicubes.cn"
TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# A 股收盘时间（上海时间），换算成"当天第几分钟"以便和 now 直接比。
# 收盘前"今天"这个交易日还没走完：能复盘的只有上一个交易日。
MARKET_CLOSE_MINUTE = 15 * 60

# 同花顺对同一账号有动态限流（HTTP 429 / 业务码 4001）。
# 这里统一做请求节流与退避重试，避免上层逻辑里到处写 sleep。
_MIN_INTERVAL = 0.35  # 两次请求之间至少间隔秒数
_last_request_at = 0.0


class DataNotReady(RuntimeError):
    """目标交易日的数据尚未生成（上游返回 code=3002）。

    为什么单独建一个异常：盘面接口在"当天还没产生数据"时行为不一致
    （涨停池可能静默回退到上一交易日、跌停池直接返回空），
    如果把它们当成真实的 0，就会产出错误的复盘报告。
    """


def _load_dotenv() -> None:
    """向上查找 .env 并注入环境变量（与 backend/tools.py 保持一致的行为）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        env_path = os.path.join(current, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


_load_dotenv()


def _api_key() -> str:
    key = os.environ.get("HITHINK_FINANCE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 HITHINK_FINANCE_API_KEY，请在项目根目录 .env 中配置")
    return key


def _request(path: str, params: dict, timeout: int = 20) -> dict:
    """单次请求，返回响应信封里的 data。带节流与退避重试。"""
    global _last_request_at
    query = {k: v for k, v in params.items() if v is not None}
    url = BASE_URL + path + ("?" + urllib.parse.urlencode(query) if query else "")
    request = urllib.request.Request(url, headers={"X-api-key": _api_key()}, method="GET")

    last_error = None
    for attempt in range(4):
        # 节流：保证两次真实请求之间有时间间隔
        wait = _MIN_INTERVAL - (time.time() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        try:
            _last_request_at = time.time()
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            code = body.get("code")
            if code == 0:
                return body.get("data") or {}
            if code == 3002:  # 数据未就绪：明确抛错，绝不静默当成空
                raise DataNotReady(f"{path} 数据未就绪：{body.get('message')}")
            if code in (4001,) or (isinstance(code, int) and code >= 5000):
                last_error = RuntimeError(f"[{code}] {body.get('message')}")
                time.sleep(1.2 * (attempt + 1))
                continue
            raise RuntimeError(f"{path} 返回错误 [{code}] {body.get('message')}")
        except RuntimeError:
            raise
        except Exception as e:  # HTTP 429 / 网络异常
            last_error = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"{path} 调用失败: {last_error}")


# ---------- 日期工具 ----------


def to_date_ms(day: str) -> int:
    """'2026-09-11' -> 该日上海时区零点的毫秒时间戳。"""
    d = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ)
    return int(d.timestamp() * 1000)


def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def previous_weekday(day: str) -> str:
    """简单回退到上一个工作日（不含法定节假日；真正的交易日判断用日历接口）。"""
    d = date.fromisoformat(day) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def fetch_trading_days() -> list:
    """近一年交易日列表（升序，格式 YYYY-MM-DD）。用于校验目标日期是不是交易日。"""
    data = _request("/api/a-share/calendar/trading-days", {})
    out = []
    for item in data.get("item") or []:
        raw = str(item.get("date") or "")
        if len(raw) == 8:  # yyyyMMdd -> yyyy-MM-dd
            out.append(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")
    return out


def now_shanghai() -> datetime:
    """当前上海时间（用于判断当日是否已收盘）。"""
    return datetime.now(TZ)


# ---------- 数据就绪校验 ----------


def latest_ready_trade_date(ladder: dict | None = None) -> str:
    """上游当前已生成盘面数据的最近交易日。

    为什么必须有这个基准：涨停池接口在"目标日数据还没生成"时**静默回退**到
    上一交易日（跌停池则直接返回空），例如 9/15 凌晨请求 9/15 会拿回 9/14 的
    55 只涨停。若不先校验，快照就会张冠李戴地把昨天的盘面写成今天。

    连板天梯返回近 30 个交易日，date_list 首项即最新可用交易日，用它当基准。
    ladder 参数允许调用方复用已经取回的天梯数据，避免重复请求触发限流。
    """
    data = ladder if ladder is not None else fetch_limit_up_ladder()
    window = data.get("window") or {}
    days = [str(d) for d in (window.get("date_list") or []) if d]
    return max(days) if days else ""


def is_trading_day(day: str) -> bool:
    """用官方交易日历判断（日历接口异常时放行，避免误伤正常取数）。"""
    try:
        days = fetch_trading_days()
    except Exception:
        return True
    return day in days if days else True


def ensure_data_ready(day: str, ladder: dict | None = None) -> None:
    """目标交易日没有可用的盘面数据时抛 DataNotReady。

    这是"取数层"唯一一处带业务含义的判断：宁可让上层拿到明确错误，也不能让
    上层把上一交易日的数据当成目标交易日的数据。
    """
    if not is_trading_day(day):
        raise DataNotReady(f"{day} 不是交易日，无法生成盘面复盘")

    latest = latest_ready_trade_date(ladder)
    if not latest or day <= latest:
        return

    if day == today_str():
        reason = "当日盘面数据要到收盘后才会生成，请收盘后再跑或改用最近交易日"
    else:
        reason = "该交易日的盘面数据尚未生成"
    raise DataNotReady(f"{day} 的盘面数据尚不可用（{reason}；上游最新可用交易日为 {latest}）")


def previous_trading_day(day: str, days: list | None = None) -> str:
    """交易日历里不晚于 day 的最近交易日（day 本身是交易日就返回它自己）。"""
    try:
        calendar = days if days is not None else fetch_trading_days()
    except Exception:
        return day
    candidates = [d for d in calendar if d <= day]
    return max(candidates) if candidates else day


def last_completed_trade_date(
    reference: str | None = None,
    *,
    now: datetime | None = None,
    calendar: list | None = None,
) -> str:
    """交易日历里"已经收盘"的、不晚于 reference 的最近交易日。

    关键在"已经收盘"：A 股 15:00 收盘前，当天这个交易日还没走完，能复盘的只有
    上一个交易日（9/15 早上 9 点前点复盘 → 9/14）。收盘后当天才算可用。

    注意不要只看上游有没有数据：上游在盘中就会开始吐当天的涨停池/天梯，
    那些是"正在进行的当天"，收盘前拿来做复盘等于用半天的数据下结论。
    """
    now = now or now_shanghai()
    today = now.strftime("%Y-%m-%d")
    days = calendar if calendar is not None else fetch_trading_days()
    reference = (reference or today).strip() or today

    if now.hour * 60 + now.minute >= MARKET_CLOSE_MINUTE:
        latest_closed = previous_trading_day(today, days)  # 今天是交易日就是今天
    else:
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        latest_closed = previous_trading_day(yesterday, days)

    return previous_trading_day(min(reference, latest_closed), days)


def resolve_trade_date(day: str | None = None) -> tuple[str, str]:
    """把"用户请求的日期"解析成"真正要复盘的交易日"，返回 (交易日, 说明)。

    为什么需要：用户点"复盘"时通常是当天，但当天盘面数据要到收盘后才有
    （9/15 早上 9 点前点复盘，能复盘的只有 9/14）。这时与其报错，不如自动
    落到最近可用交易日，并把替换原因明确告诉用户（说明为空串 = 没做替换）。

    规则，按优先级：
      1. 没传日期 → 今天；
      2. 日期比今天还晚 → 报错（那个交易日还没到）；
      3. 收盘前（含周末/节假日）→ 回退到最近一个"已经收盘"的交易日；
      4. 那天上游还没生成数据（偶尔收盘后要等一会儿）→ 再退到上游最新可用交易日。
    """
    today = today_str()
    target = (day or "").strip() or today

    if target > today:
        raise DataNotReady(f"{target} 还没到，无法复盘（今天是 {today}）")

    notes = []
    completed = last_completed_trade_date(target)
    if completed and completed != target:
        if not is_trading_day(target):
            notes.append(f"{target} 不是交易日，已改用最近交易日 {completed}")
        elif target == today:
            notes.append(
                f"今日（{today}）尚未收盘，盘面数据要等收盘后才完整，"
                f"已改用最近已收盘的交易日 {completed}"
            )
        else:
            notes.append(f"{target} 尚未收盘或不是交易日，已改用最近交易日 {completed}")
        target = completed

    ladder = fetch_limit_up_ladder()
    latest = latest_ready_trade_date(ladder)
    if latest and target > latest:
        notes.append(f"{target} 的盘面数据上游还没生成，已改用最近可用交易日 {latest}")
        target = latest

    return target, "；".join(notes)


# ---------- 原始取数 ----------


def _fetch_paged(path: str, day: str, page_size: int = 200, extra: dict | None = None) -> list:
    """按分页取完整列表（涨停池/跌停池/炸板池共用）。"""
    items, page = [], 1
    while True:
        params = {"date_ms": to_date_ms(day), "page": page, "size": page_size}
        if extra:
            params.update(extra)
        data = _request(path, params)
        batch = data.get("item") or []
        items.extend(batch)
        pagination = data.get("pagination") or {}
        total_pages = pagination.get("pages") or 1
        if page >= total_pages or not batch:
            break
        page += 1
    return items


def fetch_limit_up_pool(day: str) -> list:
    """涨停/连板股票池（含连板天数、封单额、涨停时间、涨停原因）。"""
    return _fetch_paged(
        "/api/a-share/special-data/limit-up-pool",
        day,
        extra={"sort_field": "continue_day_cnt", "sort_dir": "desc"},
    )


def fetch_limit_down_pool(day: str) -> list:
    """跌停股票池。"""
    return _fetch_paged("/api/a-share/special-data/limit-down-pool", day)


def fetch_limit_break_pool(day: str) -> list:
    """炸板股票池（曾涨停但未封住的股票）。"""
    return _fetch_paged("/api/a-share/special-data/limit-break-pool", day)


def fetch_limit_up_ladder() -> dict:
    """连板天梯：近 30 个交易日的连板梯队矩阵（无入参）。"""
    return _request("/api/a-share/special-data/limit-up-ladder", {})


def fetch_anomalies(tag_codes: str | None = None) -> list:
    """当日个股异动原因（含关键词，可用于题材聚类）。"""
    data = _request(
        "/api/a-share/special-data/anomaly-analysis-list",
        {"tag_codes": tag_codes},
    )
    return data.get("item") or []


def fetch_hot_stocks(kind: str = "hot", hours: int = 24) -> list:
    """同花顺热榜：kind='hot' 热股榜 / kind='skyrocket' 飙升榜。"""
    path = (
        "/api/a-share/special-data/hot-stock-list"
        if kind == "hot"
        else "/api/a-share/special-data/skyrocket-list"
    )
    data = _request(path, {"hours": hours})
    return data.get("item") or []


def fetch_market_snapshot(sample_step: int = 4, page_size: int = 200) -> tuple:
    """全市场行情快照（用于涨跌家数分布）。

    接口单页最多 200 条，全市场约 5000+ 只。sample_step 控制采样步长：
    每隔 sample_step 页取一页（step=1 为全量，step=4 约取 1/4 样本），
    用较少请求估算涨跌分布，避免一次复盘打太多接口触发限流。

    重要：该接口**只返回最新快照**，不支持下钻历史日期（传 date_ms 会被忽略），
    因此历史交易日的涨跌分布无法回填。返回 (items, as_of_iso)：as_of 为数据
    就绪时间，上层用它判断"这份分布到底属于哪一天"。
    """
    items, offset, step_pages = [], 0, max(1, sample_step)
    as_of_ms = None
    while True:
        data = _request(
            "/api/a-share/prices/snapshot",
            {"limit": page_size, "offset": offset},
        )
        batch = data.get("item") or []
        items.extend(batch)
        if as_of_ms is None and data.get("timestamp"):
            as_of_ms = data["timestamp"]
        if len(batch) < page_size:
            break
        offset += page_size * step_pages
    as_of = None
    if as_of_ms:
        as_of = datetime.fromtimestamp(as_of_ms / 1000, tz=TZ).strftime("%Y-%m-%d")
    return items, as_of


def fetch_index_catalog(tag: str = "cn_concept") -> list:
    """同花顺指数清单。tag: cn_concept(概念) / industry(行业) / region / tszs。"""
    data = _request("/api/a-share-index/catalog/ths-index-list", {"tag": tag})
    return data.get("item") or []


def fetch_index_snapshot(thscodes: list) -> list:
    """指数/板块行情快照，用于板块强度排序。"""
    if not thscodes:
        return []
    items = []
    for i in range(0, len(thscodes), 100):  # 单次上限 100
        chunk = thscodes[i:i + 100]
        data = _request(
            "/api/a-share-index/prices/snapshot",
            {"thscodes": ",".join(chunk)},
        )
        items.extend(data.get("item") or [])
    return items
