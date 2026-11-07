import pytest

from app import features
from app.handmodel import landmarks


@pytest.mark.parametrize("pattern", ["11111", "00000", "01000", "01100", "10000", "01111", "10001", "00001"])
def test_finger_patterns(pattern):
    f = features.extract(landmarks(pattern))
    assert f.fingers_str == pattern
    assert f.pinch is None


@pytest.mark.parametrize("orientation", ["up", "down", "left", "right"])
def test_orientation(orientation):
    f = features.extract(landmarks("01100", orientation=orientation))
    assert f.orientation == orientation
    assert f.fingers_str == "01100"


@pytest.mark.parametrize("finger", ["index", "middle", "ring", "pinky"])
def test_pinch(finger):
    f = features.extract(landmarks("11111", pinch=finger))
    assert f.pinch == finger


def test_pointer_knuckle_and_gap():
    lm = landmarks("01000")
    f = features.extract(lm)
    assert f.pointer == tuple(lm[8]) and f.knuckle == tuple(lm[5])
    assert f.pinch_gap > 0.8
    assert features.extract(landmarks("11111", pinch="index")).pinch_gap == pytest.approx(0)


def test_bbox_and_size():
    f = features.extract(landmarks("11111", scale=50, center=(100, 100)))
    assert f.hand_size == pytest.approx(50)
    assert f.bbox[0] < 100 < f.bbox[2]
