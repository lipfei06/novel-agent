"""M1 · F18 多项目隔离测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from novel_agent.storage import ProjectError, ProjectManager


def _pm() -> ProjectManager:
    return ProjectManager(Path(tempfile.mkdtemp()))


def test_create_and_exists():
    pm = _pm()
    paths = pm.create("novel1", "webnovel", "测试小说")
    assert pm.exists("novel1")
    assert paths.project_dir.exists()
    assert paths.data_dir.exists()
    assert paths.checkpoint_dir.exists()
    assert paths.meta_path.exists()


def test_create_auto_id():
    pm = _pm()
    paths = pm.create(None, "short_story", "短篇")
    assert paths.project_id.startswith("p")


def test_create_duplicate_raises():
    pm = _pm()
    pm.create("novel1", "webnovel", "a")
    try:
        pm.create("novel1", "webnovel", "b")
    except ProjectError:
        return
    raise AssertionError("expected ProjectError")


def test_get_meta_and_missing():
    pm = _pm()
    pm.create("novel1", "webnovel", "测试")
    meta = pm.get_meta("novel1")
    assert meta.title == "测试"
    assert meta.current_stage == "stage0"
    try:
        pm.get("nope")
    except ProjectError:
        return
    raise AssertionError("expected ProjectError")


def test_list():
    pm = _pm()
    pm.create("a", "webnovel", "A")
    pm.create("b", "short_story", "B")
    ids = {m.project_id for m in pm.list()}
    assert ids == {"a", "b"}


def test_update_stage():
    pm = _pm()
    pm.create("novel1", "webnovel", "a")
    pm.update_stage("novel1", "stage3")
    assert pm.get_meta("novel1").current_stage == "stage3"


def test_delete():
    pm = _pm()
    pm.create("novel1", "webnovel", "a")
    pm.delete("novel1")
    assert not pm.exists("novel1")
    try:
        pm.delete("novel1")
    except ProjectError:
        return
    raise AssertionError("expected ProjectError")


def test_isolation_dirs():
    """两个项目的产物/数据目录互不重叠。"""
    pm = _pm()
    a = pm.create("novelA", "webnovel", "A")
    b = pm.create("novelB", "webnovel", "B")
    assert a.project_dir != b.project_dir
    assert a.data_dir != b.data_dir
    assert not str(a.project_dir).endswith("novelB")


def test_chapter_path():
    pm = _pm()
    p = pm.create("novel1", "webnovel", "a")
    assert p.chapter(1, 5) == p.project_dir / "1" / "5.json"
    assert p.checkpoint_db().suffix == ".sqlite"
