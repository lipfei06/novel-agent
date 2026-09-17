"""大纲：总纲 / 卷计划 / 章级 writer_packet（Stage3-4 产出）。"""
from pydantic import BaseModel, Field


class VolumePlan(BaseModel):
    volume: int = 0
    title: str = ""
    event_arc: list[str] = Field(default_factory=list)
    foreshadow_seed: list[str] = Field(default_factory=list)
    foreshadow_payoff: list[str] = Field(default_factory=list)
    chapter_count: int = 0
    ending_hook: str = ""


class WriterPacket(BaseModel):
    volume: int = 0
    chapter: int = 0
    title: str = ""
    goal: str = ""
    conflicts: list[str] = Field(default_factory=list)
    beats: list[dict] = Field(default_factory=list)  # [{order, type, desc}]
    hook: str = ""
    foreshadow: list[dict] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    pov: str = ""
    reference_seeds: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    version: int = 1
    premise: str = ""
    structure: str = ""  # 三幕 / 起承转合
    volumes: list[VolumePlan] = Field(default_factory=list)
    core_events: list[str] = Field(default_factory=list)
    foreshadowing: list[dict] = Field(default_factory=list)
    ending: str = ""
