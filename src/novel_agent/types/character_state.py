"""主要人物状态：随章节增量更新的"当前状态卡"，供写作时注入保持一致。"""
from pydantic import BaseModel, Field


class CharacterStateEntry(BaseModel):
    character_id: str = ""
    name: str = ""
    tier: str = "supporting"
    status: str = "active"  # active 在世 / dead 死亡 / absent 退场 / transformed 蜕变
    location: str = ""  # 当前所在地
    mood: str = ""  # 情绪状态
    health: str = ""  # 身体/伤势
    resources: str = ""  # 掌握的资源/能力
    relationships: str = ""  # 与关键人物的关系现状
    knowledge: str = ""  # 已经知道什么/还不知道什么
    goal_progress: str = ""  # 当前目标与进展
    arc_stage: str = ""  # 当前成长弧光阶段（对应 Character.arc 的阶段）
    last_chapter: int = 0  # 最后出场章节


class CharacterState(BaseModel):
    version: int = 1
    entries: list[CharacterStateEntry] = Field(default_factory=list)

    def get(self, character_id: str) -> CharacterStateEntry | None:
        for e in self.entries:
            if e.character_id == character_id:
                return e
        return None
