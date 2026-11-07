"""Time-aware adaptive smoothing for a single coordinate. Uses One-Euro Filtering for low-pass smoothing."""

import math


class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.005, derivative_cutoff=1.0):
        # Cutoffs are in Hz; beta is tuned for coordinates in screen pixels.
        if min_cutoff <= 0 or derivative_cutoff <= 0 or beta < 0:
            raise ValueError("Cutoffs must be positive and beta nonnegative")
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.derivative_cutoff = derivative_cutoff
        self._time = None
        self._raw = None
        self._value = None
        self._derivative = 0.0

    @staticmethod
    def _alpha(cutoff, dt):
        return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * cutoff * dt))

    def reset(self, value, timestamp):
        """Jump to `value` at rest, so smoothing continues from there without a stale velocity."""
        self._time = timestamp
        self._raw = self._value = value
        self._derivative = 0.0

    def update(self, value, timestamp):
        if self._time is None:
            self._time = timestamp
            self._raw = self._value = value
            return value

        dt = timestamp - self._time
        if dt <= 0:
            return self._value

        velocity = (value - self._raw) / dt
        derivative_alpha = self._alpha(self.derivative_cutoff, dt)
        self._derivative += derivative_alpha * (velocity - self._derivative)
        cutoff = self.min_cutoff + self.beta * abs(self._derivative)
        alpha = self._alpha(cutoff, dt)
        self._value += alpha * (value - self._value)
        self._raw = value
        self._time = timestamp
        return self._value
