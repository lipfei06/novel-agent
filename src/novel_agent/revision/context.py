"""定点修改引擎：context 最小上下文装配（目标场景 ± 1 + 预算）。"""
from __future__ import annotations

from novel_agent.config import Config
from novel_agent.types import Chapter


def build_edit_context(chapter: Chapter, scene_id: str, cfg: Config, rag_context: str = "") -> str:
    """装配修改场景的最小上下文：目标场景 ± 1 个相邻场景。

    绝不含整章，保证 token 最小化；rag_context 为检索到的相关设定（可选）。
    """
    parts: list[str] = []
    scene_ids = [s.id for s in chapter.scenes]
    try:
        idx = scene_ids.index(scene_id)
    except ValueError:
        raise KeyError(scene_id) from None

    lo = max(0, idx - 1)
    hi = min(len(chapter.scenes), idx + 2)
    for s in chapter.scenes[lo:hi]:
        tag = "← 待修改" if s.id == scene_id else ""
        parts.append(f"<scene id={s.id} {tag}>\n{s.text}\n</scene>")
    if rag_context:
        parts.append(f"<reference>\n{rag_context}\n</reference>")
    return "\n\n".join(parts)
