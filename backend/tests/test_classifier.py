"""DeepSeek 精标测试：结构化输出解析校验、成本开关（不依赖真实网络）。"""
import json
from types import SimpleNamespace

import pytest

from app.crawler.classifier import (
    CostLimitExceeded,
    CostTracker,
    LlmResult,
    parse_llm_result,
)


# ---- parse_llm_result ----

def test_parse_valid_ai4se():
    text = json.dumps(
        {
            "is_ai4se": True,
            "topics": ["code_repair", "testing"],
            "summary_zh": "用大模型自动修复代码缺陷并生成测试用例。",
            "confidence": 0.95,
        }
    )
    r = parse_llm_result(text)
    assert isinstance(r, LlmResult)
    assert r.is_ai4se is True
    assert r.topics == ["code_repair", "testing"]
    assert r.summary_zh
    assert 0 <= r.confidence <= 1


def test_parse_valid_non_ai4se():
    """非 AI4SE：topics 置空，摘要可缺省。"""
    r = parse_llm_result(
        json.dumps({"is_ai4se": False, "summary_zh": "", "confidence": 0.9})
    )
    assert r is not None
    assert r.is_ai4se is False
    assert r.topics == []


def test_parse_invalid_json():
    assert parse_llm_result("not json at all {") is None
    assert parse_llm_result("") is None


def test_parse_missing_fields():
    assert parse_llm_result("{}") is None
    assert parse_llm_result(json.dumps({"is_ai4se": True})) is None  # 缺 topics/summary
    assert parse_llm_result(json.dumps({"is_ai4se": "yes", "topics": ["x"]})) is None


def test_parse_ai4se_without_summary():
    assert (
        parse_llm_result(
            json.dumps({"is_ai4se": True, "topics": ["other"], "confidence": 0.8})
        )
        is None
    )


def test_parse_filters_invalid_topic_slugs():
    r = parse_llm_result(
        json.dumps(
            {
                "is_ai4se": True,
                "topics": ["code_repair", "not_a_real_topic", "testing"],
                "summary_zh": "摘要",
                "confidence": 0.8,
            }
        )
    )
    assert r.topics == ["code_repair", "testing"]


def test_parse_confidence_out_of_range():
    text = json.dumps(
        {"is_ai4se": False, "summary_zh": "", "confidence": 1.5}
    )
    assert parse_llm_result(text) is None


# ---- CostTracker ----

def _usage(prompt=1000, completion=500):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def test_cost_accumulates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.crawler.classifier.CostTracker._state_file",
        lambda self: tmp_path / "llm_cost.json",
    )
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_input_usd_per_1m", 0.27)
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_output_usd_per_1m", 1.10)
    tracker = CostTracker(limit_usd=5.0)
    cost = tracker.update(_usage(1_000_000, 1_000_000))
    # 输入 1M tokens * 0.27 + 输出 1M * 1.10 = 1.37
    assert abs(cost - 1.37) < 1e-9
    assert abs(tracker.total_usd - 1.37) < 1e-9
    assert tracker.calls == 1


def test_cost_limit_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.crawler.classifier.CostTracker._state_file",
        lambda self: tmp_path / "llm_cost.json",
    )
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_input_usd_per_1m", 0.27)
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_output_usd_per_1m", 1.10)
    tracker = CostTracker(limit_usd=1.0)
    with pytest.raises(CostLimitExceeded):
        tracker.update(_usage(10_000_000, 0))  # 2.7 USD > 1.0


def test_cost_persist_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.crawler.classifier.CostTracker._state_file",
        lambda self: tmp_path / "llm_cost.json",
    )
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_input_usd_per_1m", 0.27)
    monkeypatch.setattr("app.crawler.classifier.settings.llm_price_output_usd_per_1m", 1.10)

    t1 = CostTracker(limit_usd=5.0)
    t1.update(_usage(1_000_000, 0))  # 0.27 USD
    t1.save()

    t2 = CostTracker(limit_usd=5.0)
    assert abs(t2.total_usd - 0.27) < 1e-9  # 从文件恢复


def test_cost_restored_over_limit_raises(monkeypatch, tmp_path):
    """历史累计已超限：构造时直接抛错（防止恢复后继续烧钱）。"""
    (tmp_path / "llm_cost.json").write_text(json.dumps({"total_usd": 9.9}))
    monkeypatch.setattr(
        "app.crawler.classifier.CostTracker._state_file",
        lambda self: tmp_path / "llm_cost.json",
    )
    with pytest.raises(CostLimitExceeded):
        CostTracker(limit_usd=5.0)
