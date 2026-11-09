"""Validated Earth-fixed trajectories and local-file adapters.

No propagation, ECI conversion, time-scale inference, or network I/O occurs here.
ECEF uses right-handed meters: +X at (0°,0°), +Y at (90°E,0°), +Z north.
Samples' t_s values are seconds from an explicitly caller-defined epoch.
"""
from __future__ import annotations

import csv
import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, TypedDict

# Re-export the original coordinate API for existing callers.
from .geodesy import (EcefPosition, GeodeticPosition, ecef_to_geodetic,
                      geodetic_to_ecef, project_orthographic_ecef)
from .geometry import LonLatDegrees, TimeRangeSeconds, split_antimeridian
from .paths import PathInput, input_path, output_path


class SampleRecord(TypedDict):
    time_s: float
    ecef_m: list[float]


class TrajectoryRecord(TypedDict):
    name: str
    color: str
    epoch_utc: str | None
    samples: list[SampleRecord]


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
class EcefTrajectory:
    """Immutable validated samples, strictly ordered by caller-relative seconds."""

    name: str
    samples: tuple[EcefSample, ...]
    color: str = "#ffbd69"
    epoch_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Trajectory requires a nonempty name")
        # Copy caller-owned collections before validating so later edits cannot
        # invalidate the trajectory's ordering or nonempty invariant.
        object.__setattr__(self, "samples", tuple(self.samples))
        if not all(isinstance(sample, EcefSample) for sample in self.samples):
            raise TypeError("samples must contain EcefSample objects")
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
        cls, name: str, time_s: Iterable[float], xyz_m: Iterable[Iterable[float]],
        *, color: str = "#ffbd69", epoch_utc: datetime | None = None,
    ) -> EcefTrajectory:
        """Copy iterable times/XYZ rows, rejecting unequal lengths and bad rows."""
        time_s, xyz_m = tuple(time_s), tuple(xyz_m)
        if len(time_s) != len(xyz_m):
            raise ValueError("time and position array lengths must match")
        samples: list[EcefSample] = []
        for t, xyz in zip(time_s, xyz_m):
            xyz = tuple(xyz)
            if len(xyz) != 3:
                raise ValueError("Each ECEF position must contain x,y,z in meters")
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

    def to_dict(self) -> TrajectoryRecord:
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


def read_trajectories(path: PathInput) -> list[EcefTrajectory]:
    """Read UTF-8 .json or long-form .csv (name,time_s,x_m,y_m,z_m).

    Return an editable list of immutable, validated trajectories.

    Coordinates are already ECEF, not ECI; times are seconds relative to
    the supplied epoch (when given), not Unix timestamps by default.
    JSON metadata, when present, must be ECEF/metres/seconds at both the
    document and trajectory levels. Omitted metadata retains the legacy defaults.
    """
    path = input_path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        _validate_json_metadata(raw)
        entries = raw["trajectories"] if "trajectories" in raw else [raw]
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
        return result
    if path.suffix.lower() == ".csv":
        grouped: dict[str, list[tuple[float, list[float]]]] = {}
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                name = row.get("name") or path.stem
                grouped.setdefault(name, []).append((float(row["time_s"]),
                    [float(row[k]) for k in ("x_m", "y_m", "z_m")]))
        return [EcefTrajectory.from_arrays(name,
                     [t for t, _ in rows], [xyz for _, xyz in rows])
                     for name, rows in grouped.items()]
    raise ValueError("Expected .json or .csv input")


def write_trajectories(path: PathInput, tracks: Iterable[EcefTrajectory]) -> None:
    path = output_path(path)
    payload = {"frame": "ECEF", "units": "metres", "time_units": "seconds",
               "trajectories": [track.to_dict() for track in tracks]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
