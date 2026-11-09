"""Shared illustrative example data. Not propagation or production Earth models."""
from math import cos, pi, radians, sin
from offline_earth.geometry import LonLatDegrees
from offline_earth.trajectory import EcefTrajectory, geodetic_to_ecef

from .constants import DEMO_EARTH_RADIUS_M, DEMO_EARTH_SPIN_RAD_S

DEMO_STEP_S = 40.0
DEMO_SAMPLE_COUNT = 151

def synthetic_orbit(name: str, *, inclination_deg: float, period_s: float,
                    height_m: float, phase_deg: float, color: str,
                    sample_count: int = DEMO_SAMPLE_COUNT,
                    step_s: float = DEMO_STEP_S) -> EcefTrajectory:
    if sample_count < 2:
        raise ValueError("sample_count must be at least 2")
    if step_s <= 0:
        raise ValueError("step_s must be positive")
    radius = DEMO_EARTH_RADIUS_M + height_m
    inclination_rad = radians(inclination_deg)
    phase_rad = radians(phase_deg)
    time = [float(i*step_s) for i in range(sample_count)]
    pos = []
    for t in time:
        theta_rad = 2*pi*t/period_s + phase_rad
        xi = radius * cos(theta_rad)
        yi = radius * sin(theta_rad) * cos(inclination_rad)
        zi = radius * sin(theta_rad) * sin(inclination_rad)
        spin_rad = DEMO_EARTH_SPIN_RAD_S * t
        pos.append((cos(spin_rad)*xi + sin(spin_rad)*yi,
                    -sin(spin_rad)*xi + cos(spin_rad)*yi, zi))
    return EcefTrajectory.from_arrays(name, time, pos, color=color)


def stationary_ground(name: str, *, lon_deg: float, lat_deg: float, color: str) -> EcefTrajectory:
    point = geodetic_to_ecef(lon_deg, lat_deg)
    return EcefTrajectory.from_arrays(name, [0., 6000.],
        [[point.x_m, point.y_m, point.z_m]] * 2, color=color)


def demo_ground_track(samples: int = 240, inclination_deg: float = 51.6) -> list[LonLatDegrees]:
    """Synthetic illustrative degree pairs, not derived from orbital propagation."""
    if samples < 2:
        raise ValueError('samples must be at least 2')
    return [LonLatDegrees(-180 + 360*i/(samples-1), inclination_deg*sin(4*pi*i/(samples-1)))
            for i in range(samples)]

def sample_ecef_trajectories(sample_count: int = DEMO_SAMPLE_COUNT) -> tuple[EcefTrajectory, ...]:
    """Generate repeatable demo paths spanning 0–6000 seconds, without any I/O."""
    if sample_count < 2:
        raise ValueError("sample_count must be at least 2")
    step_s = 6000.0 / (sample_count - 1)
    return (
        synthetic_orbit("LEO / 55°", inclination_deg=55, period_s=5700,
                        height_m=550_000, phase_deg=18, color="#ffbd69",
                        sample_count=sample_count, step_s=step_s),
        synthetic_orbit("LEO / 97°", inclination_deg=97, period_s=6100,
                        height_m=740_000, phase_deg=135, color="#63d8fc",
                        sample_count=sample_count, step_s=step_s),
        stationary_ground("Ground site", lon_deg=-86.59, lat_deg=34.72, color="#ec87b2"),
    )
