from __future__ import annotations

import os
import sys

try:
    import winreg  # type: ignore[import-not-found]
except ImportError:
    winreg = None  # type: ignore[assignment]

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Distinct registry value names per install mode so the MSI install and
# the portable .exe don't fight over a single `noidle` value. Without this,
# users who install the MSI and later run the portable .exe (or vice versa)
# silently overwrite each other's Run entry.
_VALUE_MSI = "noidle.app"
_VALUE_PORTABLE = "noidle.app-portable"
_VALUE_DEV = "noidle.app-dev"
_LEGACY_VALUE = "noidle"  # v0.3.0–v0.3.5 used this single name


def _install_mode() -> str:
    """Return 'msi', 'portable', or 'dev' based on where we're running from.

    MSI installs land in %LOCALAPPDATA%\\Programs\\noidle\\noidle.exe.
    Portable runs are anywhere else when frozen.
    Dev runs are not frozen at all.
    """
    if not getattr(sys, "frozen", False):
        return "dev"
    exe = os.path.normcase(os.path.abspath(sys.executable))
    msi_root = os.environ.get("LOCALAPPDATA", "")
    if msi_root:
        msi_prefix = os.path.normcase(os.path.join(msi_root, "Programs", "noidle"))
        if exe.startswith(msi_prefix):
            return "msi"
    return "portable"


def _value_name() -> str:
    return {
        "msi": _VALUE_MSI,
        "portable": _VALUE_PORTABLE,
        "dev": _VALUE_DEV,
    }[_install_mode()]


def install_mode() -> str:
    """Public accessor for the detected install mode (for diagnostics)."""
    return _install_mode()


def _require_windows() -> None:
    if winreg is None:
        raise RuntimeError("autostart only available on Windows")


def _quote(path: str) -> str:
    return f'"{path}"' if " " in path and not path.startswith('"') else path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _launcher_script() -> str:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(pkg_dir, "..", ".."))
    return os.path.join(repo_root, "noidle.py")


def current_target() -> str:
    if _frozen():
        return _quote(os.path.abspath(sys.executable))
    return f"{_quote(os.path.abspath(sys.executable))} {_quote(_launcher_script())}"


def is_enabled() -> bool:
    """True iff our Run-key entry points at the same executable as the
    current process.

    Compares only the executable portion (case-insensitively) rather than
    the full command line, so a future version that adds CLI args (e.g.
    `noidle.exe --start-minimized`) doesn't silently look "disabled" and
    get over-written by the next enable() call.
    """
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, _value_name())
    except FileNotFoundError:
        return False
    except OSError:
        return False
    stored = _first_token(str(data))
    expected = _first_token(current_target())
    return stored.casefold() == expected.casefold()


def _first_token(cmdline: str) -> str:
    """Extract the executable path from a Windows command line, handling
    the `"C:\\Program Files\\noidle\\noidle.exe" --flag` quoting case."""
    s = cmdline.strip()
    if s.startswith('"'):
        end = s.find('"', 1)
        return s[1:end] if end > 0 else s[1:]
    sp = s.find(" ")
    return s if sp < 0 else s[:sp]


def enable() -> None:
    """Write our Run-key value AND opportunistically clean up:
      - The v0.3.0–v0.3.5 legacy `noidle` value (so upgrades don't leave
        a stale entry that races with the new mode-specific value)
      - The other-mode value (if MSI is enabling, drop any portable
        leftover, and vice versa) — only one of "MSI launches at login"
        and "portable launches at login" can be true at a time anyway.
    """
    _require_windows()
    target = current_target()
    keep = _value_name()
    sweep = [v for v in (_VALUE_MSI, _VALUE_PORTABLE, _VALUE_DEV, _LEGACY_VALUE) if v != keep]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, keep, 0, winreg.REG_SZ, target)
        for stale in sweep:
            try:
                winreg.DeleteValue(key, stale)
            except FileNotFoundError:
                pass


def disable() -> None:
    """Remove BOTH the current mode's value AND any legacy `noidle` value
    so a fresh-from-v0.3.5 upgrade doesn't get re-launched on login.
    """
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for value in (_value_name(), _LEGACY_VALUE):
                try:
                    winreg.DeleteValue(key, value)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        return


# INTEGRATION:
# In src/noidle/tray.py, add `from .autostart import is_enabled, enable, disable, current_target`.
# Add a checkable MenuItem under the Method submenu separator:
#     MenuItem(
#         "Start with Windows",
#         self._toggle_autostart,
#         checked=lambda _i: _safe_is_enabled(),
#     ),
# And a debug item under "Show idle time":
#     MenuItem("Show autostart target", self._show_autostart_target),
# Callbacks on TrayApp:
#     def _toggle_autostart(self, _icon, _item):
#         try:
#             (disable if is_enabled() else enable)()
#         except RuntimeError as e:
#             self._icon.notify(str(e), "noidle")
#         self._refresh()
#     def _show_autostart_target(self, _icon, _item):
#         self._icon.notify(current_target(), "noidle")
# Wrap is_enabled() in a `_safe_is_enabled` helper that returns False on RuntimeError
# so the menu still renders during macOS dev runs.
