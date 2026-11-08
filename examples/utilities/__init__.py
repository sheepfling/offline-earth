"""Shared illustrative example data. Not propagation or production Earth models."""
from math import cos, pi, radians, sin
from offline_earth.geometry import LonLatDegrees
from offline_earth.trajectory import EcefTrajectory, geodetic_to_ecef

DEMO_EARTH_SPIN_RAD_S = 7.292115e-5
DEMO_EARTH_RADIUS_M = 6_371_000.0
DEMO_STEP_S = 40.0
DEMO_SAMPLE_COUNT = 151

def synthetic_orbit(name: str, *, inclination_deg: float, period_s: float,
                    height_m: float, phase_deg: float, color: str) -> EcefTrajectory:
    radius = DEMO_EARTH_RADIUS_M + height_m
    inclination_rad = radians(inclination_deg)
    phase_rad = radians(phase_deg)
    time = [float(i*DEMO_STEP_S) for i in range(DEMO_SAMPLE_COUNT)]
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

__all__ = ['synthetic_orbit', 'stationary_ground', 'demo_ground_track']
