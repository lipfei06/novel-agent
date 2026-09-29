"""F16 API 路由：项目 / 确认点 / 导出。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel

from novel_agent.config import ConfigError
from novel_agent.storage import ProjectManager, ProjectPaths

from .runtime import RuntimeStore

router = APIRouter(prefix="/api")


class CreateProjectIn(BaseModel):
    title: str
    genre: str = "webnovel"
    project_id: str | None = None


class StartRunIn(BaseModel):
    idea: str = ""


class ConfirmIn(BaseModel):
    action: str = "accept"  # accept | edit
    data: dict | None = None


def _pm(request: Request) -> ProjectManager:
    root: Path = request.app.state.root
    return ProjectManager(root)


def _store(request: Request) -> RuntimeStore:
    return request.app.state.runtime


def _interrupt_payload(runtime) -> dict | None:
    """返回当前确认点载荷；若无有效 interrupt 返回 None。

    注意：不能用 st.next 判断——节点内循环再次 interrupt() 后 next 为空，
    但 task.interrupts 仍持有待确认项。
    """
    st = runtime.graph.get_state(runtime.thread)
    for task in st.tasks or ():
        interrupts = getattr(task, "interrupts", ()) or ()
        if interrupts:
            return interrupts[-1].value
    return None


def _confirm_view(runtime) -> dict:
    """返回确认视图。若流水线无产出但已有旁路章节，视为过时状态（不再显示确认）。"""
    st = runtime.graph.get_state(runtime.thread)
    info = _interrupt_payload(runtime)
    values = st.values

    chapters = values.get("chapters") or {}
    packets = values.get("writer_packets") or {}

    # 已有旁路章节且流水线从未产出 packet → 流水线状态过时，跳过确认
    if chapters and not packets:
        return {
            "done": True,
            "stage": None,
            "stage_label": None,
            "payload": None,
            "current_stage": values.get("current_stage"),
            "current_volume": values.get("current_volume"),
            "current_chapter": values.get("current_chapter"),
        }

    if info is None:
        return {
            "done": True,
            "stage": None,
            "stage_label": None,
            "payload": None,
            "current_stage": values.get("current_stage"),
            "current_volume": values.get("current_volume"),
            "current_chapter": values.get("current_chapter"),
        }
    return {
        "done": False,
        "stage": info["stage"],
        "stage_label": info["stage_label"],
        "payload": info["payload"],
        "current_stage": values.get("current_stage"),
        "current_volume": values.get("current_volume"),
        "current_chapter": values.get("current_chapter"),
    }


def _volume_source(runtime, values: dict) -> list[dict]:
    """卷规划数据源：已提交 volume_plans → stage4a 待确认提案 → 总纲分卷草稿。"""
    plans = values.get("volume_plans") or []
    if plans:
        return list(plans)
    info = _interrupt_payload(runtime)
    if info and info.get("stage") == "stage4a":
        return list(info.get("payload") or [])
    return list((values.get("outline") or {}).get("volumes") or [])


def _ensure_setup_confirmed(runtime) -> None:
    """卷级细纲待确认时禁止旁路写入，避免手工数据在确认后被提案覆盖。"""
    info = _interrupt_payload(runtime)
    if info and info.get("stage") == "stage4a":
        raise HTTPException(
            status_code=409,
            detail="卷级细纲正在等待确认，请先在工作台完成该确认步骤",
        )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/profiles")
def profiles(request: Request) -> dict:
    from novel_agent.config import PROFILES_DIR, list_profiles

    return {"profiles": list_profiles(PROFILES_DIR)}


@router.post("/projects")
def create_project(body: CreateProjectIn, request: Request) -> dict:
    pm = _pm(request)
    try:
        paths = pm.create(body.project_id, body.genre, body.title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "project_id": paths.project_id,
        "title": body.title,
        "genre": body.genre,
        "dirs": {"project": str(paths.project_dir), "data": str(paths.data_dir)},
    }


@router.get("/projects")
def list_projects(request: Request) -> dict:
    """列出项目，并附带从图状态实时计算的章节数/卷数/阶段。"""
    store: RuntimeStore = _store(request)
    projects = []
    for m in _pm(request).list():
        info = m.__dict__
        try:
            runtime = store.get_or_create(m.project_id, m.genre)
            values = runtime.graph.get_state(runtime.thread).values
            chapters = values.get("chapters") or {}
            volumes = _volume_source(runtime, values)
            info["chapters"] = len(chapters)
            info["volumes"] = len(volumes)
            if chapters:
                info["stage"] = "写作中"
            elif volumes:
                info["stage"] = "设定完成"
            else:
                info["stage"] = "设定中"
        except Exception:
            info["chapters"] = 0
            info["volumes"] = 0
            info["stage"] = m.current_stage
        projects.append(info)
    return {"projects": projects}


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return meta.__dict__


@router.post("/projects/{project_id}/start")
def start_run(project_id: str, body: StartRunIn, request: Request) -> dict:
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    store: RuntimeStore = _store(request)
    runtime = store.get_or_create(project_id, meta.genre)

    pending = _interrupt_payload(runtime)
    if pending is not None:
        # 已有进行中的确认点
        return _confirm_view(runtime)

    initial = {
        "project_id": project_id,
        "project_root": str(store.root),
        "genre": meta.genre,
        "title": meta.title,
        "user_idea": (body.idea or "").strip().lstrip("\ufeff"),
        "messages": [],
    }
    try:
        from novel_agent.llm.cost import set_project

        set_project(project_id, request.app.state.root)
        runtime.graph.invoke(initial, runtime.thread)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动创作失败：{exc}") from exc
    return _confirm_view(runtime)


@router.post("/projects/{project_id}/confirm")
def confirm(project_id: str, body: ConfirmIn, request: Request) -> dict:
    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime = store.get_or_create(project_id, meta.genre)
    from novel_agent.llm.factory import LLMStructuredError

    if _interrupt_payload(runtime) is None:
        st = runtime.graph.get_state(runtime.thread)
        if st.next:
            # 上一节点崩溃（如预算超限/LLM 故障）导致停在"有断点、无确认点"状态：
            # 从 checkpoint 恢复执行，让作者修完原因后 confirm 即可续跑
            from novel_agent.llm.cost import set_project

            set_project(project_id, request.app.state.root)
            try:
                runtime.graph.invoke(None, runtime.thread)
            except HTTPException:
                raise
            except LLMStructuredError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"{exc} 图状态已停在断点，稍候重新点击「接受」即可续跑。",
                ) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"断点恢复失败：{exc}") from exc
            return _confirm_view(runtime)
        # 没有待确认点（已完成或未开始）
        return _confirm_view(runtime)

    resume = {"action": body.action}
    if body.data is not None:
        resume["data"] = body.data
    try:
        from novel_agent.llm.cost import set_project

        # cost 记账走线程局部变量，必须在执行 LLM 调用的本线程上标记项目
        set_project(project_id, request.app.state.root)
        runtime.graph.invoke(Command(resume=resume), runtime.thread)
    except HTTPException:
        raise
    except LLMStructuredError as exc:
        # LLM 瞬时故障/格式失败：图状态已停在断点，重试即可恢复——用 503 而非 500 表达"可重试"
        raise HTTPException(
            status_code=503,
            detail=f"{exc} 图状态已停在断点，稍候重新点击「接受」即可续跑。",
        ) from exc
    except Exception as exc:
        # 把真实失败原因返回给前端，避免笼统的 500
        raise HTTPException(status_code=500, detail=f"环节执行失败：{exc}") from exc
    return _confirm_view(runtime)


@router.get("/projects/{project_id}/events")
async def project_events(project_id: str, request: Request):
    """SSE：推送该项目的历史日志 + 当前确认点。"""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime = store.get_or_create(project_id, meta.genre)
    st = runtime.graph.get_state(runtime.thread)
    msgs = st.values.get("messages", [])
    view = _confirm_view(runtime)

    async def gen():
        for m in msgs:
            yield f"event: log\ndata: {json.dumps({'message': m}, ensure_ascii=False)}\n\n"
        if not view["done"]:
            yield f"event: confirmation\ndata: {json.dumps(view, ensure_ascii=False)}\n\n"
        yield f"event: eof\ndata: {json.dumps({'done': view['done']}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/projects/{project_id}/state")
def project_state(project_id: str, request: Request) -> dict:
    """返回项目当前状态：是否已开始、是否完成、当前确认点（刷新页面时恢复用）。"""
    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = store.get_or_create(project_id, meta.genre)
    st = runtime.graph.get_state(runtime.thread)
    values = st.values
    info = _interrupt_payload(runtime)
    started = info is not None or bool(values.get("concept")) or bool(values.get("chapters")) or bool(values.get("messages"))
    return {
        "started": started,
        "done": info is None and not st.next,
        "stage": info["stage"] if info else None,
        "stage_label": info["stage_label"] if info else None,
        "payload": info["payload"] if info else None,
        "current_stage": values.get("current_stage"),
    }


class UpdateProductIn(BaseModel):
    field: str  # concept | world_bible | characters | outline | volume_plans
    value: dict | list


@router.put("/projects/{project_id}/products")
def update_product(project_id: str, body: UpdateProductIn, request: Request) -> dict:
    """表单保存某个设定（选题/世界/人物/总纲/卷规划）到图状态。"""
    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.field not in ("concept", "world_bible", "characters", "outline", "volume_plans", "techniques", "narrative_blueprint"):
        raise HTTPException(status_code=400, detail=f"不支持的设定字段：{body.field}")
    runtime = store.get_or_create(project_id, meta.genre)
    # 有待确认点时禁止改设定：update_state 会清掉挂起的中断（待确认的规划/正文随之丢失）
    if _interrupt_payload(runtime) is not None:
        stage = _interrupt_payload(runtime).get("stage")
        raise HTTPException(
            status_code=409,
            detail=f"当前有『{stage}』环节待确认。请先在确认页处理（接受/放弃）后再修改设定，"
                   f"否则待确认内容会被静默清掉。",
        )
    try:
        runtime.graph.update_state(runtime.thread, {body.field: body.value})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存失败：{exc}") from exc
    return {"ok": True, "field": body.field}


@router.post("/projects/{project_id}/export")
def export_now(project_id: str, request: Request) -> dict:
    """立即导出当前已接受的章节（不必等全书写完）。"""
    import json as _json

    from novel_agent.export import assemble_final

    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = store.get_or_create(project_id, meta.genre)
    values = runtime.graph.get_state(runtime.thread).values
    chapters = values.get("chapters")
    if not chapters:
        raise HTTPException(status_code=400, detail="还没有已接受的章节，无法导出")
    cfg = store.load_config(meta.genre)
    paths = ProjectPaths(request.app.state.root, project_id)
    files = assemble_final({**values, "chapters": chapters}, cfg, paths)
    return {"ok": True, "files": files}


class VolumeIn(BaseModel):
    generate: bool = False  # True: 由 AI 依据总纲生成全部分卷；False: 手工新增一卷
    volume: dict | None = None  # generate=False 时提供


class ChapterFormIn(BaseModel):
    title: str = ""
    goal: str = ""
    conflicts: list[str] = []
    hook: str = ""
    notes: str = ""
    auto_plan: bool = True  # True: 由 AI 依据卷设定生成 writer_packet；False: 仅按表单生成
    chat_context: str = ""  # 章节对话场景（如 chapter_1_2），存在则把讨论内容纳入设计
    agentic: bool = False  # 智能研究模式：写手自主查询状态卡/伏笔账本/前文片段
    must_use_memes: list[str] = []  # 作者指定的本章必用梗（按梗库名称精确匹配）


def _project_ctx(request: Request, project_id: str, genre: str) -> tuple[RuntimeStore, ProjectRuntime, dict, Config]:
    """获取项目运行上下文（store/runtime/state values/config）。"""
    from novel_agent.llm.cost import set_project, set_chapter

    set_project(project_id, request.app.state.root)
    set_chapter(None)  # 默认不带章节归属（章节级调用点会再显式标记）
    store: RuntimeStore = _store(request)
    runtime = store.get_or_create(project_id, genre)
    values = runtime.graph.get_state(runtime.thread).values
    cfg = store.load_config(genre)
    return store, runtime, values, cfg


def _mem_paths(root: Path, project_id: str):
    p = ProjectPaths(root, project_id)
    return p.memory_dir / "mid_term.json", p.vector_dir / "long_term.json", p.graph_dir / "graph.json"


def _bounded(text: str, max_chars: int) -> str:
    """按字符上限截断长上下文（保留尾部）。

    短期记忆的价值随时间递减：最新章节的结尾（上一章钩子/最新走向）对连贯性
    最重要，超限时牺牲最早的内容而不是最新的。
    """
    if len(text) <= max_chars:
        return text
    return "…（更早内容已省略）\n" + text[-max_chars:]


def _build_writing_context(values: dict, packet, cfg: Config, root: Path, project_id: str) -> tuple[str, str]:
    """短期记忆 + 中期摘要 + 双 RAG + 主要人物状态（均设上限）。"""
    from novel_agent.memory import LongTermMemory, MidTermMemory, get_short_term
    from novel_agent.rag import TemporalGraph, retrieve
    from novel_agent.types.character_state import CharacterState, CharacterStateEntry

    mid_p, vec_p, graph_p = _mem_paths(root, project_id)
    parts = []
    full_window = int(cfg.memory.get("full_window", 1))
    all_keys = sorted(
        (values.get("chapters") or {}).keys(),
        key=lambda k: [int(x) for x in str(k).split("_")],
    )
    recent_keys = set(all_keys[-full_window:])
    short = _bounded(get_short_term(values.get("chapters") or {}, full_window), 12000)
    midterm = MidTermMemory(mid_p)
    vol = int(packet.volume or 1)
    cur_sums = midterm.summaries_for_volume(vol)
    older_cur = {c: s for c, s in cur_sums.items() if f"{vol}_{c}" not in recent_keys}
    if older_cur:
        parts.append("本卷更早章节摘要：\n" + _bounded(
            "\n".join(f"第{c}章：{s}" for c, s in sorted(older_cur.items())), 4000))
    vol_sums = midterm.volume_summaries()
    past_sums = {v: s for v, s in vol_sums.items() if v < vol}
    if past_sums:
        parts.append("之前各卷卷摘要：\n" + _bounded(
            "\n".join(f"第{v}卷：{s}" for v, s in sorted(past_sums.items())), 2000))
    if short:
        # 缓存友好（OPT-D）：摘要（稳定）在前，最近全文在后
        parts.append("最近章节全文：\n" + short)
    memory_context = "\n\n".join(parts)

    # 登场人物速查卡（main/supporting：外貌、声音、动机；background 不收录）
    chars = values.get("characters") or []
    notable = [c for c in chars if c.get("tier") in ("main", "supporting")]
    if notable:
        card = []
        for c in notable:
            bits = []
            if c.get("appearance"):
                bits.append(f"外貌={c['appearance']}")
            if c.get("voice"):
                bits.append(f"声音={c['voice']}")
            if c.get("motivation"):
                bits.append(f"动机={c['motivation']}")
            card.append(f"- {c.get('name', c.get('id', '?'))}：{'；'.join(bits)}")
        memory_context += "\n\n<人物速查卡>\n" + "\n".join(card) + "\n</人物速查卡>"

    # 主要人物当前状态注入（确保言行/处境一致）
    cs = values.get("character_state") or {}
    entries = cs.get("entries", [])
    if entries:
        lines = []
        for e in entries:
            lines.append(
                f"- {e.get('name', e.get('character_id', '?'))}："
                f"状态={e.get('status', 'active')} · 位置={e.get('location', '?')} · 情绪={e.get('mood', '?')} · "
                f"健康={e.get('health', '?')} · 弧光阶段={e.get('arc_stage', '?')} · "
                f"目标进展={e.get('goal_progress', '?')} · 知道={e.get('knowledge', '?')}"
            )
        memory_context += "\n\n<主要人物当前状态>\n" + "\n".join(lines) + "\n</主要人物当前状态>"

    long_term = LongTermMemory(vec_p)
    graph = TemporalGraph(graph_p)
    seeds = list(packet.reference_seeds or [])
    if not seeds and packet.pov:
        seeds = [packet.pov]
    if not seeds:
        # 聊天等场景构造的空 packet 没有检索种子：回退为主要角色名，
        # 保证向量检索与时序图谱这两路上下文不失效
        seeds = [
            c.get("name", "")
            for c in (values.get("characters") or [])
            if isinstance(c, dict) and c.get("name") and c.get("tier") == "main"
        ][:3]
    seeds = [s for s in seeds if s]
    ch = int(packet.chapter or 0)
    rag_context = retrieve(
        seeds, long_term, graph,
        top_k=int(cfg.rag.get("top_k", 4)),
        current_vol=vol, current_chapter=ch,
        annotate=True,
    )
    # 梗库候选：写手只从检索命中的候选里选用（梗有强时效性，模型自带的会过时）
    from novel_agent.library.searcher import meme_candidates_text

    meme_block = meme_candidates_text(f"{packet.title} {packet.goal}", root=root)
    if meme_block:
        memory_context += f"\n\n{meme_block}"
    return memory_context, rag_context


class ChapterUpdateIn(BaseModel):
    chapter: dict  # 完整章节对象（含 scenes）


@router.put("/projects/{project_id}/chapters/{vol}/{ch}")
def update_chapter(project_id: str, vol: int, ch: int, body: ChapterUpdateIn, request: Request) -> dict:
    """修改已保存的章节内容（表单编辑后保存）。旧稿自动留底，可在历史版本中恢复。"""
    from novel_agent.types import Chapter

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    key = f"{vol}_{ch}"
    chapters = dict(values.get("chapters") or {})
    if key not in chapters:
        raise HTTPException(status_code=404, detail=f"章节 {key} 不存在")
    try:
        chapter = Chapter(**body.chapter)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"章节数据校验失败：{exc}") from exc
    chapter = chapter.model_copy(update={"volume": vol, "chapter": ch})
    old = chapters.get(key)
    if old:
        from novel_agent.storage.versions import snapshot_chapter

        snapshot_chapter(request.app.state.root, project_id, old, "编辑覆盖")
    chapters[key] = chapter.model_dump()
    runtime.graph.update_state(runtime.thread, {"chapters": chapters})
    _replay_chapter_memory(request, runtime, values, cfg, project_id, chapter, key)
    return {"ok": True, "chapter": chapter.model_dump()}


def _replay_chapter_memory(request: Request, runtime, values, cfg, project_id: str,
                           chapter, key: str) -> None:
    """编辑/恢复覆盖后按新正文重放三层检索记忆与事件账本（旧索引先按章移除）。

    否则后续章节的摘要/RAG/正典注入仍是旧版——改得越多记忆漂移越厉害。
    character_state 与道具卡不重放：状态是跨章累积推导、道具事实只增，
    编辑后重放会重复或回退；大幅改剧情应走重写流程而非编辑。
    """
    try:
        from novel_agent.agents.understanding import merge_canon_updates, understand_chapter
        from novel_agent.llm import get_embedder
        from novel_agent.llm.cost import set_chapter, set_project
        from novel_agent.logutil import get_logger
        from novel_agent.memory import LongTermMemory, MidTermMemory, update_chapter_memory
        from novel_agent.rag import TemporalGraph

        root = request.app.state.root
        vol, ch = int(chapter.volume or 1), int(chapter.chapter or 1)
        set_project(project_id, root)
        set_chapter(key)  # 重放的理解调用计入该章成本
        log = get_logger()
        mid_p, vec_p, graph_p = _mem_paths(root, project_id)
        try:
            understanding = understand_chapter(
                chapter.model_dump(), values.get("characters") or [],
                (values.get("character_state") or {}).get("entries", []), cfg,
            )
        except Exception as exc:
            log.warning("[编辑同步] 章节理解失败，退回独立抽取: %s", exc)
            understanding = None
        long_term = LongTermMemory(vec_p, embed_fn=get_embedder(cfg))
        graph = TemporalGraph(graph_p)
        long_term.remove_chapter(vol, ch)
        graph.remove_chapter(vol, ch)
        update_chapter_memory(
            chapter.model_dump(), cfg, MidTermMemory(mid_p), long_term, graph,
            values.get("characters"), understanding=understanding,
        )
        if understanding is not None:
            # 事件账本按 vol_ch 整章替换（幂等）；道具卡只增，跳过防重复
            el, _pr = merge_canon_updates(
                values.get("event_ledger"), values.get("prop_registry"), vol, ch, understanding,
            )
            runtime.graph.update_state(runtime.thread, {"event_ledger": el})
    except Exception as exc:
        from novel_agent.logutil import get_logger

        get_logger().warning("[编辑同步] 记忆重放失败（章节已保存，可稍后重建记忆）: %s", exc)


@router.delete("/projects/{project_id}/volumes/{vol}/chapters/{ch}")
def delete_saved_chapter(project_id: str, vol: int, ch: int, request: Request) -> dict:
    """删除已保存的章节（仅限全书最新一章）。

    删除中间章节会导致后续编号错位、短期记忆窗口与摘要出现断层，
    因此只允许回退最新一章。删除时同步回滚：中期摘要、长期向量（按
    章节 meta 精准移除）、时序图谱（按 vol_ch 移除该章边）。无 meta 的
    旧格式向量块无法定位，不参与回滚（残留仅为少量召回噪声）。
    """
    from novel_agent.logutil import get_logger
    from novel_agent.types import Chapter

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)

    key = f"{vol}_{ch}"
    chapters = dict(values.get("chapters") or {})
    if key not in chapters:
        raise HTTPException(status_code=404, detail=f"章节 {key} 不存在")

    # 删除前自动留底：误删可在卷卡「🕘 备份」中找回
    from novel_agent.storage.versions import snapshot_chapter

    snapshot_chapter(request.app.state.root, project_id, chapters[key], "删除备份")

    def _k2tuple(k: str) -> tuple[int, int]:
        try:
            a, b = str(k).split("_")
            return (int(a), int(b))
        except ValueError:
            return (0, 0)

    last_key = max(chapters.keys(), key=_k2tuple)
    if key != last_key:
        latest = chapters[last_key]
        raise HTTPException(
            status_code=409,
            detail=f"只能删除最新章节（当前为：第{latest.get('volume')}卷第{latest.get('chapter')}章 "
            f"《{latest.get('title', '')}》）。删除中间章节会破坏章节编号与前后文连贯性。",
        )

    chapters.pop(key)
    updates: dict = {"chapters": chapters, "pending_chapter": None}
    packets = dict(values.get("writer_packets") or {})
    if key in packets:
        packets.pop(key)
        updates["writer_packets"] = packets
    runtime.graph.update_state(runtime.thread, updates)

    # 同步回滚：中期摘要 + 长期向量（按章节 meta）+ 时序图谱（按 vol_ch）
    try:
        from novel_agent.logutil import get_logger
        from novel_agent.llm import get_embedder
        from novel_agent.memory import LongTermMemory, MidTermMemory
        from novel_agent.rag import TemporalGraph

        paths = ProjectPaths(request.app.state.root, project_id)
        MidTermMemory(paths.memory_dir / "mid_term.json").remove(vol, ch)
        _, vec_p, graph_p = _mem_paths(request.app.state.root, project_id)
        cfg = _store(request).load_config(meta.genre)
        # embed_fn 必须与库 mode 一致，否则模式不匹配会把整库当空库，save 时会清空原向量
        removed_vec = LongTermMemory(vec_p, embed_fn=get_embedder(cfg)).remove_chapter(vol, ch)
        removed_edges = TemporalGraph(graph_p).remove_chapter(vol, ch)
        get_logger().info(
            f"[delete_chapter] 已回滚第{vol}卷第{ch}章：向量 {removed_vec} 块、图谱 {removed_edges} 边"
        )
    except Exception as exc:
        from novel_agent.logutil import get_logger

        get_logger().warning("[delete_chapter] 记忆回滚失败: %s", exc)

    remaining = len(chapters)
    return {"ok": True, "deleted": key, "remaining_chapters": remaining}


class MemoryRebuildIn(BaseModel):
    scope: str = "all"  # vector | graph | all


@router.post("/projects/{project_id}/memory/rebuild")
def rebuild_project_memory(project_id: str, body: MemoryRebuildIn, request: Request) -> dict:
    """从全量已接受章节重建向量库与时序图谱（记忆一致性兜底阀）。

    清空目标库后按章号升序重放"场景切片 + 关系抽取"（与增量写入同一份逻辑）。
    中期摘要不重算。真实模式下图谱重建每章消耗一次 cheap 调用。
    """
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    scope = str(body.scope or "all").lower()
    if scope not in ("vector", "graph", "all"):
        raise HTTPException(status_code=400, detail=f"非法 scope：{body.scope}（可选 vector/graph/all）")
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    chapters = values.get("chapters") or {}
    if not chapters:
        raise HTTPException(status_code=400, detail="项目暂无已接受章节，无需重建")

    from novel_agent.llm import get_embedder
    from novel_agent.memory import LongTermMemory, rebuild_memory
    from novel_agent.rag import TemporalGraph

    _, vec_p, graph_p = _mem_paths(request.app.state.root, project_id)
    cfg = _store(request).load_config(meta.genre)
    # embed_fn 必须与库 mode 一致，否则模式不匹配会当空库、save 时清空原向量
    lt = LongTermMemory(vec_p, embed_fn=get_embedder(cfg)) if scope in ("vector", "all") else None
    g = TemporalGraph(graph_p) if scope in ("graph", "all") else None
    stats = rebuild_memory(chapters, cfg, long_term=lt, graph=g, characters=values.get("characters") or [])
    return {"ok": True, "scope": scope, **stats}


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, request: Request) -> dict:
    """返回该项目累计的 token 用量与估算费用。"""
    from novel_agent.llm.cost import get_cost

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    cfg = _store(request).load_config(meta.genre)
    return get_cost(request.app.state.root, project_id, cfg.cost)


def _regenerate_job(project_id: str, vol: int, ch: int, instruction: str, chat_context: str,
                    request: Request, agentic: bool = False):
    """构造"按讨论重新生成整章"的后台 job。"""
    from novel_agent.agents.write import rewrite_chapter
    from novel_agent.api.chat import valid_context
    from novel_agent.types import WriterPacket

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    key = f"{vol}_{ch}"
    chapters = values.get("chapters") or {}
    existing = chapters.get(key)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"章节 {key} 不存在")

    if chat_context and not valid_context(chat_context):
        raise HTTPException(status_code=400, detail="未知的对话场景")

    root = request.app.state.root

    def job(progress):
        progress("读取原章与前文记忆…", 10)
        final_instruction = instruction
        if chat_context:
            progress("提炼聊天讨论的改写方向…", 25)
            from novel_agent.api.chat import _chat_path, load_history, summarize_chat_design

            msgs = load_history(_chat_path(root, project_id, chat_context))
            if msgs:
                try:
                    discussion = summarize_chat_design(msgs, cfg)
                except Exception:
                    discussion = "\n".join(
                        f"{'作者' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}" for m in msgs[-8:]
                    )
                final_instruction = (
                    f"{final_instruction.strip()}\n\n" if final_instruction.strip() else ""
                ) + f"<作者在聊天中讨论的重写方向>\n{discussion}\n</作者在聊天中讨论的重写方向>"

        packets = values.get("writer_packets") or {}
        packet = WriterPacket(**packets.get(key, {})) if packets.get(key) else None
        if packet is None:
            packet = WriterPacket(volume=vol, chapter=ch, title=existing.get("title", ""), goal="重写本章")

        progress("组装写作上下文（前文/记忆/人物状态）…", 45)
        memory_context, rag_context = _build_writing_context(values, packet, cfg, root, project_id)
        if final_instruction.strip():
            memory_context += f"\n\n<作者自定义重写指令>\n{final_instruction.strip()}\n</作者自定义重写指令>"

        progress("写手正在重写正文（约 1-3 分钟）…", 60)
        research_digest = ""
        if agentic:
            try:
                from novel_agent.agents.writer_research import run_research
                from novel_agent.agents.writer_tools import WriterCtx

                from novel_agent.types import WriterPacket as WP

                wctx = WriterCtx(values=values, vol=vol, ch=ch, root=str(root), cfg=cfg)
                research_digest = run_research(
                    wctx, packet.model_dump(), discussion=final_instruction.strip(),
                    baseline=memory_context, cfg=cfg,
                    max_rounds=_max_research_rounds(cfg),
                    progress=lambda msg, pct=None: progress(f"研究：{msg}"),
                )
            except Exception as exc:  # noqa: BLE001
                from novel_agent.logutil import get_logger

                get_logger().warning("[重生成] 研究循环失败: %s", exc)
        chapter = rewrite_chapter(
            existing, packet, cfg, memory_context=memory_context, rag_context=rag_context,
            techniques=values.get("techniques"), blueprint=values.get("narrative_blueprint"),
            research_digest=research_digest, style_samples=values.get("style_samples"),
            target_words=int((values.get("word_budget") or {}).get("per_chapter") or 0) or None,
        )

        # 质检门：机器审核先于人工预览
        from novel_agent.agents.quality import check_chapter_quality

        progress("质检中…", 95)
        quality = check_chapter_quality(
            chapter.model_dump(), packet.model_dump(), values.get("chapters") or {}, cfg,
        )
        runtime.graph.update_state(runtime.thread, {"pending_chapter": chapter.model_dump(),
                                                    "pending_quality": quality})
        progress("完成", 100)
        return {"ok": True, "pending": chapter.model_dump(), "quality": quality}

    return job


@router.post("/projects/{project_id}/volumes/{vol}/chapters/{ch}/regenerate")
def regenerate_chapter(
    project_id: str,
    vol: int,
    ch: int,
    instruction: str = "",
    chat_context: str = "",
    agentic: bool = False,
    request: Request = None,
) -> dict:
    """重新生成某章：用重写提示（保持设定一致、表达明显不同更优）生成预览。"""
    job = _regenerate_job(project_id, vol, ch, instruction, chat_context, request, agentic)
    try:
        return job(lambda msg, pct=None: None)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重新生成失败：{exc}") from exc


@router.post("/projects/{project_id}/volumes/{vol}/chapters/{ch}/regenerate-task")
def start_regenerate_task(
    project_id: str,
    vol: int,
    ch: int,
    instruction: str = "",
    chat_context: str = "",
    agentic: bool = False,
    request: Request = None,
) -> dict:
    """以后台任务启动"按讨论重新生成"，返回 task_id；进度经 SSE 流式获取。"""
    job = _regenerate_job(project_id, vol, ch, instruction, chat_context, request, agentic)
    task = request.app.state.tasks.start("chapter_regenerate", project_id, job)
    return {"task_id": task.id}


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, request: Request):
    """SSE：流式推送任务进度（progress/done/error），任务结束即关流。"""
    import json
    import time

    from fastapi.responses import StreamingResponse

    task = request.app.state.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    def gen():
        while True:
            events = task.drain()
            for ev in events:
                yield f"event: {ev['type']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
                if ev["type"] in ("done", "error"):
                    return
            if task.status != "running" and not task.drain():
                return
            time.sleep(0.3)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class RewriteSceneIn(BaseModel):
    instruction: str


@router.post("/projects/{project_id}/chapters/{vol}/{ch}/scenes/{scene}/rewrite")
def rewrite_scene(project_id: str, vol: int, ch: int, scene: str, body: RewriteSceneIn, request: Request) -> dict:
    """AI 定点改写指定场景：只重写该场景，其余内容原样保留（省 token）。"""
    from novel_agent.revision import edit_scene
    from novel_agent.types import Chapter

    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="请填写改写指令")

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    key = f"{vol}_{ch}"
    chapters = dict(values.get("chapters") or {})
    if key not in chapters:
        raise HTTPException(status_code=404, detail=f"章节 {key} 不存在")
    chapter = Chapter(**chapters[key])
    try:
        merged, new_text = edit_scene(chapter, scene, body.instruction, cfg)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"场景 {scene} 不存在") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"改写失败：{exc}") from exc

    chapters[key] = merged.model_dump()
    runtime.graph.update_state(runtime.thread, {"chapters": chapters})
    return {"ok": True, "chapter": merged.model_dump(), "scene": scene, "new_text": new_text}


@router.get("/projects/{project_id}/relations")
def project_relations(project_id: str, request: Request) -> dict:
    """返回时序关系图谱（人物关系可视化用）：节点=人物，边=带章节的关系。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)

    # 节点：人物档案（含状态）
    chars = values.get("characters") or []
    states = (values.get("character_state") or {}).get("entries", [])
    state_by_id = {s.get("character_id"): s for s in states}
    nodes = []
    for c in chars:
        st = state_by_id.get(c.get("id"), {})
        nodes.append({
            "id": c.get("id"),
            "name": c.get("name", "?"),
            "tier": c.get("tier", "supporting"),
            "status": st.get("status", "active"),
        })

    # 边：时序图谱（chapter 为兼容字段=章号，前端关系图按"第N章"渲染）
    from novel_agent.rag import TemporalGraph

    graph = TemporalGraph(_mem_paths(request.app.state.root, project_id)[2])
    edges = []
    for e in graph.edges:
        if not e.get("ch"):
            continue
        out = dict(e)
        out["chapter"] = e.get("ch")
        edges.append(out)

    return {"nodes": nodes, "edges": edges}


