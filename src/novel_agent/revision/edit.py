"""定点修改引擎：edit 单场景重写 + 合并（未改动场景字节级保留）。"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from novel_agent.agents import is_mock
from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, style_directive
from novel_agent.types import Chapter, SceneBlock

from .context import build_edit_context

SYSTEM_PROMPT = """你是小说修订编辑。重写【待修改】场景的正文，保持人设、世界观与前后文一致。
若给出修改指令：严格按指令重写，指令未涉及的情节要素保持不变。
若无修改指令：做一次"更好的自由重写"——保持情节走向、关键信息与篇幅不变，
提升文笔、细节与张力。只输出重写后的该场景正文，不要输出任何说明。"""


def edit_scene(
    chapter: Chapter,
    scene_id: str,
    instruction: str,
    cfg: Config,
    rag_context: str = "",
) -> tuple[Chapter, str]:
    """定点修改指定场景：返回 (合并后的 Chapter, 新场景文本)。

    instruction 可为空：空指令 = 不带倾向的自由重写（保持情节与信息，写得更好）。
    未修改的场景保持原对象引用（字节级不变）。
    """
    idx, scene = _require_scene(chapter, scene_id)
    new_text = _rewrite(scene, instruction, chapter, scene_id, cfg, rag_context)
    new_scene = scene.model_copy(update={"text": new_text, "paragraphs": scene.paragraphs})
    scenes = list(chapter.scenes)
    scenes[idx] = new_scene
    merged = chapter.model_copy(update={"scenes": scenes})
    return merged, new_text


def _require_scene(chapter: Chapter, scene_id: str) -> tuple[int, SceneBlock]:
    from .selector import locate_scene

    found = locate_scene(chapter, scene_id)
    if found is None:
        raise KeyError(scene_id)
    return found


def _rewrite(
    scene: SceneBlock,
    instruction: str,
    chapter: Chapter,
    scene_id: str,
    cfg: Config,
    rag_context: str,
) -> str:
    if is_mock():
        suffix = f"（按指令：{instruction}）" if instruction.strip() else "（自由重写）"
        return f"{scene.text}\n[已重写{suffix}]"
    context = build_edit_context(chapter, scene_id, cfg, rag_context)
    directive = (
        f"\n修改指令：{instruction.strip()}"
        if instruction.strip()
        else "\n本次未给修改指令：请在保持情节走向与关键信息不变的前提下，自由重写——提升文笔、细节与张力，篇幅与原场景相当。"
    )
    messages = build_messages(
        SYSTEM_PROMPT,
        f"{context}{directive}",
        "edit",
        cfg.token_budget,
        style=style_directive(cfg),
    )
    llm: ChatOpenAI = get_chat_model("cheap", cfg)
    response = llm.invoke(messages)
    from novel_agent.llm.cost import record_usage

    record_usage((getattr(response, "response_metadata", {}) or {}).get("usage"))
    return str(response.content)
