"""Unified ECEF rendering entry point, independent of optional plotting packages."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from importlib import import_module
from pathlib import Path
from .paths import PathInput, output_path
from .geometry import Degrees, ViewMode, VIEW_MODES
from .constants import (DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII)
from typing import Any, Literal, Mapping, MutableSequence, Sequence, get_args
from .figures import PostPlot, validate_post_plot

from .svg import save_svg
from .canvas import canvas_globe
from .trajectory import EcefTrajectory

Backend = Literal["svg", "map", "globe", "canvas", "plotly", "timeseries"]


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """Display choices. center_lon_deg/center_lat_deg are degrees, never radians.

    No ECI conversion or orbit propagation is implied.
    """

    backend: Backend = "map"
    mode: ViewMode = "combined"
    at_s: float | None = None
    center_lon_deg: Degrees = DEFAULT_CENTER_LON_DEG
    center_lat_deg: Degrees = DEFAULT_CENTER_LAT_DEG
    extent_earth_radii: float = DEFAULT_EXTENT_EARTH_RADII

    def __post_init__(self) -> None:
        if self.backend not in get_args(Backend):
            raise ValueError("Unrecognized render backend")
        if self.mode not in VIEW_MODES:
            raise ValueError("Unrecognized Earth display mode")
        if self.at_s is not None and not isfinite(self.at_s):
            raise ValueError("at_s must be finite")
        if not all(isfinite(v) for v in (self.center_lon_deg, self.center_lat_deg, self.extent_earth_radii)):
            raise ValueError("Camera parameters must be finite")
        if not -90 <= self.center_lat_deg <= 90:
            raise ValueError("Camera latitude must lie in [-90,90]")
        if self.extent_earth_radii < 1.05:
            raise ValueError("extent_earth_radii must be >= 1.05")


def render_ecef(
    trajectories: Sequence[EcefTrajectory],
    output: PathInput,
    *,
    spec: RenderSpec = RenderSpec(),
    post_plot: PostPlot | None = None,
    post_plot_kwargs: Mapping[str, Any] | None = None,
    figures: MutableSequence[Any] | None = None,
) -> Path:
    """Render the same ECEF inputs to any supported offline visualization backend.

    The 2D renderers display WGS84 ground-projection traces. The 3D renderers
    display original ECEF coordinates and altitude. ``at_s`` controls a static
    marker; Canvas provides a draggable time scrubber and play/pause itself.

    Figure backends accept ``post_plot(fig, path=..., **post_plot_kwargs)``.
    This replaces default saving/closing; returning a figure transfers ownership
    to the caller. Surviving figures are appended to a caller-owned ``figures``
    collection, if supplied. SVG/Canvas have no figure and do not invoke callbacks.
    The return value remains the output path; a callback may choose not to save it.

    Multiple trajectories must share a time origin. If an epoch is supplied,
    all trajectories must supply the SAME instant in their epoch_utc field.
    """
    if spec.backend in ("svg", "canvas") and (post_plot is not None or post_plot_kwargs):
        raise ValueError("post_plot callbacks require a figure backend")
    validate_post_plot(post_plot, post_plot_kwargs)
    lifecycle = dict(post_plot=post_plot, post_plot_kwargs=post_plot_kwargs)
    figure = None
    epochs = {t.epoch_utc for t in trajectories}
    if len(epochs) > 1:
        raise ValueError("All trajectories must share the same epoch_utc (or all omit it)")
    path = output_path(output)
    # The sole optional-dependency boundary: importing core presentation APIs is
    # dependency-free; selecting a backend imports only its explicit module.
    optional_modules = {
        "map": ".renderers.matplotlib", "globe": ".renderers.matplotlib",
        "plotly": ".renderers.plotly", "timeseries": ".timeseries",
    }
    renderer = (import_module(optional_modules[spec.backend], __package__)
                if spec.backend in optional_modules else None)
    if spec.backend == "svg":
        save_svg(str(path), trajectories=list(trajectories), at_s=spec.at_s,
                 mode=spec.mode)
    elif spec.backend == "map":
        figure = renderer.matplotlib_world(path, mode=spec.mode, trajectories=trajectories,
                         at_s=spec.at_s, **lifecycle)
    elif spec.backend == "globe":
        figure = renderer.matplotlib_globe(path, mode=spec.mode, trajectories=trajectories,
                         at_s=spec.at_s, center_lon_deg=spec.center_lon_deg,
                         center_lat_deg=spec.center_lat_deg,
                         extent_earth_radii=spec.extent_earth_radii, **lifecycle)
    elif spec.backend == "canvas":
        canvas_globe(path, trajectories=trajectories, mode=spec.mode, at_s=spec.at_s,
                     center_lon_deg=spec.center_lon_deg, center_lat_deg=spec.center_lat_deg)
    elif spec.backend == "plotly":
        figure = renderer.plotly_globe(path, include_imagery=(spec.mode != "political"),
                     trajectories=trajectories, at_s=spec.at_s, **lifecycle)
    else:
        figure = renderer.matplotlib_ecef_timeseries(path, trajectories, **lifecycle)
    if figures is not None and figure is not None:
        figures.append(figure)
    return path
