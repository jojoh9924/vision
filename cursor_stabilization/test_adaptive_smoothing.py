import unittest
from .adaptive_smoothing import AdaptiveSmoothing, BASELINE, PROFILES
from .one_euro_filter import OneEuroFilter


class AdaptiveTests(unittest.TestCase):
    def test_blending_fallback_and_history(self):
        x, y = OneEuroFilter(), OneEuroFilter()
        x.update(123, 0)
        policy = AdaptiveSmoothing(x, y)
        policy.update('MOVING', 0)
        policy.update('MOVING', 0.02)
        self.assertTrue(BASELINE[0] < x.min_cutoff < PROFILES['MOVING'][0])
        self.assertEqual(x.min_cutoff, y.min_cutoff)
        self.assertEqual(x._value, 123)
        for i in range(1, 100):
            policy.update('UNCERTAIN', .02 + i / 60)
        self.assertAlmostEqual(x.min_cutoff, BASELINE[0], places=4)
        policy.enabled = False
        policy.update('MOVING', 2)
        self.assertEqual((x.min_cutoff, x.beta), BASELINE)

    def test_profiles_stay_bounded(self):
        for state, target in PROFILES.items():
            f = OneEuroFilter()
            policy = AdaptiveSmoothing(f)
            for i in range(120):
                policy.update(state, i / 60)
            self.assertAlmostEqual(f.min_cutoff, target[0], places=4)
            self.assertAlmostEqual(f.beta, target[1], places=5)


if __name__ == '__main__':
    unittest.main()
