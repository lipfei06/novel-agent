"""Stage6 一致性检查 Agent：check + auto-fix（≤3 次，超限转人工）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured
from novel_agent.revision import edit_scene
from novel_agent.types import Chapter, ConsistencyIssue, ConsistencyReport

from . import is_mock

MAX_AUTO_FIX = 3
SYSTEM_PROMPT = """你是一位小说一致性审查员。对照设定库、人物性格与时间线，检查本章的：设定冲突、
人物言行是否OOC、时间线是否自洽、文风是否一致、逻辑是否矛盾。输出问题清单（severity/kind/location/description/fix_action）。
"""

# mock 可自动修复的标记 → 替换
_AUTO_FIXABLE = [
    ("设定矛盾", "设定一致"),
    ("逻辑矛盾", "逻辑自洽"),
]
# mock 不可自动修复（转人工）的标记
_HUMAN_ONLY = ["风格漂移", "角色OOC"]


def check_consistency(
    chapter: Chapter | dict, cfg: Config, attempts: int = 0, context: str = ""
) -> ConsistencyReport:
    """一致性检查。context 为可选的对照上下文（世界观/人物档案/前文摘要/人物状态），
    注入后模型才能发现跨章设定冲突与 OOC，而不是只做章内自洽检查。"""
    chapter_data = chapter.model_dump() if hasattr(chapter, "model_dump") else dict(chapter)
    if is_mock():
        return _mock_check(chapter_data, attempts)
    user = f"本章：{json.dumps(chapter_data, ensure_ascii=False)}\n请输出一致性报告。"
    if context:
        user = f"对照资料：\n{context}\n\n{user}"
    messages = build_messages(SYSTEM_PROMPT, user, "check", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    report = invoke_structured(llm, messages, schema=ConsistencyReport)
    report.auto_fix_attempts = attempts
    return report


def _mock_check(chapter: dict, attempts: int) -> ConsistencyReport:
    issues: list[ConsistencyIssue] = []
    for scene in chapter.get("scenes", []):
        text = scene.get("text", "")
        sid = scene.get("id", "")
        for marker, fixable in [("设定矛盾", True), ("逻辑矛盾", True)]:
            if marker in text and not any(i.location == sid and marker in i.description for i in issues):
                issues.append(
                    ConsistencyIssue(severity="high", kind="setting" if "设定" in marker else "logic",
                                     location=sid, description=f"检测到{marker}", fix_action="自动修复")
                )
        for marker in _HUMAN_ONLY:
            if marker in text:
                issues.append(
                    ConsistencyIssue(severity="high", kind="style" if "风格" in marker else "character",
                                     location=sid, description=f"检测到{marker}", fix_action=None)
                )
    return ConsistencyReport(chapter=chapter.get("chapter", 0), issues=issues, auto_fix_attempts=attempts,
                             needs_human=False)


def fix_issues(report: ConsistencyReport, chapter: Chapter | dict, cfg: Config) -> tuple[Chapter, ConsistencyReport]:
    """修复可自动修复的高严重问题。返回 (Chapter, 更新后 report)。"""
    chapter_obj = chapter if isinstance(chapter, Chapter) else Chapter(**chapter)
    if is_mock():
        return _mock_fix(report, chapter_obj)
    # 真实模式：逐个高严重问题定点重写；location 非法时跳过（LLM 可能给出不存在的场景 id）
    valid_ids = {s.id for s in chapter_obj.scenes}
    for issue in report.issues:
        if issue.severity != "high" or issue.resolved or not issue.fix_action:
            continue
        if issue.location not in valid_ids:
            continue
        chapter_obj, _ = edit_scene(chapter_obj, issue.location, issue.fix_action, cfg)
        issue.resolved = True
    report.auto_fix_attempts = int(report.auto_fix_attempts or 0) + 1
    return chapter_obj, report


def _mock_fix(report: ConsistencyReport, chapter: Chapter) -> tuple[Chapter, ConsistencyReport]:
    scenes = list(chapter.scenes)
    for issue in report.issues:
        if issue.severity != "high" or issue.resolved:
            continue
        idx = next((i for i, s in enumerate(scenes) if s.id == issue.location), None)
        if idx is None:
            continue
        text = scenes[idx].text
        replaced = False
        for marker, replacement in _AUTO_FIXABLE:
            if marker in text:
                text = text.replace(marker, replacement)
                replaced = True
                issue.resolved = True
                break
        if not replaced:
            # 不可自动修复（风格漂移/OOC）→ 保持，转人工
            issue.resolved = False
        scenes[idx] = scenes[idx].model_copy(update={"text": text})
    report.auto_fix_attempts = int(report.auto_fix_attempts or 0) + 1
    report.needs_human = any(i.severity == "high" and not i.resolved for i in report.issues)
    return chapter.model_copy(update={"scenes": scenes}), report
