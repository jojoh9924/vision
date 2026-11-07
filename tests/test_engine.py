from app import features
from app.actions import Backend
from app.defaults import BUNDLED
from app.engine import Engine
from app.gestures import Gesture
from app.handmodel import landmarks
from app.profiles import Mapping, Profile


class FakeBackend(Backend):
    def __init__(self):
        self.events = []
        self.pos = None

    def screen_size(self):
        return (1920, 1080)

    def move_to(self, x, y):
        self.pos = (x, y)

    def mouse_down(self):
        self.events.append("down")

    def mouse_up(self):
        self.events.append("up")

    def click(self, button="left"):
        self.events.append(f"click:{button}")

    def double_click(self):
        self.events.append("dblclick")

    def scroll(self, amount):
        self.events.append(f"scroll:{amount}")

    def dictate(self):
        self.events.append("dictate")


def feat(pattern, pinch=None, orientation="up", center=(320, 240)):
    return features.extract(landmarks(pattern, pinch=pinch, orientation=orientation, center=center))


def make_engine(profile=None):
    b = FakeBackend()
    e = Engine(b, frame_size=(640, 480), margin=100, smooth=1)
    e.set_profile(profile or next(p for p in BUNDLED() if p.id == "default"))
    return e, b


def snap(e, pose, t):
    """Open the hand, then close into `pose`, so the pinch counts as a snap."""
    e.update(feat("01000"), t)
    e.update(pose, t + 0.05)
    return t + 0.05


def test_held_pinch_without_a_snap_does_not_click():
    e, b = make_engine()
    pinched = feat("11111", pinch="index")
    e.update(pinched, 0.0)
    e.update(pinched, 0.2)
    e.update(pinched, 0.5)
    assert b.events == []


def test_oneshot_fires_once_after_hold():
    e, b = make_engine()
    f = feat("11111", pinch="middle")  # right click, hold 120 ms
    t = snap(e, f, 0.0)
    assert b.events == [] and e.candidate is not None and e.active is None
    e.update(f, t + 0.05)
    assert b.events == []
    e.update(f, t + 0.13)
    assert b.events == ["click:right"]
    e.update(f, t + 0.5)
    e.update(f, t + 1.0)
    assert b.events == ["click:right"]
    # release and re-pinch fires again
    t = snap(e, f, t + 1.1)
    e.update(f, t + 0.13)
    assert b.events == ["click:right", "click:right"]


def test_button_down_up_and_release_on_hand_loss():
    e, b = make_engine()
    f = feat("11111", pinch="index")  # left_button, hold 0
    t = snap(e, f, 0.0)
    assert b.events == ["down"]
    e.update(f, t + 0.1)
    assert b.events == ["down"]
    e.update(None, t + 0.2)
    assert b.events == ["down"]          # within LOST_TIMEOUT
    e.update(None, t + 0.6)
    assert b.events == ["down", "up"]


def test_button_released_on_gesture_change():
    e, b = make_engine()
    t = snap(e, feat("11111", pinch="index"), 0.0)
    e.update(feat("01000"), t + 0.1)
    assert b.events == ["down", "up"]


def test_move_tracks_pointer_and_mirrors_x():
    e, b = make_engine()
    e.update(feat("01000", center=(150, 240)), 0.0)
    left = b.pos
    e.update(feat("01000", center=(500, 240)), 0.1)
    right = b.pos
    assert left[0] > right[0]  # hand on the camera's left = user's right
    assert 0 <= left[0] < 1920 and 0 <= left[1] < 1080


def test_scroll_runs_every_frame_and_respects_orientation():
    e, b = make_engine()
    f = feat("01100", orientation="down")
    e.update(f, 0.0)
    e.update(f, 0.2)
    e.update(f, 0.3)
    assert b.events == ["scroll:-60", "scroll:-60"]
    e.update(feat("01100", orientation="up"), 0.4)
    e.update(feat("01100", orientation="up"), 0.6)
    assert b.events[-1] == "scroll:60"


def test_pause_releases_and_blocks():
    e, b = make_engine()
    snap(e, feat("11111", pinch="index"), 0.0)
    e.set_paused(True)
    assert b.events == ["down", "up"]
    e.update(feat("11111", pinch="index"), 0.5)
    assert b.events == ["down", "up"]


def test_most_specific_mapping_wins():
    p = Profile("t", "t", [
        Mapping("scroll_up", Gesture("*****"), 0),
        Mapping("left_click", Gesture("01000"), 0),
    ])
    e, b = make_engine(p)
    e.update(feat("01000"), 0.0)
    assert b.events == ["click:left"]


