"""事实校验与用量日志的测试。

这两个模块都是"防幻觉/可观测"的兜底网，必须自己先站得住：
- verify：LLM 写进报告的数字要能在指标里找到，编的数字要被抓出来；
- llm_client：调用记日志，summary 能给出成功率/耗时/token。
"""

import json

import llm_client
import verify


def indicators_fixture() -> dict:
    return {
        "emotion": {"limit_up_count": 89, "seal_rate_pct": 89.0, "max_consecutive_board": 6},
        "breadth": {"up_ratio_pct": 76.0, "avg_change_pct": 1.5},
        "prev_day_comparison": {"limit_up_count_delta": 57, "seal_rate_delta_pct": 31.86},
        "concept_strength": {"hot_concepts": [{"limit_up_count": 3, "max_board": 6, "streak_days": 5}]},
    }


def test_verify_accepts_numbers_present_in_indicators():
    result = {
        "emotion_summary": "涨停 89 家，封板率 89.0%，上涨占比 76.0%，平均涨幅 1.5%。",
        "market_phase": {"reasons": ["环比涨停 +57 家"]},
    }
    check = verify.verify_result(result, indicators_fixture())

    assert check["checked"] == 5
    assert check["matched"] == 5
    assert check["ratio_pct"] == 100.0
    assert check["issues"] == []


def test_verify_flags_number_without_source():
    """模型编一个快照里没有的数字：必须被标记出来。"""
    result = {"emotion_summary": "涨停 89 家，但昨日涨停股延续率高达 88.8%。"}
    check = verify.verify_result(result, indicators_fixture())

    assert check["checked"] == 2
    assert check["matched"] == 1
    assert check["issues"] == ["88.8%"]


def test_verify_allows_previous_day_value_derived_from_delta():
    """报告里常见的"昨日 X 家"= 今日 X − 环比 delta，要能推出来，不能误报。"""
    result = {"emotion_summary": "涨停 89 家（环比 +57 家），说明昨日是 32 家。"}
    check = verify.verify_result(result, indicators_fixture())

    assert check["issues"] == []
    assert check["matched"] == check["checked"]


def test_verify_ignores_non_statistical_numbers():
    """不带统计单位的数字（"2-3板补位"）不参与校验，避免误伤正常叙述。"""
    result = {"tactics": {"do": ["关注 2 板接力机会"]}}
    check = verify.verify_result(result, indicators_fixture())

    assert check["checked"] == 0
    assert check["ratio_pct"] is None


def test_verify_skips_threshold_phrases():
    """阈值/目标型表述（"回升至 60% 以上""不足 20%"）不是对今日数据的断言。"""
    result = {
        "tactics": {
            "do": ["关注封板率是否回升至 60% 以上", "避免在上涨占比不足 20% 时重仓"],
        }
    }
    check = verify.verify_result(result, indicators_fixture())

    assert check["checked"] == 0
    assert check["issues"] == []


def test_format_note_mentions_ratio_and_suspects():
    note = verify.format_note(
        {"checked": 10, "matched": 9, "ratio_pct": 90.0, "issues": ["88.8%"]}
    )
    assert "10 处统计数字" in note
    assert "90.0%" in note
    assert "88.8%" in note


def test_llm_usage_summary_reads_jsonl(tmp_path, monkeypatch):
    log = tmp_path / "usage.jsonl"
    log.write_text(
        "\n".join(
            json.dumps(entry, ensure_ascii=False)
            for entry in [
                {"source": "daily_review", "ok": True, "latency_ms": 1000, "total_tokens": 3000},
                {"source": "analysis", "ok": True, "latency_ms": 2000, "total_tokens": 1000},
                {"source": "daily_review", "ok": False, "latency_ms": 3000, "error": "timeout"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_USAGE_LOG", str(log))

    summary = llm_client.summary()

    assert summary["calls"] == 3
    assert summary["ok"] == 2 and summary["failed"] == 1
    assert summary["success_rate_pct"] == 66.67
    assert summary["avg_latency_ms"] == 2000
    assert summary["max_latency_ms"] == 3000
    assert summary["total_tokens"] == 4000
    assert summary["by_source"]["daily_review"]["calls"] == 2
    assert len(summary["recent"]) == 3


def test_llm_usage_summary_is_safe_when_log_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG", str(tmp_path / "nope.jsonl"))
    summary = llm_client.summary()

    assert summary["calls"] == 0
    assert summary["success_rate_pct"] is None
