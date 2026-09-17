"""M4 · F08 一致性检查 + auto-fix 测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.agents.consistency import MAX_AUTO_FIX, check_consistency, fix_issues
from novel_agent.config import load_config
from novel_agent.types import Chapter, SceneBlock

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
token_budget: { check: 8000 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def _chapter(*texts: str) -> Chapter:
    return Chapter(
        volume=1, chapter=1, title="测试",
        scenes=[SceneBlock(id=f"s{i+1}", heading=f"h{i+1}", text=t) for i, t in enumerate(texts)],
    )


def test_check_clean_chapter_no_issues():
    cfg = _cfg()
    report = check_consistency(_chapter("一切正常", "故事继续"), cfg)
    assert report.issues == []


def test_check_detects_fixable_issue():
    cfg = _cfg()
    report = check_consistency(_chapter("这里存在设定矛盾"), cfg)
    assert any(i.kind == "setting" and i.severity == "high" for i in report.issues)


def test_check_detects_human_only_issue():
    cfg = _cfg()
    report = check_consistency(_chapter("此处风格漂移"), cfg)
    assert any(i.kind == "style" for i in report.issues)


def test_auto_fix_resolves_fixable():
    cfg = _cfg()
    chapter = _chapter("存在设定矛盾的问题")
    report = check_consistency(chapter, cfg)
    chapter, report = fix_issues(report, chapter, cfg)
    assert report.auto_fix_attempts == 1
    assert not any(i.severity == "high" and not i.resolved for i in report.issues)
    assert "设定矛盾" not in chapter.scenes[0].text
    assert "设定一致" in chapter.scenes[0].text


def test_human_only_not_fixable():
    cfg = _cfg()
    chapter = _chapter("这段风格漂移")
    report = check_consistency(chapter, cfg)
    chapter, report = fix_issues(report, chapter, cfg)
    assert report.needs_human is True
    assert any(i.severity == "high" and not i.resolved for i in report.issues)
    assert "风格漂移" in chapter.scenes[0].text


def test_max_auto_fix_constant():
    assert MAX_AUTO_FIX == 3
