"""生成任务：后台线程执行长任务，事件经队列供 SSE 流式推送进度与结果。"""
from __future__ import annotations

import itertools
import queue
import threading
import uuid


_counters = itertools.count(1)


class Task:
    def __init__(self, task_id: str, kind: str, project_id: str) -> None:
        self.id = task_id
        self.kind = kind
        self.project_id = project_id
        self.status = "running"  # running | done | error
        self.error: str | None = None
        self.result = None
        self._events: queue.Queue = queue.Queue()

    def emit(self, etype: str, data: dict) -> None:
        self._events.put({"type": etype, "data": data})

    def drain(self) -> list[dict]:
        out: list[dict] = []
        try:
            while True:
                out.append(self._events.get_nowait())
        except queue.Empty:
            return out


class TaskManager:
    """按 task_id 管理后台生成任务；事件先入队后由 SSE 消费。"""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, project_id: str, job) -> Task:
        """启动后台任务。job(progress) 为同步函数，progress(message, pct=None) 上报进度。"""
        task_id = f"t{next(_counters)}{uuid.uuid4().hex[:6]}"
        task = Task(task_id, kind, project_id)

        def run():
            try:
                result = job(lambda msg, pct=None: task.emit("progress", {"message": msg, "pct": pct}))
                task.emit("done", {"result": result})  # 先发事件再置状态，避免 SSE 端提前退出丢事件
                task.status = "done"
            except Exception as exc:  # noqa: BLE001
                task.emit("error", {"message": str(exc)})
                task.status = "error"
                task.error = str(exc)

        th = threading.Thread(target=run, daemon=True, name=f"task-{task_id}")
        with self._lock:
            self._tasks[task_id] = task
            # 只保留最近 100 个任务，防无限增长
            if len(self._tasks) > 100:
                finished = [k for k, v in self._tasks.items() if v.status != "running"]
                for k in finished[: len(self._tasks) - 100]:
                    self._tasks.pop(k, None)
        th.start()
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)
