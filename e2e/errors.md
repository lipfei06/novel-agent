# E2E 错误记录

> 由 e2e/run.py 自动追加。空文件 = 无错误。

## 2026-09-21 15:31:59 — confirm@stage5

```
confirm accept HTTP 500: {"detail":"环节执行失败：check 预算超限: 估算 12259 > 上限 12000"}
Traceback (most recent call last):
  File "D:\project\demo1\novel-agent\e2e\run.py", line 120, in main
    v = confirm("accept")
  File "D:\project\demo1\novel-agent\e2e\run.py", line 63, in confirm
    raise RuntimeError(f"confirm {action} HTTP {r.status_code}: {r.text[:300]}")
RuntimeError: confirm accept HTTP 500: {"detail":"环节执行失败：check 预算超限: 估算 12259 > 上限 12000"}

```
