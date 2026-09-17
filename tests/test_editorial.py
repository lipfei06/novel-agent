"""M5 · F12 审校 Agent 测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.agents.editorial import generate_editorial_report
from novel_agent.config import load_config
from novel_agent.types import EditorialReport

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  editor:   { model: "m-editor", api_key_env: "K4" }
token_budget: { editorial: 10000 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def test_editorial_report_mock():
    cfg = _cfg()
    report = generate_editorial_report({}, {"1_1": {}}, None, cfg)
    assert isinstance(report, EditorialReport)
    assert report.scope == "final"
    assert report.comments
    assert report.fix_list == []


def test_editorial_reports_chapter_count():
    cfg = _cfg()
    chapters = {"1_1": {}, "1_2": {}, "1_3": {}}
    report = generate_editorial_report({}, chapters, None, cfg)
    assert "3" in report.comments
