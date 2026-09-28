"""章节版本快照：编辑覆盖/重写覆盖/删除/恢复前自动留底，可列出、查看与恢复。

每章一个目录：data/projects/<pid>/versions/<vol>_<ch>/，文件名 v_<epoch_ms>.json，
内容 {"saved_at", "reason", "chapter"}。每键最多保留 MAX_PER_KEY 份（超出删最旧）。
快照任何一步失败都静默返回 None——留底是增强功能，绝不阻断主流程。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

MAX_PER_KEY = 20

_VID_RE = re.compile(r"^v_\d+$")


def _base(root: Path, project_id: str) -> Path:
    from novel_agent.storage import ProjectPaths

    return ProjectPaths(root, project_id).data_dir / "versions"


def _key_dir(root: Path, project_id: str, key: str) -> Path:
    return _base(root, project_id) / key


def _words(chapter: dict) -> int:
    return sum(len(s.get("text") or "") for s in (chapter.get("scenes") or []))


def snapshot_chapter(root: Path, project_id: str, chapter: dict, reason: str) -> str | None:
    """留底一个章节版本（旧稿），返回版本 id；卷/章号缺失视为不可留底。"""
    try:
        vol = int(chapter.get("volume") or 0)
        ch = int(chapter.get("chapter") or 0)
        if not vol or not ch:
            return None
        d = _key_dir(Path(root), project_id, f"{vol}_{ch}")
        d.mkdir(parents=True, exist_ok=True)
        vid = f"v_{int(time.time() * 1000)}"
        from novel_agent.storage import write_json_atomic

        write_json_atomic(
            d / f"{vid}.json",
            {"saved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "reason": reason, "chapter": chapter},
        )
        _prune(d)
        return vid
    except Exception:
        return None


def _prune(d: Path) -> None:
    files = sorted(d.glob("v_*.json"))
    for f in files[: max(0, len(files) - MAX_PER_KEY)]:
        try:
            f.unlink()
        except OSError:
            pass


def _meta(vid: str, data: dict) -> dict:
    ch = data.get("chapter") or {}
    return {
        "id": vid,
        "saved_at": data.get("saved_at"),
        "reason": data.get("reason"),
        "title": ch.get("title"),
        "words": _words(ch),
    }


def list_versions(root: Path, project_id: str, vol: int, ch: int) -> list[dict]:
    """某章的版本元数据列表（新→旧），不含正文。"""
    d = _key_dir(Path(root), project_id, f"{vol}_{ch}")
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("v_*.json"), reverse=True):
        try:
            out.append(_meta(f.stem, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def load_version(root: Path, project_id: str, vol: int, ch: int, vid: str) -> dict | None:
    """读取一个版本的完整内容；id 非法或文件缺失返回 None。"""
    if not _VID_RE.match(vid or ""):
        return None
    f = _key_dir(Path(root), project_id, f"{vol}_{ch}") / f"{vid}.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        "id": vid,
        "saved_at": data.get("saved_at"),
        "reason": data.get("reason"),
        "chapter": data.get("chapter"),
    }


def volume_groups(root: Path, project_id: str, vol: int, existing_keys: set[str]) -> list[dict]:
    """卷内有备份的全部章节键（含已删除章），供「备份」入口展示。"""
    base = _base(Path(root), project_id)
    prefix = f"{vol}_"
    groups = []
    if not base.exists():
        return groups
    for d in base.iterdir():
        if not d.is_dir() or not d.name.startswith(prefix):
            continue
        try:
            ch_no = int(d.name.split("_")[1])
        except (IndexError, ValueError):
            continue
        files = sorted(d.glob("v_*.json"), reverse=True)
        if not files:
            continue
        try:
            latest = json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            latest = {}
        chap = latest.get("chapter") or {}
        groups.append({
            "key": d.name,
            "vol": vol,
            "chapter": ch_no,
            "deleted": d.name not in existing_keys,
            "count": len(files),
            "latest_saved_at": latest.get("saved_at"),
            "latest_reason": latest.get("reason"),
            "title": chap.get("title"),
            "words": _words(chap),
        })
    groups.sort(key=lambda g: g["chapter"])
    return groups
