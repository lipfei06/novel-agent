"""F18 项目路径：统一解析每本小说的隔离目录。"""
from __future__ import annotations

import re
from pathlib import Path

# 项目 ID 白名单：只允许字母/数字/下划线/连字符，防止路径穿越
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ProjectPaths:
    """项目隔离路径：产物 output/projects/<id>/，数据 data/projects/<id>/。"""

    def __init__(self, root: Path, project_id: str) -> None:
        if not _PROJECT_ID_RE.fullmatch(str(project_id)):
            raise ValueError(f"非法的项目 ID: {project_id!r}")
        self.root = Path(root)
        self.project_id = project_id
        self.project_dir = self.root / "output" / "projects" / project_id
        self.data_dir = self.root / "data" / "projects" / project_id

    @property
    def meta_path(self) -> Path:
        return self.project_dir / "meta.json"

    @property
    def libraries_overlay_dir(self) -> Path:
        return self.project_dir / "libraries"

    @property
    def world_dir(self) -> Path:
        return self.project_dir / "world"

    @property
    def characters_dir(self) -> Path:
        return self.project_dir / "characters"

    @property
    def outline_dir(self) -> Path:
        return self.project_dir / "outline"

    @property
    def writer_packets_dir(self) -> Path:
        return self.outline_dir / "writer_packets"

    @property
    def reports_dir(self) -> Path:
        return self.project_dir / "reports"

    @property
    def final_dir(self) -> Path:
        return self.project_dir / "final"

    @property
    def memory_dir(self) -> Path:
        return self.data_dir / "memory"

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "vector_stores"

    @property
    def graph_dir(self) -> Path:
        return self.data_dir / "temporal_graph"

    @property
    def checkpoint_dir(self) -> Path:
        return self.data_dir / "checkpoints"

    def checkpoint_db(self) -> Path:
        return self.checkpoint_dir / f"{self.project_id}.sqlite"

    def chapter(self, vol: int, ch: int) -> Path:
        return self.project_dir / str(vol) / f"{ch}.json"

    def chapter_md(self, vol: int, ch: int) -> Path:
        return self.project_dir / str(vol) / f"{ch}.md"

    def packet(self, vol: int, ch: int) -> Path:
        return self.writer_packets_dir / f"{vol}_{ch}.json"

    def ensure(self) -> "ProjectPaths":
        """创建项目目录结构。"""
        for d in (
            self.project_dir,
            self.data_dir,
            self.libraries_overlay_dir,
            self.world_dir,
            self.characters_dir,
            self.outline_dir,
            self.writer_packets_dir,
            self.reports_dir,
            self.final_dir,
            self.memory_dir,
            self.vector_dir,
            self.graph_dir,
            self.checkpoint_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        return self