class ChatIn(BaseModel):
    context: str  # concept | world | characters | outline | volume_1 | chapter_1_2 ...
    message: str


class ProposeIn(BaseModel):
    context: str
    target: str  # concept | world_bible | characters | outline | volume_plan | chapter


@router.get("/projects/{project_id}/chat")
def chat_history(project_id: str, context: str, request: Request) -> dict:
    """获取某场景的对话历史。"""
    from novel_agent.api.chat import _chat_path, load_history, valid_context

    if not valid_context(context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    pm = _pm(request)
    try:
        pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    messages = load_history(_chat_path(request.app.state.root, project_id, context))
    return {"context": context, "messages": messages}


@router.post("/projects/{project_id}/chat")
def chat_send(project_id: str, body: ChatIn, request: Request) -> dict:
    """发一条消息给该场景的 AI 助手，返回回复。"""
    from novel_agent.api.chat import chat_reply, valid_context

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not valid_context(body.context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    try:
        reply, history = chat_reply(project_id, body.context, body.message, request.app.state.root, cfg, values)
    except Exception as exc:
        import traceback

        from novel_agent.logutil import get_logger

        log = get_logger()
        log.warning("[chat] 对话失败: %s\n%s", body.context, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"对话失败：{exc}") from exc
    return {"reply": reply, "messages": history}


@router.post("/projects/{project_id}/chat/stream")
def chat_send_stream(project_id: str, body: ChatIn, request: Request):
    """chat_send 的 SSE 流式版：agent 循环逐 token 推送（章节场景带 ReAct 工具）。

    事件帧：token 增量 / round 新一轮 / tool 查证提示 / spawn_writer 转交写手 /
    error 中断 / done 结束。
    """
    import json as _json

    from fastapi.responses import StreamingResponse

    from novel_agent.api.chat import chat_reply_agent, valid_context

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not valid_context(body.context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    def gen():
        try:
            for kind, payload in chat_reply_agent(
                project_id, body.context, body.message, request.app.state.root, cfg, values
            ):
                if kind == "token":
                    yield f"data: {_json.dumps({'type': 'token', 'text': payload}, ensure_ascii=False)}\n\n"
                elif kind == "round":
                    yield 'data: {"type": "round"}\n\n'
                elif kind == "tool":
                    yield f"data: {_json.dumps({'type': 'tool', 'name': payload['name'], 'arg': payload['arg']}, ensure_ascii=False)}\n\n"
                elif kind == "spawn_writer":
                    yield f"data: {_json.dumps({'type': 'spawn_writer', 'note': payload['note']}, ensure_ascii=False)}\n\n"
                elif kind == "error":
                    yield f"data: {_json.dumps({'type': 'error', 'message': payload}, ensure_ascii=False)}\n\n"
                elif kind == "done":
                    yield "data: {\"type\": \"done\"}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/chat/structured")
def chat_structured(project_id: str, body: ChatIn, request: Request) -> dict:
    """章节助手结构化回复：基于讨论输出 本章目标/冲突/钩子（JSON），供自动化流程消费。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not valid_context(body.context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    _, _, values, cfg = _project_ctx(request, project_id, meta.genre)
    from novel_agent.api.chat import _chat_path, chat_design_points, load_history

    try:
        out = chat_design_points(project_id, body.context, body.message, request.app.state.root, cfg, values)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"结构化回复失败：{exc}") from exc
    history = load_history(_chat_path(request.app.state.root, project_id, body.context))
    return {**out, "messages": history}


@router.post("/projects/{project_id}/chat/propose")
def chat_propose(project_id: str, body: ProposeIn, request: Request) -> dict:
    """让 AI 依据对话输出指定目标的完整方案（JSON），前端可应用到表单。"""
    from novel_agent.api.chat import propose, valid_context

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not valid_context(body.context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    try:
        proposal = propose(project_id, body.context, body.target, request.app.state.root, cfg, values)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"方案生成失败：{exc}") from exc
    return {"target": body.target, "proposal": proposal}


@router.post("/projects/{project_id}/chat/reset")
def chat_reset(project_id: str, context: str, request: Request) -> dict:
    """清空某场景的对话历史。"""
    from novel_agent.api.chat import reset, valid_context

    pm = _pm(request)
    try:
        pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not valid_context(context):
        raise HTTPException(status_code=400, detail="未知的对话场景")
    reset(project_id, context, request.app.state.root)
    return {"ok": True}


@router.get("/projects/{project_id}/volumes")
def list_volumes(project_id: str, request: Request) -> dict:
    """列出分卷（volume_plans，未生成则回退总纲中的分卷）。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    return {"volumes": _volume_source(runtime, values)}


@router.post("/projects/{project_id}/volumes")
def create_volume(project_id: str, body: VolumeIn, request: Request) -> dict:
    from novel_agent.agents.volume_plan import generate_volume_plans
    from novel_agent.types import Outline, VolumePlan

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    _ensure_setup_confirmed(runtime)

    if body.generate:
        outline = values.get("outline")
        if not outline:
            raise HTTPException(status_code=400, detail="请先完成总纲，才能由 AI 生成分卷")
        try:
            plans = [p.model_dump() for p in generate_volume_plans(Outline(**outline), cfg)]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI 生成分卷失败：{exc}") from exc
        runtime.graph.update_state(runtime.thread, {"volume_plans": plans})
        return {"ok": True, "volumes": plans}

    if not body.volume:
        raise HTTPException(status_code=400, detail="缺少分卷信息")
    plans = list(values.get("volume_plans") or [])
    vp = VolumePlan(**body.volume)
    if any(v.get("volume") == vp.volume for v in plans):
        raise HTTPException(status_code=400, detail=f"卷{vp.volume} 已存在")
    plans.append(vp.model_dump())
    plans.sort(key=lambda v: v.get("volume", 0))
    runtime.graph.update_state(runtime.thread, {"volume_plans": plans})
    return {"ok": True, "volumes": plans}


@router.put("/projects/{project_id}/volumes/{vol}")
def update_volume(project_id: str, vol: int, body: dict, request: Request) -> dict:
    from novel_agent.types import VolumePlan

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    _ensure_setup_confirmed(runtime)
    src = _volume_source(runtime, values)
    src = list(src)
    found = next((v for v in src if v.get("volume") == vol), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"卷{vol} 不存在")
    merged = dict(found)
    merged.update(body)
    merged["volume"] = vol
    validated = VolumePlan(**merged)
    src = [validated.model_dump() if v.get("volume") == vol else v for v in src]
    runtime.graph.update_state(runtime.thread, {"volume_plans": src})
    return {"ok": True}


def _chapter_generation_job(project_id: str, vol: int, ch: int | None, body: ChapterFormIn, request: Request):
    """构造章节生成 job：job(progress) 在后台线程执行，progress(message, pct) 上报进度。

    在请求线程内完成参数校验与图状态快照；LLM 调用等耗时步骤在后台执行。
    """
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    _ensure_setup_confirmed(runtime)

    plans = values.get("volume_plans") or []
    plan = next((p for p in plans if p.get("volume") == vol), None)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"卷{vol} 不存在")

    root = request.app.state.root

    def job(progress):
        progress("校验卷规划与章节编号…", 5)
        existing = values.get("chapters") or {}
        chapter_no = ch if ch is not None else len([k for k in existing if k.startswith(f"{vol}_")]) + 1

        discussion = ""
        if body.chat_context:
            progress("提炼聊天讨论要点…", 15)
            from novel_agent.api.chat import _chat_path, load_history, summarize_chat_design

            chat_msgs = load_history(_chat_path(root, project_id, body.chat_context))
            if chat_msgs:
                try:
                    discussion = summarize_chat_design(chat_msgs, cfg)
                except Exception:
                    # 总结失败时退回原文（最近若干条）
                    discussion = "\n".join(
                        f"{'作者' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}" for m in chat_msgs[-8:]
                    )

        progress("生成章节规划（目标/冲突/节拍/伏笔）…", 30)
        from novel_agent.agents.packet import collect_pending_foreshadow, generate_writer_packet
        from novel_agent.agents.write import generate_chapter
        from novel_agent.library.searcher import tools_for_chapter
        from novel_agent.types import Outline, VolumePlan, WriterPacket

        techniques = values.get("techniques")
        blueprint = values.get("narrative_blueprint")

        done_keys = sorted((values.get("chapters") or {}).keys(),
                           key=lambda k: [int(p) for p in str(k).split("_")])
        used_titles = [(values.get("chapters") or {})[k].get("title", "")
                       for k in done_keys if (values.get("chapters") or {})[k].get("title")]

        # 规划研究循环（react_enabled 时）：规划前先查证正典与前文
        research_context = ""
        if (cfg.planner or {}).get("react_enabled"):
            try:
                from novel_agent.llm.cost import set_chapter

                set_chapter(f"{vol}_{chapter_no}")
                _, vec_p, graph_p = _mem_paths(root, project_id)
                from novel_agent.llm import get_embedder
                from novel_agent.memory import LongTermMemory, MidTermMemory
                from novel_agent.rag import TemporalGraph
                from novel_agent.agents.planner_research import PlannerCtx, run_planner_research

                midterm = MidTermMemory(_mem_paths(root, project_id)[0])
                long_term = LongTermMemory(vec_p, embed_fn=get_embedder(cfg))
                tgraph = TemporalGraph(graph_p)
                ctx = PlannerCtx(values, vol, chapter_no, midterm, long_term, tgraph, used_titles=used_titles)

                def _prog(msg):
                    progress(f"规划查证：{msg}", 38)

                research_context = run_planner_research(ctx, plan, cfg, None, _prog)
                if research_context:
                    progress("规划查证完成，结果已并入任务书素材", 44)
            except Exception as exc:
                from novel_agent.logutil import get_logger

                get_logger().warning("[生成] 规划研究失败（降级为无查证）: %s", exc)
                research_context = ""

        plan_tools = tools_for_chapter(
            root,
            {"goal": " ".join(plan.get("event_arc") or []), "hook": plan.get("ending_hook", ""), "title": plan.get("title", "")},
            top_k=int(cfg.library.get("tool_top_k", 3)),
        )
        if body.auto_plan:
            pending_fs = collect_pending_foreshadow(values.get("writer_packets"))
            packet = generate_writer_packet(
                VolumePlan(**plan), Outline(**values.get("outline", {})), values.get("characters") or [],
                chapter_no, cfg, discussion=discussion, pending_foreshadow=pending_fs,
                techniques=techniques, blueprint=blueprint, tools=plan_tools,
                event_ledger=values.get("event_ledger"), used_titles=used_titles,
                prop_registry=values.get("prop_registry"),
                research_context=research_context,
            )
            if body.title:
                packet = packet.model_copy(update={"title": body.title, "goal": body.goal or packet.goal})
        else:
            packet = WriterPacket(
                volume=vol, chapter=chapter_no, title=body.title or f"第{chapter_no}章",
                goal=body.goal, conflicts=body.conflicts, hook=body.hook,
            )

        from novel_agent.llm.cost import set_chapter

        set_chapter(f"{vol}_{chapter_no}")  # 按章成本流水归属
        progress("组装写作上下文（前文/记忆/人物状态/伏笔账本）…", 45)
        memory_context, rag_context = _build_writing_context(values, packet, cfg, root, project_id)
        if discussion:
            memory_context += f"\n\n<作者与AI讨论的设计>\n{discussion}\n</作者与AI讨论的设计>"
        if body.notes.strip():
            memory_context += f"\n\n<作者自定义写作指令>\n{body.notes.strip()}\n</作者自定义写作指令>"
        # 作者指定的本章必用梗（硬性指令，优先级高于候选块）
        if body.must_use_memes:
            from novel_agent.library.memes import must_use_memes_text

            must_block = must_use_memes_text(root, body.must_use_memes)
            if must_block:
                memory_context += f"\n\n{must_block}"

        # 智能研究模式：写手自主决定查询状态卡/伏笔账本/档案/前文片段
        research_digest = ""
        if body.agentic:
            progress("写手研究：检索状态卡/伏笔账本/前文片段…", 52)
            try:
                from novel_agent.agents.writer_research import run_research
                from novel_agent.agents.writer_tools import WriterCtx

                wctx = WriterCtx(values=values, vol=vol, ch=chapter_no, root=str(root), cfg=cfg)
                research_digest = run_research(
                    wctx, packet.model_dump(), discussion=discussion,
                    baseline=memory_context, cfg=cfg,
                    max_rounds=_max_research_rounds(cfg),
                    progress=lambda msg, pct=None: progress(f"研究：{msg}", 52),
                )
            except Exception as exc:  # noqa: BLE001
                from novel_agent.logutil import get_logger

                get_logger().warning("[生成] 研究循环失败，回退常规写作: %s", exc)

        progress("写手正在写正文（约 1-3 分钟）…", 60)
        chapter_tools = tools_for_chapter(root, packet.model_dump(), top_k=int(cfg.library.get("tool_top_k", 3)))
        from novel_agent.agents.write import arc_directive

        chapter = generate_chapter(
            packet, cfg, memory_context=memory_context, rag_context=rag_context,
            techniques=techniques, blueprint=blueprint, tools=chapter_tools,
            research_digest=research_digest, style_samples=values.get("style_samples"),
            arc_note=arc_directive(values.get("characters"), values.get("character_state")),
            target_words=int((values.get("word_budget") or {}).get("per_chapter") or 0) or None,
        )

        # 质检门：机器审核先于人工预览（查重/节拍兑现/文风），报告随预览交付
        from novel_agent.agents.quality import check_chapter_quality

        progress("质检中…", 90)
        quality = check_chapter_quality(
            chapter.model_dump(), packet.model_dump(), values.get("chapters") or {}, cfg,
        )
        progress("保存预览…", 95)
        updates = {
            "pending_chapter": chapter.model_dump(),
            "pending_quality": quality,
            # 任务书随章归档：作者可追溯每章是按什么目标/讨论要点/指令生成的
            "writer_packets": {**(values.get("writer_packets") or {}),
                               f"{vol}_{chapter_no}": packet.model_dump()},
        }
        # 智能提案：写手提出记忆更新提案，暂存供接受章节时合并
        proposals = None
        if body.agentic:
            try:
                from novel_agent.agents.writer_research import propose_updates

                proposals = propose_updates(chapter.model_dump(), values.get("characters") or [], cfg)
                if proposals.get("state_updates") or proposals.get("foreshadow_plants"):
                    updates["writer_proposals"] = proposals
            except Exception as exc:  # noqa: BLE001
                from novel_agent.logutil import get_logger

                get_logger().warning("[生成] 记忆提案失败: %s", exc)
        runtime.graph.update_state(runtime.thread, updates)
        progress("完成", 100)
        return {
            "ok": True,
            "pending": chapter.model_dump(),
            "packet": packet.model_dump(),
            "context": memory_context,
            "quality": quality,
        }

    return job


@router.post("/projects/{project_id}/volumes/{vol}/chapters")
def create_chapter(project_id: str, vol: int, body: ChapterFormIn, request: Request) -> dict:
    """提交章节表单 → 智能体按卷+总纲+记忆生成 → 返回预览（未保存）。"""
    job = _chapter_generation_job(project_id, vol, None, body, request)
    try:
        return job(lambda msg, pct=None: None)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI 生成章节失败：{exc}") from exc


@router.post("/projects/{project_id}/volumes/{vol}/chapters/{ch}/generate-task")
def start_chapter_generate_task(project_id: str, vol: int, ch: int, body: ChapterFormIn, request: Request) -> dict:
    """以后台任务启动章节生成，返回 task_id；进度经 GET /api/tasks/{task_id}/events 流式获取。"""
    job = _chapter_generation_job(project_id, vol, ch, body, request)
    task = request.app.state.tasks.start("chapter_generate", project_id, job)
    return {"task_id": task.id}


def _finalize_chapter(runtime, values, cfg, root: Path, project_id: str, chapter, key: str,
                      author_hints: list[dict] | None = None) -> None:
    """章节落库后的收尾：三层记忆 + 主要人物状态 + 路人升级。"""
    from novel_agent.llm import get_embedder
    from novel_agent.llm.cost import set_chapter
    from novel_agent.logutil import get_logger

    set_chapter(key)  # 收尾的理解调用计入该章成本
    log = get_logger()
    mid_p, vec_p, graph_p = _mem_paths(root, project_id)
    from novel_agent.memory import LongTermMemory, MidTermMemory
    from novel_agent.rag import TemporalGraph

    prev_entries = (values.get("character_state") or {}).get("entries", [])
    # 章节理解三合一（OPT-B）：一次调用产出 摘要+状态+关系；失败退回独立抽取
    understanding = None
    try:
        from novel_agent.agents.understanding import understand_chapter

        understanding = understand_chapter(
            chapter.model_dump(), values.get("characters") or [], prev_entries, cfg,
            author_hints=author_hints,
        )
    except Exception as exc:
        log.warning("[finalize] 章节理解合并调用失败: %s", exc)

    try:
        from novel_agent.memory import update_chapter_memory

        long_term = LongTermMemory(vec_p, embed_fn=get_embedder(cfg))
        graph = TemporalGraph(graph_p)
        # 重写-再接受场景：先移除本章旧索引再重放，避免向量切片/关系边重复累积
        long_term.remove_chapter(int(chapter.volume or 1), int(chapter.chapter or 1))
        graph.remove_chapter(int(chapter.volume or 1), int(chapter.chapter or 1))
        update_chapter_memory(
            chapter.model_dump(), cfg, MidTermMemory(mid_p), long_term, graph,
            values.get("characters"),
            understanding=understanding,
        )
    except Exception as exc:
        log.warning("[finalize] 记忆更新失败: %s", exc)

    try:
        from novel_agent.types.character_state import CharacterState

        if understanding is not None:
            new_state = CharacterState(entries=understanding.entries)
        else:
            from novel_agent.agents.state_update import extract_character_states

            prev_state = CharacterState(**values["character_state"]) if values.get("character_state") else None
            new_state = extract_character_states(
                chapter.model_dump(), values.get("characters") or [], prev_state, cfg,
                author_hints=author_hints,
            )
        runtime.graph.update_state(runtime.thread, {"character_state": new_state.model_dump()})
    except Exception as exc:
        log.warning("[finalize] 状态更新失败: %s", exc)

    # 正典事实层：事件账本 + 道具登记卡随章节更新（失败不阻断）
    if understanding is not None:
        try:
            from novel_agent.agents.understanding import merge_canon_updates

            el, pr = merge_canon_updates(
                values.get("event_ledger"), values.get("prop_registry"),
                int(chapter.volume or 1), int(chapter.chapter or 1), understanding,
            )
            runtime.graph.update_state(runtime.thread, {"event_ledger": el, "prop_registry": pr})
        except Exception as exc:
            log.warning("[finalize] 正典账本更新失败: %s", exc)

    try:
        from novel_agent.agents.recurring import extract_recurring_characters

        new_chars = extract_recurring_characters(chapter.model_dump(), values.get("characters") or [], cfg)
        if new_chars:
            chars = list(values.get("characters") or [])
            chars.extend([c.model_dump() for c in new_chars])
            runtime.graph.update_state(runtime.thread, {"characters": chars})
    except Exception as exc:
        from novel_agent.logutil import get_logger

        get_logger().warning("[finalize] 路人升级失败: %s", exc)


class AcceptChapterIn(BaseModel):
    chapter: dict | None = None  # 可选：作者在预览中修改后的章节字段，覆盖待接受章节


@router.post("/projects/{project_id}/chapters/{vol}/{ch}/accept")
def accept_chapter(project_id: str, vol: int, ch: int, request: Request,
                   body: AcceptChapterIn | None = None) -> dict:
    """接受生成的章节：写入 chapters + 更新记忆。body.chapter 可选，作者预览直改后覆盖待接受章节。"""
    from novel_agent.memory import update_chapter_memory
    from novel_agent.types import Chapter

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    pending = values.get("pending_chapter")
    if pending is None:
        raise HTTPException(status_code=400, detail="没有待接受的章节，请先提交章节表单")
    pending = dict(pending)
    if body and body.chapter:
        pending.update(body.chapter)
    try:
        chapter = Chapter(**pending)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"章节数据校验失败：{exc}") from exc
    chapter = chapter.model_copy(update={"volume": vol, "chapter": ch})
    key = f"{vol}_{ch}"
    chapters = dict(values.get("chapters") or {})
    # 重写-再接受：旧稿自动留底（首次接受无旧稿，跳过）
    if key in chapters:
        from novel_agent.storage.versions import snapshot_chapter

        snapshot_chapter(request.app.state.root, project_id, chapters[key], "重写覆盖")
    chapters[key] = chapter.model_dump()
    runtime.graph.update_state(runtime.thread, {"chapters": chapters, "pending_chapter": None})
    # 写手智能体的记忆提案：状态 hints 进 _finalize_chapter，伏笔登记并入账本
    proposals = values.get("writer_proposals") or {}
    _finalize_chapter(runtime, values, cfg, request.app.state.root, project_id, chapter, key,
                      author_hints=proposals.get("state_updates") or None)
    if proposals.get("foreshadow_plants"):
        from novel_agent.types import WriterPacket

        packets = dict(values.get("writer_packets") or {})
        pk = dict(packets.get(key) or {
            "volume": vol, "chapter": ch, "title": chapter.title, "goal": "旁路生成",
        })
        fs = list(pk.get("foreshadow") or [])
        for desc in proposals["foreshadow_plants"]:
            d = desc if isinstance(desc, str) else (desc or {}).get("desc", "")
            if d and d.strip():
                fs.append({"kind": "seed", "desc": d.strip()})
        pk["foreshadow"] = fs
        packets[key] = pk
        runtime.graph.update_state(runtime.thread, {"writer_packets": packets})
    # 提案已消费
    runtime.graph.update_state(runtime.thread, {"writer_proposals": None})
    return {"ok": True, "chapter": chapter.model_dump()}


