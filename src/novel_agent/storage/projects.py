"""F18 项目管理：建/查/列/删多本小说项目（数据隔离）。"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .jsonio import write_json_atomic
from .paths import ProjectPaths


class ProjectError(Exception):
    """项目操作失败。"""


@dataclass
class ProjectMeta:
    project_id: str
    title: str
    genre: str
    created_at: str
    current_stage: str = "stage0"
    total_chapters: int = 0


class ProjectManager:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.projects_dir = self.root / "output" / "projects"

    def _meta_path(self, project_id: str) -> Path:
        return ProjectPaths(self.root, project_id).meta_path

    def exists(self, project_id: str) -> bool:
        return self._meta_path(project_id).exists()

    def create(self, project_id: str | None, genre: str, title: str) -> ProjectPaths:
        """创建项目。project_id 省略时自动生成。id 重复抛 ProjectError。"""
        pid = project_id or f"p{uuid.uuid4().hex[:8]}"
        if self.exists(pid):
            raise ProjectError(f"项目已存在: {pid}")
        paths = ProjectPaths(self.root, pid).ensure()
        meta = ProjectMeta(
            project_id=pid,
            title=title,
            genre=genre,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write_meta(meta)
        return paths

    def get(self, project_id: str) -> ProjectPaths:
        """获取项目路径，不存在抛 ProjectError。"""
        if not self.exists(project_id):
            raise ProjectError(f"项目不存在: {project_id}")
        return ProjectPaths(self.root, project_id)

    def get_meta(self, project_id: str) -> ProjectMeta:
        path = self._meta_path(project_id)
        if not path.exists():
            raise ProjectError(f"项目不存在: {project_id}")
        with path.open("r", encoding="utf-8") as fh:
            return ProjectMeta(**json.load(fh))

    def list(self) -> list[ProjectMeta]:
        metas: list[ProjectMeta] = []
        if not self.projects_dir.exists():
            return metas
        for meta_file in sorted(self.projects_dir.glob("*/meta.json")):
            with meta_file.open("r", encoding="utf-8") as fh:
                metas.append(ProjectMeta(**json.load(fh)))
        return metas

    def delete(self, project_id: str) -> None:
        if not self.exists(project_id):
            raise ProjectError(f"项目不存在: {project_id}")
        paths = ProjectPaths(self.root, project_id)
        for d in (paths.data_dir, paths.project_dir):
            if d.exists():
                for p in sorted(d.rglob("*"), reverse=True):
                    if p.is_dir():
                        p.rmdir()
                    else:
                        p.unlink()
                d.rmdir()

    def update_stage(self, project_id: str, stage: str) -> None:
        meta = self.get_meta(project_id)
        meta.current_stage = stage
        self._write_meta(meta)

    def _write_meta(self, meta: ProjectMeta) -> None:
        path = self._meta_path(meta.project_id)
        write_json_atomic(path, asdict(meta))
