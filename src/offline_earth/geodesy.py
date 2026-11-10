"""Dependency-free WGS84 coordinates, transforms, and horizon projection.

ECEF uses right-handed meters: +X at (0°,0°), +Y at (90°E,0°), +Z north.
This module performs coordinate math only, with no trajectory or file I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, isfinite, radians, sin, sqrt
from sys import float_info

from .constants import EARTH_RADIUS_M, WGS84_A_M, WGS84_B_M, WGS84_E2
from .geometry import Degrees, OrthographicPoint, camera_basis


# gamma(32), with binary64 unit roundoff u = epsilon/2. See NUMERICS.md for
# the expanded-polynomial error bound and its conservative tangent convention.
_RAY_DISCRIMINANT_ROUNDOFF = 32 * (float_info.epsilon / 2) / (1 - 32 * (float_info.epsilon / 2))


@dataclass(frozen=True, slots=True)
class EcefPosition:
    """Finite Earth-centred, Earth-fixed Cartesian coordinates in meters."""

    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.x_m, self.y_m, self.z_m)):
            raise ValueError("ECEF components must be finite meters")

    @property
    def radius_m(self) -> float:
        return sqrt(self.x_m**2 + self.y_m**2 + self.z_m**2)


@dataclass(frozen=True, slots=True)
class GeodeticPosition:
    """WGS84 longitude/latitude degrees and ellipsoidal height in meters."""

    lon_deg: float
    lat_deg: float
    height_m: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.lon_deg, self.lat_deg, self.height_m)):
            raise ValueError("Geodetic coordinates must be finite")
        if not -90 <= self.lat_deg <= 90:
            raise ValueError("Latitude must lie between -90 and +90 degrees")


def geodetic_to_ecef(lon_deg: float, lat_deg: float, height_m: float = 0.0) -> EcefPosition:
    """WGS84 longitude/latitude/ellipsoidal-height to ECEF (meters)."""
    p = GeodeticPosition(lon_deg, lat_deg, height_m)
    lon_rad, lat_rad = radians(p.lon_deg), radians(p.lat_deg)
    sl, cl = sin(lat_rad), cos(lat_rad)
    n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
    return EcefPosition((n + height_m) * cl * cos(lon_rad),
                        (n + height_m) * cl * sin(lon_rad),
                        (n * (1 - WGS84_E2) + height_m) * sl)


def ecef_to_geodetic(position: EcefPosition) -> GeodeticPosition:
    """WGS84 inverse, robust near poles; undefined at Earth's centre."""
    x, y, z = position.x_m, position.y_m, position.z_m
    p = hypot(x, y)
    if p < 1e-8:
        if abs(z) < 1e-8:
            raise ValueError("Geodetic position undefined at Earth centre")
        return GeodeticPosition(0.0, 90.0 if z > 0 else -90.0, abs(z) - WGS84_B_M)
    lon_deg = degrees(atan2(y, x))
    # Iteratively solve latitude; heights can be thousands of kilometers.
    lat_rad = atan2(z, p * (1 - WGS84_E2))
    for _ in range(16):
        sl = sin(lat_rad)
        n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
        next_lat_rad = atan2(z + WGS84_E2 * n * sl, p)
        if abs(next_lat_rad - lat_rad) < 1e-15:
            lat_rad = next_lat_rad
            break
        lat_rad = next_lat_rad
    sl, cl = sin(lat_rad), cos(lat_rad)
    n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
    h = p / cl - n if abs(cl) > 1e-8 else abs(z) / abs(sl) - n * (1 - WGS84_E2)
    return GeodeticPosition(lon_deg, degrees(lat_rad), h)


def project_orthographic_ecef(
    position: EcefPosition, center_lon_deg: Degrees, center_lat_deg: Degrees,
    *, display_radius_m: float = EARTH_RADIUS_M,
) -> OrthographicPoint:
    """Orthographic globe coordinates (Earth radii) and WGS84 horizon visibility.

    center_lon_deg and center_lat_deg are degrees. The camera is at infinity along that direction.
    Visibility uses an ellipsoid ray intersection, preserving altitude: a far-side
    satellite may be visible beyond the limb while a surface point is occluded.
    """
    forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
    p = (position.x_m, position.y_m, position.z_m)
    u = sum(a*b for a, b in zip(p, east)) / display_radius_m
    v = sum(a*b for a, b in zip(p, north)) / display_radius_m
    # Ray from position toward camera; any positive intersection blocks sight.
    wa, wb = 1 / WGS84_A_M**2, 1 / WGS84_B_M**2
    fx, fy, fz = forward
    x, y, z = p
    # Explicit order matches Canvas, including Python versions with improved sum().
    aa = wa*fx*fx + wa*fy*fy + wb*fz*fz
    bx, by, bz = wa*x*fx, wa*y*fy, wb*z*fz
    bb = 2 * (bx + by + bz)
    squared_radius = wa*x*x + wa*y*y + wb*z*z
    cc = squared_radius - 1
    determinant = bb*bb - 4*aa*cc
    # Bound cancellation using unsigned terms, not abs(cc) or abs(bb).
    absolute_bb = 2 * (abs(bx) + abs(by) + abs(bz))
    roundoff = _RAY_DISCRIMINANT_ROUNDOFF * (
        absolute_bb*absolute_bb + 4*aa*(squared_radius + 1)
    )
    if isfinite(roundoff) and -roundoff <= determinant < 0:
        determinant = 0.0
    visible = True
    if determinant >= 0:
        sqrt_d = sqrt(determinant)
        hi = (-bb + sqrt_d) / (2*aa)
        # A self-hit near t=0 does not cancel a later Earth exit.
        # Keep the existing one-meter tolerance for intersections at the origin.
        visible = not (hi > 1.0)
    return OrthographicPoint(u, v, visible)
