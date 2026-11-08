"""Validated Earth-fixed trajectories and WGS84 geodetic transforms.

No propagation, ECI conversion, time-scale inference, or network I/O occurs here.
ECEF uses right-handed metres: +X at (0°,0°), +Y at (90°E,0°), +Z north.
Samples' t_s values are seconds from an explicitly caller-defined epoch.
"""
from __future__ import annotations

import csv
import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, degrees, hypot, isfinite, radians, sin, sqrt
from typing import Iterable, Sequence

from .constants import WGS84_A_M, WGS84_F, WGS84_E2, WGS84_B_M, EARTH_RADIUS_M
from .geometry import (Degrees, LonLatDegrees, TimeRangeSeconds, OrthographicPoint,
                       camera_basis, split_antimeridian)
from .paths import PathInput, input_path, output_path


@dataclass(frozen=True, slots=True)
class EcefPosition:
    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.x_m, self.y_m, self.z_m)):
            raise ValueError("ECEF components must be finite metres")

    @property
    def radius_m(self) -> float:
        return sqrt(self.x_m**2 + self.y_m**2 + self.z_m**2)


@dataclass(frozen=True, slots=True)
class EcefSample:
    t_s: float
    position: EcefPosition

    def __post_init__(self) -> None:
        if not isfinite(self.t_s):
            raise ValueError("Sample time must be finite")
        if not isinstance(self.position, EcefPosition):
            raise TypeError("position must be EcefPosition")


@dataclass(frozen=True, slots=True)
class GeodeticPosition:
    lon_deg: float
    lat_deg: float
    height_m: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.lon_deg, self.lat_deg, self.height_m)):
            raise ValueError("Geodetic coordinates must be finite")
        if not -90 <= self.lat_deg <= 90:
            raise ValueError("Latitude must lie between -90 and +90 degrees")


def geodetic_to_ecef(lon_deg: float, lat_deg: float, height_m: float = 0.0) -> EcefPosition:
    """WGS84 longitude/latitude/ellipsoidal-height to ECEF (metres)."""
    p = GeodeticPosition(lon_deg, lat_deg, height_m)
    lon, lat = radians(p.lon_deg), radians(p.lat_deg)
    sl, cl = sin(lat), cos(lat)
    n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
    return EcefPosition((n + height_m) * cl * cos(lon),
                        (n + height_m) * cl * sin(lon),
                        (n * (1 - WGS84_E2) + height_m) * sl)


def ecef_to_geodetic(position: EcefPosition) -> GeodeticPosition:
    """WGS84 inverse, robust near poles; undefined at Earth's centre."""
    x, y, z = position.x_m, position.y_m, position.z_m
    p = hypot(x, y)
    if p < 1e-8:
        if abs(z) < 1e-8:
            raise ValueError("Geodetic position undefined at Earth centre")
        return GeodeticPosition(0.0, 90.0 if z > 0 else -90.0, abs(z) - WGS84_B_M)
    lon = degrees(atan2(y, x))
    # Iteratively solve latitude; heights can be thousands of kilometres.
    lat = atan2(z, p * (1 - WGS84_E2))
    for _ in range(16):
        sl = sin(lat)
        n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
        next_lat = atan2(z + WGS84_E2 * n * sl, p)
        if abs(next_lat - lat) < 1e-15:
            lat = next_lat
            break
        lat = next_lat
    sl, cl = sin(lat), cos(lat)
    n = WGS84_A_M / sqrt(1 - WGS84_E2 * sl * sl)
    h = p / cl - n if abs(cl) > 1e-8 else abs(z) / abs(sl) - n * (1 - WGS84_E2)
    return GeodeticPosition(lon, degrees(lat), h)


@dataclass(frozen=True, slots=True)
class EcefTrajectory:
    name: str
    samples: tuple[EcefSample, ...]
    color: str = "#ffbd69"
    epoch_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Trajectory requires a nonempty name")
        if not self.samples:
            raise ValueError("Trajectory must have at least one sample")
        if any(b.t_s <= a.t_s for a, b in zip(self.samples, self.samples[1:])):
            raise ValueError("Times must be strictly increasing; duplicate timestamps forbidden")
        if self.epoch_utc is not None and (self.epoch_utc.tzinfo is None or
                                          self.epoch_utc.utcoffset() is None):
            raise ValueError("epoch_utc must be timezone-aware")
        # Hex colors only: safe to inject into CSS/SVG/HTML without script escape.
        if re.fullmatch(r"#[0-9a-fA-F]{6}", self.color) is None:
            raise ValueError("color must be #RRGGBB")

    @classmethod
    def from_arrays(
        cls, name: str, time_s: Sequence[float], xyz_m: Sequence[Sequence[float]],
        *, color: str = "#ffbd69", epoch_utc: datetime | None = None,
    ) -> EcefTrajectory:
        if len(time_s) != len(xyz_m):
            raise ValueError("time and position array lengths must match")
        samples: list[EcefSample] = []
        for t, xyz in zip(time_s, xyz_m):
            if len(xyz) != 3:
                raise ValueError("Each ECEF position must contain x,y,z in metres")
            samples.append(EcefSample(float(t), EcefPosition(*[float(v) for v in xyz])))
        return cls(name=name, samples=tuple(samples), color=color, epoch_utc=epoch_utc)

    @property
    def time_range(self) -> TimeRangeSeconds:
        return TimeRangeSeconds(self.samples[0].t_s, self.samples[-1].t_s)

    def at(self, t_s: float) -> EcefPosition:
        """Piecewise linear ECEF interpolation; reject extrapolation."""
        if not isfinite(t_s):
            raise ValueError("Query time must be finite")
        if not self.samples[0].t_s <= t_s <= self.samples[-1].t_s:
            raise ValueError("Query time outside trajectory range; no extrapolation")
        ts = [sample.t_s for sample in self.samples]
        right = bisect_right(ts, t_s)
        if right == len(ts):
            return self.samples[-1].position
        if right == 0:
            return self.samples[0].position
        a, b = self.samples[right - 1], self.samples[right]
        f = (t_s - a.t_s) / (b.t_s - a.t_s)
        return EcefPosition(*(u + f * (v - u) for u, v in zip(
            (a.position.x_m, a.position.y_m, a.position.z_m),
            (b.position.x_m, b.position.y_m, b.position.z_m))))

    def ground_track(self) -> list[LonLatDegrees]:
        """WGS84 geodetic ground-projection lon/lat, retaining sample order."""
        ll = [ecef_to_geodetic(p.position) for p in self.samples]
        return [LonLatDegrees(p.lon_deg, p.lat_deg) for p in ll]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name, "color": self.color,
            "epoch_utc": self.epoch_utc.astimezone(timezone.utc).isoformat() if self.epoch_utc else None,
            "samples": [{"time_s": sample.t_s, "ecef_m": [sample.position.x_m,
                          sample.position.y_m, sample.position.z_m]} for sample in self.samples],
        }


