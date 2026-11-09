"""Shared physical and display constants; units are explicit in every name."""
from typing import Final

WGS84_A_M: Final[float] = 6_378_137.0
WGS84_F: Final[float] = 1.0 / 298.257223563
WGS84_E2: Final[float] = WGS84_F * (2.0 - WGS84_F)
WGS84_B_M: Final[float] = WGS84_A_M * (1.0 - WGS84_F)
EARTH_SPIN_RAD_S: Final[float] = 7.292115e-5

# Approximate spherical display radius, not a WGS84 ellipsoid parameter.
EARTH_RADIUS_M: Final[float] = 6_371_000.0
METERS_PER_KM: Final[float] = 1_000.0
KM_PER_METERS: Final[float] = 1.0 / METERS_PER_KM
EARTH_RADIUS_KM: Final[float] = EARTH_RADIUS_M * KM_PER_METERS
DEFAULT_CENTER_LON_DEG: Final[float] = -30.0
DEFAULT_CENTER_LAT_DEG: Final[float] = 22.0
DEFAULT_EXTENT_EARTH_RADII: Final[float] = 1.35
