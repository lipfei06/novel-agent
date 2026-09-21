"""Stage5 正文写作 Agent（生成场景块数组）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Chapter, SceneBlock, WriterPacket

from . import is_mock

SYSTEM_PROMPT = """你是一位网文写手。依据 writer_packet 生成单章正文，输出为场景块数组（每块带 id/heading/text）。
人物言行需符合其性格设定，章节结尾落实钩子。
背景/路人角色（跑龙套）无需建立档案：直接用通用性格 + 轻度随机化表现即可，不必刻意设计。
字数是硬性要求：必须写足目标字数，用具体的场景、对话、动作与心理描写展开，禁止概要式、提纲式写作。
【字段要求】每个场景的完整正文必须写在 text 字段里（不得留空、不得只给提纲、不得把正文拆进其他字段）。"""

SYSTEM_PROMPT_REWRITE = """你是一位资深网文写手，负责对【既有章节】进行重新创作。
要求：
- 保持本章情节走向、世界观设定、人物言行与外貌一致（不得凭空改变已确立的事实）
- 但叙事角度、场景组织、语言表达要有**明显不同**，且整体质量更高
- 若原章存在拖沓、平淡、冲突不足等问题，在新版中要修正
- 严格沿用章节规划中的目标、冲突、钩子
- 重新创作是"换一种更好的写法"，不是缩写：篇幅必须与原章相当，禁止概括式压缩
- 每个场景的完整正文必须写在 text 字段里（不得留空、不得把正文拆进其他字段）
输出为场景块数组（每块带 id/heading/text）。"""


def _length_directive(target: int) -> str:
    return f"本章目标字数：约 {target} 字（正文实写字数，不含标题与标点统计口径），写足为止。" if target > 0 else ""


def generate_chapter(
    packet: WriterPacket | dict,
    cfg: Config,
    memory_context: str = "",
    rag_context: str = "",
    techniques: list[dict] | None = None,
    blueprint: dict | None = None,
    tools: list[dict] | None = None,
    research_digest: str = "",
) -> Chapter:
    packet_data = packet.model_dump() if hasattr(packet, "model_dump") else dict(packet)
    if is_mock():
        return _mock_chapter(packet_data)
    extra = ""
    if memory_context:
        extra += f"\n<memory>\n{memory_context}\n</memory>"
    if rag_context:
        extra += f"\n<reference>\n{rag_context}\n</reference>"
    from novel_agent.agents.blueprint import dark_line_directive
    from novel_agent.library.techniques import stage_guidance

    length = _length_directive(int(getattr(cfg.genre, "words_per_chapter", 0) or 0))
    tech_note = stage_guidance(techniques, ("writing",))
    dark_note = dark_line_directive(blueprint)
    tool_note = ""
    if tools:
        refs = [f"- {t.get('name')}（{t.get('category', '')}）：{t.get('usage_guidelines', '')}" for t in tools]
        tool_note = "\n<本章可运用的叙事技法>\n" + "\n".join(refs) + "\n</本章可运用的叙事技法>"
    research_note = f"\n{research_digest}" if research_digest else ""
    # 缓存友好（OPT-D）：跨章最稳定的记忆块前置，每章变化的 packet 随后
    user = (
        f"{extra}\nwriter_packet：{json.dumps(packet_data, ensure_ascii=False)}\n{length}\n"
        f"{tech_note}{dark_note}{tool_note}{research_note}\n请写本章正文。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "write", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("writer", cfg)
    return invoke_structured(llm, messages, schema=Chapter)


def rewrite_chapter(
    existing: Chapter | dict,
    packet: WriterPacket | dict,
    cfg: Config,
    memory_context: str = "",
    rag_context: str = "",
    techniques: list[dict] | None = None,
    blueprint: dict | None = None,
    research_digest: str = "",
) -> Chapter:
    """重新创作既有章节：保持设定一致，但叙事/表达明显不同且更优。"""
    existing_data = existing.model_dump() if hasattr(existing, "model_dump") else dict(existing)
    packet_data = packet.model_dump() if hasattr(packet, "model_dump") else dict(packet)
    if is_mock():
        ch = _mock_chapter(packet_data)
        if ch.scenes:
            ch.scenes[0] = ch.scenes[0].model_copy(update={"text": ch.scenes[0].text + "（重写版）"})
        return ch
    extra = ""
    if memory_context:
        extra += f"\n<memory>\n{memory_context}\n</memory>"
    if rag_context:
        extra += f"\n<reference>\n{rag_context}\n</reference>"
    from novel_agent.agents.blueprint import dark_line_directive
    from novel_agent.library.techniques import stage_guidance

    orig_len = sum(len(s.get("text") or "") for s in existing_data.get("scenes") or [])
    target = int(getattr(cfg.genre, "words_per_chapter", 0) or 0)
    length_parts = []
    if orig_len > 0:
        length_parts.append(f"原章约 {orig_len} 字，新版篇幅不得明显少于原章")
    if target > 0:
        length_parts.append(f"本章目标约 {target} 字")
    length = ("字数要求：" + "；".join(length_parts) + "。逐场景充分展开，禁止概括式缩写。") if length_parts else ""
    tech_note = stage_guidance(techniques, ("writing",))
    dark_note = dark_line_directive(blueprint)
    research_note = f"\n{research_digest}" if research_digest else ""
    # 缓存友好（OPT-D）：记忆块前置，随后才是每章变化的规划与原文
    user = (
        f"{extra}\n"
        f"章节规划：{json.dumps(packet_data, ensure_ascii=False)}\n"
        f"原章节：{json.dumps(existing_data, ensure_ascii=False)}\n"
        f"{length}\n{tech_note}{dark_note}{research_note}\n请重新创作本章，与原文有明显不同且质量更优。"
    )
    messages = build_messages(SYSTEM_PROMPT_REWRITE, user, "write", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("writer", cfg)
    return invoke_structured(llm, messages, schema=Chapter)


def _mock_chapter(packet: dict) -> Chapter:
    title = packet.get("title") or "章节"
    goal = packet.get("goal") or "推进情节"
    return Chapter(
        volume=int(packet.get("volume", 1)),
        chapter=int(packet.get("chapter", 1)),
        title=title,
        scenes=[
            SceneBlock(id="s1", heading="开场", text=f"（{title}）开场：围绕「{goal}」展开。"),
            SceneBlock(id="s2", heading="冲突", text=f"（{title}）冲突升级，矛盾推向顶点。"),
            SceneBlock(id="s3", heading="钩子", text=f"（{title}）结尾：{packet.get('hook') or '新悬念浮现'}。"),
        ],
    )
