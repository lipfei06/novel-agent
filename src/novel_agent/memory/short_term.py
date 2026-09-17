"""F09 短期记忆：最近 N 章正文窗口。"""
from __future__ import annotations

from typing import Any


def get_short_term(chapters: dict[str, Any], window: int = 3) -> str:
    """返回最近 window 章的正文（按 vol_ch 数字排序，截断到预算由调用方控制）。"""
    if not chapters:
        return ""
    keys = sorted(chapters.keys(), key=lambda k: [int(x) for x in k.split("_")])
    recent = keys[-window:]
    parts = []
    for key in recent:
        ch = chapters[key]
        scenes = ch.get("scenes", []) if isinstance(ch, dict) else getattr(ch, "scenes", [])
        text = "\n".join(s.get("text", "") if isinstance(s, dict) else s.text for s in scenes)
        parts.append(f"<chapter {key}>\n{text}\n</chapter>")
    return "\n\n".join(parts)
