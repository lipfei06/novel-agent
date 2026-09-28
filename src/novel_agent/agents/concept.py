"""Stage0 选题立项 Agent。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.skills import skill_text
from novel_agent.types import Concept

from . import is_mock

SYSTEM_PROMPT = """你是一位小说选题策划师。根据用户的初始立意与题材要求，产出一份结构化立项书。
要点：提炼核心卖点、明确目标读者、给出合理篇幅与分卷规划、标注世界基调与敏感红线、写一句高度浓缩的一句话故事（logline）。"""


def generate_concept(inputs: dict, cfg: Config) -> Concept:
    """输入：{"idea": 用户立意}。输出：Concept。"""
    idea = str(inputs.get("idea") or "").strip() or "（未提供，请自行构思）"
    user = (
        f"题材：{cfg.genre.name}（{cfg.genre.id}）\n"
        f"目标篇幅：约 {cfg.genre.target_word_count} 字 / {cfg.genre.default_volumes} 卷\n"
        f"用户初始立意：{idea}\n"
        "请输出立项书。"
    )
    if is_mock():
        return _mock_concept(idea, cfg)
    messages = build_messages(SYSTEM_PROMPT, user, "concept", cfg.token_budget,
                              style=style_directive(cfg), skill=skill_text("stage0"))
    llm = get_chat_model("creative", cfg)
    return invoke_structured(llm, messages, schema=Concept)


def _mock_concept(idea: str, cfg: Config) -> Concept:
    p = cfg.genre
    return Concept(
        genre=p.id,
        title_idea=idea,
        core_selling=f"围绕「{idea}」展开的{p.name}核心卖点",
        target_reader=f"{p.name}读者",
        target_words=p.target_word_count,
        volumes=p.default_volumes,
        tone=f"{p.name}基调（示例）",
        red_lines=list(p.red_lines),
        logline=f"一个关于「{idea}」的{p.name}故事。",
    )


def concept_to_json(c: Concept) -> str:
    return json.dumps(c.model_dump(), ensure_ascii=False, indent=2)
