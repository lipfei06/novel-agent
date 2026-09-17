"""M1 · F01 配置测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from novel_agent.config import ConfigError, list_profiles, load_config, load_genre_profile

MINIMAL_CONFIG = """\
genre: webnovel
projects: { root: "output/projects", data_root: "data/projects" }
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  cheap:    { model: "m-cheap", api_key_env: "K2", temperature: 0.2, max_tokens: 1024 }
memory: { short_window: 3 }
rag: { top_k: 6 }
token_budget: { write: 12000 }
library: { base_dir: "output/libraries" }
export: { epub: false }
"""


def _tmp_config(content: str = MINIMAL_CONFIG) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_config_defaults():
    cfg = load_config(_tmp_config())
    assert cfg.genre.id == "webnovel"
    assert cfg.genre.default_volumes > 0
    assert "creative" in cfg.tiers
    assert cfg.tier("creative").model == "m-creative"
    assert cfg.tier("cheap").max_tokens == 1024
    assert cfg.token_budget["write"] == 12000


def test_load_config_genre_override():
    cfg = load_config(_tmp_config(), genre="short_story")
    assert cfg.genre.id == "short_story"
    assert cfg.genre.default_volumes == 1


def test_missing_config_raises():
    missing = Path(tempfile.mkdtemp()) / "nope.yaml"
    try:
        load_config(missing)
    except ConfigError:
        return
    raise AssertionError("expected ConfigError")


def test_missing_llm_model_raises():
    bad = MINIMAL_CONFIG.replace("{ model: \"m-creative\", api_key_env: \"K1\" }", "{ api_key_env: \"K1\" }")
    try:
        load_config(_tmp_config(bad))
    except ConfigError:
        return
    raise AssertionError("expected ConfigError")


def test_unknown_tier_raises():
    cfg = load_config(_tmp_config())
    try:
        cfg.tier("nope")
    except ConfigError:
        return
    raise AssertionError("expected ConfigError")


def test_genre_profiles_loaded():
    profiles = list_profiles()
    assert {"webnovel", "literary", "short_story"} <= set(profiles)


def test_webnovel_profile_shape():
    p = load_genre_profile("webnovel")
    assert p.target_word_count == 1000000
    assert p.world_requirements
    assert p.red_lines
