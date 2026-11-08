"""Unified ECEF rendering entry point, independent of optional plotting packages."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, Sequence

from . import save_svg
from .canvas import canvas_globe
from .earth import ViewMode, matplotlib_globe, matplotlib_world, plotly_globe
from .timeseries import matplotlib_ecef_timeseries
from .trajectory import EcefTrajectory

Backend = Literal["svg", "map", "globe", "canvas", "plotly", "timeseries"]


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """Explicit display choices; doesn't imply ECI conversion or orbit propagation."""

    backend: Backend = "map"
    mode: ViewMode = "combined"
    at_s: float | None = None
    center_lon: float = -30.0
    center_lat: float = 22.0
    extent_earth_radii: float = 1.35

    def __post_init__(self) -> None:
        if self.backend not in ("svg", "map", "globe", "canvas", "plotly", "timeseries"):
            raise ValueError("Unrecognized render backend")
        if self.mode not in ("imagery", "political", "combined"):
            raise ValueError("Unrecognized Earth display mode")
        if self.at_s is not None and not isfinite(self.at_s):
            raise ValueError("at_s must be finite")
        if not all(isfinite(v) for v in (self.center_lon, self.center_lat, self.extent_earth_radii)):
            raise ValueError("Camera parameters must be finite")
        if not -90 <= self.center_lat <= 90:
            raise ValueError("Camera latitude must lie in [-90,90]")
        if self.extent_earth_radii < 1.05:
            raise ValueError("extent_earth_radii must be >= 1.05")


def render_ecef(
    trajectories: Sequence[EcefTrajectory],
    output: str | Path,
    *,
    spec: RenderSpec = RenderSpec(),
) -> Path:
    """Render the same ECEF inputs to any supported offline visualization backend.

    The 2D renderers display WGS84 ground-projection traces. The 3D renderers
    display original ECEF coordinates and altitude. ``at_s`` controls a static
    marker; Canvas provides a draggable time scrubber and play/pause itself.

    Multiple trajectories must share a time origin. If an epoch is supplied,
    all trajectories must supply the SAME instant in their epoch_utc field.
    """
    epochs = {t.epoch_utc for t in trajectories}
    if len(epochs) > 1:
        raise ValueError("All trajectories must share the same epoch_utc (or all omit it)")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if spec.backend == "svg":
        save_svg(str(path), trajectories=list(trajectories), at_s=spec.at_s,
                 mode=spec.mode)
    elif spec.backend == "map":
        matplotlib_world(path, mode=spec.mode, trajectories=trajectories,
                         at_s=spec.at_s)
    elif spec.backend == "globe":
        matplotlib_globe(path, mode=spec.mode, trajectories=trajectories,
                         at_s=spec.at_s, center_lon=spec.center_lon,
                         center_lat=spec.center_lat,
                         extent_earth_radii=spec.extent_earth_radii)
    elif spec.backend == "canvas":
        canvas_globe(path, trajectories=trajectories, mode=spec.mode, at_s=spec.at_s,
                     center_lon=spec.center_lon, center_lat=spec.center_lat)
    elif spec.backend == "plotly":
        plotly_globe(path, include_imagery=(spec.mode != "political"),
                     trajectories=trajectories, at_s=spec.at_s)
    else:
        matplotlib_ecef_timeseries(path, trajectories)
    return path