def _parse_epoch(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("epoch_utc must be an ISO8601 string with UTC offset")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("epoch_utc must have an explicit timezone")
    return result


def _validate_json_metadata(value: object) -> None:
    """Reject explicit frame/unit conflicts; absent legacy metadata is allowed."""
    if not isinstance(value, dict):
        raise ValueError("Trajectory JSON must contain objects")
    for key, expected in (("frame", "ECEF"), ("units", "metres"),
                          ("time_units", "seconds")):
        if key in value and value[key] != expected:
            raise ValueError(f"JSON {key} must be {expected!r}; got {value[key]!r}. "
                             "Coordinate and time conversion is not performed.")


def read_trajectories(path: PathInput) -> tuple[EcefTrajectory, ...]:
    """Read UTF-8 .json or long-form .csv (name,time_s,x_m,y_m,z_m).

    Coordinates are already ECEF, not ECI; times are seconds relative to
    the supplied epoch (when given), not Unix timestamps by default.
    JSON metadata, when present, must be ECEF/metres/seconds at both the
    document and trajectory levels. Omitted metadata retains the legacy defaults.
    """
    path = input_path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        _validate_json_metadata(raw)
        entries = raw["trajectories"] if isinstance(raw, dict) and "trajectories" in raw else [raw]
        result = []
        for entry in entries:
            _validate_json_metadata(entry)
            result.append(EcefTrajectory.from_arrays(
                str(entry["name"]),
                [sample["time_s"] for sample in entry["samples"]],
                [sample["ecef_m"] for sample in entry["samples"]],
                color=str(entry.get("color", "#ffbd69")),
                epoch_utc=_parse_epoch(entry.get("epoch_utc")),
            ))
        return tuple(result)
    if path.suffix.lower() == ".csv":
        grouped: dict[str, list[tuple[float, list[float]]]] = {}
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                name = row.get("name") or path.stem
                grouped.setdefault(name, []).append((float(row["time_s"]),
                    [float(row[k]) for k in ("x_m", "y_m", "z_m")]))
        return tuple(EcefTrajectory.from_arrays(name,
                     [t for t, _ in rows], [xyz for _, xyz in rows])
                     for name, rows in grouped.items())
    raise ValueError("Expected .json or .csv input")


def write_trajectories(path: PathInput, tracks: Iterable[EcefTrajectory]) -> None:
    path = output_path(path)
    payload = {"frame": "ECEF", "units": "metres", "time_units": "seconds",
               "trajectories": [track.to_dict() for track in tracks]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def project_orthographic_ecef(
    position: EcefPosition, center_lon: Degrees, center_lat: Degrees,
    *, display_radius_m: float = EARTH_RADIUS_M,
) -> OrthographicPoint:
    """Orthographic globe coordinates (Earth radii) and WGS84 horizon visibility.

    center_lon and center_lat are degrees. The camera is at infinity along that direction.
    Visibility uses an ellipsoid ray intersection, preserving altitude: a far-side
    satellite may be visible beyond the limb while a surface point is occluded.
    """
    forward, east, north = camera_basis(center_lon, center_lat)
    p = (position.x_m, position.y_m, position.z_m)
    u = sum(a*b for a, b in zip(p, east)) / display_radius_m
    v = sum(a*b for a, b in zip(p, north)) / display_radius_m
    # Ray from position toward camera; any positive intersection blocks sight.
    weights = (1 / WGS84_A_M**2, 1 / WGS84_A_M**2, 1 / WGS84_B_M**2)
    aa = sum(w * f*f for w, f in zip(weights, forward))
    bb = 2 * sum(w * x*f for w, x, f in zip(weights, p, forward))
    cc = sum(w * x*x for w, x in zip(weights, p)) - 1
    determinant = bb*bb - 4*aa*cc
    visible = True
    if determinant >= 0:
        sqrt_d = sqrt(determinant)
        lo = (-bb - sqrt_d) / (2*aa)
        hi = (-bb + sqrt_d) / (2*aa)
        visible = not (hi > 1.0 and (lo > 1.0 or cc < -1e-12))
    return OrthographicPoint(u, v, visible)
