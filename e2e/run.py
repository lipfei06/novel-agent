"""E2E 驱动：真假千金十万字真实生成（可断点续跑）。

用法（项目根目录）:
  python e2e/run.py --max-chapters 3   # 推进到第3章为止（本轮批量上限）
  python e2e/run.py --max-chapters 20  # 一直写到全书完成
  python e2e/run.py --feature-checks   # 执行功能抽查（重建/图谱/助手/成本）

行为:
- 全程 API 驱动 http://127.0.0.1:8000，需后端以真实模式启动（无 NOVEL_ENGINE_MOCK）
- 每步异常写入 e2e/errors.md（时间戳+步骤+堆栈），日志写 e2e/run.log
- 幂等：重复运行自动从当前确认点续跑
"""
from __future__ import annotations

import argparse
import time
import traceback
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api"
PID = "e2e_zjqn100k"
HERE = Path(__file__).resolve().parent
ERR = HERE / "errors.md"
LOG = HERE / "run.log"

IDEA = (
    "现代都市真假千金爽文：真千金林知夏流落小城十八年，假千金沈娇娇鸠占鹊巢。"
    "真千金被接回豪门沈家后遭继母与假千金联手排挤，却凭生母遗物（一块怀表）"
    "牵出海外遗产线索，靠自身能力步步反击：族宴露锋芒、商战反杀、揭穿换女阴谋，"
    "最终继承权归位、亲情与爱情双收。爽点密集，每3章一次小打脸，每卷一次大打脸。"
    "总篇幅约10万字，分2卷，每卷10章。"
)

client = httpx.Client(timeout=httpx.Timeout(connect=30, read=1800, write=120, pool=30), base_url=BASE)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def err(step: str, exc: Exception, tb: str = "") -> None:
    with ERR.open("a", encoding="utf-8") as f:
        f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M:%S')} — {step}\n\n```\n{exc}\n{tb}\n```\n")
    log(f"!! 错误已记录：{step}: {exc}")


def get_view() -> dict:
    r = client.get(f"/projects/{PID}/state")
    r.raise_for_status()
    return r.json()


def confirm(action: str, data=None) -> dict:
    t0 = time.time()
    body = {"action": action, **({"data": data} if data is not None else {})}
    r = client.post(f"/projects/{PID}/confirm", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"confirm {action} HTTP {r.status_code}: {r.text[:300]}")
    v = r.json()
    log(f"confirm {action} -> stage={v.get('stage')} done={v.get('done')} 耗时 {time.time() - t0:.0f}s")
    return v


def ensure_project() -> None:
    r = client.get("/projects")
    r.raise_for_status()
    if any(p["project_id"] == PID for p in r.json().get("projects", [])):
        log(f"项目 {PID} 已存在，续跑")
        return
    r = client.post("/projects", json={"title": "真假千金之千金归位", "genre": "e2e100k", "project_id": PID})
    if r.status_code >= 400:
        raise RuntimeError(f"创建项目失败: {r.text[:300]}")
    log(f"项目 {PID} 创建成功（genre=e2e100k，10万字配置）")


def chapter_no(v: dict) -> int:
    """当前待写章号：stage4b 视图里的 current_chapter；其余阶段取已接受章数+1。"""
    if v.get("current_chapter"):
        return int(v["current_chapter"])
    r = client.get(f"/projects/{PID}/products")
    r.raise_for_status()
    return len(r.json().get("chapters") or {}) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chapters", type=int, default=100)
    args = ap.parse_args()
    log(f"===== E2E 开始（本轮章节上限 {args.max_chapters}）=====")

    try:
        ensure_project()
    except Exception as exc:  # noqa: BLE001
        err("ensure_project", exc, traceback.format_exc())
        return

    v = get_view()
    if not v.get("started"):
        try:
            t0 = time.time()
            r = client.post(f"/projects/{PID}/start", json={"idea": IDEA})
            r.raise_for_status()
            v = r.json()
            log(f"start -> stage={v.get('stage')} 耗时 {time.time() - t0:.0f}s")
        except Exception as exc:  # noqa: BLE001
            err("start/stage0生成", exc, traceback.format_exc())
            return

    while not v.get("done"):
        stage = v.get("stage")
        try:
            if stage == "stage4b" and chapter_no(v) > args.max_chapters:
                log(f"已达本轮章节上限（已推进至第{args.max_chapters}章），停止等待下批")
                break
            v = confirm("accept")
        except Exception as exc:  # noqa: BLE001
            err(f"confirm@{stage}", exc, traceback.format_exc())
            break

    if v.get("done"):
        log("===== 全书完成 =====")
    else:
        log(f"===== 本轮暂停于 stage={v.get('stage')} =====")


if __name__ == "__main__":
    main()
