"""F09 中期记忆：每章摘要表。"""
from __future__ import annotations

import json
from pathlib import Path

from novel_agent.config import Config


class MidTermMemory:
    """章节摘要持久化。key 形如 "1_3"。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._summaries: dict[str, str] = {}
        self._vol_summaries: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "summaries" in data:
            # 新格式：两级（章摘要 + 卷摘要）
            self._summaries = dict(data.get("summaries") or {})
            self._vol_summaries = {str(k): v for k, v in (data.get("vol_summaries") or {}).items()}
        else:
            # 旧格式：纯 {vol_ch: summary}
            self._summaries = dict(data)
            self._vol_summaries = {}

    def _save(self) -> None:
        from novel_agent.storage import write_json_atomic

        write_json_atomic(self.path, {
            "summaries": self._summaries,
            "vol_summaries": self._vol_summaries,
        })

    def summarize_chapter(self, chapter: dict, cfg: Config) -> str:
        """章节摘要：mock 用标题+场景首句；真实模式用 cheap 模型生成
        （失败时回退截取式摘要，不阻断创作）。"""
        from novel_agent.agents import is_mock

        if not is_mock():
            try:
                return self._llm_summary(chapter, cfg)
            except Exception:  # noqa: BLE001
                pass
        title = chapter.get("title", "")
        scenes = chapter.get("scenes", [])
        heads = [s.get("text", "")[:40] for s in scenes if s.get("text")]
        return f"{title}：{' / '.join(heads)}"

    def _llm_summary(self, chapter: dict, cfg: Config) -> str:
        from pydantic import BaseModel, Field

        from novel_agent.llm import build_messages, get_chat_model, invoke_structured
        from novel_agent.types import chapter_plaintext

        class ChapterSummary(BaseModel):
            summary: str = Field(default="")

        system = (
            "你是小说编辑。用 80-150 字概括本章：关键事件、人物动机与行动、冲突结果、"
            "留给下一章的钩子。只输出 JSON：{\"summary\": \"...\"}"
        )
        user = f"本章：\n{chapter_plaintext(chapter)}"
        messages = build_messages(system, user, "summary", cfg.token_budget)
        llm = get_chat_model("cheap", cfg, task="summary")  # 任务级覆写：摘要可路由到本地模型
        result = invoke_structured(llm, messages, schema=ChapterSummary)
        text = (result.summary or "").strip()
        if not text:
            raise ValueError("模型返回了空摘要")
        return text

    def add(self, vol: int, ch: int, summary: str) -> None:
        self._summaries[f"{vol}_{ch}"] = summary
        self._save()

    def remove(self, vol: int, ch: int) -> None:
        """删除某章摘要（配合章节删除）。"""
        self._summaries.pop(f"{vol}_{ch}", None)
        self._save()

    def get(self, vol: int, ch: int) -> str | None:
        return self._summaries.get(f"{vol}_{ch}")

    def recent(self, limit: int = 10) -> list[str]:
        keys = sorted(self._summaries.keys(), key=lambda k: [int(x) for x in k.split("_")])
        return [self._summaries[k] for k in keys[-limit:]]

    def summaries_for_volume(self, vol: int) -> dict[int, str]:
        """本卷已写章的章摘要，按章号升序。"""
        out: dict[int, str] = {}
        for k, s in self._summaries.items():
            try:
                v, c = (int(x) for x in k.split("_"))
            except ValueError:
                continue
            if v == vol:
                out[c] = s
        return dict(sorted(out.items()))

    def volume_summaries(self) -> dict[int, str]:
        """全部已生成的卷摘要 {卷号: 卷摘要}。"""
        return {int(k): v for k, v in self._vol_summaries.items()}

    def set_volume_summary(self, vol: int, summary: str) -> None:
        self._vol_summaries[str(vol)] = summary
        self._save()

    def summarize_volume(self, vol: int, cfg: Config) -> str:
        """卷摘要：聚合本卷全部章摘要（真实=cheap 模型；mock/失败=拼接回退）。"""
        from novel_agent.agents import is_mock

        sums = self.summaries_for_volume(vol)
        if not sums:
            return ""
        if not is_mock():
            try:
                s = self._llm_volume_summary(vol, sums, cfg)
                if s.strip():
                    return s
            except Exception:  # noqa: BLE001
                pass
        joined = "\n".join(f"第{c}章：{sums[c][:60]}" for c in sorted(sums))
        return f"第{vol}卷要点：\n{joined}"[:1200]

    def _llm_volume_summary(self, vol: int, chapter_sums: dict, cfg: Config) -> str:
        from pydantic import BaseModel

        from novel_agent.llm import build_messages, get_chat_model, invoke_structured

        class VolumeSummary(BaseModel):
            summary: str = ""

        system = (
            "你是小说编辑。把本卷全部章节摘要聚合为一份卷摘要（300-500字）："
            "本卷主线事件走向、主要人物弧光进展、伏笔的埋设与回收状态、遗留问题与卷末局面。"
            '只输出 JSON：{"summary": "..."}'
        )
        user = (
            f"第{vol}卷各章摘要：\n"
            + "\n".join(f"{k}：{s}" for k, s in sorted(chapter_sums.items()))
        )
        messages = build_messages(system, user, "research", cfg.token_budget)
        llm = get_chat_model("cheap", cfg, task="summary")  # 任务级覆写：摘要可路由到本地模型
        result = invoke_structured(llm, messages, schema=VolumeSummary)
        s = (result.summary or "").strip()
        if not s:
            raise ValueError("空卷摘要")
        return s
