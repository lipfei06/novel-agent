"""M1 · F03 数据模型测试。"""
from __future__ import annotations

from novel_agent.types import (
    Chapter,
    Character,
    Concept,
    ConsistencyIssue,
    Outline,
    SceneBlock,
    VolumePlan,
    WorldBible,
    WriterPacket,
)


def test_concept_defaults():
    c = Concept(title_idea="测试")
    assert c.genre == ""
    assert c.red_lines == []
    assert c.volumes == 1


def test_world_bible_defaults():
    w = WorldBible()
    assert w.geography == []
    assert w.glossary == []


def test_character_roundtrip():
    c = Character(id="c1", name="张三", role="protagonist")
    d = c.model_dump()
    assert d["role"] == "protagonist"
    assert Character(**d) == c


def test_outline_version_and_volumes():
    o = Outline(version=3, premise="立意", volumes=[VolumePlan(volume=1, chapter_count=10)])
    assert o.version == 3
    assert o.volumes[0].chapter_count == 10


def test_writer_packet_defaults():
    p = WriterPacket(volume=1, chapter=1)
    assert p.beats == []
    assert p.pov == ""


def test_chapter_scene_block():
    ch = Chapter(volume=1, chapter=2, title="测试章", scenes=[SceneBlock(id="s1", text="正文")])
    assert len(ch.scenes) == 1
    assert ch.scenes[0].paragraphs is None


def test_consistency_issue_defaults():
    i = ConsistencyIssue(description="x")
    assert i.severity == "medium"
    assert i.resolved is False


def test_all_models_serializable():
    for model in (Concept(), WorldBible(), Character(name="x"), Outline(), Chapter()):
        model.model_dump()
