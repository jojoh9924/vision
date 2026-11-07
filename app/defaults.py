"""Bundled profiles, written to profiles/ on first run."""

from .gestures import Gesture
from .profiles import Mapping, Profile


def _m(action, fingers="*****", pinch=None, orientation="any", hold_ms=120):
    return Mapping(action, Gesture(fingers, pinch, orientation), hold_ms)


def BUNDLED() -> list[Profile]:
    return [
        # Thumb is a wildcard for pointing and scrolling: people hold it out or
        # tucked without noticing, and it must not stop the cursor.
        Profile("default", "Default (pinch)", [
            _m("move", "*1000", hold_ms=0),
            _m("left_button", pinch="index", hold_ms=0),
            _m("right_click", pinch="middle"),
            _m("double_click", pinch="ring"),
            _m("scroll_up", "*1100", orientation="up"),
            _m("scroll_down", "*1100", orientation="down"),
            _m("speech_to_text", "11111", hold_ms=1000),
            _m("toggle_gestures", "10001", hold_ms=1500),
        ], bundled=True),

        Profile("low-dexterity", "Low dexterity", [
            _m("move", "01000", hold_ms=0),
            _m("left_click", "11000", hold_ms=300),
            _m("right_click", "10000", hold_ms=300),
            _m("drag", "01100"),
            _m("scroll_down", "00000"),
            _m("scroll_up", "11111"),
            _m("double_click", "00001", hold_ms=300),
            _m("speech_to_text", "10001", hold_ms=800),
            _m("toggle_gestures", "01111", hold_ms=1500),
        ], bundled=True),

        Profile("legacy", "Legacy (original Archand)", [
            _m("move", "*10**", hold_ms=0),
            _m("left_click", "01100"),
            _m("double_click", "01001"),
            _m("right_click", "10000"),
            _m("drag", "01111"),
            _m("scroll_down", "00000"),
            _m("scroll_up", "11111"),
            _m("speech_to_text", "00100", hold_ms=500),
            _m("toggle_gestures", "10001", hold_ms=1500),
        ], bundled=True),
    ]
