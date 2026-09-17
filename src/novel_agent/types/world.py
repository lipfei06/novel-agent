"""世界观设定库（Stage1 产出）。各字段为结构化的条目列表（可被 RAG 切片）。"""
from pydantic import BaseModel, Field


class WorldBible(BaseModel):
    geography: list[dict] = Field(default_factory=list)
    factions: list[dict] = Field(default_factory=list)
    power_system: list[dict] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)
    customs: list[dict] = Field(default_factory=list)
    glossary: list[dict] = Field(default_factory=list)