@router.delete("/projects/{project_id}/chapters/{vol}/{ch}")
def discard_chapter(project_id: str, vol: int, ch: int, request: Request) -> dict:
    """放弃待接受的章节（不保存）。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    if values.get("pending_chapter") is not None:
        runtime.graph.update_state(runtime.thread, {"pending_chapter": None})
    return {"ok": True}


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, request: Request) -> dict:
    """全局用量 + 按章成本流水（USD 估价按模型单价折算）。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, _runtime, _values, cfg = _project_ctx(request, project_id, meta.genre)
    from novel_agent.llm.cost import get_cost

    return get_cost(Path(request.app.state.root), project_id, getattr(cfg, "cost", None))


@router.get("/projects/{project_id}/chapters/{vol}/{ch}/versions")
def list_chapter_versions(project_id: str, vol: int, ch: int, request: Request) -> dict:
    """某章的历史版本列表（新→旧，元数据）。"""
    pm = _pm(request)
    try:
        pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from novel_agent.storage.versions import list_versions

    return {"versions": list_versions(Path(request.app.state.root), project_id, vol, ch)}


@router.get("/projects/{project_id}/chapters/{vol}/{ch}/versions/{vid}")
def get_chapter_version(project_id: str, vol: int, ch: int, vid: str, request: Request) -> dict:
    """读取一个历史版本的完整章节内容。"""
    pm = _pm(request)
    try:
        pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from novel_agent.storage.versions import load_version

    version = load_version(Path(request.app.state.root), project_id, vol, ch, vid)
    if not version:
        raise HTTPException(status_code=404, detail=f"版本 {vid} 不存在")
    return {"version": version}


