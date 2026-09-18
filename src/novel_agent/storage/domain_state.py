"""章节事件驱动的领域状态管理。

每章确认后，总结智能体从正文中提炼结构化的章节事件（ChapterEvent），
各领域（情节/人物/伏笔/主题/文风）根据事件自主更新自己维护的精简状态。

架构原则：
- 写入由章节事件驱动（非全量覆盖）
- 各领域状态独立存储（JSON），可独立查询和调试
- 状态是"提炼后的知识"，可随时从章节正文重建
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_agent.storage import read_json, write_json_atomic

_DOMAINS = ("plot", "characters", "foreshadow", "theme", "style")


def domain_dir(project_root: str | Path, project_id: str) -> Path:
    """返回领域状态目录：data/projects/<id>/domains/。"""
    return Path(project_root) / "data" / "projects" / project_id / "domains"


def load_domain_state(
    project_root: str | Path, project_id: str, domain: str
) -> dict[str, Any]:
    """读取指定领域的状态文件；不存在返回空 dict。"""
    path = domain_dir(project_root, project_id) / f"{domain}.json"
    return read_json(path, default={})


def save_domain_state(
    project_root: str | Path, project_id: str, domain: str, state: dict[str, Any]
) -> None:
    """原子写入指定领域的状态文件。"""
    path = domain_dir(project_root, project_id) / f"{domain}.json"
    write_json_atomic(path, state)
