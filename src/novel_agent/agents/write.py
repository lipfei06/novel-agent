"""Stage5 正文写作 Agent（生成场景块数组）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Chapter, SceneBlock, WriterPacket, chapter_plaintext

from . import is_mock

SYSTEM_PROMPT = """你是一位网文写手。依据 writer_packet 生成单章正文，输出为场景块数组（每块带 id/heading/text）。
人物言行需符合其性格设定，章节结尾落实钩子。
背景/路人角色（跑龙套）无需建立档案：直接用通用性格 + 轻度随机化表现即可，不必刻意设计。
字数是硬性要求：必须写足目标字数，用具体的场景、对话、动作与心理描写展开，禁止概要式、提纲式写作。
【防重复硬规则】每个场景对应一个独立节拍、独立事件：同一情节只写一遍，禁止对同一节拍输出两个版本或换措辞重演；
同一段对话/出示证据/摊牌内容只能出现一次。若本章需再次到访已写过的地点办理同类事务，压缩为不超过 150 字的蒙太奇，
只写与上次不同的变化。
【字段要求】每个场景的完整正文必须写在 text 字段里（不得留空、不得只给提纲、不得把正文拆进其他字段）。"""

SYSTEM_PROMPT_REWRITE = """你是一位资深网文写手，负责对【既有章节】进行重新创作。
要求：
- 保持本章情节走向、世界观设定、人物言行与外貌一致（不得凭空改变已确立的事实）
- 但叙事角度、场景组织、语言表达要有**明显不同**，且整体质量更高
- 若原章存在拖沓、平淡、冲突不足等问题，在新版中要修正
- 严格沿用章节规划中的目标、冲突、钩子
- 重新创作是"换一种更好的写法"，不是缩写：篇幅必须与原章相当，禁止概括式压缩
- 【防重复硬规则】每个场景对应一个独立节拍：同一情节只写一遍，禁止对同一节拍输出两个版本或换措辞重演
- 每个场景的完整正文必须写在 text 字段里（不得留空、不得把正文拆进其他字段）
输出为场景块数组（每块带 id/heading/text）。"""

MAX_STYLE_SAMPLES = 3
MAX_STYLE_SAMPLE_CHARS = 800


def _style_note(style_samples: list[dict] | None) -> str:
    """作者风格样本 → 写手 prompt 的 few-shot 锚点（跨章稳定内容，前置利于缓存）。"""
    parts = []
    for i, s in enumerate(style_samples or []):
        text = (s or {}).get("text", "").strip()
        if not text:
            continue
        name = (s or {}).get("name") or f"样本{i + 1}"
        digest = (s or {}).get("digest", "").strip()
        head = f"【{name}】风格要点：{digest}\n原文：" if digest else f"【{name}】"
        parts.append(f"{head}\n{text[:MAX_STYLE_SAMPLE_CHARS]}")
    if not parts:
        return ""
    return (
        "\n<作者风格样本>\n模仿以下样本的叙事口吻、句式节奏与用词密度；"
        "情节与人物必须服从本章规划，样本仅供风格参照。\n"
        + "\n---\n".join(parts)
        + "\n</作者风格样本>"
    )


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
    style_samples: list[dict] | None = None,
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
    style_note = _style_note(style_samples)
    # 缓存友好（OPT-D）：跨章最稳定的内容（风格样本→记忆）前置，每章变化的 packet 随后
    user = (
        f"{style_note}{extra}\nwriter_packet：{json.dumps(packet_data, ensure_ascii=False)}\n{length}\n"
        f"本章标题必须为《{packet.title}》，不得另起标题。\n"
        f"{tech_note}{dark_note}{tool_note}{research_note}\n请写本章正文。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "write", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("writer", cfg)
    chapter = invoke_structured(llm, messages, schema=Chapter)
    # 标题硬约束（写手偶发自拟标题）+ 字数核验轻修（OPT 批次发现：每章超写 20~30%）
    chapter = chapter.model_copy(update={"title": packet.title or chapter.title})
    target = int(getattr(cfg.genre, "words_per_chapter", 0) or 0)
    if target:
        chapter = tune_length(chapter, target, cfg)
    return chapter


def tune_length(chapter: Chapter, target_chars: int, cfg: Config) -> Chapter:
    """字数核验：偏差 ≤25% 直接返回；超出则一轮扩写/精简轻修（保持情节与钩子不变）。"""
    if is_mock() or not target_chars or not chapter.scenes:
        return chapter
    actual = sum(len(s.text or "") for s in chapter.scenes)
    if abs(actual - target_chars) / target_chars <= 0.25:
        return chapter
    action = "精简" if actual > target_chars else "扩写"
    how = "删除次要描写与重复信息，保留全部关键情节" if actual > target_chars else "补充场景细节与感官描写，保持节奏不注水"
    user = (
        f"{chapter_plaintext(chapter)}\n\n"
        f"当前约 {actual} 字，{'超出' if actual > target_chars else '低于'}目标 {target_chars} 字。"
        f"请{action}至 {target_chars} 字左右（±10%）：{how}；标题保持《{chapter.title}》不变。"
    )
    system = "你是小说编辑。按指令调整章节篇幅：情节、人物与钩子完全不变，只调整描写密度。"
    messages = build_messages(system, user, "write", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("writer", cfg)
    fixed = invoke_structured(llm, messages, schema=Chapter)
    return fixed.model_copy(update={"title": chapter.title, "volume": chapter.volume, "chapter": chapter.chapter})


def rewrite_chapter(
    existing: Chapter | dict,
    packet: WriterPacket | dict,
    cfg: Config,
    memory_context: str = "",
    rag_context: str = "",
    techniques: list[dict] | None = None,
    blueprint: dict | None = None,
    research_digest: str = "",
    style_samples: list[dict] | None = None,
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
    style_note = _style_note(style_samples)
    # 缓存友好（OPT-D）：记忆块前置，随后才是每章变化的规划与原文
    user = (
        f"{style_note}{extra}\n"
        f"章节规划：{json.dumps(packet_data, ensure_ascii=False)}\n"
        f"原章节：{json.dumps(existing_data, ensure_ascii=False)}\n"
        f"{length}\n{tech_note}{dark_note}{research_note}\n请重新创作本章，与原文有明显不同且质量更优。"
    )
    messages = build_messages(SYSTEM_PROMPT_REWRITE, user, "write", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("writer", cfg)
    fixed = invoke_structured(llm, messages, schema=Chapter)
    # 重写保留原章标题（写手偶发自拟标题）
    return fixed.model_copy(update={"title": existing_data.get("title", fixed.title)})


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
