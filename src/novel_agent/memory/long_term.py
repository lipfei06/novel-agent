"""F09 长期记忆：向量库（M4 用确定性二元组 embedding，可离线测试；后续可换真 embedding）。"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path


def _bigrams(text: str) -> dict[str, float]:
    s = re.sub(r"[\s，。.!！?？、;；:：()（）“”\"'\-—…]+", "", str(text or ""))
    counts: dict[str, float] = {}
    if len(s) == 0:
        return counts
    if len(s) <= 2:
        counts[s] = counts.get(s, 0.0) + 1.0
        return counts
    for i in range(len(s) - 1):
        g = s[i : i + 2]
        counts[g] = counts.get(g, 0.0) + 1.0
    return counts


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class LongTermMemory:
    """长期向量记忆：chunk 文本 + 向量，JSON 持久化。

    向量后端可插拔：传入 embed_fn（text -> list[float]）时使用真 embedding
    （OpenAI 兼容 /embeddings 接口，见 llm.get_embedder）；缺省回退本地
    bigram 稀疏向量（离线可测，无语义泛化能力）。
    """

    MODE_SPARSE = "sparse"
    MODE_DENSE = "dense"

    def __init__(self, path: Path, embed_fn=None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._embed = embed_fn
        self._mode = self.MODE_DENSE if embed_fn is not None else self.MODE_SPARSE
        self._chunks: list[str] = []
        self._vectors: list = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        chunks = list(data.get("chunks", []))
        vectors = list(data.get("vectors", []))
        mode = str(data.get("mode", self.MODE_SPARSE))
        if mode != self._mode:
            # 后端切换：旧向量与新检索方式不兼容，重建索引
            import sys

            print(
                f"[long_term] 向量后端由 {mode} 切换为 {self._mode}，重建索引（丢弃 {len(chunks)} 条旧向量）",
                file=sys.stderr,
                flush=True,
            )
            return
        self._chunks = chunks
        self._vectors = vectors

    def _save(self) -> None:
        from novel_agent.storage import write_json_atomic

        write_json_atomic(self.path, {"mode": self._mode, "chunks": self._chunks, "vectors": self._vectors})

    def _vector(self, text: str):
        return self._embed(text) if self._embed is not None else _bigrams(text)

    def add(self, chunks: list[str]) -> None:
        for c in chunks:
            if not c:
                continue
            self._chunks.append(c)
            self._vectors.append(self._vector(c))
        self._save()

    def search(self, query: str, top_k: int = 4) -> list[str]:
        q = self._vector(query)
        if not q:
            return []
        if self._mode == self.MODE_DENSE:
            scored = [(i, _cosine_dense(q, v)) for i, v in enumerate(self._vectors)]
        else:
            scored = [(i, _cosine(q, v)) for i, v in enumerate(self._vectors)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [self._chunks[i] for i, _ in scored[:top_k]]

    def add_diff(self, old: str, new: str) -> None:
        """仅重算改动部分：按 chunk 文本定位移除 old，写入 new。"""
        try:
            i = self._chunks.index(old)
        except ValueError:
            i = -1
        if i >= 0:
            self._chunks.pop(i)
            self._vectors.pop(i)
        self.add([new])

    def clear(self) -> None:
        self._chunks = []
        self._vectors = []
        self._save()

    def __len__(self) -> int:
        return len(self._chunks)


def _cosine_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
