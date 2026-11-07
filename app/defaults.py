"""Default gesture set, written to profiles/default.json on first run and on reset."""

from .gestures import Gesture
from .profiles import Mapping, Profile


def _m(action, fingers="*****", pinch=None, orientation="any", hold_ms=120):
    return Mapping(action, Gesture(fingers, pinch, orientation), hold_ms)


def default_profile() -> Profile:
    # Thumb is a wildcard for pointing and scrolling: people hold it out or
    # tucked without noticing, and it must not stop the cursor.
    return Profile("default", "Default", [
        _m("move", "*1000", hold_ms=0),
        _m("left_button", pinch="index", hold_ms=0),
        _m("right_click", pinch="middle"),
        _m("double_click", pinch="ring"),
        _m("scroll_up", "*1100", orientation="up"),
        _m("scroll_down", "*1100", orientation="down"),
        _m("speech_to_text", "11111", hold_ms=1000),
        _m("toggle_gestures", "10001", hold_ms=1500),
    ], bundled=True)


def BUNDLED() -> list[Profile]:
    return [default_profile()]
