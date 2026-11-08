"""Dependency-free semantic coordinates and shared camera geometry."""
from math import cos, sin, radians
from typing import Annotated, Literal, NamedTuple, Sequence, TypeAlias

ViewMode: TypeAlias = Literal["imagery", "political", "combined"]
Degrees: TypeAlias = Annotated[float, "degrees"]


class LonLatDegrees(NamedTuple):
    lon_deg: float
    lat_deg: float


# Public sequences also accept ordinary ordered (longitude, latitude) degree pairs.
LonLatInput: TypeAlias = LonLatDegrees | tuple[float, float]
GroundTrack: TypeAlias = Sequence[LonLatInput]


class Vector3(NamedTuple):
    x: float
    y: float
    z: float


class CameraBasis(NamedTuple):
    forward: Vector3
    east: Vector3
    north: Vector3


class TimeRangeSeconds(NamedTuple):
    start_s: float
    end_s: float


class OrthographicPoint(NamedTuple):
    east_earth_radii: float
    north_earth_radii: float
    visible: bool


def camera_basis(center_lon_deg: Degrees, center_lat_deg: Degrees) -> CameraBasis:
    """Unit camera vectors from longitude/latitude in degrees, never radians."""
    lon_rad, lat_rad = radians(center_lon_deg), radians(center_lat_deg)
    return CameraBasis(Vector3(cos(lat_rad)*cos(lon_rad), cos(lat_rad)*sin(lon_rad), sin(lat_rad)),
                       Vector3(-sin(lon_rad), cos(lon_rad), 0.0),
                       Vector3(-sin(lat_rad)*cos(lon_rad), -sin(lat_rad)*sin(lon_rad), cos(lat_rad)))


def camera_to_world(east: float, north: float, depth: float, basis: CameraBasis) -> Vector3:
    """Convert scalar camera coordinates to a named world XYZ vector."""
    return Vector3(*(f*depth + e*east + n*north
                 for f, e, n in zip(basis.forward, basis.east, basis.north)))


def split_antimeridian(track: GroundTrack) -> list[list[LonLatDegrees]]:
    """Split degree-valued ground tracks at the map seam, retaining pair compatibility."""
    segments: list[list[LonLatDegrees]] = []
    segment: list[LonLatDegrees] = []
    for pair in track:
        point = LonLatDegrees(*pair)
        if segment and abs(point.lon_deg - segment[-1].lon_deg) > 180:
            if len(segment) >= 2:
                segments.append(segment)
            segment = []
        segment.append(point)
    if len(segment) >= 2:
        segments.append(segment)
    return segments
