"""
noidle.activity
===============

Activity-aware policy helpers used by the noidle engine to decide whether a
scheduled tick should be skipped:

  1. Smart-pause: skip injection when the user has produced real input within
     the last few seconds (Windows' GetLastInputInfo already advanced).
  2. Screen-share detection: skip injection when Microsoft Teams is actively
     sharing the screen — the user is provably present, and a stray cursor
     twitch in the middle of a presentation is unprofessional.

This module is import-safe on non-Windows platforms. Detection functions
return False on any error so the engine degrades to "always tick" rather
than "never tick" — failing open keeps the core feature working.

No pywin32. Direct ctypes only, mirroring the style of `winapi.py`.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

from .winapi import get_idle_seconds

__all__ = [
    "should_skip_for_user_activity",
    "is_teams_screen_sharing",
]

log = logging.getLogger("noidle.activity")

_IS_WINDOWS = sys.platform.startswith("win")


# --------------------------------------------------------------------------- #
# Smart-pause
# --------------------------------------------------------------------------- #


def should_skip_for_user_activity(min_idle_seconds: float = 5.0) -> bool:
    """
    Return True if the user has produced real input within the last
    `min_idle_seconds` seconds — meaning we don't need to tick this cycle
    because Windows' idle counter (and therefore Teams/Slack presence) has
    already been reset by genuine activity.

    Threshold rationale (default ~5s, NOT close to the tick interval):
      Skipping a single tick is harmless. If the user goes idle the instant
      after we skip, the next scheduled tick is at most `interval_seconds`
      away — well under Teams' 5-minute Away threshold for any sane interval
      (we cap at 1s minimum and default to 45s). Using a tight 5s window means
      we only suppress redundant injections during obviously-active typing
      bursts and never risk missing the presence window.

    Returns False (i.e. "do not skip, tick normally") if `get_idle_seconds`
    raises — fail open so the engine keeps running through transient Win32
    weirdness (RDP reconnects, session-switch races, etc.).
    """
    try:
        idle = get_idle_seconds()
    except Exception:
        log.debug("get_idle_seconds raised; defaulting to no-skip", exc_info=True)
        return False
    return idle < float(min_idle_seconds)


# --------------------------------------------------------------------------- #
# Screen-share detection (Teams)
# --------------------------------------------------------------------------- #

# EnumWindowsProc signature: BOOL CALLBACK Proc(HWND hwnd, LPARAM lParam)
_EnumWindowsProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
) if _IS_WINDOWS else None


def _bind_screenshare_user32():
    """Bind user32 once at module level instead of every call.

    The previous implementation did `WinDLL("user32", use_last_error=True)`
    plus the four argtype assignments inside `is_teams_screen_sharing`
    every time. That added ~1-2ms per call AND allocated a fresh
    WINFUNCTYPE callback per call — held only on the local stack — which
    is technically GC-unsafe while EnumWindows is iterating (synchronous,
    so OK in practice but fragile).

    Returns None on non-Windows so the function still degrades cleanly.
    """
    if not _IS_WINDOWS:
        return None
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    u32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
    u32.EnumWindows.restype = wintypes.BOOL
    u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u32.GetWindowTextLengthW.restype = ctypes.c_int
    u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u32.GetWindowTextW.restype = ctypes.c_int
    u32.IsWindowVisible.argtypes = [wintypes.HWND]
    u32.IsWindowVisible.restype = wintypes.BOOL
    return u32


_user32 = _bind_screenshare_user32()


# Heuristic chosen: match against the visible "You're sharing your screen"
# floating callout that modern Teams (2024+ WebView2 client) renders as a
# top-level window. Title text is the most stable, version-independent
# signal — Teams localizes the string but the English-stem detection here
# covers en-US/en-GB/en-AU which is the audience we care about.
#
# Why not match on window class alone? "Chrome_WidgetWin_1" and
# "TeamsWebView" are shared by many Chromium/WebView2 surfaces (the main
# Teams window, Outlook's new client, even Slack via Electron). The class
# alone produces false positives. Title-based matching with the strings
# below is the most reliable cross-version indicator.
_TEAMS_SHARE_TITLE_HINTS = (
    "you're sharing",       # primary callout text, en-US
    "you are sharing",      # variant
    "sharing your screen",  # toolbar tooltip / accessible name
    "stop sharing",         # control bar that appears while sharing
)


def is_teams_screen_sharing() -> bool:
    """
    Return True iff a top-level window matching the Microsoft Teams
    screen-share UI is currently present on the current desktop.

    Detection strategy (most reliable first):
      Enumerate top-level windows via EnumWindows; for each, fetch the title
      with GetWindowTextW and case-insensitively match against known Teams
      screen-share strings. The "Stop sharing" / "You're sharing" floating
      controls only exist while a share is active, so a positive match is a
      strong signal.

    Returns False on non-Windows platforms or on any Win32 error.
    """
    if not _IS_WINDOWS or _user32 is None or _EnumWindowsProc is None:
        return False

    try:
        found = ctypes.c_bool(False)
        u32 = _user32  # local for closure speed; module-level cached binding

        def _cb(hwnd: int, _lparam: int) -> int:
            try:
                if not u32.IsWindowVisible(hwnd):
                    return True  # keep enumerating
                length = u32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                u32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                if not title:
                    return True
                for hint in _TEAMS_SHARE_TITLE_HINTS:
                    if hint in title:
                        found.value = True
                        return False  # stop enumeration
            except Exception:
                # Never let a per-window failure abort the whole sweep.
                return True
            return True

        proc = _EnumWindowsProc(_cb)
        # EnumWindows returns 0 if the callback returned 0 OR on error; both
        # are fine for us — we only trust the `found` flag. The `proc`
        # local stays alive across the synchronous EnumWindows call so the
        # GC can't collect the WINFUNCTYPE callback mid-iteration.
        u32.EnumWindows(proc, 0)
        return bool(found.value)
    except Exception:
        log.debug("is_teams_screen_sharing failed", exc_info=True)
        return False


# INTEGRATION:
# In src/noidle/engine.py, add at the top with the other relative imports:
#     from .activity import should_skip_for_user_activity, is_teams_screen_sharing
#
# Then in Engine._do_tick, as the very first thing inside the method
# (before the `with self._lock:` that reads `method`), add:
#     if should_skip_for_user_activity() or is_teams_screen_sharing():
#         with self._lock:
#             self._state.tick_count += 1
#         self._notify()
#         log.debug("tick skipped: user active or screen sharing")
#         return
#
# Rationale: skip *before* any SendInput call so we neither move the cursor
# during a presentation nor inject redundantly while the user is typing.
# We still bump tick_count + notify so the tray UI shows the loop is alive.
# The `_run` loop's _next_delay() schedule is unaffected — we just no-op
# this tick. No new state, no new locks, no behavior change when both
# checks return False (the v0.1 hot path).
