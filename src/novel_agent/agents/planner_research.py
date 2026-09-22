"""规划师研究循环（ReAct 简化形态）：澄清作者 → 只读取证 → 汇总规划依据。

设计要点（详见 docs/规划智能体ReAct改造需求分析.md §8）：
- ask_author（向作者澄清方向分叉）只在循环最前端的干净边界触发一次 interrupt；
  循环内只有确定性只读查询——规避 resume 重放导致的前序 LLM 决策重跑与不确定性。
- 决策（查什么/查几轮）由模型给出，执行与上限由代码约束；全部工具只读。
"""
from __future__ import annotations

import json

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured

from . import is_mock

MAX_ROUNDS = 3
MAX_ACTIONS = 4


class _PlannerAction(BaseModel):
    tool: str = ""
    args: dict = Field(default_factory=dict)
    reason: str = ""


class PlannerStep(BaseModel):
    thought: str = ""
    actions: list[_PlannerAction] = Field(default_factory=list)


class _ClarifyQ(BaseModel):
    question: str = ""
    options: list[str] = Field(default_factory=list)
    default: str = ""


class ClarifyQuestions(BaseModel):
    questions: list[_ClarifyQ] = Field(default_factory=list)


class PlannerCtx:
    """规划研究上下文：图状态值 + 记忆库句柄 + 卷章信息（由 stage4r 构造传入）。"""

    def __init__(self, values: dict, vol: int, ch: int, midterm, long_term, graph, used_titles=None) -> None:
        self.values = values
        self.used_titles = used_titles or []
        self.vol = vol
        self.ch = ch
        self.midterm = midterm
        self.long_term = long_term
        self.graph = graph


# ---- 只读工具集（规划员专用） ----

def _tool_query_vector(ctx: PlannerCtx, args: dict) -> dict:
    keyword = str(args.get("keyword") or "")
    top_k = int(args.get("top_k") or 3)
    hits = ctx.long_term.search(keyword, top_k=top_k) if keyword else []
    return {"hits": hits} if hits else {"hits": [], "note": "无检索结果"}


def _tool_query_timeline(ctx: PlannerCtx, args: dict) -> dict:
    entity = str(args.get("entity") or "")
    rels = ctx.graph.neighbors(entity, ctx.vol, ctx.ch) if entity else []
    return {"relations": [f"{r['kind']}（第{r['vol']}卷第{r['ch']}章）" for r in rels]}


def _tool_get_chapter_summary(ctx: PlannerCtx, args: dict) -> dict:
    ch_no = int(args.get("chapter") or 0)
    text = ctx.midterm.get(ctx.vol, ch_no) or ""
    return {"summary": text[:400]} if text else {"note": "该章无摘要"}


def _tool_list_recent_events(ctx: PlannerCtx, args: dict) -> dict:
    n = int(args.get("count") or 6)
    el = ctx.values.get("event_ledger") or {}
    keys = sorted(el.keys(), key=lambda x: [int(p) for p in str(x).split("_")])[-n:]
    return {"events": [f"第{k}章：{'；'.join(el[k])}" for k in keys]}


def _tool_get_prop_facts(ctx: PlannerCtx, args: dict) -> dict:
    name = str(args.get("name") or "")
    entry = (ctx.values.get("prop_registry") or {}).get(name)
    return {name: entry} if entry else {"note": f"无 {name} 的登记事实"}


def _tool_check_titles(ctx: PlannerCtx, args: dict) -> dict:
    chs = ctx.values.get("chapters") or {}
    keys = sorted(chs.keys(), key=lambda k: [int(p) for p in str(k).split("_")])
    return {"used_titles": [chs[k].get("title", "") for k in keys]}


TOOL_EXEC = {
    "query_vector": _tool_query_vector,
    "query_timeline": _tool_query_timeline,
    "get_chapter_summary": _tool_get_chapter_summary,
    "get_prop_facts": _tool_get_prop_facts,
    "list_recent_events": _tool_list_recent_events,
    "check_titles": _tool_check_titles,
}

TOOL_MENU = "\n".join(
    f"- {name}: {fn.__doc__ or ''}".strip()
    for name, fn in TOOL_EXEC.items()
)


# ---- 澄清阶段（ask_author） ----

class _ClarifyQ(BaseModel):
    question: str = ""
    options: list[str] = Field(default_factory=list)
    default: str = ""


class ClarifyQuestions(BaseModel):
    questions: list[_ClarifyQ] = Field(default_factory=list)


