"""Stage8 编辑审校 Agent（卷级复核 + 全书终审）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import EditorialReport, Outline

from . import is_mock

SYSTEM_PROMPT = """你是一位小说总编。全盘审读：节奏、伏笔回收、人物弧光完整、开头钩子、结局力度、文风统一。
输出编辑意见书（comments）与修改清单（fix_list，每项可指向 scene_id + 修改指令，供定点修改引擎消费）。"""


def generate_editorial_report(
    outline: Outline | dict,
    chapters: dict,
    characters: list[dict] | None,
    cfg: Config,
    scope: str = "final",
) -> EditorialReport:
    outline_data = outline.model_dump() if hasattr(outline, "model_dump") else dict(outline)
    if is_mock():
        return _mock_report(outline_data, chapters, scope)
    user = (
        f"总纲：{json.dumps(outline_data, ensure_ascii=False)}\n"
        f"章节数：{len(chapters or {})}\n"
        f"请输出{scope}审校意见书。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "editorial", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("editor", cfg)
    report = invoke_structured(llm, messages, schema=EditorialReport)
    report.scope = scope
    return report


def _mock_report(outline: dict, chapters: dict, scope: str) -> EditorialReport:
    n = len(chapters or {})
    return EditorialReport(
        scope=scope,
        comments=f"{scope}审校：共 {n} 章，节奏整体可读；建议核对伏笔回收与结局力度。",
        fix_list=[],
    )
