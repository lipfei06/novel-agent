"""写作手法条目：可挂载到单本小说的叙事技法（知识型 / 机制型）。

- knowledge（知识型）：guidance 注入对应环节的 prompt 作参考，即挂即用。
- mechanism（机制型）：除 guidance 外还携带 structure_schema 描述的结构化数据
  （如暗线的叙事蓝图）与专项检查（checklist），由流水线执行协议。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TechniqueEntry(BaseModel):
    """写作手法库条目。id 为稳定标识，修改走 update（version 自增）。"""

    id: str
    name: str
    category: str = ""  # 结构 / 节奏 / 悬念 / 网文 / 视角 ...
    mode: str = "knowledge"  # knowledge | mechanism
    apply_stage: str = "all"  # planning | writing | review | all
    description: str = ""  # 手法说明（作者可读）
    guidance: str = ""  # 注入 prompt 的执行指导（AI 可读）
    checklist: list[str] = Field(default_factory=list)  # 检查要点（校验环节引用）
    examples: list[str] = Field(default_factory=list)  # 微示例（正/反例，供 AI 对照）
    tags: list[str] = Field(default_factory=list)
    structure_schema: str = ""  # 机制型：所需数据结构的说明
    version: int = 1


def stage_guidance(techniques: list[dict] | None, stages: tuple[str, ...]) -> str:
    """拼装适用于指定阶段的手法 guidance 为一段 prompt 文本。

    apply_stage 为 all 的条目对所有阶段生效；无命中时返回空串。
    """
    parts: list[str] = []
    for t in techniques or []:
        if not isinstance(t, dict):
            continue
        stage = t.get("apply_stage", "all")
        if stage != "all" and stage not in stages:
            continue
        g = (t.get("guidance") or "").strip()
        if not g:
            continue
        parts.append(f"【{t.get('name', '手法')}】{g}")
        for c in t.get("checklist") or []:
            parts.append(f"  - 自查：{c}")
    if not parts:
        return ""
    return "已挂载的写作手法（务必遵循）：\n" + "\n".join(parts)
