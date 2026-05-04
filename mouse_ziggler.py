"""PyInstaller-friendly entry point.

Uses absolute imports (PyInstaller runs the entry script as a top-level
module with no parent package, which breaks `from .tray import ...`).
Adds src/ to sys.path so dev runs (`python mouse_ziggler.py`) work too.

Wraps startup in a top-level exception handler that writes any crash to
%LOCALAPPDATA%\\MouseZiggler\\crash.log so users get a debuggable
artifact instead of a raw "Failed to execute script" Windows dialog.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

_HERE = Path(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
_SRC = _HERE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _crash_log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    d = base / "MouseZiggler"
    d.mkdir(parents=True, exist_ok=True)
    return d / "crash.log"


def _write_crash(exc: BaseException) -> Path:
    p = _crash_log_path()
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.now().isoformat()} =====\n")
        f.write(f"argv: {sys.argv!r}\n")
        f.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
        f.write(f"executable: {sys.executable}\n")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
    return p


def _smoke() -> int:
    """Import + instantiate everything the live app touches, then exit 0.

    Run by CI after PyInstaller builds. Catches:
      - Relative-import regressions (the v0.1.0 bug)
      - Constructor signature drift between modules
      - Missing-symbol regressions (e.g. winapi exports a function the
        jiggler imports)
      - Method-signature mismatches at call sites used in startup code
    Does NOT call into ctypes (Win32) or pystray.run() — those can't be
    safely exercised in headless CI.
    """
    import zig.jiggler
    import zig.tray
    import zig.winapi

    j = zig.jiggler.Jiggler(interval_seconds=10.0, method="both")
    assert j.state.running is False
    j.set_interval(20.0)
    j.set_method("mouse")
    assert j.method == "mouse"

    for name in ("prevent_sleep", "allow_sleep", "send_mouse_jitter",
                 "send_f15", "get_idle_seconds"):
        if not hasattr(zig.winapi, name):
            print(f"smoke FAIL: zig.winapi missing {name}", flush=True)
            return 2

    import inspect
    sig = inspect.signature(zig.winapi.send_mouse_jitter)
    if len(sig.parameters) != 0:
        print(f"smoke FAIL: send_mouse_jitter has params {sig}", flush=True)
        return 3

    print("smoke ok", flush=True)
    return 0


def main() -> int:
    if "--smoke" in sys.argv:
        return _smoke()
    if "--version" in sys.argv:
        print("mouse_ziggler 0.1.2", flush=True)
        return 0
    from zig.tray import run_tray
    run_tray()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        path = _write_crash(exc)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"MouseZiggler crashed.\n\nDetails written to:\n{path}\n\n{exc!r}",
                "MouseZiggler — crash",
                0x10,
            )
        except Exception:
            pass
        raise SystemExit(1)
