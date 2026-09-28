"""LibraryStore：写作基础库 CRUD + 版本自增 + 导出。

两层存储：
- base_dir（全局共享）：`output/libraries/`，跨小说复用，含预置条目
- overlay_dir（项目覆盖层，可选）：`output/projects/<pid>/libraries/`，扩展某本特有素材

规则：get/list 项目层优先（overlay 覆盖同 id 的共享条目）；add/update/delete
在设置了 overlay_dir 时作用于项目层，否则作用于共享层。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .memes import MemeEntry
from .personality import PersonalityEntry
from .techniques import TechniqueEntry
from .tools import NovelToolEntry
from novel_agent.types.character_template import CharacterTemplate

from .styles import StyleEntry

Kind = Literal["personality", "tool", "character_template", "technique", "meme", "style"]

_MODELS: dict[Kind, type] = {
    "personality": PersonalityEntry,
    "tool": NovelToolEntry,
    "character_template": CharacterTemplate,
    "technique": TechniqueEntry,
    "meme": MemeEntry,
    "style": StyleEntry,
}


class LibraryStore:
    def __init__(self, base_dir: Path, overlay_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.overlay_dir = Path(overlay_dir) if overlay_dir else None
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if self.overlay_dir is not None:
            self.overlay_dir.mkdir(parents=True, exist_ok=True)

    # ---- 底层读写 -------------------------------------------------
    @staticmethod
    def _filename(kind: Kind) -> str:
        return f"{kind}.json"

    def _shared_path(self, kind: Kind) -> Path:
        return self.base_dir / self._filename(kind)

    def _overlay_path(self, kind: Kind) -> Path | None:
        if self.overlay_dir is None:
            return None
        return self.overlay_dir / self._filename(kind)

    def _read(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []

    def _write(self, path: Path, entries: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=2)

    # ---- CRUD -----------------------------------------------------
    def add(self, kind: Kind, entry) -> None:
        """新增条目。目标层同 id 已存在则抛 ValueError。

        目标层 = overlay_dir（若设置）否则共享层。与共享层 id 相同是允许的，
        这是"项目覆盖层定制共享条目"的语义。
        """
        target = self._overlay_path(kind) or self._shared_path(kind)
        entries = self._read(target)
        if any(e["id"] == entry.id for e in entries):
            raise ValueError(f"{kind} entry {entry.id!r} already exists in target layer")
        entries.append(entry.model_dump())
        self._write(target, entries)

    def update(self, kind: Kind, entry_id: str, fields: dict):
        """更新条目字段（id 不可改），version 自增。不存在则抛 KeyError。

        设置了 overlay_dir 时始终写入覆盖层：条目已在覆盖层则就地更新，
        否则从任一可见层拷贝后覆盖（共享层不受影响）。
        """
        if "id" in fields:
            raise ValueError("entry id is immutable; use add to create a new entry")
        current = self.get(kind, entry_id)
        if current is None:
            raise KeyError(entry_id)
        if self.overlay_dir is not None:
            target = self._overlay_path(kind)
            assert target is not None
            entries = self._read(target)
            merged = None
            for idx, raw in enumerate(entries):
                if raw["id"] == entry_id:
                    merged = dict(raw)
                    merged.update(fields)
                    merged["version"] = int(raw.get("version", 1)) + 1
                    entries[idx] = merged
                    break
            if merged is None:
                merged = current.model_dump()
                merged.update(fields)
                merged["version"] = int(current.version) + 1
                entries.append(merged)
            self._write(target, entries)
        else:
            target = self._shared_path(kind)
            entries = self._read(target)
            for idx, raw in enumerate(entries):
                if raw["id"] == entry_id:
                    merged = dict(raw)
                    merged.update(fields)
                    merged["version"] = int(raw.get("version", 1)) + 1
                    entries[idx] = merged
                    self._write(target, entries)
                    return _MODELS[kind](**merged)
            raise KeyError(entry_id)
        return _MODELS[kind](**merged)

    def delete(self, kind: Kind, entry_id: str) -> None:
        """删除条目。不存在则抛 KeyError。先查 overlay，再查 shared。"""
        for path in (self._overlay_path(kind), self._shared_path(kind)):
            if path is None or not path.exists():
                continue
            entries = self._read(path)
            remaining = [e for e in entries if e["id"] != entry_id]
            if len(remaining) != len(entries):
                self._write(path, remaining)
                return
        raise KeyError(entry_id)

    def get(self, kind: Kind, entry_id: str):
        """查询条目：overlay 优先，其次 shared。"""
        for path in (self._overlay_path(kind), self._shared_path(kind)):
            if path is None:
                continue
            for raw in self._read(path):
                if raw["id"] == entry_id:
                    return _MODELS[kind](**raw)
        return None

    def list(self, kind: Kind, category: str | None = None) -> list:
        """列出条目（shared + overlay 合并，overlay 同 id 覆盖），可按 category 过滤，按 id 排序。"""
        merged: dict[str, dict] = {}
        for path in (self._shared_path(kind), self._overlay_path(kind)):
            if path is None:
                continue
            for raw in self._read(path):
                merged[raw["id"]] = raw
        entries = [_MODELS[kind](**raw) for raw in merged.values()]
        if category is not None:
            entries = [e for e in entries if e.category == category]
        return sorted(entries, key=lambda e: e.id)

    def export(self, kind: Kind, out_path: Path) -> Path:
        """导出合并后的条目到指定 JSON 文件。"""
        entries = [e.model_dump() for e in self.list(kind)]
        self._write(Path(out_path), entries)
        return Path(out_path)

    def seed(self, presets: dict[Kind, list[PersonalityEntry | NovelToolEntry]]) -> int:
        """写入预置条目（仅当共享层不存在该 id 时）。返回实际写入数。"""
        written = 0
        for kind, items in presets.items():
            existing = {e["id"] for e in self._read(self._shared_path(kind))}
            new_entries = [e.model_dump() for e in items if e.id not in existing]
            if new_entries:
                entries = self._read(self._shared_path(kind))
                entries.extend(new_entries)
                self._write(self._shared_path(kind), entries)
                written += len(new_entries)
        return written
