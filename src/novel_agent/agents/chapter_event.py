"""章节事件智能体：从正文中提炼结构化的章节事件（情节/人物/伏笔/关系/主题）。

生成的 ChapterEvent 是各领域状态更新的统一数据源——
情节状态、人物状态卡、伏笔账本、关系图谱、主题进展都从这里驱动。
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from novel_agent.config import Config

from . import is_mock


# ---- 输出 Schema ----

class PlotEvent(BaseModel):
    event: str = ""
    status: str = "completed"  # completed | in_progress | pending


class CharacterChange(BaseModel):
    name: str = ""
    field: str = ""  # location / mood / knowledge / goal_progress
    change: str = ""


class ForeshadowItem(BaseModel):
    desc: str = ""
    status: str = "planted"  # planted | resolved


class RelationChange(BaseModel):
    a: str = ""
    b: str = ""
    from_state: str = ""
    to_state: str = ""


class ChapterEventData(BaseModel):
    chapter: str = ""
    volume: int = 0
    plot_events: list[PlotEvent] = Field(default_factory=list)
    character_changes: list[CharacterChange] = Field(default_factory=list)
    foreshadow_planted: list[str] = Field(default_factory=list)
    foreshadow_resolved: list[str] = Field(default_factory=list)
    relationship_changes: list[RelationChange] = Field(default_factory=list)
    theme_progress: str = ""


SYSTEM_PROMPT = """你是小说的连续性管理员。阅读本章正文，提炼结构化的章节事件：
1. plot_events：本章推进或完成的主要情节事件（2-4 条，对照卷事件弧）；
2. character_changes：主要角色的状态变化（位置/情绪/认知/目标进展），只包含确实变化的；
3. foreshadow_planted：本章新埋下的伏笔（一句话描述）；
4. foreshadow_resolved：本章回收的伏笔（引用此前埋下的描述）；
5. relationship_changes：人物关系的变化（从什么状态变为什么状态）；
6. theme_progress：本章对主题的推进（一句话）。
只输出 JSON，字段名和类型严格匹配。"""


def extract_chapter_event(
    chapter_data: dict,
    volume: int,
    cfg: Config,
    prev_event: dict | None = None,
) -> dict:
    """从正文中提炼章节事件（真实=cheap 模型；mock=确定性输出）。"""
    if is_mock():
        return _mock_event(chapter_data, volume)

    from novel_agent.llm import build_messages, get_chat_model, invoke_structured

    user = f"本章正文：{json.dumps(chapter_data, ensure_ascii=False)}\n"
    if prev_event:
        user += f"上一章事件（供参考，保持连续性）：{json.dumps(prev_event, ensure_ascii=False)}\n"
    user += "请提炼本章的结构化事件。"
    messages = build_messages(SYSTEM_PROMPT, user, "research", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=ChapterEventData)
    event = result.model_dump()
    event["chapter"] = str(chapter_data.get("chapter", ""))
    event["volume"] = int(chapter_data.get("volume", volume))
    event["word_count"] = sum(len(s.get("text") or "") for s in chapter_data.get("scenes") or [])
    return event


def _mock_event(chapter_data: dict, volume: int) -> dict:
    title = chapter_data.get("title", "")
    return {
        "chapter": str(chapter_data.get("chapter", "")),
        "volume": volume,
        "plot_events": [{"event": f"{title}：推进主线", "status": "completed"}],
        "character_changes": [],
        "foreshadow_planted": [],
        "foreshadow_resolved": [],
        "relationship_changes": [],
        "theme_progress": "",
        "word_count": sum(len(s.get("text") or "") for s in chapter_data.get("scenes") or []),
    }
