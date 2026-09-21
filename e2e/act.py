"""E2E 辅助：以 UTF-8 安全地发送 confirm 决策，避免 Windows 控制台编码问题。

用法:
  python e2e/act.py accept
  python e2e/act.py fix <scene_id> <instruction...>
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api"
PID = "e2e_zjqn100k"

client = httpx.Client(timeout=httpx.Timeout(connect=30, read=1800, write=120, pool=30), base_url=BASE)

action = sys.argv[1] if len(sys.argv) > 1 else "accept"
body: dict = {"action": action}
if action == "fix":
    scene_id = sys.argv[2]
    instruction = " ".join(sys.argv[3:])
    body = {"action": "edit", "data": {"apply_edits": True, "fixes": [{"scene_id": scene_id, "instruction": instruction}]}}

t0 = time.time()
r = client.post(f"/projects/{PID}/confirm", json=body)
r.raise_for_status()
v = r.json()
report = v.get("payload") or {}
out = {
    "耗时秒": round(time.time() - t0, 1),
    "stage": v.get("stage"),
    "done": v.get("done"),
    "报告问题数": len(report.get("issues") or []),
    "未解决": [i.get("description", "")[:60] for i in (report.get("issues") or []) if not i.get("resolved")],
}
print(json.dumps(out, ensure_ascii=False, indent=1))
