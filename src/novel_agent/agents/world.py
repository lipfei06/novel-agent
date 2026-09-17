"""Stage1 世界观构建 Agent。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Concept, WorldBible

from . import is_mock

SYSTEM_PROMPT = """你是一位世界构建师。依据立项书与题材要求构建结构化世界观设定库。
覆盖：地理、势力、力量体系/规则、历史事件、社会文化、特有术语。条目要具体、自洽、可检索。"""


def generate_world(concept: Concept | dict, cfg: Config) -> WorldBible:
    concept_data = concept.model_dump() if hasattr(concept, "model_dump") else dict(concept)
    requirements = "、".join(cfg.genre.world_requirements) or "通用设定"
    user = (
        f"立项书：{json.dumps(concept_data, ensure_ascii=False)}\n"
        f"世界观必含项：{requirements}\n"
        "请输出世界观设定库。"
    )
    if is_mock():
        return _mock_world(concept_data, cfg)
    messages = build_messages(SYSTEM_PROMPT, user, "world", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("creative", cfg)
    return invoke_structured(llm, messages, schema=WorldBible)


def _mock_world(concept: dict, cfg: Config) -> WorldBible:
    title = concept.get("title_idea") or "示例世界"
    return WorldBible(
        geography=[{"name": "主大陆", "desc": f"{title}的主要舞台"}],
        factions=[{"name": "中立势力", "desc": "示例势力"}],
        power_system=[{"name": "力量体系", "desc": "示例规则"}],
        history=[{"name": "创世纪", "desc": "示例历史事件"}],
        customs=[{"name": "习俗", "desc": "示例社会文化"}],
        glossary=[{"name": "术语", "desc": "示例特有术语"}],
    )
