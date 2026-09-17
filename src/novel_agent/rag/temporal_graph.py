"""F09 双 RAG（二）：时序知识图谱——实体关系随时间演变。"""
from __future__ import annotations

import json
from pathlib import Path

from novel_agent.storage import write_json_atomic


class TemporalGraph:
    """有向关系边 {a, b, kind, chapter, note}。可查询"截至某章"的关系与演变历史。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.nodes: set[str] = set()
        self.edges: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.nodes = set(data.get("nodes", []))
        self.edges = list(data.get("edges", []))

    def _save(self) -> None:
        write_json_atomic(self.path, {"nodes": sorted(self.nodes), "edges": self.edges})

    def add_node(self, entity: str) -> None:
        self.nodes.add(entity)

    def add_edge(self, a: str, b: str, kind: str, chapter: int, note: str = "") -> None:
        self.nodes.update({a, b})
        self.edges.append({"a": a, "b": b, "kind": kind, "chapter": chapter, "note": note})
        self._save()

    def add_edges(self, edges: list[dict]) -> None:
        """批量追加关系边，只落盘一次（避免每条边整文件重写）。"""
        if not edges:
            return
        for e in edges:
            self.nodes.update({e["a"], e["b"]})
            self.edges.append(
                {"a": e["a"], "b": e["b"], "kind": e.get("kind", "互动"), "chapter": e.get("chapter", 0), "note": e.get("note", "")}
            )
        self._save()

    def neighbors(self, entity: str, chapter: int) -> list[dict]:
        """截至 chapter 的邻接关系（不泄露未来信息）。"""
        out = []
        for e in self.edges:
            if e["chapter"] > chapter:
                continue
            if e["a"] == entity:
                out.append({"entity": e["b"], "kind": e["kind"], "chapter": e["chapter"], "note": e.get("note", "")})
            elif e["b"] == entity:
                out.append({"entity": e["a"], "kind": e["kind"], "chapter": e["chapter"], "note": e.get("note", "")})
        return out

    def evolution(self, a: str, b: str) -> list[dict]:
        """两实体间关系演变（按章节升序）。"""
        out = [e for e in self.edges if (e["a"] == a and e["b"] == b) or (e["a"] == b and e["b"] == a)]
        out.sort(key=lambda e: e["chapter"])
        return out

    def __len__(self) -> int:
        return len(self.edges)
