"""Stage3 总纲 Agent。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Character, Concept, Outline, VolumePlan, WorldBible

from . import is_mock

SYSTEM_PROMPT = """你是一位长篇小说架构师。依据立项书、世界观与人物，设计全书总纲。
输出：三幕/起承转合结构说明、分卷规划（每卷事件弧与伏笔）、核心转折事件、伏笔总清单、结局。
分卷数量需匹配立项书，每卷给出结尾钩子。"""


def generate_outline(
    concept: Concept | dict,
    world: WorldBible | dict | None,
    characters: list[Character] | list[dict],
    cfg: Config,
) -> Outline:
    concept_data = concept.model_dump() if hasattr(concept, "model_dump") else dict(concept)
    volumes = int(concept_data.get("volumes") or cfg.genre.default_volumes or 1)
    if is_mock():
        return _mock_outline(concept_data, volumes, cfg.genre.chapters_per_volume)
    world_data = world.model_dump() if hasattr(world, "model_dump") else dict(world)
    chars = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in characters]
    user = (
        f"立项书：{json.dumps(concept_data, ensure_ascii=False)}\n"
        f"世界观：{json.dumps(world_data, ensure_ascii=False)}\n"
        f"人物：{json.dumps(chars, ensure_ascii=False)}\n"
        f"全书目标字数约 {cfg.genre.target_word_count} 字，分 {volumes} 卷，"
        f"每卷固定 {cfg.genre.chapters_per_volume} 章（每卷的 chapter_count 必须恰好等于该值，不得增减）。\n"
        f"请设计 {volumes} 卷的总纲。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "outline", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("creative", cfg)
    outline = invoke_structured(llm, messages, schema=Outline)
    # 章数硬绑定（LLM 自定章数会偏离全书字数目标：剧情内容归 LLM，长度归配置）
    per_vol = int(cfg.genre.chapters_per_volume or 0)
    if per_vol > 0 and outline.volumes:
        for v in outline.volumes:
            v.chapter_count = per_vol
    return outline


def _mock_outline(concept: dict, volumes: int, chapters_per_volume: int = 20) -> Outline:
    title = concept.get("title_idea") or "示例"
    return Outline(
        version=1,
        premise=concept.get("logline") or f"关于「{title}」的故事",
        structure="起承转合（示例）",
        volumes=[
            VolumePlan(
                volume=v + 1,
                title=f"第{v + 1}卷",
                event_arc=[f"卷{v + 1}事件弧"],
                foreshadow_seed=[f"卷{v + 1}埋的伏笔"],
                foreshadow_payoff=[],
                chapter_count=chapters_per_volume,
                ending_hook=f"卷{v + 1}结尾钩子",
            )
            for v in range(volumes)
        ],
        core_events=["核心转折（示例）"],
        foreshadowing=[{"seed": "示例伏笔", "payoff": "待回收"}],
        ending="示例结局",
    )
