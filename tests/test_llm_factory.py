"""M1 · F02 LLM 工厂与 prompt 守卫测试（仅构造/校验，不调用真实 API）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from langchain_openai import ChatOpenAI

from novel_agent.config import ConfigError, load_config
from novel_agent.llm import (
    TokenBudgetExceeded,
    build_messages,
    estimate_tokens,
    get_chat_model,
    get_model_name,
    guard_tokens,
)

MINIMAL_CONFIG = """\
genre: webnovel
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  cheap:    { model: "m-cheap", api_key_env: "K2", temperature: 0.2, max_tokens: 1024 }
token_budget: { write: 12000, edit: 4000 }
"""


def _cfg() -> object:
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def test_get_chat_model_returns_openai_model():
    cfg = _cfg()
    model = get_chat_model("creative", cfg)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "m-creative"


def test_get_model_name():
    cfg = _cfg()
    assert get_model_name("cheap", cfg) == "m-cheap"


def test_unknown_tier_raises():
    cfg = _cfg()
    try:
        get_chat_model("nope", cfg)
    except ConfigError:
        return
    raise AssertionError("expected ConfigError")


def test_estimate_tokens():
    assert estimate_tokens("你好世界") == 4
    assert estimate_tokens("") == 1


def test_guard_within_budget():
    total = guard_tokens("write", {"system": "short", "user": "hi"}, {"write": 12000})
    assert total > 0


def test_guard_over_budget_raises():
    big = "x" * 10000
    try:
        guard_tokens("write", {"user": big}, {"write": 100})
    except TokenBudgetExceeded as exc:
        assert exc.stage == "write"
        return
    raise AssertionError("expected TokenBudgetExceeded")


def test_build_messages_shape():
    msgs = build_messages("sys", "usr", "write", {"write": 12000})
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
