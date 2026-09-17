"""内置迷你测试运行器（无 pytest 环境时使用）。

用法：python tests/run_tests.py
与 pytest 兼容：同一批 test_* 函数，装了 pytest 后直接 `pytest tests/` 效果一致。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    test_dir = pathlib.Path(__file__).resolve().parent
    passed = 0
    failed = 0
    failures: list[tuple[str, str, str]] = []

    for path in sorted(test_dir.glob("test_*.py")):
        if path.name == "run_tests.py":
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            fn = getattr(module, name)
            if not callable(fn):
                continue
            try:
                fn()
            except Exception:
                failed += 1
                failures.append((path.name, name, traceback.format_exc()))
            else:
                passed += 1

    print(f"\n==== {passed} passed, {failed} failed ====")
    for fname, tname, tb in failures:
        print(f"\n--- FAIL {fname}::{tname} ---")
        print(tb)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
