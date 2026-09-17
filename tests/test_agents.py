"""M2 · F05 阶段 Agent 测试（mock 模式，无需 API key）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.agents.character import generate_characters
from novel_agent.agents.concept import generate_concept
from novel_agent.agents.outline import generate_outline
from novel_agent.agents.world import generate_world
from novel_agent.config import load_config
from novel_agent.types import Character, Concept, Outline, WorldBible

MINIMAL_CONFIG = """\
genre: webnovel
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000 }
library: { personality_top_k: 3 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def test_generate_concept_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "修仙少年逆天改命"}, cfg)
    assert isinstance(c, Concept)
    assert "修仙少年逆天改命" in c.title_idea
    assert c.genre == "webnovel"
    assert c.volumes == cfg.genre.default_volumes
    assert c.red_lines  # 来自题材红线


def test_generate_concept_empty_idea():
    cfg = _cfg()
    c = generate_concept({}, cfg)
    assert c.title_idea


def test_generate_world_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    w = generate_world(c, cfg)
    assert isinstance(w, WorldBible)
    assert w.geography and w.factions


def test_generate_characters_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    w = generate_world(c, cfg)
    chars = generate_characters(c, w, cfg)
    assert len(chars) >= 2
    assert all(isinstance(ch, Character) for ch in chars)
    assert any(ch.role == "protagonist" for ch in chars)


def test_generate_outline_mock_volume_count():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    w = generate_world(c, cfg)
    chars = generate_characters(c, w, cfg)
    o = generate_outline(c, w, chars, cfg)
    assert isinstance(o, Outline)
    assert len(o.volumes) == c.volumes


def test_outline_serializable():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    w = generate_world(c, cfg)
    o = generate_outline(c, w, [], cfg)
    d = o.model_dump()
    assert d["version"] == 1
