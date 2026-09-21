"""F04 LangGraph 图编排（M2：创意链路 Stage0-3 + interrupt 确认点）。

每个创意节点：调用对应 Agent 生成产物 → interrupt() 挂起等人确认 →
按确认结果（accept/edit/regenerate）写入 state 后继续下一环节。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from novel_agent.agents.character import generate_characters
from novel_agent.agents.concept import generate_concept
from novel_agent.agents.consistency import MAX_AUTO_FIX, check_consistency, fix_issues
from novel_agent.agents.editorial import generate_editorial_report
from novel_agent.agents.outline import generate_outline
from novel_agent.agents.packet import generate_writer_packet
from novel_agent.agents.volume_plan import generate_volume_plans
from novel_agent.agents.world import generate_world
from novel_agent.agents.write import generate_chapter
from novel_agent.config import Config
from novel_agent.export import assemble_final
from novel_agent.llm import get_embedder
from novel_agent.memory import LongTermMemory, MidTermMemory, get_short_term, update_chapter_memory
from novel_agent.rag import TemporalGraph, retrieve
from novel_agent.revision import edit_scene
from novel_agent.storage import ProjectPaths
from novel_agent.types import (
    Chapter,
    Character,
    Concept,
    ConsistencyReport,
    EditorialReport,
    Outline,
    VolumePlan,
    WorldBible,
    WriterPacket,
)

from .state import NovelState

STAGES = [
    "stage0", "stage1", "stage2", "stage3",
    "stage4a", "stage4b", "stage5", "stage6",
    "stage7", "stage8", "stage9",
]


def _confirmation(stage: str, label: str, payload: dict) -> dict:
    """挂起并返回人工确认结果 {action: accept|edit, data: 替换字段}。"""
    return interrupt({"stage": stage, "stage_label": label, "payload": payload})


def _decide(decision: dict | None) -> dict:
    """解析确认结果；缺省或未知视为 accept。"""
    d = decision or {}
    action = d.get("action", "accept")
    if action == "regenerate":
        return {"action": "regenerate"}
    if action == "edit" and isinstance(d.get("data"), dict):
        return {"action": "edit", "data": d["data"]}
    return {"action": "accept"}


def _confirm_product(stage: str, label: str, generate_fn, payload_fn=None, rebuild=None):
    """生成产物 → interrupt 确认循环。

    accept 返回当前产物；edit 用 rebuild(product, data) 重建；regenerate 重新调用 generate_fn。
    """
    while True:
        product = generate_fn()
        payload = payload_fn(product) if payload_fn else product.model_dump()
        decision = _decide(_confirmation(stage, label, payload))
        if decision["action"] == "regenerate":
            continue
        if decision["action"] == "edit" and rebuild is not None:
            return rebuild(product, decision["data"])
        return product


def _stage0(cfg: Config):
    def node(state: NovelState) -> dict:
        idea = state.get("user_idea", "")
        concept = _confirm_product(
            "stage0",
            "选题立项",
            lambda: generate_concept({"idea": idea}, cfg),
            rebuild=lambda _p, d: Concept(**d),
        )
        return {
            "concept": concept.model_dump(),
            "current_stage": "stage1",
            "messages": [*state.get("messages", []), f"stage0 立项书确认：{concept.logline}"],
        }

    return node


def _stage1(cfg: Config):
    def node(state: NovelState) -> dict:
        concept = Concept(**state.get("concept", {}))
        world = _confirm_product(
            "stage1",
            "世界观构建",
            lambda: generate_world(concept, cfg),
            rebuild=lambda _p, d: WorldBible(**d),
        )
        return {
            "world_bible": world.model_dump(),
            "current_stage": "stage2",
            "messages": [*state.get("messages", []), "stage1 世界观确认"],
        }

    return node


def _stage2(cfg: Config):
    def node(state: NovelState) -> dict:
        concept = Concept(**state.get("concept", {}))
        world = WorldBible(**state.get("world_bible", {}))
        characters = _confirm_product(
            "stage2",
            "人物设定",
            lambda: generate_characters(concept, world, cfg, root=state.get("project_root")),
            payload_fn=lambda cs: [c.model_dump() for c in cs],
            rebuild=lambda _p, d: [Character(**x) for x in d],
        )
        return {
            "characters": [c.model_dump() for c in characters],
            "current_stage": "stage3",
            "messages": [*state.get("messages", []), "stage2 人物档案确认"],
        }

    return node


def _stage3(cfg: Config):
    def node(state: NovelState) -> dict:
        concept = Concept(**state.get("concept", {}))
        world = WorldBible(**state.get("world_bible", {}))
        characters = [Character(**c) for c in state.get("characters") or []]
        outline = _confirm_product(
            "stage3",
            "全书总纲",
            lambda: generate_outline(concept, world, characters, cfg),
            rebuild=lambda _p, d: Outline(**d),
        )
        return {
            "outline": outline.model_dump(),
            "current_stage": "stage4a",
            "messages": [*state.get("messages", []), "stage3 总纲确认"],
        }

    return node


def _stage4a(cfg: Config):
    def node(state: NovelState) -> dict:
        outline = Outline(**state.get("outline", {}))
        plans = _confirm_product(
            "stage4a",
            "卷级细纲",
            lambda: generate_volume_plans(outline, cfg),
            payload_fn=lambda ps: [p.model_dump() for p in ps],
            rebuild=lambda _p, d: [VolumePlan(**x) for x in d],
        )
        return {
            "volume_plans": [p.model_dump() for p in plans],
            "current_volume": 1,
            "current_chapter": 1,
            "writer_packets": {},
            "chapters": {},
            "current_stage": "stage4b",
            "messages": [*state.get("messages", []), "stage4a 卷级细纲确认"],
        }

    return node


def _stage4b(cfg: Config):
    def node(state: NovelState) -> dict:
        plans = [VolumePlan(**p) for p in state.get("volume_plans") or []]
        vol = int(state.get("current_volume", 1))
        ch = int(state.get("current_chapter", 1))
        if vol < 1 or vol > len(plans):
            raise ValueError(f"卷{vol} 超出卷规划范围（共 {len(plans)} 卷），章节游标与卷规划不一致")
        plan = plans[vol - 1]
        outline = Outline(**state.get("outline", {}))
        characters = [Character(**c) for c in state.get("characters") or []]
        from novel_agent.agents.packet import collect_pending_foreshadow
        from novel_agent.library.searcher import tools_for_chapter

        pending_fs = collect_pending_foreshadow(state.get("writer_packets"))
        techniques = state.get("techniques")
        blueprint = state.get("narrative_blueprint")
        root = state.get("project_root")
        plan_tools = tools_for_chapter(
            root,
            {"goal": " ".join(plan.event_arc or []), "hook": plan.ending_hook or "", "title": plan.title or ""},
            top_k=int(cfg.library.get("tool_top_k", 3)),
        ) if root else []
        packet = _confirm_product(
            "stage4b",
            "章级规划",
            lambda: generate_writer_packet(
                plan, outline, characters, ch, cfg,
                pending_foreshadow=pending_fs, techniques=techniques, blueprint=blueprint, tools=plan_tools,
            ),
            rebuild=lambda _p, d: WriterPacket(**d),
        )
        packets = dict(state.get("writer_packets") or {})
        packets[f"{vol}_{ch}"] = packet.model_dump()
        return {
            "writer_packets": packets,
            "current_stage": "stage5",
            "messages": [*state.get("messages", []), f"stage4b 第{vol}卷第{ch}章 packet 确认"],
        }

    return node


def _stage5(cfg: Config):
    def node(state: NovelState) -> dict:
        vol = int(state.get("current_volume", 1))
        ch = int(state.get("current_chapter", 1))
        raw_packet = (state.get("writer_packets") or {}).get(f"{vol}_{ch}")
        if not raw_packet:
            raise ValueError(f"缺少第{vol}卷第{ch}章的章级规划，请先完成章级规划环节")
        packet = WriterPacket(**raw_packet)
        memory_context = _memory_context(state, cfg)
        rag_context = _rag_context(state, packet, ch, cfg)
        from novel_agent.library.searcher import tools_for_chapter

        chapter_tools = tools_for_chapter(
            state.get("project_root"), packet.model_dump(),
            top_k=int(cfg.library.get("tool_top_k", 3)),
        ) if state.get("project_root") else []

        # 智能研究模式：写手自主决定查询状态卡/伏笔账本/档案/前文片段
        research_digest = ""
        if _agentic_research_enabled(cfg):
            try:
                from novel_agent.agents.writer_research import run_research
                from novel_agent.agents.writer_tools import WriterCtx

                wctx = WriterCtx(values=state, vol=vol, ch=ch,
                                 root=state.get("project_root", "."), cfg=cfg)
                research_digest = run_research(
                    wctx, packet.model_dump(), discussion="",
                    baseline=memory_context, cfg=cfg,
                    max_rounds=_max_research_rounds(cfg),
                )
            except Exception as exc:  # noqa: BLE001
                from novel_agent.logutil import get_logger

                get_logger().warning("[stage5] 研究循环失败，回退常规写作: %s", exc)

        chapter = _confirm_product(
            "stage5",
            "章节正文",
            lambda: generate_chapter(
                packet, cfg, memory_context=memory_context, rag_context=rag_context,
                techniques=state.get("techniques"), blueprint=state.get("narrative_blueprint"),
                tools=chapter_tools, research_digest=research_digest,
            ),
            rebuild=lambda cur, d: (
                edit_scene(cur, d["scene_id"], d.get("instruction", ""), cfg)[0]
                if isinstance(d, dict) and "scene_id" in d
                else Chapter(**d)
            ),
        )
        chapters = dict(state.get("chapters") or {})
        chapters[f"{vol}_{ch}"] = chapter.model_dump()
        proposals = None
        if _agentic_research_enabled(cfg):
            try:
                from novel_agent.agents.writer_research import propose_updates

                proposals = propose_updates(
                    chapter.model_dump(),
                    ((state.get("character_state") or {}).get("entries")) or [],
                    cfg,
                )
            except Exception as exc:  # noqa: BLE001
                from novel_agent.logutil import get_logger

                get_logger().warning("[stage5] 记忆提案失败: %s", exc)
        return {
            "chapters": chapters,
            "writer_proposals": proposals,
            "messages": [*state.get("messages", []), f"stage5 第{vol}卷第{ch}章正文确认"],
        }

    return node


def _agentic_research_enabled(cfg: Config) -> bool:
    """智能研究模式总开关：config.writer.agentic_research 且非 mock 模式。"""
    from novel_agent.agents import is_mock

    return bool((getattr(cfg, "writer", {}) or {}).get("agentic_research")) and not is_mock()


def _max_research_rounds(cfg: Config) -> int:
    return max(1, int((getattr(cfg, "writer", {}) or {}).get("max_research_rounds", 3)))


def _memory_context(state: NovelState, cfg: Config) -> str:
    """分层记忆上下文：近 N 章全文 + 本卷章摘要 + 之前各卷卷摘要 + 人物状态卡。

    覆盖金字塔：紧邻（全文）→ 本卷（章摘要）→ 跨卷（卷摘要）→ 人物认知（状态卡）。
    """
    paths = _project_paths(state)
    parts = []
    window = int(cfg.memory.get("short_window", 5))
    chapters = state.get("chapters") or {}
    short = get_short_term(chapters, window)
    if short:
        parts.append(short)
    midterm = MidTermMemory(paths.memory_dir / "mid_term.json")

    # 本卷已写章摘要（排除短期窗口已覆盖的最近几章，避免重复）
    keys = sorted(chapters.keys(), key=lambda k: [int(x) for x in k.split("_")])
    recent_keys = set(keys[-window:])
    cur_sums = midterm.summaries_for_volume(vol=int(state.get("current_volume", 1)))
    older_cur = {c: s for c, s in cur_sums.items() if f"{state.get('current_volume', 1)}_{c}" not in recent_keys}
    if older_cur:
        parts.append("本卷更早章节摘要：\n" + "\n".join(f"第{c}章：{s}" for c, s in sorted(older_cur.items()))[:4000])

    # 之前各卷卷摘要（跨卷骨架）
    vol_sums = midterm.volume_summaries()
    past_sums = {v: s for v, s in vol_sums.items() if v < int(state.get("current_volume", 1))}
    if past_sums:
        parts.append("之前各卷卷摘要：\n" + "\n".join(f"第{v}卷：{s}" for v, s in sorted(past_sums.items()))[:2000])

    cs = state.get("character_state")
    if cs:
        parts.append(
            "<人物当前状态（截至上一章，写作时必须保持一致：人物只知道该知道的、只在该在的位置）>\n"
            + json.dumps(cs, ensure_ascii=False)[:3000]
            + "\n</人物当前状态（截至上一章）>"
        )
    return "\n\n".join(parts)


def _consistency_context(state: NovelState) -> str:
    """一致性检查的对照上下文：世界观要点 + 人物档案 + 前文摘要 + 人物当前状态。

    没有它，检查模型只能看到本章内容，发现不了跨章设定冲突和 OOC。
    """
    parts = []
    world = state.get("world_bible") or {}
    if world:
        parts.append("<世界观设定>\n" + json.dumps(world, ensure_ascii=False)[:4000] + "\n</世界观设定>")
    chars = [c for c in (state.get("characters") or []) if isinstance(c, dict)]
    if chars:
        brief = [
            {k: c.get(k, "") for k in ("name", "role", "tier", "motivation", "flaw", "appearance", "voice", "background")}
            for c in chars
        ]
        parts.append("<人物档案>\n" + json.dumps(brief, ensure_ascii=False)[:4000] + "\n</人物档案>")
    midterm = MidTermMemory(_project_paths(state).memory_dir / "mid_term.json")
    recent = midterm.recent(5)
    if recent:
        parts.append("<前文摘要>\n" + "\n".join(recent) + "\n</前文摘要>")
    cs = state.get("character_state")
    if cs:
        parts.append("<人物当前状态>\n" + json.dumps(cs, ensure_ascii=False)[:2000] + "\n</人物当前状态>")
    # 挂载手法的检查要点（review 阶段）与暗线揭示纪律
    from novel_agent.agents.blueprint import dark_line_directive

    review_bits = []
    for t in state.get("techniques") or []:
        if isinstance(t, dict) and t.get("apply_stage") in ("review", "all") and (t.get("checklist") or t.get("guidance")):
            checks = "；".join(t.get("checklist") or [])
            review_bits.append(f"【{t.get('name')}】{checks or t.get('guidance', '')}")
    if review_bits:
        parts.append("<写作手法检查要点>\n" + "\n".join(review_bits) + "\n</写作手法检查要点>")
    bp = state.get("narrative_blueprint")
    if bp:
        parts.append(
            dark_line_directive(bp)
            + "\n另请专项检查：正文是否提前点破了任何暗线真相（对照揭示纪律）。"
        )
    return "\n\n".join(parts)


def _rag_context(state: NovelState, packet: WriterPacket, current_chapter: int, cfg: Config) -> str:
    """双 RAG 上下文：向量 top-k ∪ 时序图谱。"""
    paths = _project_paths(state)
    long_term = LongTermMemory(paths.vector_dir / "long_term.json", embed_fn=get_embedder(cfg))
    graph = TemporalGraph(paths.graph_dir / "graph.json")
    seeds = packet.reference_seeds or ([packet.pov] if packet.pov else [])
    return retrieve(seeds, long_term, graph, top_k=int(cfg.rag.get("top_k", 4)), current_chapter=current_chapter)


def _project_paths(state: NovelState) -> ProjectPaths:
    return ProjectPaths(Path(state.get("project_root", ".")), state.get("project_id", "unknown"))


def _stage6(cfg: Config):
    def node(state: NovelState) -> dict:
        vol = int(state.get("current_volume", 1))
        ch = int(state.get("current_chapter", 1))
        key = f"{vol}_{ch}"
        raw = (state.get("chapters") or {}).get(key)
        if not raw:
            raise ValueError(f"缺少第{vol}卷第{ch}章正文，无法执行一致性检查")
        chapter = Chapter(**raw)
        check_ctx = _consistency_context(state)
        max_auto_fix = int((getattr(cfg, "consistency", {}) or {}).get("max_auto_fix", MAX_AUTO_FIX))
        attempts = 0  # auto-fix 计数按章重置，不跨章累积
        while True:
            report = check_consistency(chapter, cfg, attempts, context=check_ctx)
            while True:
                high = [i for i in report.issues if i.severity == "high" and not i.resolved]
                if not high or attempts >= max_auto_fix:
                    break
                chapter, report = fix_issues(report, chapter, cfg)
                attempts += 1
                report = check_consistency(chapter, cfg, attempts, context=check_ctx)
            high = [i for i in report.issues if i.severity == "high" and not i.resolved]
            if high and attempts >= max_auto_fix:
                report = report.model_copy(update={"needs_human": True})
            # 设计：一致性结果始终走人工确认（含无问题时的"通过"）
            # 载荷附场景清单（id+标题），供前端"人工修复指令"下拉定位场景
            report_payload = report.model_dump()
            report_payload["scenes"] = [
                {"id": s.id, "heading": s.heading} for s in chapter.scenes
            ]
            decision = _decide(_confirmation("stage6", "一致性检查", report_payload))
            if decision["action"] == "regenerate":
                continue  # 重新检查当前章节
            if decision["action"] == "edit":
                data = decision["data"]
                if isinstance(data, dict) and data.get("apply_edits"):
                    # 作者的定点修复指令：逐条改写后重新检查，再次确认
                    for fix in data.get("fixes", []):
                        chapter, _ = edit_scene(chapter, fix.get("scene_id", ""), fix.get("instruction", ""), cfg)
                    continue
            break
        chapters = dict(state.get("chapters") or {})
        chapters[key] = chapter.model_dump()
        return {
            "chapters": chapters,
            "consistency_report": report.model_dump(),
            "auto_fix_attempts": attempts,
            "current_stage": state.get("current_stage"),
            "messages": [*state.get("messages", []), f"stage6 第{vol}卷第{ch}章一致性（auto-fix {attempts} 次）"],
        }

    return node


def _stage7(cfg: Config):
    def node(state: NovelState) -> dict:
        vol = int(state.get("current_volume", 1))
        ch = int(state.get("current_chapter", 1))
        key = f"{vol}_{ch}"
        chapter = state.get("chapters", {}).get(key, {})
        paths = _project_paths(state)
        midterm = MidTermMemory(paths.memory_dir / "mid_term.json")
        long_term = LongTermMemory(paths.vector_dir / "long_term.json", embed_fn=get_embedder(cfg))
        graph = TemporalGraph(paths.graph_dir / "graph.json")
        update_chapter_memory(chapter, cfg, midterm, long_term, graph, state.get("characters"))

        # 人物状态增量 + 路人升级：随章节自动更新（失败不阻断主流程）
        from novel_agent.logutil import get_logger

        log = get_logger()
        proposals = state.get("writer_proposals") or {}
        character_state_update = None
        try:
            from novel_agent.agents.state_update import extract_character_states
            from novel_agent.types.character_state import CharacterState

            prev_state = CharacterState(**state["character_state"]) if state.get("character_state") else None
            # 传原始 dict（agent 内部按 dict 处理，Pydantic 对象会破坏 mock 分支）
            characters = state.get("characters") or []
            new_state = extract_character_states(
                chapter, characters, prev_state, cfg,
                author_hints=proposals.get("state_updates") or None,
            )
            character_state_update = new_state.model_dump()
        except Exception as exc:  # noqa: BLE001
            log.warning("[stage7] 人物状态更新失败: %s", exc)

        new_chars: list = []
        try:
            from novel_agent.agents.recurring import extract_recurring_characters

            new_chars = extract_recurring_characters(chapter, state.get("characters") or [], cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("[stage7] 路人升级失败: %s", exc)

        # 章节事件提炼：写入领域状态目录（供写作上下文按需查询）
        try:
            from novel_agent.agents.chapter_event import extract_chapter_event
            from novel_agent.storage import write_json_atomic

            event = extract_chapter_event(chapter, vol, cfg)
            event_dir = paths.data_dir / "domains" / "events"
            event_dir.mkdir(parents=True, exist_ok=True)
            write_json_atomic(event_dir / f"chapter_{ch}.json", event)
        except Exception as exc:  # noqa: BLE001
            log.warning("[stage7] 章节事件提炼失败: %s", exc)

        # 记忆更新完成后推进章节游标
        nxt = _next_position(state.get("volume_plans") or [], vol, ch)
        finished = nxt is None
        next_vol, next_ch = nxt if nxt else (vol, ch)

        # 卷完成时聚合卷摘要（换卷/全书完成触发；失败不阻断）
        if finished or next_vol > vol:
            try:
                vol_summary = midterm.summarize_volume(vol, cfg)
                if vol_summary:
                    midterm.set_volume_summary(vol, vol_summary)
            except Exception as exc:  # noqa: BLE001
                log.warning("[stage7] 卷摘要聚合失败: %s", exc)

        updates = {
            "current_volume": next_vol,
            "current_chapter": next_ch,
            "current_stage": "done" if finished else "stage4b",
            "memory_notes": [*state.get("memory_notes", []), f"第{vol}卷第{ch}章记忆已更新"],
            "messages": [*(state.get("messages", [])[-30:]), f"stage7 第{vol}卷第{ch}章记忆更新"],
            # 写手提案已作为 author_hints 消费（见上方提取调用），此处清除
            "writer_proposals": None,
        }
        if character_state_update is not None:
            updates["character_state"] = character_state_update
        if new_chars:
            updates["characters"] = [
                *(state.get("characters") or []),
                *[c.model_dump() for c in new_chars],
            ]
        return updates

    return node


def _next_position(
    plans: list[dict], vol: int, ch: int
) -> tuple[int, int] | None:
    """返回下一章位置 (vol, ch)；写完返回 None。"""
    if vol < 1 or vol > len(plans):
        return None
    if ch < int(plans[vol - 1].get("chapter_count", 0)):
        return (vol, ch + 1)
    if vol < len(plans):
        return (vol + 1, 1)
    return None


def _stage8(cfg: Config):
    def node(state: NovelState) -> dict:
        outline = Outline(**state.get("outline", {}))
        chapters = state.get("chapters") or {}
        characters = state.get("characters")
        report = _confirm_product(
            "stage8",
            "编辑审校",
            lambda: generate_editorial_report(outline, chapters, characters, cfg),
            rebuild=lambda _p, d: EditorialReport(**d),
        )
        return {
            "editorial_report": report.model_dump(),
            "messages": [*state.get("messages", []), "stage8 全书终审确认"],
        }

    return node


def _stage9(cfg: Config):
    def node(state: NovelState) -> dict:
        paths = _project_paths(state)
        final_paths = assemble_final(state, cfg, paths)
        return {
            "final_paths": final_paths,
            "current_stage": "done",
            "messages": [*state.get("messages", []), f"stage9 导出完成：{len(final_paths)} 个文件"],
        }

    return node


def _after_stage7(state: NovelState) -> str:
    """记忆更新完成后推进：还有章 → stage4b；写完 → stage8 终审。"""
    return "stage4b" if state.get("current_stage") == "stage4b" else "stage8"


def build_graph(cfg: Config) -> StateGraph:
    g = StateGraph(NovelState)
    g.add_node("stage0", _stage0(cfg))
    g.add_node("stage1", _stage1(cfg))
    g.add_node("stage2", _stage2(cfg))
    g.add_node("stage3", _stage3(cfg))
    g.add_node("stage4a", _stage4a(cfg))
    g.add_node("stage4b", _stage4b(cfg))
    g.add_node("stage5", _stage5(cfg))
    g.add_node("stage6", _stage6(cfg))
    g.add_node("stage7", _stage7(cfg))
    g.add_node("stage8", _stage8(cfg))
    g.add_node("stage9", _stage9(cfg))
    g.add_edge(START, "stage0")
    g.add_edge("stage0", "stage1")
    g.add_edge("stage1", "stage2")
    g.add_edge("stage2", "stage3")
    g.add_edge("stage3", "stage4a")
    g.add_edge("stage4a", "stage4b")
    g.add_edge("stage4b", "stage5")
    g.add_edge("stage5", "stage6")
    g.add_edge("stage6", "stage7")
    g.add_conditional_edges(
        "stage7",
        _after_stage7,
        {"stage4b": "stage4b", "stage8": "stage8"},
    )
    g.add_edge("stage8", "stage9")
    g.add_edge("stage9", END)
    return g


def compile_graph(cfg: Config, checkpointer=None) -> CompiledStateGraph:
    """编译图。默认 MemorySaver；持久化用 SqliteSaver（M5 接入）。"""
    return build_graph(cfg).compile(checkpointer=checkpointer or MemorySaver())


def compile_persistent_graph(cfg: Config, db_path: Path) -> CompiledStateGraph:
    """编译为 SQLite 持久化图：断点跨进程保留，thread_id = project_id。"""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    compiled = build_graph(cfg).compile(checkpointer=saver)
    compiled._sqlite_conn = conn  # 供 RuntimeStore.invalidate 关闭连接，避免文件占用
    return compiled
