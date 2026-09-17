"""立项书（Stage0 产出）。"""
from pydantic import BaseModel, Field


class Concept(BaseModel):
    genre: str = ""
    title_idea: str = ""
    core_selling: str = ""
    target_reader: str = ""
    target_words: int = 0
    volumes: int = 1
    tone: str = ""
    red_lines: list[str] = Field(default_factory=list)
    logline: str = ""
