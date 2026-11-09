"""Dependency-free spherical geometry for illustrative Earth displays."""
from math import cos, radians, sin

from .constants import EARTH_RADIUS_KM
from .geometry import Vector3


def sphere_xyz(lon_deg: float, lat_deg: float, radius: float = EARTH_RADIUS_KM) -> Vector3:
    lon_rad, lat_rad = radians(lon_deg), radians(lat_deg)
    return Vector3(radius * cos(lat_rad) * cos(lon_rad), radius * cos(lat_rad) * sin(lon_rad), radius * sin(lat_rad))
