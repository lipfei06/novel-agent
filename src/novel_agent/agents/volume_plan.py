"""Stage4a 卷级细纲 Agent（大章节规划）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.skills import skill_text
from novel_agent.types import Outline, VolumePlan
from pydantic import BaseModel, Field

from . import is_mock


class VolumePlanList(BaseModel):
    """列表包装：langchain json_mode 不支持裸 list[...] schema。"""

    items: list[VolumePlan] = Field(default_factory=list)

SYSTEM_PROMPT = """你是一位卷规划师。依据全书总纲逐卷细化：本卷事件弧、要埋/收的伏笔、卷末悬念。
保持与总纲一致，卷数与每卷 chapter_count 不增不减（章数以上方给定值为准，只细化剧情内容）。"""


def generate_volume_plans(outline: Outline | dict, cfg: Config) -> list[VolumePlan]:
    outline_data = outline.model_dump() if hasattr(outline, "model_dump") else dict(outline)
    if is_mock():
        return _mock_plans(outline_data, cfg)
    per_vol = int(cfg.genre.chapters_per_volume or 0)
    if per_vol > 0:
        outline_data["volumes"] = [
            {**v, "chapter_count": per_vol} for v in outline_data.get("volumes", []) or []
        ]
    user = (
        f"总纲：{json.dumps(outline_data, ensure_ascii=False)}\n"
        f"请细化各卷。每卷章数安排以上述 chapter_count 为准，不得增减。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "volume_plan", cfg.token_budget,
                              style=style_directive(cfg), skill=skill_text("stage3b"))
    llm = get_chat_model("creative", cfg)
    result = invoke_structured(llm, messages, schema=VolumePlanList)
    plans = result.items
    # 章数硬绑定：卷规划只细化剧情，长度归配置（LLM 自定章数会偏离全书字数目标）
    if per_vol > 0:
        plans = [vp.model_copy(update={"chapter_count": per_vol}) for vp in plans]
    return plans


def _mock_plans(outline: dict, cfg: Config) -> list[VolumePlan]:
    chapter_count = cfg.genre.chapters_per_volume or 20
    plans = []
    for v in outline.get("volumes", []) or []:
        vp = VolumePlan(**v)
        if not vp.chapter_count:
            vp = vp.model_copy(update={"chapter_count": chapter_count})
        plans.append(vp)
    return plans or [VolumePlan(volume=1, chapter_count=chapter_count)]
