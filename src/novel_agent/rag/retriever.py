"""F09 组合检索器：向量 top-k ∪ 时序图谱实体上下文 ∪ 外部知识库（预留）。"""
from __future__ import annotations

from novel_agent.memory import LongTermMemory

from .temporal_graph import TemporalGraph


def retrieve(
    seeds: list[str],
    long_term: LongTermMemory,
    graph: TemporalGraph | None = None,
    top_k: int = 4,
    current_vol: int = 0,
    current_chapter: int = 0,
    annotate: bool = False,
) -> str:
    """按种子词组合检索，返回拼装的上下文文本（供写作/修改引用）。

    current_vol/current_chapter 用于图谱时序过滤（不泄露未来信息）；
    annotate=True 时向量召回块带 [第x卷第x章] 来源前缀。
    """
    parts: list[str] = []
    seen: set[str] = set()

    for seed in seeds:
        if not seed:
            continue
        for hit in long_term.search(seed, top_k=top_k, with_source=annotate):
            if hit not in seen:
                seen.add(hit)
                parts.append(hit)

    if graph is not None:
        for seed in seeds:
            for rel in graph.neighbors(seed, current_vol, current_chapter):
                line = f"{seed}→{rel['entity']}（{rel['kind']}，第{rel['vol']}卷第{rel['ch']}章）"
                if line not in seen:
                    seen.add(line)
                    parts.append(line)

    return "\n\n".join(parts)
