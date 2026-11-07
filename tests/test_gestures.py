import pytest

from app import features
from app.gestures import Gesture, PRESET_GESTURES
from app.handmodel import landmarks


def feat(pattern, pinch=None, orientation="up"):
    return features.extract(landmarks(pattern, pinch=pinch, orientation=orientation))


def test_exact_match_and_wildcards():
    assert Gesture("01000").matches(feat("01000"))
    assert not Gesture("01000").matches(feat("01100"))
    assert Gesture("*1***").matches(feat("01100"))
    assert Gesture("*****").matches(feat("00000"))


def test_pinch_required_or_forbidden():
    assert Gesture("*****", "index").matches(feat("11111", pinch="index"))
    assert not Gesture("*****", "index").matches(feat("11111"))
    assert not Gesture("11111").matches(feat("11111", pinch="index"))
    assert not Gesture("*****", "index").matches(feat("11111", pinch="middle"))


def test_orientation():
    assert Gesture("01100", None, "down").matches(feat("01100", orientation="down"))
    assert not Gesture("01100", None, "down").matches(feat("01100", orientation="up"))
    assert Gesture("01100").matches(feat("01100", orientation="down"))


def test_specificity_order():
    pinch = Gesture("*****", "index")
    exact = Gesture("01100")
    exact_oriented = Gesture("01100", None, "down")
    wild = Gesture("*1***")
    assert pinch.specificity() > exact_oriented.specificity() > exact.specificity() > wild.specificity()


def test_describe():
    assert Gesture("11111").describe() == "Open hand"
    assert Gesture("00000").describe() == "Fist"
    assert Gesture("01000").describe() == "Index only"
    assert Gesture("01100", None, "down").describe() == "Index + middle, pointing down"
    assert Gesture("*****", "middle").describe() == "Pinch thumb + middle"


def test_round_trip_and_validation():
    g = Gesture("01100", "ring", "left")
    assert Gesture.from_dict(g.to_dict()) == g
    with pytest.raises(ValueError):
        Gesture("0110")
    with pytest.raises(ValueError):
        Gesture("01100", "thumb")


def test_presets_are_unique_and_valid():
    gestures = [g for _, g in PRESET_GESTURES]
    assert len(set(gestures)) == len(gestures)
