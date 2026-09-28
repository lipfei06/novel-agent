"""Skill 层测试：加载、降级、注入位置、agent 接线（mock 模式）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.skills import SkillLoader, skill_text

STAGES = ["stage0", "stage1", "stage2", "stage3", "stage3b"]


def test_loader_loads_all_setup_skills():
    loader = SkillLoader()
    meta = {m["stage"]: m for m in loader.describe()}
    assert set(meta) == set(STAGES)  # 恰好五个设定阶段
    for s in STAGES:
        text = loader.load(s)
        assert text.startswith("<skill name="), s
        assert "手艺指导" in text  # 包装说明
        assert len(text) > 200, f"{s} 正文过短"


def test_loader_missing_stage_degrades():
    loader = SkillLoader()
    assert loader.load("stage5") == ""  # 未建文件的阶段 → 空串
    assert skill_text("stage5") == ""


def test_loader_bad_file_is_skipped():
    d = Path(tempfile.mkdtemp())
    (d / "broken.md").write_text("---\napply_stage: [broken\n", encoding="utf-8")  # 坏 YAML
    (d / "ok.md").write_text(
        "---\nname: ok\ndescription: d\napply_stage: stage0\n---\n正文内容。\n",
        encoding="utf-8",
    )
    loader = SkillLoader(base=d)
    assert loader.load("stage0") != ""  # 好文件正常加载
    assert len(loader.describe()) == 1


def test_loader_no_frontmatter_is_ignored():
    d = Path(tempfile.mkdtemp())
    (d / "plain.md").write_text("没有 frontmatter 的普通 markdown", encoding="utf-8")
    assert SkillLoader(base=d).describe() == []


def test_build_messages_skill_position():
    from novel_agent.llm import build_messages

    msgs = build_messages(
        "你是角色定义。", "用户输入", "concept", {"concept": 99999},
        style="风格指令内容", skill='<skill name="x">\n手艺要点\n</skill>',
    )
    system = msgs[0]["content"]
    assert system.index("角色定义") < system.index("<skill") < system.index("风格指令内容")
    # 不带 skill 时与旧行为一致
    msgs2 = build_messages("sys", "usr", "concept", {"concept": 99999})
    assert msgs2[0]["content"] == "sys"


def test_agent_wiring_concept_includes_skill():
    """generate_concept 的 messages 里应包含 stage0 skill 正文。"""
    import tempfile as tf

    from unittest.mock import patch

    import novel_agent.agents.concept as concept_mod
    from novel_agent.config import load_config
    from novel_agent.types import Concept

    captured = {}

    def fake_invoke(llm, messages, schema=None, **kw):
        captured["messages"] = messages
        return Concept(genre="short_story", title_idea="t", logline="l")

    d = tf.mkdtemp()
    (Path(d) / "config.yaml").write_text(
        "genre: short_story\nllm:\n  creative: { model: m, api_key_env: K }\n"
        "token_budget: { concept: 99999 }\n",
        encoding="utf-8",
    )
    with patch.object(concept_mod, "invoke_structured", fake_invoke), \
         patch.object(concept_mod, "is_mock", lambda: False):
        concept_mod.generate_concept({"idea": "测试立意"}, load_config(Path(d) / "config.yaml"))
    system = captured["messages"][0]["content"]
    assert "concept-craft" in system
    assert "一句话立意三要素" in system
