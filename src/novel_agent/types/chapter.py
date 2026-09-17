"""正文：场景块 + 章节（Stage5 产出）。"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field, model_validator


class SceneBlock(BaseModel):
    id: str = ""
    heading: str = ""
    text: str = ""
    paragraphs: list[str] | None = None  # 预留段落级

    @model_validator(mode="after")
    def _fill_text_from_paragraphs(self):
        """兼容模型把正文写进 paragraphs 而留空 text 的情况：自动拼接回填。"""
        if (self.text or "").strip():
            return self
        paras = self.paragraphs or []
        parts = []
        for p in paras:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                # 防御：段落对象取 text/content 字段，或整个序列化
                v = p.get("text") or p.get("content") or ""
                parts.append(v if isinstance(v, str) else json.dumps(p, ensure_ascii=False))
        joined = "\n".join(x for x in parts if x and x.strip())
        if joined.strip():
            return self.model_copy(update={"text": joined, "paragraphs": None})
        return self


class Chapter(BaseModel):
    volume: int = 0
    chapter: int = 0
    title: str = ""
    scenes: list[SceneBlock] = Field(default_factory=list)
