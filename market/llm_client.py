"""DeepSeek 调用客户端：统一重试、超时，并把每次调用记成一条 JSONL。

为什么单独抽一层：
- 复盘（market/daily_review.py）和个股研究（backend/graph.py）原本各写了一份调用逻辑，
  重试次数、超时、报错文案容易各漂各的；
- 出问题时需要能回答"哪一次调用、耗时多久、烧了多少 token、成功没有"，
  而不是只看到一句"LLM 调用失败"。日志默认写 market/logs/llm-usage.jsonl
  （可用 LLM_USAGE_LOG 覆盖），同时通过 /api/metrics 暴露汇总。

写日志失败一律吞掉：观测不能反过来把主流程搞挂（serverless 只读文件系统也会走到这里）。
"""

import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


def log_path() -> Path:
    """用量日志位置。每次读环境变量，方便测试与部署时改目录。"""
    override = os.environ.get("LLM_USAGE_LOG", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "logs" / "llm-usage.jsonl"


def _load_dotenv() -> None:
    """向上找 .env 注入环境变量（与 market/data/hithink.py、backend/tools.py 同一约定）。

    复盘链路平时靠 import 链顺带加载 .env；直接调这个客户端时不能依赖那个副作用。
    """
    current = Path(__file__).resolve().parent
    for _ in range(6):
        env_path = current / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            except OSError:
                pass
            return
        if current.parent == current:
            break
        current = current.parent


def record(entry: dict) -> None:
    """追加一行用量日志；任何异常都不向外抛。"""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def call(
    messages: list,
    *,
    source: str = "unknown",
    max_tokens: int = 3000,
    retries: int = 2,
    timeout: int = 180,
) -> str:
    """调用 DeepSeek（OpenAI 兼容接口），失败重试，返回正文文本。"""
    _load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在项目根目录 .env 中配置")

    url = os.environ.get("DEEPSEEK_API_URL", DEFAULT_API_URL)
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    body = json.dumps(payload).encode("utf-8")
    prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
    started = time.time()
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage") or {}
            record(
                {
                    "ts": datetime.now(CN_TZ).isoformat(timespec="seconds"),
                    "source": source,
                    "model": model,
                    "ok": True,
                    "attempt": attempt + 1,
                    "latency_ms": int((time.time() - started) * 1000),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "prompt_chars": prompt_chars,
                    "response_chars": len(content),
                }
            )
            return content
        except Exception as exc:  # 网络抖动 / 限流 / 5xx 都在这里重试
            last_error = exc
            if attempt < retries:
                time.sleep(attempt + 1)

    record(
        {
            "ts": datetime.now(CN_TZ).isoformat(timespec="seconds"),
            "source": source,
            "model": model,
            "ok": False,
            "attempt": retries + 1,
            "latency_ms": int((time.time() - started) * 1000),
            "prompt_chars": prompt_chars,
            "error": str(last_error),
        }
    )
    raise RuntimeError(f"LLM 调用失败（{source}）: {last_error}")


def summary(limit: int = 2000) -> dict:
    """聚合用量日志：调用次数、成功率、耗时、token，以及最近几次调用。"""
    path = log_path()
    empty = {
        "log": str(path),
        "calls": 0,
        "ok": 0,
        "failed": 0,
        "success_rate_pct": None,
        "avg_latency_ms": None,
        "max_latency_ms": None,
        "total_tokens": 0,
        "by_source": {},
        "recent": [],
    }
    if not path.exists():
        return empty

    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f.readlines()[-limit:]:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        return empty
    if not entries:
        return empty

    ok = [e for e in entries if e.get("ok")]
    by_source: dict = {}
    for entry in entries:
        bucket = by_source.setdefault(
            entry.get("source") or "unknown", {"calls": 0, "ok": 0, "total_tokens": 0}
        )
        bucket["calls"] += 1
        bucket["ok"] += 1 if entry.get("ok") else 0
        bucket["total_tokens"] += int(entry.get("total_tokens") or 0)

    latencies = [int(e.get("latency_ms") or 0) for e in entries]
    return {
        **{k: v for k, v in empty.items() if k not in ("by_source", "recent")},
        "calls": len(entries),
        "ok": len(ok),
        "failed": len(entries) - len(ok),
        "success_rate_pct": round(len(ok) / len(entries) * 100, 2),
        "avg_latency_ms": int(sum(latencies) / len(latencies)),
        "max_latency_ms": max(latencies),
        "total_tokens": sum(int(e.get("total_tokens") or 0) for e in entries),
        "by_source": by_source,
        "recent": entries[-5:],
    }