@router.post("/projects/{project_id}/chapters/{vol}/{ch}/versions/{vid}/restore")
def restore_chapter_version(project_id: str, vol: int, ch: int, vid: str, request: Request) -> dict:
    """恢复章节到历史版本：当前稿先自动留底，再写回并按恢复稿重放记忆。"""
    from novel_agent.types import Chapter

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from novel_agent.storage import versions as vstore

    root = Path(request.app.state.root)
    version = vstore.load_version(root, project_id, vol, ch, vid)
    if not version or not version.get("chapter"):
        raise HTTPException(status_code=404, detail=f"版本 {vid} 不存在")
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    try:
        chapter = Chapter(**version["chapter"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"版本数据校验失败：{exc}") from exc
    chapter = chapter.model_copy(update={"volume": vol, "chapter": ch})
    key = f"{vol}_{ch}"
    chapters = dict(values.get("chapters") or {})
    if key in chapters:
        vstore.snapshot_chapter(root, project_id, chapters[key], "恢复前备份")
    chapters[key] = chapter.model_dump()
    runtime.graph.update_state(runtime.thread, {"chapters": chapters})
    _replay_chapter_memory(request, runtime, values, cfg, project_id, chapter, key)
    return {"ok": True, "chapter": chapter.model_dump()}


@router.get("/projects/{project_id}/volumes/{vol}/versions")
def list_volume_versions(project_id: str, vol: int, request: Request) -> dict:
    """卷内有备份的全部章节（含已删除章），供「备份」入口展示。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    from novel_agent.storage.versions import volume_groups

    existing = set((values.get("chapters") or {}).keys())
    return {"groups": volume_groups(Path(request.app.state.root), project_id, vol, existing)}


class PendingSceneRewriteIn(BaseModel):
    scene_id: str
    instruction: str = ""


@router.post("/projects/{project_id}/chapters/{vol}/{ch}/pending-scene-rewrite")
def pending_scene_rewrite(project_id: str, vol: int, ch: int, body: PendingSceneRewriteIn, request: Request) -> dict:
    """对【待接受】章节的指定场景做 AI 定点重写（质检裁决的"✨ AI 重写"按钮）。

    只重写该场景并更新 pending_chapter，重跑质检门后一并返回；章节仍未保存，
    作者可继续编辑或接受。"""
    from novel_agent.revision import edit_scene
    from novel_agent.types import Chapter

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)

    pending = values.get("pending_chapter")
    if pending is None:
        raise HTTPException(status_code=400, detail="没有待接受的章节")
    try:
        chapter = Chapter(**pending)
        merged, new_text = edit_scene(chapter, body.scene_id, body.instruction, cfg)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"场景 {body.scene_id} 不存在") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"改写失败：{exc}") from exc

    from novel_agent.agents.quality import check_chapter_quality

    packet = (values.get("writer_packets") or {}).get(f"{vol}_{ch}")
    quality = check_chapter_quality(merged.model_dump(), packet, values.get("chapters") or {}, cfg)
    runtime.graph.update_state(runtime.thread, {"pending_chapter": merged.model_dump(),
                                                "pending_quality": quality})
    return {"ok": True, "chapter": merged.model_dump(), "new_text": new_text, "quality": quality}


class StyleSamplesIn(BaseModel):
    samples: list[dict]  # [{id, name, text}]


@router.put("/projects/{project_id}/style-samples")
def update_style_samples(project_id: str, body: StyleSamplesIn, request: Request) -> dict:
    """设置作者风格样本（≤3 段，每段 ≤800 字）：注入写手 prompt 作风格锚点。"""
    from novel_agent.agents.write import MAX_STYLE_SAMPLES, MAX_STYLE_SAMPLE_CHARS

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, _values, _cfg = _project_ctx(request, project_id, meta.genre)

    samples = []
    for s in body.samples or []:
        text = (s or {}).get("text", "").strip()
        if not text:
            continue
        if len(text) > MAX_STYLE_SAMPLE_CHARS:
            raise HTTPException(status_code=400,
                                detail=f"样本「{s.get('name') or '未命名'}」超过 {MAX_STYLE_SAMPLE_CHARS} 字上限")
        item = {"id": s.get("id") or f"st{len(samples) + 1}", "name": (s.get("name") or "").strip(),
                "text": text}
        if (s.get("digest") or "").strip():
            item["digest"] = s["digest"].strip()
        if s.get("source_id"):
            item["source_id"] = s["source_id"]
        samples.append(item)
    if len(samples) > MAX_STYLE_SAMPLES:
        raise HTTPException(status_code=400, detail=f"最多 {MAX_STYLE_SAMPLES} 段样本")
    runtime.graph.update_state(runtime.thread, {"style_samples": samples})
    return {"ok": True, "samples": samples}


@router.get("/projects/{project_id}/products")
def project_products(project_id: str, request: Request) -> dict:
    """返回项目已产出的设定/人物/大纲/章节（从图状态读取）。"""
    pm = _pm(request)
    store: RuntimeStore = _store(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = store.get_or_create(project_id, meta.genre)
    values = runtime.graph.get_state(runtime.thread).values
    return {
        "concept": values.get("concept"),
        "world_bible": values.get("world_bible"),
        "characters": values.get("characters"),
        "outline": values.get("outline"),
        "volume_plans": values.get("volume_plans"),
        "writer_packets": values.get("writer_packets"),
        "chapters": values.get("chapters"),
        "event_ledger": values.get("event_ledger"),
        "prop_registry": values.get("prop_registry"),
        "style_samples": values.get("style_samples"),
        "pending_quality": values.get("pending_quality"),
        "word_budget": values.get("word_budget"),
        "character_state": values.get("character_state"),
        "techniques": values.get("techniques"),
        "narrative_blueprint": values.get("narrative_blueprint"),
        "current_stage": values.get("current_stage"),
    }


class WordBudgetIn(BaseModel):
    per_chapter: int  # 每章目标字数；<=0 表示清除覆盖，回退题材 Profile


@router.put("/projects/{project_id}/word-budget")
def update_word_budget(project_id: str, body: WordBudgetIn, request: Request) -> dict:
    """设置项目级每章字数预算（结构漂移治理：立项目标超标时压缩后续章节）。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, _values, _cfg = _project_ctx(request, project_id, meta.genre)
    n = int(body.per_chapter)
    if n > 0 and not (300 <= n <= 50000):
        raise HTTPException(status_code=400, detail="每章字数应在 300-50000 之间；0 表示清除覆盖")
    value = {"per_chapter": n} if n > 0 else None
    runtime.graph.update_state(runtime.thread, {"word_budget": value})
    return {"ok": True, "word_budget": value}


@router.put("/projects/{project_id}/techniques")
def set_project_techniques(project_id: str, body: dict, request: Request) -> dict:
    """挂载/取消写作手法：body={"ids": [库条目id]}，解析为条目快照写入图状态。"""
    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from novel_agent.library import LibraryStore, PRESETS, TechniqueEntry

    ids = body.get("ids")
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids 应为条目 id 数组")
    base = Path(request.app.state.root) / "output" / "libraries"
    lib = LibraryStore(base)
    lib.seed(PRESETS)
    snapshots = []
    for tid in ids:
        entry = lib.get("technique", str(tid))
        if entry is None:
            raise HTTPException(status_code=404, detail=f"手法条目不存在：{tid}")
        snapshots.append(entry.model_dump())
    runtime = _store(request).get_or_create(project_id, meta.genre)
    runtime.graph.update_state(runtime.thread, {"techniques": snapshots})
    return {"ok": True, "techniques": snapshots}


@router.post("/projects/{project_id}/blueprint/generate")
def generate_blueprint_api(project_id: str, request: Request) -> dict:
    """AI 生成叙事蓝图（主题/意象/暗线列表）：基于立项书+总纲+已写章节。"""
    from novel_agent.agents.blueprint import generate_blueprint

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, cfg = _project_ctx(request, project_id, meta.genre)
    try:
        bp = generate_blueprint(
            values.get("concept") or {}, values.get("outline") or {},
            values.get("chapters") or {}, values.get("characters") or [], cfg,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"蓝图生成失败：{exc}") from exc
    runtime.graph.update_state(runtime.thread, {"narrative_blueprint": bp})
    return {"ok": True, "blueprint": bp}


@router.get("/projects/{project_id}/final")
def final_files(project_id: str, request: Request) -> dict:
    pm = _pm(request)
    try:
        pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    final_dir = ProjectPaths(request.app.state.root, project_id).final_dir
    files = [{"name": p.name, "path": str(p)} for p in sorted(final_dir.iterdir())] if final_dir.exists() else []
    return {"files": files}


_LIBRARY_KINDS = ("personality", "tool", "character_template", "technique", "meme", "style")
_KIND_LABEL = "personality / tool / character_template / technique / meme / style"


def _library_model(kind: str):
    from novel_agent.library import MemeEntry, NovelToolEntry, PersonalityEntry, StyleEntry, TechniqueEntry
    from novel_agent.types.character_template import CharacterTemplate

    models = {
        "personality": PersonalityEntry,
        "tool": NovelToolEntry,
        "character_template": CharacterTemplate,
        "technique": TechniqueEntry,
        "meme": MemeEntry,
        "style": StyleEntry,
    }
    return models[kind]


@router.get("/library/{kind}")
def library_list(kind: str, request: Request) -> dict:
    from novel_agent.library import LibraryStore, PRESETS

    if kind not in _LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 仅支持 {_KIND_LABEL}")
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    store.seed(PRESETS)
    entries = [e.model_dump() for e in store.list(kind)]
    return {"kind": kind, "entries": entries}


@router.post("/library/memes/populate")
def library_memes_populate(body: dict, request: Request) -> dict:
    """AI 填充梗库：按题材方向批量生成梗条目并去重入库，减少人工录入。"""
    from novel_agent.config import load_config
    from novel_agent.library import LibraryStore, PRESETS, populate_memes

    topic = str(body.get("topic") or "通用").strip()[:60]
    try:
        count = int(body.get("count") or 10)
    except Exception:
        count = 10
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    store.seed(PRESETS)
    cfg = load_config(Path(request.app.state.root) / "config.yaml")
    try:
        added = populate_memes(request.app.state.root, topic, count, cfg, store=store)
    except Exception as exc:
        import traceback

        from novel_agent.logutil import get_logger

        get_logger().warning("[梗库] AI 填充失败: %s\n%s", topic, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI 填充失败：{exc}") from exc
    return {"ok": True, "added": len(added), "entries": [e.model_dump() for e in added]}


@router.post("/library/memes/extract")
def library_memes_extract(body: dict, request: Request) -> dict:
    """粘贴提取：从作者粘贴的素材（网页摘录/段子罗列）中提取梗条目入库。"""
    from novel_agent.config import load_config
    from novel_agent.library import LibraryStore, PRESETS, extract_memes_from_text

    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="粘贴内容不能为空")
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    store.seed(PRESETS)
    cfg = load_config(Path(request.app.state.root) / "config.yaml")
    try:
        added = extract_memes_from_text(request.app.state.root, text, cfg, store=store)
    except Exception as exc:
        import traceback

        from novel_agent.logutil import get_logger

        get_logger().warning("[梗库] 粘贴提取失败: %s\n%s", text[:60], traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"提取失败：{exc}") from exc
    return {"ok": True, "added": len(added), "entries": [e.model_dump() for e in added]}


@router.post("/library/styles/extract")
def library_styles_extract(body: dict, request: Request) -> dict:
    """粘贴提取：作者粘贴认可的文本 → 声线采样提取风格要点 → 建仿写库条目。"""
    from novel_agent.config import load_config
    from novel_agent.library import LibraryStore, PRESETS, analyze_style_sample, new_style_entry

    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="粘贴内容不能为空")
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    store.seed(PRESETS)
    cfg = load_config(Path(request.app.state.root) / "config.yaml")
    try:
        ana = analyze_style_sample(text, cfg)
        entry = new_style_entry(text, name=str(body.get("name") or ""),
                                digest=ana["digest"], tags=ana["tags"])
        store.add("style", entry)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"提取失败：{exc}") from exc
    return {"ok": True, "entry": entry.model_dump()}


