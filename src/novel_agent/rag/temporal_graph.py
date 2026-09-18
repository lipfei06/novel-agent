"""F09 双 RAG（二）：时序知识图谱——实体关系随时间演变。"""
from __future__ import annotations

import json
from pathlib import Path

from novel_agent.storage import write_json_atomic


class TemporalGraph:
    """有向关系边 {a, b, kind, vol, ch, note}。可查询"截至某章"的关系与演变历史。

    章序一律用 (vol, ch) 元组比较——只存章号无法区分"卷1第3章"与"卷2第3章"，
    按章回滚会误伤。旧格式（仅 chapter 字段）加载时迁移为 vol=1（存量项目均为
    单卷，假设成立；多卷存量应走记忆重建）。
    """

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
        norm: list[dict] = []
        for e in list(data.get("edges", [])):
            if "vol" in e and "ch" in e:
                norm.append(e)
            else:
                # 旧格式迁移：仅 chapter 章号 → 卷1 + 章号
                norm.append({**e, "vol": 1, "ch": int(e.get("chapter", 0) or 0)})
        self.edges = norm

    def _save(self) -> None:
        write_json_atomic(self.path, {"nodes": sorted(self.nodes), "edges": self.edges})

    @staticmethod
    def _order(e: dict) -> tuple[int, int]:
        return (int(e.get("vol", 1)), int(e.get("ch", 0)))

    def add_node(self, entity: str) -> None:
        self.nodes.add(entity)

    def add_edge(self, a: str, b: str, kind: str, vol: int = 1, ch: int = 0, note: str = "") -> None:
        self.nodes.update({a, b})
        self.edges.append({"a": a, "b": b, "kind": kind, "vol": int(vol), "ch": int(ch), "note": note})
        self._save()

    def add_edges(self, edges: list[dict]) -> None:
        """批量追加关系边，只落盘一次（避免每条边整文件重写）。"""
        if not edges:
            return
        for e in edges:
            self.nodes.update({e["a"], e["b"]})
            self.edges.append(
                {
                    "a": e["a"],
                    "b": e["b"],
                    "kind": e.get("kind", "互动"),
                    "vol": int(e.get("vol", 1)),
                    "ch": int(e.get("ch", 0)),
                    "note": e.get("note", ""),
                }
            )
        self._save()

    def remove_chapter(self, vol: int, ch: int) -> int:
        """回滚某章的全部关系边（配合章节删除），返回删除数。节点集不清理。"""
        before = len(self.edges)
        self.edges = [e for e in self.edges if self._order(e) != (int(vol), int(ch))]
        removed = before - len(self.edges)
        if removed:
            self._save()
        return removed

    def clear_edges(self) -> None:
        """清空全部关系边（节点集保留），用于重建。"""
        self.edges = []
        self._save()

    def neighbors(self, entity: str, vol: int = 0, ch: int = 0) -> list[dict]:
        """截至 (vol, ch) 的邻接关系（不泄露未来信息）。附带 chapter 展示字段。"""
        cur = (int(vol), int(ch))
        out = []
        for e in self.edges:
            if self._order(e) > cur:
                continue
            if e["a"] == entity:
                other = e["b"]
            elif e["b"] == entity:
                other = e["a"]
            else:
                continue
            out.append(
                {
                    "entity": other,
                    "kind": e["kind"],
                    "vol": e.get("vol", 1),
                    "ch": e.get("ch", 0),
                    "chapter": f"{e.get('vol', 1)}_{e.get('ch', 0)}",
                    "note": e.get("note", ""),
                }
            )
        return out

    def evolution(self, a: str, b: str) -> list[dict]:
        """两实体间关系演变（按 (vol, ch) 升序）。"""
        out = [e for e in self.edges if (e["a"] == a and e["b"] == b) or (e["a"] == b and e["b"] == a)]
        out.sort(key=self._order)
        return [
            {
                "a": e["a"],
                "b": e["b"],
                "kind": e["kind"],
                "vol": e.get("vol", 1),
                "ch": e.get("ch", 0),
                "chapter": f"{e.get('vol', 1)}_{e.get('ch', 0)}",
                "note": e.get("note", ""),
            }
            for e in out
        ]

    def __len__(self) -> int:
        return len(self.edges)
