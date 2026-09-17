"""F13 组装导出：Markdown / TXT / EPUB。"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from novel_agent.config import Config
from novel_agent.storage import ProjectPaths

if TYPE_CHECKING:
    from novel_agent.graph.state import NovelState


def _chapter_key(k: str) -> list[int]:
    """章节键 "vol_ch" → 排序用数字对；非法键容错为 [0,0] 排到最后。"""
    try:
        parts = str(k).split("_")
        return [int(parts[0]), int(parts[1])]
    except (ValueError, IndexError):
        return [1 << 30, 1 << 30]


def export_markdown(chapters: dict, meta: dict) -> str:
    parts = [f"# {meta.get('title', '未命名')}", ""]
    if meta.get("genre"):
        parts.append(f"> 题材：{meta['genre']}")
        parts.append("")
    for key in sorted(chapters.keys(), key=_chapter_key):
        ch = chapters[key]
        parts.append(f"## 第{ch.get('volume')}卷 · 第{ch.get('chapter')}章 {ch.get('title', '')}")
        for scene in ch.get("scenes", []):
            heading = scene.get("heading") or ""
            parts.append(f"### {heading}")
            parts.append(scene.get("text", ""))
            parts.append("")
    return "\n".join(parts)


def export_txt(chapters: dict, meta: dict) -> str:
    parts = [meta.get("title", "未命名"), "=" * 20, ""]
    for key in sorted(chapters.keys(), key=_chapter_key):
        ch = chapters[key]
        parts.append(f"第{ch.get('volume')}卷 第{ch.get('chapter')}章 {ch.get('title', '')}")
        for scene in ch.get("scenes", []):
            parts.append(scene.get("text", ""))
            parts.append("")
    return "\n".join(parts)


def _slug(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]", "_", title)[:40] or "novel"


def export_epub(chapters: dict, meta: dict, out: Path) -> Path:
    """最小合法 EPUB3：zip 结构（mimetype/container/opf/xhtml）。"""
    title = meta.get("title", "未命名")
    slug = _slug(title)
    chapter_xhtml: list[str] = []
    spine: list[str] = []
    for idx, key in enumerate(sorted(chapters.keys(), key=_chapter_key)):
        ch = chapters[key]
        cid = f"chap{idx + 1}"
        body = "".join(f"<h2>{s.get('heading','')}</h2><p>{s.get('text','')}</p>" for s in ch.get("scenes", []))
        chapter_xhtml.append(
            f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>{ch.get("title","")}</title></head><body>{body}</body></html>'
        )
        spine.append(cid)
    manifest = "".join(
        f'<item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>' for cid in spine
    )
    spine_items = "".join(f'<itemref idref="{cid}"/>' for cid in spine)
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">{slug}</dc:identifier>'
        f'<dc:title>{title}</dc:title><dc:language>zh</dc:language></metadata>'
        f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>{manifest}</manifest>'
        f'<spine>{spine_items}</spine></package>'
    )
    nav = (
        '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>目录</title></head><body><nav epub:type="toc">'
        + "".join(f'<li><a href="{cid}.xhtml">{cid}</a></li>' for cid in spine)
        + "</nav></body></html>"
    )
    container = (
        '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml", nav)
        for cid, xhtml in zip(spine, chapter_xhtml):
            zf.writestr(f"OEBPS/{cid}.xhtml", xhtml)
    return out


def assemble_final(state: NovelState, cfg: Config, paths: ProjectPaths) -> list[str]:
    """组装并写出最终产物到 final_dir，返回文件路径列表。"""
    chapters = state.get("chapters") or {}
    meta = {"title": state.get("title", "未命名"), "genre": state.get("genre", "")}
    paths.final_dir.mkdir(parents=True, exist_ok=True)

    md = paths.final_dir / f"{_slug(meta['title'])}.md"
    md.write_text(export_markdown(chapters, meta), encoding="utf-8")

    txt = paths.final_dir / f"{_slug(meta['title'])}.txt"
    txt.write_text(export_txt(chapters, meta), encoding="utf-8")

    result = [str(md), str(txt)]
    if cfg.export.get("epub", False):
        epub = export_epub(chapters, meta, paths.final_dir / f"{_slug(meta['title'])}.epub")
        result.append(str(epub))
    return result
