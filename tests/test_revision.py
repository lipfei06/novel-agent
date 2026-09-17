"""M3 · F10 定点修改引擎测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.config import load_config
from novel_agent.revision import build_edit_context, edit_scene, locate_paragraph, locate_scene, render_diff
from novel_agent.types import Chapter, SceneBlock

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
token_budget: { edit: 4000 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def _chapter() -> Chapter:
    return Chapter(
        volume=1, chapter=1, title="测试章",
        scenes=[
            SceneBlock(id="s1", heading="开场", text="开场正文AAAA"),
            SceneBlock(id="s2", heading="冲突", text="冲突正文BBBB"),
            SceneBlock(id="s3", heading="钩子", text="钩子正文CCCC"),
        ],
    )


def test_locate_scene():
    ch = _chapter()
    idx, scene = locate_scene(ch, "s2")
    assert idx == 1
    assert scene.heading == "冲突"
    assert locate_scene(ch, "nope") is None


def test_locate_paragraph():
    scene = SceneBlock(id="s1", text="x", paragraphs=["第一段", "第二段"])
    assert locate_paragraph(scene, "二段") == (1, "第二段")
    assert locate_paragraph(SceneBlock(id="s1", text="x"), "x") is None  # 未分段


def test_edit_scene_only_target_changes():
    cfg = _cfg()
    ch = _chapter()
    merged, new_text = edit_scene(ch, "s2", "改缓和些", cfg)
    assert "改缓和些" in new_text
    assert merged.scenes[1].text == new_text
    # 未修改场景字节级不变
    assert merged.scenes[0].text == "开场正文AAAA"
    assert merged.scenes[2].text == "钩子正文CCCC"
    # 场景顺序与数量不变
    assert [s.id for s in merged.scenes] == ["s1", "s2", "s3"]


def test_edit_scene_missing_raises():
    cfg = _cfg()
    try:
        edit_scene(_chapter(), "nope", "x", cfg)
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_build_edit_context_minimal():
    cfg = _cfg()
    ctx = build_edit_context(_chapter(), "s2", cfg, rag_context="设定检索结果")
    assert "开场正文AAAA" in ctx      # s1（前邻）
    assert "冲突正文BBBB" in ctx      # s2（目标）
    assert "钩子正文CCCC" in ctx      # s3（后邻）
    assert "设定检索结果" in ctx
    assert "<reference>" in ctx


def test_render_diff():
    d = render_diff("第一行\n第二行\n", "第一行\n第二行（改）\n")
    assert "修改前" in d
    assert "修改后" in d
    assert "第二行（改）" in d
