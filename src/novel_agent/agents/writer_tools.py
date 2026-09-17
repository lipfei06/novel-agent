"""写手智能体的查询工具：注册表 + 确定性执行器。

权限模型："读开放、写提案、底线兜底"——
- 工具全部只读、无副作用，执行不经过 LLM（写手模型只发"查询请求"，
  由编排层确定性执行后把结果回填）；
- 写记忆走"提案制"，见 writer_research.propose_updates；
- 底线上下文（近章全文/摘要）不做成工具，强制注入防漏查。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from novel_agent.config import Config

# 工具菜单：名称 + 能力说明 + 参数说明（进提示词供写手感知）
TOOL_MENU: list[dict[str, str]] = [
    {
        "name": "query_character_state",
        "desc": "查询主要角色的当前状态（位置/情绪/知道什么/目标进展/弧光阶段）",
        "args": '{"names": ["角色名", ...]}（省略 names 则返回全部主要角色）',
    },
    {
        "name": "query_foreshadow",
        "desc": "查询伏笔账本：此前章节埋下、尚未回收的伏笔清单",
        "args": "{}",
    },
    {
        "name": "query_character_profile",
        "desc": "查询单个角色的完整档案（外貌/声音/动机/缺陷/关系/背景）",
        "args": '{"name": "角色名"}',
    },
    {
        "name": "search_memory",
        "desc": "按关键词检索前文的相关场景片段",
        "args": '{"keyword": "关键词", "top_k": 4}',
    },
    {
        "name": "query_volume_progress",
        "desc": "查询本卷进度：已写章节/剩余章数/待回收伏笔/卷末钩子",
        "args": "{}",
    },
]


def tool_menu_text() -> str:
    return "\n".join(f"- {t['name']}：{t['desc']}；参数：{t['args']}" for t in TOOL_MENU)


@dataclass
class WriterCtx:
    """写手工具的执行上下文：图状态快照 + 当前卷章 + 项目根。"""

    values: dict
    vol: int
    ch: int
    root: str
    cfg: "Config"
    extra: dict = field(default_factory=dict)


def _safe_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _q_character_state(ctx: WriterCtx, args: dict) -> str:
    names = [str(n) for n in (args.get("names") or [])]
    entries = (ctx.values.get("character_state") or {}).get("entries") or []
    picked = [
        e for e in entries
        if not names or e.get("name") in names or e.get("character_id") in names
    ]
    return _safe_dump({"entries": picked})


def _q_foreshadow(ctx: WriterCtx, args: dict) -> str:
    from novel_agent.agents.packet import collect_pending_foreshadow

    return _safe_dump({"pending": collect_pending_foreshadow(ctx.values.get("writer_packets"))})


def _q_character_profile(ctx: WriterCtx, args: dict) -> str:
    name = str(args.get("name") or "")
    for c in ctx.values.get("characters") or []:
        if isinstance(c, dict) and c.get("name") == name:
            return _safe_dump(c)
    return _safe_dump({"error": f"未找到角色：{name}"})


def _q_search_memory(ctx: WriterCtx, args: dict) -> str:
    from novel_agent.memory import LongTermMemory

    keyword = str(args.get("keyword") or "")
    top_k = int(args.get("top_k") or 4)
    paths = _project_paths(ctx)
    hits = LongTermMemory(paths.vector_dir / "long_term.json").search(keyword, top_k=top_k)
    return _safe_dump({"hits": hits})


def _q_volume_progress(ctx: WriterCtx, args: dict) -> str:
    plans = ctx.values.get("volume_plans") or []
    plan = next((p for p in plans if p.get("volume") == ctx.vol), None) or {}
    chapters = ctx.values.get("chapters") or {}
    keys = sorted((k for k in chapters if k.startswith(f"{ctx.vol}_")), key=_chapter_sort_key)
    written = [
        {"chapter": int(k.split("_")[1]), "title": (chapters[k] or {}).get("title", "")}
        for k in keys
    ]
    return _safe_dump({
        "volume": ctx.vol,
        "chapter_count": (plan or {}).get("chapter_count"),
        "written": written,
        "foreshadow_payoff": (plan or {}).get("foreshadow_payoff") or [],
        "ending_hook": (plan or {}).get("ending_hook", ""),
    })


def _chapter_sort_key(k: str) -> tuple[int, int]:
    try:
        a, b = str(k).split("_")
        return (int(a), int(b))
    except ValueError:
        return (1 << 30, 1 << 30)


def _project_paths(ctx: WriterCtx):
    from novel_agent.storage import ProjectPaths

    return ProjectPaths(Path(ctx.root), str(ctx.values.get("project_id", "")))


_HANDLERS = {
    "query_character_state": _q_character_state,
    "query_foreshadow": _q_foreshadow,
    "query_character_profile": _q_character_profile,
    "search_memory": _q_search_memory,
    "query_volume_progress": _q_volume_progress,
}


def execute_query(ctx: WriterCtx, tool: str, args: dict) -> str:
    """执行单个查询工具，返回 JSON 字符串。未知工具/异常返回错误说明（供写手自纠）。"""
    handler = _HANDLERS.get(tool)
    if handler is None:
        return _safe_dump({"error": f"未知工具：{tool}", "available": list(_HANDLERS)})
    try:
        return handler(ctx, dict(args or {}))
    except Exception as exc:  # noqa: BLE001
        return _safe_dump({"error": f"工具执行失败：{exc}"})
