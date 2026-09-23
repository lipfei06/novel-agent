"""F09 长期记忆：向量库（场景切片 + 章节 meta，可离线 bigram 或接真 embedding）。"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

# 单 chunk 长度上限：超出按段落/句子二次切分（长文本向量表征会被"平均"，检索失真）
MAX_CHUNK_LEN = 1200

_SENT_RE = re.compile(r"[^。！？!?…]+[。！？!?…]?")


def _split_sentences(para: str, max_len: int) -> list[str]:
    """段内按句子切；单句仍超长则字符硬切。"""
    out: list[str] = []
    buf = ""
    for s in _SENT_RE.findall(para):
        if not s:
            continue
        if not buf:
            buf = s
        elif len(buf) + len(s) <= max_len:
            buf += s
        else:
            out.append(buf)
            buf = s
        while len(buf) > max_len:
            out.append(buf[:max_len])
            buf = buf[max_len:]
    if buf:
        out.append(buf)
    return out


def _split_long(text: str, max_len: int) -> list[str]:
    """超长 chunk 二次切分：段落贪心打包；单段超长按句切；单句超长字符硬切。"""
    if len(text) <= max_len:
        return [text]
    out: list[str] = []
    buf = ""
    for para in text.split("\n"):
        pieces = [para] if len(para) <= max_len else _split_sentences(para, max_len)
        for piece in pieces:
            if not buf:
                buf = piece
            elif len(buf) + 1 + len(piece) <= max_len:
                buf = f"{buf}\n{piece}"
            else:
                out.append(buf)
                buf = piece
    if buf:
        out.append(buf)
    return out


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
    """长期向量记忆：chunk 文本 + 向量 + 章节 meta，JSON 持久化。

    向量后端可插拔：传入 embed_fn（text -> list[float]）时使用真 embedding
    （OpenAI 兼容 /embeddings 接口，见 llm.get_embedder）；缺省回退本地
    bigram 稀疏向量（离线可测，无语义泛化能力）。

    meta 与 chunks 平行：{vol, ch, scene, key, part?, parts?}。旧格式文件无
    meta 时自动补 None——此类块不参与按章回滚与来源标注。

    后端模式与已存库不一致时（如稠密/稀疏切换），按 chunks 文本重算向量，
    语料无损；稠密重算接口故障时降级为稀疏检索。
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
        self._meta: list[dict | None] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        chunks = list(data.get("chunks", []))
        vectors = list(data.get("vectors", []))
        mode = str(data.get("mode", self.MODE_SPARSE))
        metas = data.get("meta")
        if not isinstance(metas, list) or len(metas) != len(chunks):
            metas = [None] * len(chunks)
        if mode != self._mode:
            # 后端切换：旧向量与新检索方式不兼容。chunks 文本是源数据——
            # 按新方式重算向量即可，绝不能丢弃（丢弃=不可逆的语料损失）。
            import sys

            print(
                f"[long_term] 向量后端由 {mode} 切换为 {self._mode}，按文本重算 {len(chunks)} 条向量（无数据丢失）",
                file=sys.stderr,
                flush=True,
            )
            self._chunks = chunks
            self._meta = list(metas)
            try:
                self._vectors = [self._vector(c) for c in self._chunks]
            except Exception as exc:  # noqa: BLE001  稠密接口故障：降级稀疏，文本仍在
                print(
                    f"[long_term] 重算向量失败（{exc}），降级为稀疏检索（文本已保留）",
                    file=sys.stderr,
                    flush=True,
                )
                self._mode = self.MODE_SPARSE
                self._vectors = [_bigrams(c) for c in self._chunks]
            self._save()
            return
        self._chunks = chunks
        self._vectors = vectors
        self._meta = list(metas)

    def _save(self) -> None:
        from novel_agent.storage import write_json_atomic

        write_json_atomic(
            self.path,
            {"mode": self._mode, "chunks": self._chunks, "vectors": self._vectors, "meta": self._meta},
        )

    def _vector(self, text: str):
        return self._embed(text) if self._embed is not None else _bigrams(text)

    @staticmethod
    def _meta_key(m: dict | None) -> str | None:
        if not m:
            return None
        k = m.get("key")
        if isinstance(k, str) and k:
            return k
        if m.get("vol") is not None and m.get("ch") is not None:
            return f"{m['vol']}_{m['ch']}"
        return None

    def add(self, chunks: list[str], metas: list[dict | None] | None = None) -> None:
        """入库；超长块自动二次切分（子块继承 meta 并附 part/parts）。"""
        for i, c in enumerate(chunks):
            if not c:
                continue
            base = metas[i] if metas and i < len(metas) else None
            parts = _split_long(c, MAX_CHUNK_LEN)
            for j, p in enumerate(parts):
                m = dict(base) if base else None
                if m is not None and len(parts) > 1:
                    m["part"] = j + 1
                    m["parts"] = len(parts)
                self._chunks.append(p)
                self._meta.append(m)
                self._vectors.append(self._vector(p))
        self._save()

    def search(self, query: str, top_k: int = 4, with_source: bool = False) -> list[str]:
        q = self._vector(query)
        if not q:
            return []
        if self._mode == self.MODE_DENSE:
            scored = [(i, _cosine_dense(q, v)) for i, v in enumerate(self._vectors)]
        else:
            scored = [(i, _cosine(q, v)) for i, v in enumerate(self._vectors)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        out = []
        for i, _ in scored[:top_k]:
            chunk = self._chunks[i]
            if with_source:
                prefix = self._source_prefix(self._meta[i] if i < len(self._meta) else None)
                if prefix:
                    chunk = f"{prefix} {chunk}"
            out.append(chunk)
        return out

    @staticmethod
    def _source_prefix(m: dict | None) -> str:
        if not m:
            return ""
        v, c = m.get("vol"), m.get("ch")
        if v is None or c is None:
            return ""
        return f"[第{v}卷第{c}章]"

    def add_diff(self, old: str, new: str, meta: dict | None = None) -> None:
        """替换旧块：优先按元数据（key+scene）定位（文本可变），退化按文本精确匹配。"""
        i = -1
        if meta:
            want = self._meta_key(meta)
            if want:
                for idx, m in enumerate(self._meta):
                    if not m or self._meta_key(m) != want:
                        continue
                    if meta.get("scene") is None or m.get("scene") == meta.get("scene"):
                        i = idx
                        break
        if i < 0:
            try:
                i = self._chunks.index(old)
            except ValueError:
                i = -1
        if i >= 0:
            self._chunks.pop(i)
            self._vectors.pop(i)
            if i < len(self._meta):
                self._meta.pop(i)
        self.add([new], [meta] if meta else None)

    def remove_chapter(self, vol: int, ch: int) -> int:
        """按元数据删除某章全部切片（无 meta 的旧块不受影响），返回删除数。"""
        key = f"{vol}_{ch}"
        kept_c: list[str] = []
        kept_v: list = []
        kept_m: list[dict | None] = []
        removed = 0
        for i, c in enumerate(self._chunks):
            m = self._meta[i] if i < len(self._meta) else None
            if m is not None and self._meta_key(m) == key:
                removed += 1
                continue
            kept_c.append(c)
            kept_v.append(self._vectors[i])
            kept_m.append(m)
        if removed:
            self._chunks, self._vectors, self._meta = kept_c, kept_v, kept_m
            self._save()
        return removed

    def clear(self) -> None:
        self._chunks = []
        self._vectors = []
        self._meta = []
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