def clarify_with_author(plan_data: dict, cfg: Config, canon_text: str) -> list[dict]:
    """判断是否有必须由作者裁决的方向分叉；有则生成问题（interrupt 由调用方执行）。"""
    if is_mock():
        return []
    system = (
        "你是章节规划的澄清助手。阅读本章规划素材，判断是否存在**必须由作者裁决的方向分叉**："
        "卷计划事件弧冲突、正典与讨论意图分歧、主线/伏笔孰先的取舍等。"
        "只提出真正影响走向的问题（最多 2 个），每个问题给出 2~3 个候选方向与推荐默认项；"
        "没有分叉就返回空列表。资料能查到、能自行决定的一律不问。只输出 JSON。"
    )
    user = (
        f"本章规划素材：\n{json.dumps(plan_data, ensure_ascii=False)[:2500]}\n"
        f"正典事实（已确立，不可矛盾）：\n{canon_text[:1200]}\n"
        "请判断是否需要作者裁决。"
    )
    messages = build_messages(system, user, "clarify", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    result = invoke_structured(llm, messages, schema=ClarifyQuestions)
    return [
        {
            "question": q.question,
            "options": [o for o in q.options if o.strip()][:4],
            "default": q.default,
        }
        for q in result.questions
        if q.question.strip()
    ][:2]


# ---- 研究循环 ----

class PlannerStep(BaseModel):
    thought: str = ""
    actions: list[_PlannerAction] = Field(default_factory=list)


def _plan_step(ctx: PlannerCtx, plan_data: dict, cfg: Config, executed: list[dict], round_no: int,
               answers: dict | None, followup: bool) -> PlannerStep:
    template = (
        "你是章节规划师的研究助手。基于资料为第{ch}章任务书做查证研究。\n"
        "每轮输出：thought（当前规划思路与信息缺口）+ actions（查证动作，每条带 reason）。\n"
        "可用工具（只读）：\n{menu}\n"
        "规则：不需要更多查证时 actions 返回空数组；每轮最多 {n} 条。只输出 JSON。"
    ).format(ch=ctx.ch, menu=TOOL_MENU, n=MAX_ACTIONS)
    if followup:
        template = (
            "你是章节规划师的研究助手。以下是已执行的查证与结果，判断是否需要补充查证：\n"
            "资料已足够支撑规划时 actions 返回空数组；确有必要才继续（每轮最多 {n} 条）。"
            "只输出 JSON。可用工具：\n{menu}\n"
        ).format(menu=TOOL_MENU, n=MAX_ACTIONS)
    parts = [f"卷计划与本章素材：{json.dumps(plan_data, ensure_ascii=False)[:2500]}"]
    if answers:
        parts.append(f"作者澄清解答：{json.dumps(answers, ensure_ascii=False)[:800]}")
    if executed:
        parts.append("已执行的查证与结果：\n" + json.dumps(executed, ensure_ascii=False)[:3000])
    messages = build_messages(template, "\n".join(parts), "research", cfg.token_budget)
    llm = get_chat_model("cheap", cfg)
    return invoke_structured(llm, messages, schema=PlannerStep)


def _execute_action(ctx: PlannerCtx, act) -> str:
    """确定性执行单个查证动作，返回观察文本。ask_author 不在此处理（交互类不进循环）。"""
    tool = act.tool
    args = act.args or {}
    try:
        if tool == "query_vector":
            hits = ctx.long_term.search(str(args.get("keyword") or ""), top_k=int(args.get("top_k") or 3))
            return json.dumps({"hits": hits}, ensure_ascii=False)[:800]
        if tool == "query_timeline":
            rels = ctx.graph.neighbors(str(args.get("entity") or ""), ctx.vol, ctx.ch)
            return json.dumps({"relations": rels}, ensure_ascii=False)[:600]
        if tool == "get_chapter_summary":
            s = ctx.midterm.get(ctx.vol, int(args.get("chapter") or 0))
            return s or "（该章无摘要）"
        if tool == "get_prop_facts":
            e = (ctx.values.get("prop_registry") or {}).get(str(args.get("name") or ""))
            return json.dumps(e, ensure_ascii=False)[:400] if e else "（无登记事实）"
        if tool == "list_recent_events":
            el = ctx.values.get("event_ledger") or {}
            keys = sorted(el.keys(), key=lambda k: [int(p) for p in str(k).split("_")])[-int(args.get("count") or 5):]
            return json.dumps([f"第{k}章：{el[k]}" for k in keys], ensure_ascii=False)[:800]
        if tool == "check_titles":
            return json.dumps(ctx.used_titles, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return f"（查询异常：{exc}）"
    return f"（未知工具：{tool}）"


def run_planner_research(
    ctx: PlannerCtx,
    plan_data: dict,
    cfg: Config,
    answers: dict | None = None,
    progress=None,
) -> str:
    """规划研究循环（只读查证，无作者交互）。返回《规划研究上下文》文本。"""
    if is_mock():
        if progress:
            progress("规划查证（mock 模式，跳过）")
        return ""
    executed: list[dict] = []
    for round_no in range(1, MAX_ROUNDS + 1):
        step = _plan_step(ctx, plan_data, cfg, executed, round_no, answers, bool(answers or executed))
        acts = [a for a in step.actions if a.tool][:MAX_ACTIONS]
        if not acts:
            break
        if progress:
            progress(f"规划查证第 {round_no} 轮：{'、'.join(a.tool for a in acts)}")
        for a in acts:
            executed.append({
                "tool": a.tool,
                "args": a.args,
                "result": _execute_action(ctx, a),
            })
    if not executed:
        return ""
    lines = []
    for e in executed:
        result = e["result"]
        if len(result) > 400:
            result = result[:400] + "…"
        lines.append(f"- [{e['tool']}] {json.dumps(e['args'], ensure_ascii=False)}\n  结果：{result}")
    return (
        "<规划研究上下文（规划师查证的前文事实与原文，可直接引用）>\n"
        + "\n".join(lines)
        + "\n</规划研究上下文>"
    )