@router.post("/library/{kind}")
def library_add(kind: str, body: dict, request: Request) -> dict:
    from novel_agent.library import LibraryStore, PRESETS

    if kind not in _LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 仅支持 {_KIND_LABEL}")
    try:
        entry = _library_model(kind)(**body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"条目校验失败：{exc}") from exc
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    store.seed(PRESETS)
    try:
        store.add(kind, entry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": entry.id}


@router.put("/library/{kind}/{entry_id}")
def library_update(kind: str, entry_id: str, body: dict, request: Request) -> dict:
    from novel_agent.library import LibraryStore

    if kind not in _LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 仅支持 {_KIND_LABEL}")
    base = Path(request.app.state.root) / "output" / "libraries"
    try:
        updated = LibraryStore(base).update(kind, entry_id, body)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "id": updated.id, "version": updated.version}


@router.delete("/library/{kind}/{entry_id}")
def library_delete(kind: str, entry_id: str, request: Request) -> dict:
    from novel_agent.library import LibraryStore

    if kind not in _LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 仅支持 {_KIND_LABEL}")
    base = Path(request.app.state.root) / "output" / "libraries"
    try:
        LibraryStore(base).delete(kind, entry_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "id": entry_id}


@router.post("/projects/{project_id}/characters/{character_id}/template")
def save_character_template(project_id: str, character_id: str, request: Request) -> dict:
    """把本作品中某个设计好的角色保存为跨作品可复用的人物模板。"""
    import uuid

    from novel_agent.library import LibraryStore
    from novel_agent.types.character_template import CharacterTemplate

    pm = _pm(request)
    try:
        meta = pm.get_meta(project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _, runtime, values, _ = _project_ctx(request, project_id, meta.genre)
    chars = values.get("characters") or []
    char = next((c for c in chars if c.get("id") == character_id), None)
    if char is None:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 不存在")
    name = (char.get("name") or "未命名") + "（模板）"
    tpl = CharacterTemplate(
        id=f"ct_{uuid.uuid4().hex[:8]}",
        name=name,
        role=char.get("role", "supporting"),
        description=char.get("motivation", ""),
        motivation=char.get("motivation", ""),
        flaw=char.get("flaw", ""),
        arc=char.get("arc", []),
    )
    base = Path(request.app.state.root) / "output" / "libraries"
    store = LibraryStore(base)
    try:
        store.add("character_template", tpl)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": tpl.id, "name": tpl.name}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, request: Request) -> dict:
    # 先关闭该项目的运行时（SQLite 连接），否则 Windows 下 checkpoint 文件被占用无法删除
    _store(request).invalidate(project_id)
    try:
        _pm(request).delete(project_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": project_id}
