"""Blend classifier-selected One Euro parameters without resetting position history."""
import math

BASELINE = (1.0, 0.005)
PROFILES = {
    'STATIONARY': (0.7, 0.003),
    'PRECISION': (0.9, 0.004),
    'MOVING': (1.3, 0.008),
}


class AdaptiveSmoothing:
    def __init__(self, *filters, enabled=True):
        self.filters = filters
        self.enabled = enabled
        self.last_time = None

    def update(self, state, timestamp):
        dt = 0.0 if self.last_time is None else max(0.0, timestamp - self.last_time)
        self.last_time = timestamp
        target = PROFILES.get(state, BASELINE) if self.enabled else BASELINE
        alpha = -math.expm1(-min(dt, 0.1) / 0.15)
        for filter_ in self.filters:
            if not self.enabled:
                filter_.min_cutoff, filter_.beta = BASELINE
            else:
                filter_.min_cutoff += alpha * (target[0] - filter_.min_cutoff)
                filter_.beta += alpha * (target[1] - filter_.beta)
