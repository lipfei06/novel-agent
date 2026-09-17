"""人物档案（Stage2 产出）。"""
from pydantic import BaseModel, Field


class Character(BaseModel):
    id: str = ""
    name: str = ""
    role: str = "supporting"  # protagonist / ally / antagonist / supporting
    tier: str = "supporting"  # main（主，需状态跟踪）/ supporting（次，简要档案）/ background（路人，不建档）
    motivation: str = ""
    flaw: str = ""
    arc: list[dict] = Field(default_factory=list)  # [{stage, change}]
    relationships: list[dict] = Field(default_factory=list)  # [{target_id, kind, evolution}]
    timeline: list[dict] = Field(default_factory=list)  # [{chapter_range, event}]
    # 外貌与基础信息（主角色详细；次要角色给关键特征；路人不存）
    appearance: str = ""  # 外貌：身高体型/面容/标志性特征/着装/气质
    voice: str = ""  # 音色/语速/口头禅/说话方式
    habits: str = ""  # 小动作/习惯
    background: str = ""  # 出身/关键过往
    signature_item: str = ""  # 标志性随身物品
