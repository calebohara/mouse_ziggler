"""Tests for zig.hotkey.parse_hotkey — pure Python, no Win32."""
import pytest

from zig.hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, parse_hotkey


class TestParseHotkey:
    def test_ctrl_alt_letter(self):
        mods, vk = parse_hotkey("ctrl+alt+z")
        assert mods == MOD_CONTROL | MOD_ALT
        assert vk == 0x5A  # VK_Z

    def test_single_letter_no_modifier(self):
        mods, vk = parse_hotkey("a")
        assert mods == 0
        assert vk == 0x41  # VK_A

    def test_function_key_f13(self):
        mods, vk = parse_hotkey("f13")
        assert mods == 0
        assert vk == 0x7C  # VK_F13

    def test_function_key_f1(self):
        _, vk = parse_hotkey("f1")
        assert vk == 0x70  # VK_F1

    def test_function_key_f24(self):
        _, vk = parse_hotkey("f24")
        assert vk == 0x87  # VK_F24

    def test_shift_modifier(self):
        mods, _ = parse_hotkey("shift+a")
        assert mods & MOD_SHIFT

    def test_win_modifier(self):
        mods, _ = parse_hotkey("win+a")
        assert mods & MOD_WIN

    def test_all_modifiers(self):
        mods, _ = parse_hotkey("ctrl+alt+shift+f1")
        assert mods == MOD_CONTROL | MOD_ALT | MOD_SHIFT

    def test_case_insensitive(self):
        mods1, vk1 = parse_hotkey("CTRL+ALT+Z")
        mods2, vk2 = parse_hotkey("ctrl+alt+z")
        assert mods1 == mods2 and vk1 == vk2

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_hotkey("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_hotkey("   ")

    def test_unknown_modifier_raises(self):
        with pytest.raises(ValueError, match="unknown modifier"):
            parse_hotkey("hyper+z")

    def test_invalid_key_raises(self):
        with pytest.raises(ValueError, match="key must be"):
            parse_hotkey("ctrl+1")

    def test_f25_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_hotkey("f25")

    def test_f0_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_hotkey("f0")
