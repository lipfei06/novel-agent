"""智能体 Skill 层：阶段化手艺知识注入（需求分析见 docs/智能体Skill体系需求分析.md）。

文件格式：每个 skill 是一个 markdown 文件 = YAML frontmatter（name/description/
apply_stage/priority/ask_author）+ 正文（给模型看的手艺要点与正反例）。

加载策略：启动时解析全部 frontmatter 常驻内存；load(stage) 返回命中 skill 的
包装正文（一阶段一个）。缺文件/解析失败一律降级为空串——skill 注入永不阻塞生成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    apply_stage: str
    priority: int = 50
    ask_author: list = field(default_factory=list)
    body: str = ""


class SkillLoader:
    def __init__(self, base: Path | None = None) -> None:
        self.base = Path(base) if base else Path(__file__).parent
        self._skills: dict[str, Skill] = {}
        for path in sorted(self.base.glob("*.md")):
            try:
                skill = _parse(path)
            except Exception:
                continue  # 单个文件坏了不拖垮其他 skill
            if skill and skill.apply_stage:
                self._skills[skill.apply_stage] = skill

    def load(self, stage: str) -> str:
        """返回该阶段 skill 的包装正文；未命中返回空串。"""
        skill = self._skills.get(stage)
        if not skill or not skill.body.strip():
            return ""
        return (
            f'<skill name="{skill.name}">\n{skill.body.strip()}\n</skill>\n'
            "（以上 skill 是本阶段的手艺指导：只影响内容取向，不改变输出格式与字段要求。）"
        )

    def describe(self) -> list[dict]:
        """全部已加载 skill 的元数据（诊断/前端展示用）。"""
        return [
            {
                "stage": stage,
                "name": s.name,
                "description": s.description,
                "priority": s.priority,
                "ask_author": s.ask_author,
            }
            for stage, s in sorted(self._skills.items())
        ]


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    return Skill(
        name=str(meta.get("name") or path.stem),
        description=str(meta.get("description") or ""),
        apply_stage=str(meta.get("apply_stage") or ""),
        priority=int(meta.get("priority") or 50),
        ask_author=list(meta.get("ask_author") or []),
        body=body,
    )


@lru_cache(maxsize=1)
def get_skill_loader() -> SkillLoader:
    return SkillLoader()


def skill_text(stage: str) -> str:
    """agent 便捷入口：任何异常都降级为空串。"""
    try:
        return get_skill_loader().load(stage)
    except Exception:
        return ""
