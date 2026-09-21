"""人物状态提取：每章写完后，为 main 角色提取增量状态（次要/路人不处理）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured
from novel_agent.types import Chapter, Character, chapter_plaintext
from novel_agent.types.character_state import CharacterState, CharacterStateEntry
from pydantic import BaseModel, Field

from . import is_mock

SYSTEM_PROMPT = """你是一位人物状态分析师。读取本章正文，为**主要角色（main）**更新状态卡。
字段：所在位置、情绪、身体/伤势、资源、关键关系现状、知道/不知道什么、目标进展、
**状态（在世/死亡/退场/蜕变）**、**当前弧光阶段**（对照该角色的成长弧光判断当前处于哪一阶段）。
仅处理 main 角色；次要/路人不在此更新。状态要承接上一章，只记录本章的变化与现状。"""


class CharacterStateList(BaseModel):
    """列表包装：langchain json_mode 不支持裸 list[...] schema。"""

    entries: list[CharacterStateEntry] = Field(default_factory=list)


def extract_character_states(
    chapter: Chapter | dict,
    characters: list[Character] | list[dict],
    previous: CharacterState | dict | None,
    cfg: Config,
    author_hints: list[dict] | None = None,
) -> CharacterState:
    """返回更新后的完整状态集（previous + 本章增量）。

    author_hints：写手智能体的状态变化提案（作者写作意图），作为提取参考注入。
    """
    chapter_data = chapter.model_dump() if hasattr(chapter, "model_dump") else dict(chapter)
    mains = [c for c in characters if (c.get("tier") if isinstance(c, dict) else c.tier) == "main"]
    prev = previous.model_dump() if hasattr(previous, "model_dump") else (previous or {})
    prev_entries = prev.get("entries", [])

    if not mains:
        return CharacterState(entries=[CharacterStateEntry(**e) for e in prev_entries])

    if is_mock():
        return _mock_state(chapter_data, mains, prev_entries, int(cfg.genre.chapters_per_volume or 6))

    user = (
        f"{chapter_plaintext(chapter_data)}\n"
        f"主要角色：{json.dumps([{k: c[k] for k in ('id', 'name', 'role') if k in c} for c in mains], ensure_ascii=False)}\n"
        f"上一章状态：{json.dumps(prev_entries, ensure_ascii=False)}\n"
    )
    if author_hints:
        user += f"作者写本章时的意图性状态变化（优先参考，结合正文核正）：{json.dumps(author_hints, ensure_ascii=False)}\n"
    user += "请输出本章更新后的主要角色状态。"
    messages = build_messages(SYSTEM_PROMPT, user, "state_update", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=CharacterStateList)

    # 合并：previous 中不在本次输出的保留；本次输出按 character_id 覆盖
    updated: dict[str, CharacterStateEntry] = {e["character_id"]: CharacterStateEntry(**e) for e in prev_entries}
    for e in result.entries:
        e.last_chapter = int(chapter_data.get("chapter", 0))
        updated[e.character_id] = e
    return CharacterState(entries=list(updated.values()))


def _mock_state(chapter: dict, mains: list[dict], prev: list[dict], total_chapters: int = 6) -> CharacterState:
    ch = int(chapter.get("chapter", 0))
    # 弧光大致按章节进度推进（start→mid→end）
    if total_chapters <= 0:
        arc_stage = ""
    elif ch <= total_chapters / 3:
        arc_stage = "start"
    elif ch <= total_chapters * 2 / 3:
        arc_stage = "mid"
    else:
        arc_stage = "end"
    updated: dict[str, CharacterStateEntry] = {e["character_id"]: CharacterStateEntry(**e) for e in prev}
    for c in mains:
        eid = c.get("id", "")
        if eid not in updated:
            updated[eid] = CharacterStateEntry(character_id=eid, name=c.get("name", ""), tier="main")
        updated[eid].last_chapter = ch
        updated[eid].goal_progress = f"推进至第{ch}章（示例）"
        if arc_stage:
            updated[eid].arc_stage = arc_stage
        updated[eid].status = updated[eid].status or "active"
    return CharacterState(entries=list(updated.values()))
