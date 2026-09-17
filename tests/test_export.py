"""M5 · F13 组装导出测试（MD/TXT/EPUB）。"""
from __future__ import annotations

import zipfile
from pathlib import Path

from novel_agent.export import export_epub, export_markdown, export_txt

META = {"title": "测试小说", "genre": "short_story"}
CHAPTERS = {
    "1_1": {
        "volume": 1, "chapter": 1, "title": "第一章",
        "scenes": [{"id": "s1", "heading": "开场", "text": "第一段正文"}, {"id": "s2", "heading": "钩子", "text": "悬念出现"}],
    },
    "1_2": {
        "volume": 1, "chapter": 2, "title": "第二章",
        "scenes": [{"id": "s1", "heading": "发展", "text": "第二段正文"}],
    },
}


def test_export_markdown_structure():
    md = export_markdown(CHAPTERS, META)
    assert "# 测试小说" in md
    assert "## 第1卷 · 第1章 第一章" in md
    assert "第一段正文" in md
    assert "第二章" in md
    # 顺序：第1章在前
    assert md.index("第一章") < md.index("第二章")


def test_export_txt_structure():
    txt = export_txt(CHAPTERS, META)
    assert "测试小说" in txt
    assert "第1卷 第1章 第一章" in txt
    assert "悬念出现" in txt


def test_export_epub_valid_zip():
    out = Path(__import__("tempfile").mkdtemp()) / "test.epub"
    p = export_epub(CHAPTERS, META, out)
    assert p.exists()
    with zipfile.ZipFile(p) as zf:
        names = zf.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert any(n.endswith(".xhtml") for n in names)
        assert zf.read("mimetype").decode() == "application/epub+zip"


def test_export_epub_chapter_count():
    import tempfile

    out = Path(tempfile.mkdtemp()) / "t.epub"
    export_epub(CHAPTERS, META, out)
    with zipfile.ZipFile(out) as zf:
        xhtmls = [n for n in zf.namelist() if n.startswith("OEBPS/") and n.endswith(".xhtml")]
        assert len(xhtmls) == 3  # nav + 2 章
