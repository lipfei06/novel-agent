"""写手智能体的研究循环：计划 → 查询 → 汇编，以及写后记忆更新提案。

三段式中的段 1（研究规划师，cheap 档）与段 4（提案，cheap 档）；
段 2 工具执行是确定性代码（writer_tools.execute_query），段 3 写作在 write.py。
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured

from . import is_mock
from .writer_tools import WriterCtx, execute_query, tool_menu_text

_MAX_QUERIES_PER_ROUND = 4

RESEARCH_PROMPT = """你是写手的资料研究员。作者即将让写手写本章，你的任务：
1. 先给出本章写作计划（要点式）；
2. 判断还缺哪些资料，发出查询请求（每条注明查询理由）。
只输出 JSON：{"plan": "...", "queries": [{"tool": "工具名", "args": {...}, "reason": "..."}]}
规则：
- 工具名必须来自下方工具菜单；不需要更多资料时 queries 返回空数组；
- 每轮最多 {_MAX_QUERIES_PER_ROUND} 条查询。"""

FOLLOWUP_PROMPT = """你是写手的资料研究员。以下是已执行的查询与结果，判断是否需要补充查询：
如果资料已足够支撑写作，queries 返回空数组；确有必要才继续查询（每轮最多 {_MAX_QUERIES_PER_ROUND} 条）。
只输出 JSON：{"plan": "...", "queries": [...]}"""


class _ResearchQuery(BaseModel):
    tool: str = ""
    args: dict = Field(default_factory=dict)
    reason: str = ""


class ResearchPlan(BaseModel):
    plan: str = ""
    queries: list[_ResearchQuery] = Field(default_factory=list)


def run_research(
    ctx: WriterCtx,
    packet_data: dict,
    discussion: str,
    baseline: str,
    cfg: Config,
    max_rounds: int = 3,
    progress=None,
) -> str:
    """研究循环编排：返回《研究结果》文本块（无查询时返回空串）。

    第 1 轮为计划轮；后续轮把已有结果喂回，由模型决定是否补充查询。
    """
    is_followup = False
    executed: list[dict] = []
    for round_no in range(1, max_rounds + 1):
        queries = _research_queries(
            packet_data, discussion, baseline, executed, cfg,
            round_no=round_no, is_followup=is_followup,
        )
        if not queries:
            break
        if progress is not None:
            progress(f"研究第 {round_no} 轮：{'、'.join(q['tool'] for q in queries)}", None)
        for q in queries[:_MAX_QUERIES_PER_ROUND]:
            executed.append({
                "tool": q["tool"],
                "args": q.get("args", {}),
                "result": execute_query(ctx, q["tool"], q.get("args") or {}),
            })
        is_followup = True
    if not executed:
        return ""
    lines = []
    for r in executed:
        result = r["result"]
        if len(result) > 800:
            result = result[:800] + "…"
        lines.append(f"- [{r['tool']}] {json.dumps(r['args'], ensure_ascii=False)}\n  结果：{result}")
    return (
        "<研究结果（研究员按写作计划检索的资料，供参考）>\n"
        + "\n".join(lines)
        + "\n</研究结果（研究员按写作计划检索的资料）>"
    )


def _research_queries(
    packet_data: dict,
    discussion: str,
    baseline: str,
    executed: list[dict],
    cfg: Config,
    round_no: int,
    is_followup: bool,
) -> list[dict]:
    if is_mock():
        # mock：第 1 轮返回一条确定性查询（验证链路），后续轮为空
        return [{"tool": "query_foreshadow", "args": {}, "reason": "mock"}] if round_no == 1 else []
    template = FOLLOWUP_PROMPT if is_followup else RESEARCH_PROMPT
    system = template.replace("{_MAX_QUERIES_PER_ROUND}", str(_MAX_QUERIES_PER_ROUND)) + "\n\n工具菜单：\n" + tool_menu_text()
    user_parts = [f"章节规划：{json.dumps(packet_data, ensure_ascii=False)}"]
    if discussion:
        user_parts.append(f"作者讨论要点：{discussion}")
    if baseline:
        user_parts.append(f"已有基础资料（必给，无需重复查询）：\n{baseline[:2000]}")
    if executed:
        user_parts.append("已执行的查询与结果：\n" + json.dumps(executed, ensure_ascii=False)[:3000])
    messages = build_messages(system, "\n".join(user_parts), "research", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=ResearchPlan)
    return [q.model_dump() for q in result.queries if q.tool]


def propose_updates(chapter_data: dict, state_entries: list[dict], cfg: Config) -> dict:
    """写后记忆更新提案：状态变化 + 伏笔登记（mock 返回空提案）。

    提案交由 stage7 / 章节接受流程校验合并——写手只提议，不直接改记忆。
    """
    if is_mock():
        return {"state_updates": [], "foreshadow_plants": []}
    from pydantic import BaseModel

    from novel_agent.llm import build_messages, get_chat_model, invoke_structured

    class StateUpdate(BaseModel):
        name: str = ""
        location: str = ""
        mood: str = ""
        knowledge: str = ""
        goal_progress: str = ""

    class ForeshadowPlant(BaseModel):
        desc: str = ""

    class MemoryProposal(BaseModel):
        state_updates: list[StateUpdate] = Field(default_factory=list)
        foreshadow_plants: list[ForeshadowPlant] = Field(default_factory=list)

    system = """你是小说连续性管理员。刚写完本章，请提出记忆更新提案：
1. state_updates：本章造成的主要角色状态变化（位置/情绪/知道什么/目标进展），只包含确实变化的；
2. foreshadow_plants：本章新埋下的伏笔（一句话描述）。
规则：只依据本章正文；没有变化返回空列表。只输出 JSON。"""
    user = (
        f"本章正文：{json.dumps(chapter_data, ensure_ascii=False)}\n"
        f"当前主要角色状态：{json.dumps(state_entries, ensure_ascii=False)}\n"
        "请输出记忆更新提案。"
    )
    messages = build_messages(system, user, "research", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=MemoryProposal)
    return {
        "state_updates": [s.model_dump() for s in result.state_updates],
        "foreshadow_plants": [f.desc for f in result.foreshadow_plants if f.desc.strip()],
    }
