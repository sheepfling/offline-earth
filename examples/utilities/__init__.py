"""Shared illustrative example data. Not propagation or production Earth models."""
from .constants import DEMO_EARTH_RADIUS_M, DEMO_EARTH_SPIN_RAD_S
from .trajectories import (
    DEMO_SAMPLE_COUNT, DEMO_STEP_S, demo_ground_track, sample_ecef_trajectories,
    stationary_ground, synthetic_orbit,
)

__all__ = [
    "DEMO_EARTH_RADIUS_M", "DEMO_EARTH_SPIN_RAD_S", "DEMO_SAMPLE_COUNT", "DEMO_STEP_S",
    "demo_ground_track", "sample_ecef_trajectories", "stationary_ground", "synthetic_orbit",
]
