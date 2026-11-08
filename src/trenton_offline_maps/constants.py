"""Shared physical and display constants; units are explicit in every name."""
WGS84_A_M = 6_378_137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
WGS84_B_M = WGS84_A_M * (1.0 - WGS84_F)

# Approximate spherical display radius, not a WGS84 ellipsoid parameter.
EARTH_RADIUS_M = 6_371_000.0
METRES_PER_KM = 1000.0
EARTH_RADIUS_KM = EARTH_RADIUS_M / METRES_PER_KM
DEFAULT_CENTER_LON_DEG = -30.0
DEFAULT_CENTER_LAT_DEG = 22.0
DEFAULT_EXTENT_EARTH_RADII = 1.35
