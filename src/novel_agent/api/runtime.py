"""F16 API 运行时：每个项目持有编译图 + 线程配置（供 REST/SSE 驱动确认点）。"""
from __future__ import annotations

import threading
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from novel_agent.config import Config, ConfigError, load_config
from novel_agent.graph import compile_persistent_graph
from novel_agent.storage import ProjectManager, ProjectPaths


class ProjectRuntime:
    def __init__(self, graph: CompiledStateGraph, thread: dict) -> None:
        self.graph = graph
        self.thread = thread

    @property
    def thread_id(self) -> str:
        return self.thread["configurable"]["thread_id"]


class RuntimeStore:
    """按 project_id 缓存运行时；重启后按 checkpoint DB 重新编译即可续写。"""

    def __init__(self, root: Path, config_path: Path | None = None) -> None:
        self.root = Path(root)
        self.config_path = config_path or (self.root / "config.yaml")
        self._cache: dict[str, ProjectRuntime] = {}
        self._lock = threading.Lock()

    def load_config(self, genre: str) -> Config:
        try:
            return load_config(self.config_path, genre)
        except ConfigError:
            # 服务端允许未配置完整 llm（mock 模式），用默认题材
            return load_config(self.config_path)

    def get_or_create(self, project_id: str, genre: str, cfg: Config | None = None) -> ProjectRuntime:
        # 双检锁：并发首访同一项目只编译一次图、开一条 sqlite 连接
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached
        with self._lock:
            cached = self._cache.get(project_id)
            if cached is not None:
                return cached
            cfg = cfg or self.load_config(genre)
            db_path = ProjectPaths(self.root, project_id).checkpoint_db()
            graph = compile_persistent_graph(cfg, db_path)
            runtime = ProjectRuntime(graph, {"configurable": {"thread_id": project_id}})
            self._cache[project_id] = runtime
            return runtime

    def invalidate(self, project_id: str) -> None:
        """移除缓存并关闭其 SQLite 连接，否则 Windows 下项目文件被占用无法删除。"""
        with self._lock:
            cached = self._cache.pop(project_id, None)
        if cached is None:
            return
        conn = getattr(cached.graph, "_sqlite_conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
