"""路人自动升级：识别本章反复出现的未建档角色，建议升为次要角色并建档。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured
from novel_agent.types import Character, Chapter
from pydantic import BaseModel, Field

from . import is_mock

SYSTEM_PROMPT = """你是人物档案管理员。阅读本章正文，找出【反复出现、但尚未建档】的有名字/有辨识度的角色
（例如多次出场、有台词、推动情节的配角），将它们升级为次要角色（tier=supporting）并建立简要档案。
规则：
- 只在主角团的背景/路人角色里找；真正一次性跑龙套的不要
- 给每人一个稳定 id 与姓名；档案只需：动机、一句外貌关键特征、出身（简要）
- 若没有这样的角色，返回空数组"""


class CharacterArchive(BaseModel):
    """列表包装：langchain json_mode 不支持裸 list[...] schema。"""

    items: list[Character] = Field(default_factory=list)


def extract_recurring_characters(
    chapter: Chapter | dict,
    existing: list[Character] | list[dict],
    cfg: Config,
) -> list[Character]:
    """返回本章应新增建档的次要角色（mock 模式返回空）。"""
    chapter_data = chapter.model_dump() if hasattr(chapter, "model_dump") else dict(chapter)
    existing_ids = {c.get("id") if isinstance(c, dict) else c.id for c in existing}
    existing_names = {(c.get("name") if isinstance(c, dict) else c.name) for c in existing}

    if is_mock():
        return []

    user = (
        f"本章正文：{json.dumps(chapter_data, ensure_ascii=False)}\n"
        f"已建档角色：{json.dumps(sorted(n for n in existing_names if n), ensure_ascii=False)}\n"
        "请识别需要升级建档的反复出现角色。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "character_archive", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=CharacterArchive)
    out = []
    for c in result.items:
        if c.id and c.id not in existing_ids and c.name and c.name not in existing_names:
            c = c.model_copy(update={"tier": "supporting"})
            out.append(c)
    return out
