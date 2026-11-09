"""Shared illustrative example data. Not propagation or production Earth models."""
from .constants import EARTH_RADIUS_M, EARTH_SPIN_RAD_S
from .trajectories import (
    DEMO_SAMPLE_COUNT, DEMO_STEP_S, demo_ground_track, sample_ecef_trajectories,
    stationary_ground, synthetic_orbit,
)

__all__ = [
    "EARTH_RADIUS_M", "EARTH_SPIN_RAD_S", "DEMO_SAMPLE_COUNT", "DEMO_STEP_S",
    "demo_ground_track", "sample_ecef_trajectories", "stationary_ground", "synthetic_orbit",
]
