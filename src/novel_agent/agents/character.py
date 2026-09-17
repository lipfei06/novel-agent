"""Stage2 人物设定 Agent。"""
from __future__ import annotations

import json
from pathlib import Path

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Character, Concept, WorldBible
from novel_agent.library import PersonalityEntry
from novel_agent.library.searcher import personality_for, templates_for
from pydantic import BaseModel, Field

from . import is_mock


class CharacterList(BaseModel):
    """列表包装：langchain json_mode 不支持裸 list[...] schema。"""

    items: list[Character] = Field(default_factory=list)

SYSTEM_PROMPT = """你是一位人物设计师。依据立项书与世界观设计核心人物。
每人需有：动机、缺陷、成长弧光、关系网。主角弧光必须明确。可参考给定的性格原型保持言行一致性。
分级与信息要求：
- main（主角/关键反派/重要配角）：详细档案（含外貌、声音说话方式、小动作、出身、标志性物品）+ 成长弧光，后续需跟踪其状态
- supporting（次要角色）：简要档案（动机、关键事件、一句外貌关键特征、出身）即可
- background（跑龙套/路人）：不要建档案，写作时直接按通用性格随机生成即可
输出角色时 role 与 tier 要匹配（protagonist/antagonist 一般为 main）。
外貌要具体稳定（身高体型、面容、标志性特征），便于后续保持描写一致。"""


def _personality_context(spec: str, genres: list[str], cfg: Config, root: str | None) -> list[dict]:
    """从写作基础库按需求描述检索性格原型（query 随立意动态变化）。"""
    try:
        if root:
            return personality_for(root, spec, genres=genres, top_k=int(cfg.library.get("personality_top_k", 3)))
    except Exception:
        pass
    return []


def _template_context(root: str | None) -> list[dict]:
    """人物模板库条目（若设置项目根则读取；供设计时参考/起步）。"""
    try:
        if root:
            return templates_for(root)
    except Exception:
        pass
    return []


def generate_characters(
    concept: Concept | dict,
    world: WorldBible | dict,
    cfg: Config,
    root: str | None = None,
) -> list[Character]:
    concept_data = concept.model_dump() if hasattr(concept, "model_dump") else dict(concept)
    world_data = world.model_dump() if hasattr(world, "model_dump") else dict(world)
    # 检索需求随立意动态生成，而非固定字符串——不同题材/立意选到的原型才不同
    spec = " ".join(
        filter(None, [
            concept_data.get("logline", ""),
            concept_data.get("core_selling_point", ""),
            concept_data.get("tone", ""),
            world_data.get("glossary", "") and " ".join(
                g.get("name", "") for g in world_data.get("glossary", []) if isinstance(g, dict)
            ),
        ]),
    ) or "主角 配角 关键人物"
    personalities = _personality_context(spec, [concept_data.get("genre", "")], cfg, root)
    templates = _template_context(root)
    template_note = ""
    if templates:
        brief = [
            {"name": t.get("name"), "description": t.get("description"), "motivation": t.get("motivation"), "flaw": t.get("flaw")}
            for t in templates
        ]
        template_note = (
            f"\n可选人物模板（若与故事契合可作设计基底，不合适则忽略）：{json.dumps(brief, ensure_ascii=False)}"
        )
    proto = [p.get("name") if isinstance(p, dict) else p.name for p in personalities]
    user = (
        f"立项书：{json.dumps(concept_data, ensure_ascii=False)}\n"
        f"世界观：{json.dumps(world_data, ensure_ascii=False)}\n"
        f"可选性格原型：{proto}\n"
        f"请设计核心人物（主角/配角/反派）。{template_note}"
    )
    if is_mock():
        return _mock_characters(concept_data, personalities)
    messages = build_messages(SYSTEM_PROMPT, user, "character", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("creative", cfg)
    result = invoke_structured(llm, messages, schema=CharacterList)
    return result.items


def _mock_characters(concept: dict, personalities: list) -> list[Character]:
    title = concept.get("title_idea") or "示例"
    main_name = f"{title}主角"
    first = personalities[0] if personalities else None
    persona = (first.get("name") if isinstance(first, dict) else getattr(first, "name", "")) or "示例性格"
    return [
        Character(id="c_protagonist", name=main_name, role="protagonist", tier="main",
                  motivation="追寻真相", flaw="固执", arc=[{"stage": "start", "change": "迷茫"}],
                  appearance="身形挺拔，眼神沉静，衣饰素净",
                  voice="语速平缓，少言但语气坚定",
                  habits="思考时会轻叩桌面",
                  background="出身寒微，心怀执念", signature_item="一枚旧玉佩",
                  relationships=[], timeline=[]),
        Character(id="c_ally", name=f"{title}伙伴", role="ally", tier="supporting",
                  motivation="守护重要之人", flaw="冲动",
                  appearance="个子不高，眉眼开朗，总是带着笑意",
                  background="市井出身，讲义气",
                  arc=[], relationships=[{"target_id": "c_protagonist", "kind": "战友", "evolution": "初识"}],
                  timeline=[]),
    ]
