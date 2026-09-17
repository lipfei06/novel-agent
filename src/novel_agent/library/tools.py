"""小说工具条目：写作时供细纲与正文设计章节技法的常用创作工具。"""
from pydantic import BaseModel, Field

class NovelToolEntry(BaseModel):
    """小说工具库条目。id 为稳定标识，修改走 update（version 自增）。"""

    id: str
    name: str
    category: str = ""
    description: str = ""
    usage_guidelines: str = ""
    examples: list[str] = Field(default_factory=list)
    chapter_placement: str = ""
    common_mistakes: list[str] = Field(default_factory=list)
    version: int = 1
