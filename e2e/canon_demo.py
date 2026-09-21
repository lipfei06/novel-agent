"""试跑：正典事实层（事件账本+道具登记卡+标题去重）对第 21 章规划的实际效果。

步骤：
1) 从既有 20 章构建事件账本（摘要即事件行）与章节标题清单；
2) 一次 cheap 调用从 20 章摘要中提取道具/秘密既定事实，构建道具登记卡（存量重放的最小版）；
3) 用注入正典的 generate_writer_packet 真实生成第 21 章 packet（creative 档）；
4) 与管线里旧的 ch21 packet 对比标题/目标。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx
from pydantic import BaseModel, Field

from novel_agent.agents.packet import generate_writer_packet
from novel_agent.config import load_config
from novel_agent.llm import get_chat_model, invoke_structured
from novel_agent.types import Character, Outline, VolumePlan

PID = "e2e_zjqn100k"
ROOT = Path(__file__).resolve().parents[1]
c = httpx.Client(base_url="http://127.0.0.1:8000/api", timeout=120)

cfg = load_config(ROOT / "config.yaml", "e2e100k")
_r = c.get(f"/projects/{PID}/products")
_r.raise_for_status()
pr = _r.json()
chs = pr.get("chapters") or {}
outline = Outline(**(pr.get("outline") or {}))
chars = pr.get("characters") or []

keys = sorted(chs.keys(), key=lambda k: [int(x) for x in k.split("_")])
used_titles = [chs[k].get("title", "") for k in keys if chs[k].get("title")]

mid = json.loads((ROOT / "data" / "projects" / PID / "memory" / "mid_term.json").read_text(encoding="utf-8"))
summaries = mid.get("summaries") or {}
event_ledger = {k: [s] for k, s in summaries.items()}

# 道具登记卡存量构建：一次 cheap 调用，从 20 章摘要提取道具/秘密既定事实
class _PF(BaseModel):
    prop: str = ""
    fact: str = ""

class _PFList(BaseModel):
    items: list[_PF] = Field(default_factory=list)

sum_lines = "\n".join(f"第{k.split('_')[1]}章：{summaries[k]}" for k in keys if k in summaries)
assert sum_lines, "摘要为空，无法构建道具登记卡"
system = (
    "你是小说连续性管理员。以下是一本小说全部章节的摘要。提取其中**已经确立**的道具/秘密既定事实，"
    "例如怀表的刻字/夹层/芯片状态、关键证据（流水、审批单、录音）的金额与编号、人物身份事实等。"
    "每条格式为'道具或证据名 + 确立的事实'，同一道具可多条，最多 20 条。只输出 JSON。"
)
llm = get_chat_model("cheap", cfg)
res = invoke_structured(llm, [{"role": "system", "content": system}, {"role": "user", "content": sum_lines}], schema=_PFList)
prop_registry: dict = {}
for p in res.items:
    if not p.prop or not p.fact:
        continue
    e = prop_registry.setdefault(p.prop, {"facts": [], "first_ch": "1_1", "last_ch": keys[-1]})
    if p.fact not in e["facts"]:
        e["facts"].append(p.fact)

print("== 道具登记卡（存量构建）==")
for name, e in prop_registry.items():
    print(f"  {name}: {'；'.join(e['facts'][:3])}")

plan = VolumePlan(**(outline.volumes[0].model_dump()))
new_pkt = generate_writer_packet(
    plan, outline, [Character(**x) if not isinstance(x, dict) else x for x in (chars or [])],
    21, cfg, event_ledger=event_ledger, used_titles=used_titles, prop_registry=prop_registry,
)

# 旧 pipeline 里的 ch21 packet（OPT 前、无正典注入时生成）
old_pending = None
try:
    st = c.get(f"/projects/{PID}/state").json()
    old_pending = (st.get("payload") or {}) if st.get("stage") == "stage4b" else None
except Exception:
    pass

print("\n== 新旧第 21 章任务书对比 ==")
print("旧（无正典注入）: 标题=", (old_pending or {}).get("title"), " | 目标=", (old_pending or {}).get("goal", "")[:60])
print("新（正典注入）  : 标题=", new_pkt.title, " | 目标=", new_pkt.goal[:60])
print("  冲突:", json.dumps(new_pkt.conflicts, ensure_ascii=False)[:150])
print("  标题是否与旧标题重复:", new_pkt.title in used_titles)
