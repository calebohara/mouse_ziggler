from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from .activity import is_teams_screen_sharing, should_skip_for_user_activity
from .winapi import (
    allow_sleep,
    get_idle_seconds,
    prevent_sleep,
    send_f15,
    send_mouse_jitter,
)

from .stats import Stats

log = logging.getLogger("noidle.engine")

Method = Literal["mouse", "key", "both"]

_JITTER_RATIO = 0.20
_MIN_INTERVAL_S = 1.0


@dataclass
class EngineState:
    running: bool = False
    last_tick_at: Optional[float] = None
    last_idle_seconds: Optional[float] = None
    tick_count: int = 0


@dataclass
class Engine:
    interval_seconds: float = 45.0
    method: Method = "both"
    smart_pause: bool = True
    pause_on_screen_share: bool = True
    on_state_change: Optional[Callable[[EngineState], None]] = None
    stats: Optional[Stats] = None

    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _state: EngineState = field(default_factory=EngineState, init=False, repr=False)

    @property
    def state(self) -> EngineState:
        with self._lock:
            return EngineState(
                running=self._state.running,
                last_tick_at=self._state.last_tick_at,
                last_idle_seconds=self._state.last_idle_seconds,
                tick_count=self._state.tick_count,
            )

    def set_interval(self, seconds: float) -> None:
        if seconds < _MIN_INTERVAL_S:
            raise ValueError(f"interval must be >= {_MIN_INTERVAL_S}s")
        with self._lock:
            self.interval_seconds = float(seconds)

    def set_method(self, method: Method) -> None:
        if method not in ("mouse", "key", "both"):
            raise ValueError(f"invalid method: {method}")
        with self._lock:
            self.method = method

    def set_smart_pause(self, enabled: bool) -> None:
        with self._lock:
            self.smart_pause = bool(enabled)

    def set_pause_on_screen_share(self, enabled: bool) -> None:
        with self._lock:
            self.pause_on_screen_share = bool(enabled)

    def start(self) -> None:
        with self._lock:
            if self._state.running:
                return
            self._stop.clear()
            prevent_sleep()
            self._state.running = True
            self._thread = threading.Thread(
                target=self._run, name="noidle-engine", daemon=True
            )
            self._thread.start()
        self._notify()
        log.info("engine started method=%s interval=%.1fs", self.method, self.interval_seconds)

    def stop(self) -> None:
        with self._lock:
            if not self._state.running:
                return
            self._state.running = False
            self._stop.set()
            t = self._thread
            self._thread = None
        if t is not None:
            t.join(timeout=5.0)
        try:
            allow_sleep()
        finally:
            self._notify()
            log.info("engine stopped")

    def _next_delay(self) -> float:
        with self._lock:
            base = self.interval_seconds
        spread = base * _JITTER_RATIO
        delay = base + random.uniform(-spread, spread)
        return max(_MIN_INTERVAL_S, delay)

    def _do_tick(self) -> None:
        with self._lock:
            method = self.method
            smart = self.smart_pause
            pause_share = self.pause_on_screen_share
            interval = self.interval_seconds

        # Smart-pause threshold scales with the interval so a tight 15s
        # interval doesn't have its entire window swallowed by the
        # default 5s smart-pause. min(5s, interval × 0.3) means at 15s
        # we use 4.5s, at 10s we use 3s, at 60s+ we use the full 5s.
        smart_pause_threshold = min(5.0, max(1.0, interval * 0.3))

        if smart and should_skip_for_user_activity(smart_pause_threshold):
            with self._lock:
                self._state.tick_count += 1
            if self.stats is not None:
                self.stats.record_skip("active")
            log.debug("tick skipped: user is active (threshold %.1fs)", smart_pause_threshold)
            self._notify()
            return

        if pause_share and is_teams_screen_sharing():
            with self._lock:
                self._state.tick_count += 1
            if self.stats is not None:
                self.stats.record_skip("screenshare")
            log.debug("tick skipped: Teams is screen sharing")
            self._notify()
            return

        if method in ("mouse", "both"):
            send_mouse_jitter()

        if method in ("key", "both"):
            send_f15()

        idle = None
        try:
            idle = float(get_idle_seconds())
        except Exception:
            log.exception("get_idle_seconds failed")

        with self._lock:
            self._state.last_tick_at = time.time()
            self._state.last_idle_seconds = idle
            self._state.tick_count += 1

        if self.stats is not None:
            self.stats.record_tick(idle)

        if idle is not None and idle > 2.0:
            log.warning("post-tick idle=%.2fs (expected ~0)", idle)
        else:
            log.debug("tick ok idle=%s", idle)

        self._notify()

    def _run(self) -> None:
        try:
            self._do_tick()
            while not self._stop.is_set():
                if self._stop.wait(self._next_delay()):
                    break
                self._do_tick()
        except Exception:
            log.exception("engine loop crashed")
        finally:
            with self._lock:
                self._state.running = False
            try:
                allow_sleep()
            except Exception:
                log.exception("allow_sleep failed during cleanup")

    def _notify(self) -> None:
        cb = self.on_state_change
        if cb is None:
            return
        try:
            cb(self.state)
        except Exception:
            log.exception("on_state_change callback failed")