def test_pinch_start_freezes_cursor_and_drag_needs_real_motion():
    import dataclasses
    e, b = make_engine()
    positions = []
    for i, t in enumerate([0.0, 0.1, 0.2, 0.3]):
        e.update(feat("01000", center=(200 + i * 40, 240)), t)
        positions.append(b.pos)
    # thumb and index closing fast: the cursor is put back where it was ~120 ms ago and frozen
    closing = dataclasses.replace(feat("01000", center=(400, 240)), pinch_gap=0.4)
    e.update(closing, 0.33)
    before = b.pos
    assert before == positions[1]          # rewound ~150 ms, to the t=0.1 position, not the latest
    # pinch lands: button down at the frozen position, small wobble ignored
    e.update(feat("11111", pinch="index", center=(400, 240)), 0.36)
    e.update(feat("11111", pinch="index", center=(404, 242)), 0.4)
    assert b.events == ["down"] and b.pos == before
    # moving the whole hand drags
    e.update(feat("11111", pinch="index", center=(520, 240)), 0.5)
    assert b.pos != before
    e.update(feat("01000", center=(520, 240)), 0.6)
    assert b.events == ["down", "up"]


def test_small_motion_after_long_hold_is_not_locked():
    e, b = make_engine()
    for i in range(31):
        e.update(feat("01000", center=(300, 240)), i / 30)
    before = b.pos
    e.update(feat("01000", center=(300.25, 240)), 1.04)
    assert b.pos[0] < before[0]  # responds on the very next frame
    assert abs(b.pos[0] - before[0]) < 2


def test_toggle_gesture_fires_even_while_paused_and_only_that():
    e, b = make_engine()
    e.set_paused(True)
    # a normal gesture does nothing while paused
    e.update(feat("11111", pinch="index"), 0.0)
    e.update(feat("11111", pinch="index"), 0.5)
    assert b.events == [] and not e.toggle_requested
    # the toggle gesture (thumb + pinky, 1.5 s) still works
    e.update(feat("10001"), 1.0)
    e.update(feat("10001"), 2.0)
    assert not e.toggle_requested
    e.update(feat("10001"), 2.6)
    assert e.toggle_requested
    e.toggle_requested = False
    e.update(feat("10001"), 5.0)      # latched: no repeat while held
    assert not e.toggle_requested


def test_suspended_engine_does_nothing_and_releases_buttons():
    e, b = make_engine()
    snap(e, feat("11111", pinch="index"), 0.0)
    e.set_suspended(True)
    assert b.events == ["down", "up"]
    e.update(feat("11111", pinch="index"), 0.5)
    e.update(feat("10001"), 1.0)
    e.update(feat("10001"), 3.0)
    assert b.events == ["down", "up"] and not e.toggle_requested
    e.set_suspended(False)
    snap(e, feat("11111", pinch="index"), 3.2)
    assert b.events == ["down", "up", "down"]


def test_classifier_adjusts_filter_without_replacing_gesture_logic():
    class MovingClassifier:
        def reset(self):
            pass

        def update(self, now, x, y):
            assert 0 <= x <= 1 and 0 <= y <= 1
            return 'MOVING', 0.95

    e, b = make_engine()
    e.adaptive.enabled = True   # adaptive One Euro is opt-in (toggle 'a' in the camera window)
    e.cursor_state = MovingClassifier()
    e.update(feat('01000', center=(200, 240)), 0.0)
    e.update(feat('01000', center=(250, 240)), 0.1)
    assert e.cursor_label == 'MOVING'
    assert e.filter_x.min_cutoff > 1.0
    assert e.filter_x.min_cutoff == e.filter_y.min_cutoff
    assert b.pos is not None
    e.adaptive.enabled = False
    e.update(feat('01000', center=(300, 240)), 0.2)
    assert e.filter_x.min_cutoff == 1.0 and e.filter_x.beta == 0.005
    e.update(None, 0.3)
    assert e.cursor_label == 'NO HAND'


def test_curling_finger_does_not_move_cursor_but_hand_motion_does():
    import dataclasses
    e, b = make_engine()
    f0 = feat("01000", center=(300, 240))
    for i in range(6):
        e.update(f0, i * 0.033)
    settled = b.pos
    # fingertip drops 60 px toward the palm in one frame (a curl); knuckle unchanged
    curled = dataclasses.replace(f0, pointer=(f0.pointer[0], f0.pointer[1] + 60))
    for i in range(6, 12):
        e.update(curled, i * 0.033)       # stays curled for 200 ms, pinch not landed yet
    assert abs(b.pos[1] - settled[1]) < 3
    # the whole hand moving (knuckle and tip together) still points
    e.update(feat("01000", center=(300, 330)), 12 * 0.033)
    e.update(feat("01000", center=(300, 330)), 13 * 0.033)
    assert b.pos[1] - settled[1] > 30
