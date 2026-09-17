"""人物模板：完整设计好的人物，跨作品可复用/改造。"""
from pydantic import BaseModel, Field


class CharacterTemplate(BaseModel):
    id: str = ""
    name: str = ""  # 模板名（如：孤高剑客）
    role: str = "supporting"  # protagonist / ally / antagonist / supporting
    description: str = ""  # 人物定位描述
    motivation: str = ""  # 动机线
    flaw: str = ""  # 缺陷
    arc: list[dict] = Field(default_factory=list)  # 成长弧光 [{stage, change}]
    behavior: str = ""  # 言行风格
    dialogue_style: str = ""  # 对话风格
    tags: list[str] = Field(default_factory=list)
    applicable_genres: list[str] = Field(default_factory=list)
    version: int = 1
