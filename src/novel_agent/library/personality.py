"""人物性格条目：写作时供人物设定与正文写作引用的性格参考。"""
from pydantic import BaseModel, Field

class PersonalityEntry(BaseModel):
    """性格库条目。id 为稳定标识，修改走 update（version 自增），不直接改已发布文本。"""

    id: str
    name: str
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    behavior_patterns: list[str] = Field(default_factory=list)
    dialogue_style: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    growth_direction: str = ""
    example_reference: list[str] = Field(default_factory=list)
    applicable_genres: list[str] = Field(default_factory=list)
    version: int = 1
