"""定点修改引擎：selector 定位场景/段落。"""
from __future__ import annotations

from novel_agent.types import Chapter, SceneBlock


def locate_scene(chapter: Chapter, scene_id: str) -> tuple[int, SceneBlock] | None:
    """返回 (索引, 场景块)；不存在返回 None。"""
    for idx, scene in enumerate(chapter.scenes):
        if scene.id == scene_id:
            return idx, scene
    return None


def locate_paragraph(scene: SceneBlock, target: str) -> tuple[int, str] | None:
    """预留段落级：target 为段落前缀/关键字，返回 (段落索引, 段落文本)。"""
    if scene.paragraphs is None:
        return None
    for idx, para in enumerate(scene.paragraphs):
        if target in para:
            return idx, para
    return None
