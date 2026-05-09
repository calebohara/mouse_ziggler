"""Tests for zig.jiggler public API — no Win32 calls needed for these checks."""
import pytest

from zig.jiggler import Jiggler, JigglerState


class TestJigglerState:
    def test_defaults(self):
        s = JigglerState()
        assert s.running is False
        assert s.last_jiggle_at is None
        assert s.last_idle_seconds is None
        assert s.tick_count == 0


class TestJigglerInit:
    def test_default_interval(self):
        j = Jiggler()
        assert j.interval_seconds == 45.0

    def test_custom_interval(self):
        j = Jiggler(interval_seconds=30.0)
        assert j.interval_seconds == 30.0

    def test_not_running_on_init(self):
        j = Jiggler()
        assert j.state.running is False

    def test_state_returns_copy(self):
        j = Jiggler()
        s1 = j.state
        s2 = j.state
        assert s1 is not s2


class TestSetInterval:
    def test_valid_interval(self):
        j = Jiggler()
        j.set_interval(60.0)
        assert j.interval_seconds == 60.0

    def test_minimum_allowed(self):
        j = Jiggler()
        j.set_interval(1.0)
        assert j.interval_seconds == 1.0

    def test_below_minimum_raises(self):
        j = Jiggler()
        with pytest.raises(ValueError, match=">="):
            j.set_interval(0.5)

    def test_zero_raises(self):
        j = Jiggler()
        with pytest.raises(ValueError):
            j.set_interval(0.0)


class TestSetMethod:
    def test_mouse(self):
        j = Jiggler()
        j.set_method("mouse")
        assert j.method == "mouse"

    def test_key(self):
        j = Jiggler()
        j.set_method("key")
        assert j.method == "key"

    def test_both(self):
        j = Jiggler()
        j.set_method("both")
        assert j.method == "both"

    def test_invalid_raises(self):
        j = Jiggler()
        with pytest.raises(ValueError, match="invalid method"):
            j.set_method("telekinesis")


class TestSmartPause:
    def test_set_false(self):
        j = Jiggler()
        j.set_smart_pause(False)
        assert j.smart_pause is False

    def test_set_true(self):
        j = Jiggler(smart_pause=False)
        j.set_smart_pause(True)
        assert j.smart_pause is True


class TestPauseOnScreenShare:
    def test_set_false(self):
        j = Jiggler()
        j.set_pause_on_screen_share(False)
        assert j.pause_on_screen_share is False
