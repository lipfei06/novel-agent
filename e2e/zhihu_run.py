"""知乎体 1 万字短篇：通过智能体对话创作，一次跑完全书。

用法: python e2e/zhihu_run.py
流程（每章）:
  1. 与「章节助手」对话一轮，确定本章目标/冲突/钩子（助手输出三行结构化要点）
  2. 把要点经 confirm edit 合入 stage4b 任务书
  3. 接受任务书 → 正文预览 → 一致性审查 → 记忆更新
四章完成后自动进入 终审 → 导出 → 全书完成。错误写入 e2e/errors.md。
"""
from __future__ import annotations

import re
import time
import traceback
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api"
PID = "zhihu_style"
MAX_CH = 4
HERE = Path(__file__).resolve().parent
ERR = HERE / "errors.md"
LOG = HERE / "zhihu_run.log"

IDEA = (
    "知乎体第一人称职场爽文，约1万字，共4章。故事：'我'是启明科技的运营负责人，"
    "周四下午被HR约谈'优化'，赔偿金按最低标准算。收拾工位时'我'发现组长王胜修改了后台权限记录，"
    "把'我'做的年度增长方案署成了他的名字。'我'没有吵，平静签了字——因为手里有三年的用户增长"
    "原始数据和对赌协议复盘文档。竞对公司'跳板互联'当天就来挖'我'带团队。"
    "四章节奏：第一章【被优化】裁员当天的冷静与第一记反手（带走数据与团队人心）；"
    "第二章【首战】新东家产品对打老东家，前组长来挖墙脚被当场揭穿改记录的事；"
    "第三章【反击】老东家大客户因服务崩盘投奔'我'，老东家启动竞业诉讼，'我'甩出聊天记录证明泄密的是公司；"
    "第四章【终局】仲裁胜诉、组长被开除背锅、老东家股价下跌，'我'的团队完成融资，收尾金句点题。"
    "风格要求：知乎体，第一人称，短段落，每章结尾反转钩子，冷静克制带梗。"
)

# 每章与章节助手对话时给出的方向（写作者意图，一句话即可）
DIRECTIONS = {
    1: "第一章【被优化】：裁员当天得知方案被组长王胜冒名，冷静签字，反手带数据与团队人心入职对手公司。结尾钩子：前组长发来消息'行，咱们走着瞧'。",
    2: "第二章【首战】：新产品对打上线成功，前组长王胜来挖'我'团队被当场揭穿曾篡改权限记录。结尾钩子：老东家大客户主动联系'我'。",
    3: "第三章【反击】：大客户崩盘投奔，老东家打竞业官司，'我'甩出聊天记录证明泄密的是公司自己。结尾钩子：仲裁庭通知下周开庭，对方律师是行业最狠的张律。",
    4: "第四章【终局】：仲裁胜诉、王胜被开除背锅、老东家股价大跌，'我'团队完成融资。结尾金句收尾点题：真正裁不掉的，是长在自己身上的本事。",
}

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


def chat_once(context: str, message: str) -> str:
    """与助手对话一轮，返回回复。"""
    r = client.post(f"/projects/{PID}/chat", json={"context": context, "message": message})
    if r.status_code >= 400:
        raise RuntimeError(f"chat {context} HTTP {r.status_code}: {r.text[:200]}")
    return r.json().get("reply", "")


def parse_design(reply: str) -> dict:
    """从章节助手回复中解析 目标/冲突/钩子 三行（解析不到就退回空）。"""
    out = {"goal": "", "conflicts": "", "hook": ""}
    for key in out:
        m = re.search(rf"{key}[：:]\s*(.+)", reply)
        if m:
            out[key] = m.group(1).strip()
    return out


def main() -> None:
    log("===== 知乎体 1 万字创作开始 =====")
    try:
        r = client.post("/projects", json={"title": "裁员那天我笑了", "genre": "zhihu10k", "project_id": PID})
        r.raise_for_status()
        log("项目创建成功（zhihu10k，1万字/1卷4章）")
    except Exception as exc:  # noqa: BLE001
        if "已存在" not in str(exc):
            log(f"项目已存在或创建跳过：{exc}")

    try:
        r = client.post(f"/projects/{PID}/start", json={"idea": IDEA})
        r.raise_for_status()
        v = r.json()
        log(f"start -> stage={v.get('stage')}")
    except Exception as exc:  # noqa: BLE001
        err("start", exc, traceback.format_exc())
        return

    done_ch = 0
    while not v.get("done"):
        stage = v.get("stage")
        try:
            if stage == "stage4b" and v.get("current_chapter", 1) > MAX_CH:
                log("章节数已达 4，异常（应进入 stage8）")
                break
            if stage == "stage4b":
                ch_no = v.get("current_chapter", done_ch + 1)
                ctx = f"chapter_{v.get('current_volume', 1)}_{ch_no}"
                direction = DIRECTIONS.get(int(ch_no), "")
                log(f"第{ch_no}章：与章节助手对话定方向…")
                reply = chat_once(ctx, f"{direction}\n请按'目标：…/冲突：…/钩子：…'三行复述本章任务要点。")
                design = parse_design(reply)
                log(f"  助手要点: 目标={design['goal'][:40]} | 钩子={design['hook'][:40]}")
                # 把对话确定的方向合入任务书（edit 应用后自动进入 stage5）
                payload = v.get("payload") or {}
                payload["title"] = ["被优化", "首战", "反击", "终局"][int(ch_no) - 1]
                if design["goal"]:
                    payload["goal"] = design["goal"]
                if design["hook"]:
                    payload["hook"] = design["hook"]
                if design["conflicts"]:
                    payload["conflicts"] = [c for c in re.split(r"[;；]", design["conflicts"]) if c.strip()][:3]
                v = confirm("edit", payload)
            else:
                v = confirm("accept")
        except Exception as exc:  # noqa: BLE001
            err(f"confirm@{stage}", exc, traceback.format_exc())
            break
        if stage == "stage4b":
            done_ch = int(v.get("current_chapter", done_ch + 1)) - 1 if v.get("current_chapter") else done_ch + 1
            done_ch = max(done_ch, 1)

    if v.get("done"):
        log("===== 全书完成（含终审与导出）=====")
    else:
        log(f"===== 暂停于 stage={v.get('stage')} =====")


def confirm(action: str, data=None) -> dict:
    t0 = time.time()
    body = {"action": action, **({"data": data} if data is not None else {})}
    r = client.post(f"/projects/{PID}/confirm", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"confirm {action} HTTP {r.status_code}: {r.text[:300]}")
    v = r.json()
    log(f"confirm {action} -> stage={v.get('stage')} done={v.get('done')} 耗时 {time.time() - t0:.0f}s")
    return v


if __name__ == "__main__":
    main()
