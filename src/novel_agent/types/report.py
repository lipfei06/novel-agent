"""报告：一致性检查（Stage6）与审校（Stage8）。"""
from pydantic import BaseModel, Field


class ConsistencyIssue(BaseModel):
    severity: str = "medium"  # high / medium / low
    kind: str = ""  # setting / character / timeline / style / logic
    location: str = ""  # 指向场景/段落
    description: str = ""
    fix_action: str | None = None
    resolved: bool = False


class ConsistencyReport(BaseModel):
    chapter: int = 0
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    auto_fix_attempts: int = 0
    needs_human: bool = False


class EditorialReport(BaseModel):
    scope: str = ""  # volume / final
    volume: int | None = None
    comments: str = ""
    fix_list: list[dict] = Field(default_factory=list)  # [{scene_id, instruction}]
