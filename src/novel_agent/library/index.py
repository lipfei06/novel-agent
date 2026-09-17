"""LibraryIndex：写作基础库的离线关键词索引。

M0 阶段采用确定性的"中文二元组重叠"打分，无需外部 embedding，离线可测；
M4（F09）将替换/升级为向量 RAG。本索引只负责排名，检索入口在 searcher.py。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .store import Kind, LibraryStore

_WS = re.compile(r"[\s,，。.!！?？、;；:：()（）“”\"'\-—…]+")


def _bigrams(text: str) -> set[str]:
    """中文/混合文本的二元组集合；长度 <=2 时返回原串（去空白）。"""
    s = _WS.sub("", str(text or ""))
    if len(s) <= 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


class LibraryIndex:
    """索引内容为 {kind: {id: {text, name}}}，text 由条目各检索字段拼接。"""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.index_dir / "index.json"
        self._data: dict[str, dict[str, dict]] = {}
        self._load()

    # ---- 持久化 ---------------------------------------------------
    def _load(self) -> None:
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._data = data if isinstance(data, dict) else {}

    def _save(self) -> None:
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    # ---- 维护 -----------------------------------------------------
    def rebuild(self, store: LibraryStore) -> None:
        """从 store 全量重建索引。"""
        self._data = {}
        for kind in ("personality", "tool", "character_template", "technique"):
            for entry in store.list(kind):  # type: ignore[arg-type]
                self._index_entry(kind, entry)
        self._save()

    def upsert(self, kind: Kind, entry: object) -> None:
        """增量写入/更新单条。"""
        self._index_entry(kind, entry)
        self._save()

    def remove(self, kind: Kind, entry_id: str) -> None:
        self._data.setdefault(kind, {}).pop(entry_id, None)
        self._save()

    def has_kind(self, kind: Kind) -> bool:
        """索引中是否已有该 kind 的数据（为空时调用方应先 rebuild）。"""
        return bool(self._data.get(kind))

    def clear(self) -> None:
        self._data = {}
        self._save()

    # ---- 检索 -----------------------------------------------------
    def search(self, query: str, kind: Kind, top_k: int = 3) -> list[dict]:
        """返回按相关度降序的 [{id, score}]。分数 = 字段二元组重叠 + 名称精确命中加成。"""
        q_terms = _bigrams(query)
        if not q_terms:
            return []
        scored: list[tuple[str, float]] = []
        for entry_id, payload in self._data.get(kind, {}).items():
            text_terms = _bigrams(payload.get("text", ""))
            overlap = len(q_terms & text_terms)
            if overlap == 0:
                continue
            score = float(overlap)
            name = payload.get("name", "")
            if name and name in query:
                score += 2.0
            scored.append((entry_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [{"id": eid, "score": score} for eid, score in scored[:top_k]]

    # ---- 内部 -----------------------------------------------------
    def _index_entry(self, kind: Kind, entry: object) -> None:
        d = entry.model_dump() if hasattr(entry, "model_dump") else dict(entry)  # type: ignore[arg-type]
        fields = [
            d.get("name", ""),
            d.get("category", ""),
            " ".join(str(x) for x in d.get("tags", [])),
            d.get("description", ""),
            " ".join(str(x) for x in d.get("behavior_patterns", []))
            or " ".join(str(x) for x in d.get("usage_guidelines", [])),
            " ".join(str(x) for x in d.get("weaknesses", [])),
        ]
        self._data.setdefault(kind, {})[str(d.get("id"))] = {
            "name": str(d.get("name", "")),
            "text": " ".join(f for f in fields if f),
        }
