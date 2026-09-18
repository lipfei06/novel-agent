"""F11 记忆更新：章节摘要→中期；场景切片→长期；实体关系→时序图谱（diff 增量）。"""
from __future__ import annotations

from novel_agent.config import Config
from novel_agent.rag import TemporalGraph

from .long_term import LongTermMemory
from .mid_term import MidTermMemory


def update_chapter_memory(
    chapter: dict,
    cfg: Config,
    midterm: MidTermMemory,
    long_term: LongTermMemory,
    graph: TemporalGraph | None = None,
    characters: list[dict] | None = None,
) -> dict:
    """对已完成章节执行三层记忆更新，返回本次变更摘要。"""
    vol = int(chapter.get("volume", 1))
    ch = int(chapter.get("chapter", 1))
    summary = midterm.summarize_chapter(chapter, cfg)
    midterm.add(vol, ch, summary)

    scene_texts = [s.get("text", "") for s in chapter.get("scenes", []) if s.get("text")]
    metas = [
        {"vol": vol, "ch": ch, "scene": i + 1, "key": f"{vol}_{ch}"}
        for i in range(len(scene_texts))
    ]
    long_term.add(scene_texts, metas)

    if graph is not None:
        for c in characters or []:
            if c.get("name"):
                graph.add_node(c["name"])
        relations = extract_relations(chapter, characters or [], cfg)
        edges = [
            {"a": r["a"], "b": r["b"], "kind": r.get("kind", "互动"), "vol": vol, "ch": ch,
             "note": (r.get("note") or summary[:30])}
            for r in relations
        ]
        if edges:
            graph.add_edges(edges)

    return {"summary": summary, "scenes": len(scene_texts), "relations": len(edges) if graph is not None else 0}


def extract_relations(chapter: dict, characters: list[dict], cfg: Config) -> list[dict]:
    """抽取本章人物关系/互动。

    mock 模式：确定性地返回"主角×盟友"一条互动（与旧硬编码行为一致，便于测试）。
    真实模式：用 cheap 模型从正文抽取，限定在已建档角色名单内。
    """
    from novel_agent.agents import is_mock

    names = [
        c.get("name", "")
        for c in characters or []
        if isinstance(c, dict) and c.get("name") and c.get("role") in ("protagonist", "ally")
    ]
    if is_mock():
        return [{"a": names[0], "b": names[1], "kind": "互动", "note": ""}] if len(names) >= 2 else []

    import json

    from pydantic import BaseModel, Field

    from novel_agent.llm import build_messages, get_chat_model, invoke_structured

    class Relation(BaseModel):
        a: str = ""
        b: str = ""
        kind: str = "互动"
        note: str = ""

    class RelationList(BaseModel):
        items: list[Relation] = Field(default_factory=list)

    known = sorted({c.get("name", "") for c in characters or [] if isinstance(c, dict) and c.get("name")})
    system = (
        "你是小说关系分析师。阅读本章正文，抽取人物之间本章发生的关系或互动（结盟/冲突/误会/情感变化等）。"
        "只使用已建档角色名单中的名字；每条给出关系类型（1-4 字）与一句备注；最多 5 条；没有则返回空列表。"
    )
    user = (
        f"本章：{json.dumps(chapter, ensure_ascii=False)}\n"
        f"已建档角色名单：{json.dumps(known, ensure_ascii=False)}\n"
        "请输出本章人物关系。"
    )
    messages = build_messages(system, user, "relation", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=RelationList)
    known_set = set(known)
    out = []
    for r in result.items:
        if r.a in known_set and r.b in known_set and r.a != r.b:
            out.append({"a": r.a, "b": r.b, "kind": r.kind or "互动", "note": r.note})
    return out[:5]
