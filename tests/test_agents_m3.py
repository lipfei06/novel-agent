"""M3 · 写作链路 Agent 测试（卷细纲/章packet/正文，mock）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.agents.concept import generate_concept
from novel_agent.agents.outline import generate_outline
from novel_agent.agents.packet import generate_writer_packet
from novel_agent.agents.volume_plan import generate_volume_plans
from novel_agent.agents.write import generate_chapter
from novel_agent.config import load_config
from novel_agent.types import Chapter, VolumePlan, WriterPacket

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  writer:   { model: "m-writer", api_key_env: "K3" }
token_budget: { volume_plan: 8000, packet: 8000, write: 12000 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def test_volume_plans_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    o = generate_outline(c, None, [], cfg)
    plans = generate_volume_plans(o, cfg)
    assert plans
    assert all(isinstance(p, VolumePlan) for p in plans)
    assert all(p.chapter_count > 0 for p in plans)
    assert len(plans) == c.volumes


def test_writer_packet_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    o = generate_outline(c, None, [], cfg)
    plans = generate_volume_plans(o, cfg)
    packet = generate_writer_packet(plans[0], o, [], 1, cfg)
    assert isinstance(packet, WriterPacket)
    assert packet.chapter == 1
    assert packet.beats
    assert packet.hook


def test_write_chapter_mock():
    cfg = _cfg()
    c = generate_concept({"idea": "x"}, cfg)
    o = generate_outline(c, None, [], cfg)
    plans = generate_volume_plans(o, cfg)
    packet = generate_writer_packet(plans[0], o, [], 1, cfg)
    ch = generate_chapter(packet, cfg)
    assert isinstance(ch, Chapter)
    assert len(ch.scenes) >= 2
    assert all(s.id and s.text for s in ch.scenes)


def test_write_chapter_with_context():
    cfg = _cfg()
    packet = WriterPacket(volume=1, chapter=1, title="第一章", goal="目标")
    ch = generate_chapter(packet, cfg, memory_context="前文记忆", rag_context="设定")
    assert isinstance(ch, Chapter)


def test_scoped_outline_hides_future():
    """防剧透：裁剪后只含当前卷，隐藏结局/未来卷/伏笔回收点/核心转折。"""
    from novel_agent.agents.packet import _scoped_outline

    outline = {
        "version": 1,
        "premise": "立意",
        "structure": "起承转合",
        "ending": "大结局：主角登基",
        "core_events": ["第5卷大反转"],
        "foreshadowing": [{"seed": "旧玉佩", "payoff": "第30章揭晓"}],
        "volumes": [
            {"volume": 1, "title": "卷1", "event_arc": ["卷一弧"], "foreshadow_seed": ["玉佩"],
             "foreshadow_payoff": ["第20章收"], "ending_hook": "卷1钩子"},
            {"volume": 2, "title": "卷2", "event_arc": ["卷二弧"], "foreshadow_payoff": []},
        ],
    }
    scoped = _scoped_outline(outline, volume=1)
    assert "ending" not in scoped
    assert "core_events" not in scoped
    assert "foreshadowing" not in scoped
    # 只保留当前卷，且该卷的 payoff 被隐藏
    assert len(scoped["volumes"]) == 1
    assert scoped["volumes"][0]["volume"] == 1
    assert "foreshadow_payoff" not in scoped["volumes"][0]
    assert scoped["volumes"][0]["foreshadow_seed"] == ["玉佩"]
