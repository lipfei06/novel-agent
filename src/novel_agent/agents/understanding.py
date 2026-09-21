"""章节理解三合一（成本优化 OPT-B）：摘要 + 主要角色状态卡 + 人物关系，一次 LLM 调用产出。

原先同一章正文分别喂给 summarize_chapter / extract_character_states / extract_relations
三次；合并后单次调用分发结果，省 2 次全章输入。输入统一走纯文本（OPT-C）。
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured
from novel_agent.types import chapter_plaintext
from novel_agent.types.character_state import CharacterState, CharacterStateEntry

from . import is_mock

SYSTEM_PROMPT = """你是小说连续性管理员。阅读本章正文，一次性完成三项分析：
1. summary：用 80-150 字概括本章（关键事件、人物动机与行动、冲突结果、留给下一章的钩子）；
2. entries：为**主要角色（main）**更新状态卡——所在位置、情绪、身体/伤势、资源、
   关键关系现状、知道/不知道什么、目标进展、状态（在世/死亡/退场/蜕变）、当前弧光阶段。
   只处理主要角色名单中的角色；承接上一章状态，只记录本章的变化与现状；
3. relations：抽取本章人物之间发生的关系或互动（结盟/冲突/误会/情感变化等），
   只使用名单中的名字，每条给关系类型（1-4 字）与一句备注，最多 5 条，没有则返回空列表。"""


class Relation(BaseModel):
    a: str = ""
    b: str = ""
    kind: str = "互动"
    note: str = ""


class ChapterUnderstanding(BaseModel):
    summary: str = Field(default="")
    entries: list[CharacterStateEntry] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


def merge_state_entries(prev_entries: list[dict], new_entries: list[dict], ch: int) -> list[dict]:
    """previous 中未被覆盖的保留；本次输出按 character_id 覆盖并打上 last_chapter。"""
    updated: dict[str, dict] = {e["character_id"]: dict(e) for e in prev_entries}
    for e in new_entries:
        e = dict(e)
        e["last_chapter"] = ch
        updated[e["character_id"]] = e
    return list(updated.values())


def understand_chapter(
    chapter: dict,
    characters: list[dict],
    prev_entries: list[dict],
    cfg: Config,
    author_hints: list[dict] | None = None,
) -> ChapterUnderstanding:
    """一章一次调用，产出 {summary, entries(全量状态集), relations}。

    mock 模式复刻原三个环节的确定性输出，端到端行为不变。
    """
    chapter_data = dict(chapter or {})
    ch = int(chapter_data.get("chapter", 0))
    mains = [c for c in characters or [] if isinstance(c, dict) and c.get("tier") == "main"]

    if is_mock():
        from novel_agent.agents.state_update import _mock_state
        from novel_agent.memory.update import extract_relations

        title = chapter_data.get("title", "")
        heads = [s.get("text", "")[:40] for s in chapter_data.get("scenes", []) if s.get("text")]
        summary = f"{title}：{' / '.join(heads)}"
        relations = extract_relations(chapter_data, characters or [], cfg)
        state = _mock_state(chapter_data, mains, prev_entries, int(getattr(cfg.genre, "chapters_per_volume", 0) or 6))
        return ChapterUnderstanding(
            summary=summary,
            entries=state.entries,
            relations=[Relation(**r) for r in relations],
        )

    known = sorted({c.get("name", "") for c in characters or [] if isinstance(c, dict) and c.get("name")})
    user = (
        f"{chapter_plaintext(chapter_data)}\n\n"
        f"主要角色：{json.dumps([{k: c.get(k) for k in ('id', 'name', 'role')} for c in mains], ensure_ascii=False)}\n"
        f"已建档角色名单：{json.dumps(known, ensure_ascii=False)}\n"
        f"上一章状态：{json.dumps(prev_entries, ensure_ascii=False)}\n"
    )
    if author_hints:
        user += f"作者写本章时的意图性状态变化（优先参考，结合正文核正）：{json.dumps(author_hints, ensure_ascii=False)}\n"
    user += "请一次性输出 summary / entries / relations。"
    messages = build_messages(SYSTEM_PROMPT, user, "understanding", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=ChapterUnderstanding)

    # 关系白名单过滤（防编造，与旧路径一致）；状态与上一章合并
    known_set = set(known)
    relations = [
        r for r in result.relations
        if r.a in known_set and r.b in known_set and r.a != r.b
    ][:5]
    entries = merge_state_entries(prev_entries, [e.model_dump() for e in result.entries], ch)
    return ChapterUnderstanding(summary=result.summary.strip(), entries=[CharacterStateEntry(**e) for e in entries], relations=relations)
