"""novel-agent 交互式 CLI（M0：写作基础库命令）。"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from langgraph.types import Command
from rich.console import Console
from rich.table import Table

from novel_agent.config import ConfigError, load_config
from novel_agent.graph import compile_persistent_graph
from novel_agent.library import (
    Kind,
    LibraryIndex,
    LibraryStore,
    NovelToolEntry,
    PersonalityEntry,
    PRESETS,
    pick_for_chapter,
    pick_for_character,
    search_personality,
    search_tool,
)
from novel_agent.types.character_template import CharacterTemplate
from novel_agent.storage import ProjectManager, ProjectPaths

app = typer.Typer(help="多 Agent 小说写作系统")
lib = typer.Typer(help="维护写作基础库（性格库 / 小说工具库）")
project = typer.Typer(help="多项目管理（每本小说一个项目）")
app.add_typer(lib, name="lib")
app.add_typer(project, name="project")

console = Console()

_MODELS = {"personality": PersonalityEntry, "tool": NovelToolEntry, "character_template": CharacterTemplate}


def _store(root: Path, project: str | None) -> LibraryStore:
    base = Path(root) / "output" / "libraries"
    overlay = Path(root) / "output" / "projects" / project / "libraries" if project else None
    return LibraryStore(base_dir=base, overlay_dir=overlay)


def _index(root: Path) -> LibraryIndex:
    return LibraryIndex(Path(root) / "output" / "libraries" / ".index")


def _parse_entry(kind: str, raw: str):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("JSON 必须是对象")
    model = _MODELS[kind]
    try:
        return model(**data)
    except Exception as exc:
        raise typer.BadParameter(f"条目校验失败：{exc}") from exc


@lib.command("seed")
def lib_seed(
    root: Path = typer.Option(".", "--root", help="项目根目录"),
) -> None:
    """写入预置的性格库与小说工具库条目（已存在的 id 跳过）。"""
    store = _store(root, None)
    count = store.seed(PRESETS)
    LibraryIndex(Path(root) / "output" / "libraries" / ".index").rebuild(store)
    console.print(f"[green]已写入 {count} 条预置条目[/green]（性格 {len(PRESETS['personality'])} 条 / 工具 {len(PRESETS['tool'])} 条）")


@lib.command("list")
def lib_list(
    kind: Kind = typer.Argument("personality", help="personality | tool"),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project", help="项目覆盖层（可选）"),
    category: str | None = typer.Option(None, "--category", help="按分类过滤"),
) -> None:
    """列出基础库条目。"""
    store = _store(root, project)
    entries = store.list(kind, category=category)
    if not entries:
        console.print("[yellow]（空）[/yellow]")
        return
    table = Table(title=f"{kind} 条目（{len(entries)} 条）")
    table.add_column("id")
    table.add_column("名称")
    table.add_column("分类")
    table.add_column("版本")
    for e in entries:
        table.add_row(e.id, e.name, e.category, str(e.version))
    console.print(table)


@lib.command("add")
def lib_add(
    kind: Kind = typer.Argument(..., help="personality | tool"),
    entry_json: str = typer.Option(..., "--json", help="条目 JSON"),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project"),
) -> None:
    """新增一条基础库条目。"""
    entry = _parse_entry(kind, entry_json)
    _store(root, project).add(kind, entry)
    console.print(f"[green]已新增 {kind} 条目 {entry.id}[/green]")


@lib.command("edit")
def lib_edit(
    kind: Kind = typer.Argument(..., help="personality | tool"),
    entry_id: str = typer.Argument(..., help="条目 id"),
    fields_json: str = typer.Option(..., "--json", help="要更新的字段 JSON"),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project"),
) -> None:
    """更新条目字段（id 不可改，version 自增）。"""
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"不是合法 JSON：{exc}") from exc
    if not isinstance(fields, dict):
        raise typer.BadParameter("JSON 必须是对象")
    updated = _store(root, project).update(kind, entry_id, fields)
    console.print(f"[green]已更新 {kind} 条目 {entry_id}（version={updated.version}）[/green]")


@lib.command("delete")
def lib_delete(
    kind: Kind = typer.Argument(..., help="personality | tool"),
    entry_id: str = typer.Argument(..., help="条目 id"),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project"),
) -> None:
    """删除一条基础库条目。"""
    _store(root, project).delete(kind, entry_id)
    console.print(f"[green]已删除 {kind} 条目 {entry_id}[/green]")


@lib.command("search")
def lib_search(
    kind: Kind = typer.Argument(..., help="personality | tool"),
    query: str = typer.Argument(..., help="检索关键词"),
    top_k: int = typer.Option(3, "--top-k", min=1, max=20),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project"),
) -> None:
    """检索基础库（按相关度排序）。"""
    store = _store(root, project)
    index = _index(root)
    if kind == "personality":
        entries = search_personality(query, top_k=top_k, store=store, index=index)
    else:
        entries = search_tool(query, top_k=top_k, store=store, index=index)
    if not entries:
        console.print("[yellow]无结果[/yellow]")
        return
    for e in entries:
        console.print(f"[bold]{e.name}[/bold]（{e.id}）· {e.category}")
        console.print(f"  {e.description}")


@lib.command("export")
def lib_export(
    kind: Kind = typer.Argument(..., help="personality | tool"),
    out: Path = typer.Option(..., "--out", help="导出路径"),
    root: Path = typer.Option(".", "--root"),
    project: str | None = typer.Option(None, "--project"),
) -> None:
    """导出合并后的条目到 JSON 文件（备份/迁移）。"""
    path = _store(root, project).export(kind, out)
    console.print(f"[green]已导出到 {path}[/green]")


@app.command("pick-character")
def pick_character(
    spec: str = typer.Argument(..., help="人物需求描述"),
    genres: str = typer.Option("", "--genres", help="题材，逗号分隔"),
    top_k: int = typer.Option(3, "--top-k"),
    root: Path = typer.Option(".", "--root"),
) -> None:
    """为人物设定选性格原型（写作时引用）。"""
    store = _store(root, None)
    index = _index(root)
    genre_list = [g.strip() for g in genres.split(",") if g.strip()]
    for e in pick_for_character(spec, genres=genre_list or None, top_k=top_k, store=store, index=index):
        console.print(f"[bold]{e.name}[/bold]（{e.id}）· 适用题材：{', '.join(e.applicable_genres) or '不限'}")
        console.print(f"  {e.description}")


@app.command("pick-tool")
def pick_tool(
    goal: str = typer.Argument(..., help="本章目标/钩子描述"),
    top_k: int = typer.Option(3, "--top-k"),
    root: Path = typer.Option(".", "--root"),
) -> None:
    """为章节选叙事技法（写作时引用）。"""
    store = _store(root, None)
    index = _index(root)
    for e in pick_for_chapter({"goal": goal}, top_k=top_k, store=store, index=index):
        console.print(f"[bold]{e.name}[/bold]（{e.id}）· 适用位置：{e.chapter_placement or '全程'}")
        console.print(f"  {e.usage_guidelines or e.description}")


@project.command("create")
def project_create(
    title: str = typer.Option(..., "--title", help="书名/项目名"),
    genre: str = typer.Option("webnovel", "--genre", help="题材 Profile，如 webnovel/literary/short_story"),
    project_id: str | None = typer.Option(None, "--id", help="自定义项目 id（缺省自动生成）"),
    root: Path = typer.Option(".", "--root"),
) -> None:
    """创建新小说项目（数据隔离目录初始化）。"""
    pm = ProjectManager(root)
    paths = pm.create(project_id, genre, title)
    console.print(f"[green]已创建项目 {paths.project_id}[/green]（{genre} · {title}）")
    console.print(f"  产物目录: {paths.project_dir}")


@project.command("list")
def project_list(root: Path = typer.Option(".", "--root")) -> None:
    """列出全部小说项目。"""
    metas = ProjectManager(root).list()
    if not metas:
        console.print("[yellow]（暂无项目）[/yellow]")
        return
    table = Table(title=f"项目列表（{len(metas)}）")
    table.add_column("id")
    table.add_column("书名")
    table.add_column("题材")
    table.add_column("阶段")
    table.add_column("创建时间")
    for m in metas:
        table.add_row(m.project_id, m.title, m.genre, m.current_stage, m.created_at)
    console.print(table)


@project.command("get")
def project_get(project_id: str = typer.Argument(...), root: Path = typer.Option(".", "--root")) -> None:
    """查看项目信息。"""
    pm = ProjectManager(root)
    meta = pm.get_meta(project_id)
    console.print(f"[bold]{meta.title}[/bold]（{meta.project_id}）")
    console.print(f"  题材: {meta.genre} · 当前阶段: {meta.current_stage} · 创建: {meta.created_at}")


@project.command("delete")
def project_delete(project_id: str = typer.Argument(...), root: Path = typer.Option(".", "--root")) -> None:
    """删除项目（数据一并删除，谨慎）。"""
    ProjectManager(root).delete(project_id)
    console.print(f"[green]已删除项目 {project_id}[/green]")


@project.command("run")
def project_run(project_id: str = typer.Argument(...), root: Path = typer.Option(".", "--root")) -> None:
    """启动项目会话：创意链路（选题/世界/人物/总纲），每个确认点可 accept/edit/quit。"""
    pm = ProjectManager(root)
    meta = pm.get_meta(project_id)
    try:
        cfg = load_config(Path(root) / "config.yaml", meta.genre)
    except ConfigError as exc:
        console.print(f"[red]配置加载失败：{exc}[/red]")
        raise typer.Exit(1)

    graph = compile_persistent_graph(cfg, ProjectPaths(Path(root), project_id).checkpoint_db())
    thread = {"configurable": {"thread_id": project_id}}

    pending = graph.get_state(thread)
    if pending.next:
        # 已有进行中的确认点：直接续写（跨进程持久化），不再重新提问
        console.print("[dim]检测到未完成的确认点，直接续写…[/dim]")
        _confirm_loop(graph, thread)
        return

    idea = (typer.prompt("请描述初始立意（一句话）", default="") or "").strip().lstrip("\ufeff")
    initial = {
        "project_id": project_id,
        "project_root": str(Path(root)),
        "genre": meta.genre,
        "title": meta.title,
        "user_idea": idea,
        "messages": [],
    }
    console.print("[dim]mock 模式：设置 NOVEL_ENGINE_MOCK=1 可离线跑确定性结果[/dim]")
    graph.invoke(initial, thread)
    _confirm_loop(graph, thread)


def _confirm_loop(graph, thread: dict) -> None:
    """在 interrupt 确认点之间循环，直到图执行完毕。"""
    while True:
        state = graph.get_state(thread)
        if not state.next:
            console.print("[green]当前流程执行完毕。[/green]")
            return
        task = state.tasks[-1]
        info = task.interrupts[-1].value
        console.print(f"\n[bold]确认点：{info['stage_label']}[/bold]（{info['stage']}）")
        console.print_json(json.dumps(info["payload"], ensure_ascii=False))
        action = typer.prompt("操作：accept=接受 / edit=编辑替换 / quit=退出", default="accept")
        choice = action.strip().lower()
        if choice in ("q", "quit"):
            console.print("[yellow]已退出（图状态已 checkpoint 保留），再次 project run 可继续。[/yellow]")
            return
        if choice in ("e", "edit"):
            raw = typer.prompt("输入替换后的完整 JSON")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                console.print("[red]JSON 解析失败，本次按接受处理[/red]")
                data = info["payload"]
            graph.invoke(Command(resume={"action": "edit", "data": data}), thread)
        else:
            graph.invoke(Command(resume={"action": "accept"}), thread)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    root: Path = typer.Option(".", "--root"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="代码变更自动重启（开发用，生产用 --no-reload）"),
) -> None:
    """启动 FastAPI 服务（前端联调用）。"""
    import socket

    import uvicorn

    # 端口占用预检：被占用时给出明确提示而不是直接崩溃退出
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            console.print(f"[red]端口 {port} 已被占用，服务未能启动。[/red]")
            console.print(f"[yellow]排查：{host}:{port} 可能已有 novel-agent 服务在跑。[/yellow]")
            console.print(
                "[yellow]  1) 先停掉旧服务，或换端口：novel-agent serve --port 8001[/yellow]"
            )
            console.print(
                "[yellow]  2) 查看占用：Get-NetTCPConnection -LocalPort "
                f"{port} -State Listen[/yellow]"
            )
            raise typer.Exit(1)

    console.print(f"[green]novel-agent API 服务：http://{host}:{port}[/green]（root={root}）")
    console.print("[dim]提示：本终端关闭即停止服务；保持本窗口开启。[/dim]")
    if reload:
        console.print("[dim]开发模式：后端代码变更会自动重载，无需手动重启。[/dim]")

    import os

    # 统一日志输出（替代散落的 print）
    from novel_agent.logutil import configure_logging

    configure_logging()

    # uvicorn --reload 要求以"导入字符串 + factory"方式加载应用，root 经环境变量传入
    from novel_agent.api.app import _ROOT_ENV

    os.environ[_ROOT_ENV] = str(root)
    uvicorn.run(
        "novel_agent.api.app:create_app",
        host=host,
        port=port,
        factory=True,
        reload=reload,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
