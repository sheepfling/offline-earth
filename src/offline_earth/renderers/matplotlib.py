"""Optional static Matplotlib Earth maps and orthographic globes."""
from __future__ import annotations

from typing import Any, Final, Mapping, Sequence

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.collections import PolyCollection
from matplotlib.patches import Circle

from ..assets import BLUE_MARBLE, countries
from ..constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII
from ..geometry import Degrees, GroundTrack, ViewMode, VIEW_MODES, camera_basis, split_antimeridian
from ..paths import PathInput, output_path
from ..figures import PostPlot, finish_figure, validate_post_plot
from ..trajectory import EcefTrajectory, ecef_to_geodetic, project_orthographic_ecef
from .blue_marble import texture_rgb
from .raster import ORTHOGRAPHIC_EXTENT, orthographic_rgb, _project_ring


# Colors are named for their drawing roles; world and globe shades intentionally
# differ where the original renderers used different contrast against the Earth.
FIGURE_BACKGROUND_COLOR: Final[str] = "#071522"
TRAJECTORY_MARKER_EDGE_COLOR: Final[str] = "white"
TRAJECTORY_LABEL_COLOR: Final[str] = "#ffffff"

WORLD_OCEAN_COLOR: Final[str] = "#143454"
WORLD_POLITICAL_LAND_COLOR: Final[str] = "#a0bdb1"
WORLD_POLITICAL_BORDER_COLOR: Final[str] = "#27495e"
WORLD_IMAGERY_BORDER_COLOR: Final[str] = "#fff2c1"
WORLD_GROUND_TRACK_COLOR: Final[str] = "#ffb65e"
WORLD_AXIS_TICK_COLOR: Final[str] = "#bdcbd6"
WORLD_TITLE_COLOR: Final[str] = "#f1f5fa"
WORLD_AXIS_LABEL_COLOR: Final[str] = "#b4c8d9"
WORLD_GRID_COLOR: Final[str] = "white"

GLOBE_ATMOSPHERE_COLOR: Final[str] = "#69a9d4"
GLOBE_IMAGERY_BORDER_COLOR: Final[str] = "#fff0c2"
GLOBE_POLITICAL_BORDER_COLOR: Final[str] = "#2c5364"
GLOBE_GROUND_TRACK_COLOR: Final[str] = "#ffb160"
GLOBE_TITLE_COLOR: Final[str] = "#e8f4ff"
GLOBE_CAPTION_COLOR: Final[str] = "#8baec4"


def matplotlib_world(
    path: PathInput,
    *,
    mode: ViewMode = "combined",
    track: GroundTrack | None = None,
    title: str | None = None,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
    post_plot: PostPlot | None = None,
    post_plot_kwargs: Mapping[str, Any] | None = None,
) -> Figure | None:
    """Render a 2D equirectangular world map as PNG/SVG/PDF through Matplotlib.

    Default: save and close. ``post_plot(fig, path=..., **post_plot_kwargs)``
    replaces this behavior; return a figure to retain it or None to release it.
    """

    validate_post_plot(post_plot, post_plot_kwargs)
    if mode not in VIEW_MODES:
        raise ValueError(f"Unknown mode: {mode!r}")
    fig, ax = plt.subplots(figsize=(14.4, 7.5), dpi=140)
    try:
        fig.patch.set_facecolor(FIGURE_BACKGROUND_COLOR)
        ax.set_facecolor(WORLD_OCEAN_COLOR)
        if mode in ("imagery", "combined"):
            ax.imshow(texture_rgb(), extent=BLUE_MARBLE.extent_deg, origin=BLUE_MARBLE.origin, zorder=0, interpolation="bilinear")
        if mode == "political":
            polygons = [ring for c in countries() for ring in c["rings"] if len(ring) >= 3]
            ax.add_collection(PolyCollection(polygons, facecolors=WORLD_POLITICAL_LAND_COLOR, edgecolors=WORLD_POLITICAL_BORDER_COLOR, linewidths=.5, zorder=1))
        elif mode == "combined":
            polygons = [ring for c in countries() for ring in c["rings"] if len(ring) >= 3]
            ax.add_collection(PolyCollection(polygons, facecolors="none", edgecolors=WORLD_IMAGERY_BORDER_COLOR, linewidths=.38, alpha=.88, zorder=2))
        if track is not None:
            for segment in split_antimeridian(track):
                ax.plot([p[0] for p in segment], [p[1] for p in segment], color=WORLD_GROUND_TRACK_COLOR, linewidth=2.0, zorder=5)
        if trajectories:
            for tr in trajectories:
                for segment in split_antimeridian(tr.ground_track()):
                    ax.plot([p[0] for p in segment], [p[1] for p in segment],
                            color=tr.color, linewidth=1.85, zorder=6, label=tr.name)
                marker = tr.samples[-1].position if at_s is None else (
                    tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
                if marker is not None:
                    geo = ecef_to_geodetic(marker)
                    ax.plot([geo.lon_deg], [geo.lat_deg], linestyle="none", marker="o",
                            markersize=7.5, color=tr.color, zorder=8,
                            markeredgecolor=TRAJECTORY_MARKER_EDGE_COLOR, markeredgewidth=.85)
                    ax.annotate(tr.name, (geo.lon_deg, geo.lat_deg), xytext=(7, 8),
                                textcoords="offset points", fontsize=8, color=TRAJECTORY_LABEL_COLOR)
        ax.set(xlim=(-180, 180), ylim=(-90, 90), xlabel="Longitude", ylabel="Latitude",
               title=title or f"{mode.title()} · Global Earth visualization (offline)")
        ax.tick_params(colors=WORLD_AXIS_TICK_COLOR, labelsize=9)
        ax.title.set_color(WORLD_TITLE_COLOR)
        ax.xaxis.label.set_color(WORLD_AXIS_LABEL_COLOR)
        ax.yaxis.label.set_color(WORLD_AXIS_LABEL_COLOR)
        ax.grid(color=WORLD_GRID_COLOR, alpha=.13, linewidth=.5)
        ax.set_aspect("equal")
        fig.tight_layout(pad=2.2)
        target = output_path(path)
        return finish_figure(
            fig, target, post_plot=post_plot, post_plot_kwargs=post_plot_kwargs,
            save=lambda: fig.savefig(target, facecolor=fig.get_facecolor()), close=plt.close,
        )
    except BaseException:
        plt.close(fig)
        raise

def matplotlib_globe(
    path: PathInput,
    *,
    mode: ViewMode = "combined",
    center_lon_deg: Degrees = DEFAULT_CENTER_LON_DEG,
    center_lat_deg: Degrees = DEFAULT_CENTER_LAT_DEG,
    track: GroundTrack | None = None,
    size: int = 780,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
    extent_earth_radii: float = DEFAULT_EXTENT_EARTH_RADII,
    post_plot: PostPlot | None = None,
    post_plot_kwargs: Mapping[str, Any] | None = None,
) -> Figure | None:
    """Render a Blue Marble orthographic globe with optional borders and tracks.

    Default: save and close. ``post_plot(fig, path=..., **post_plot_kwargs)``
    replaces this behavior; return a figure to retain it or None to release it.
    """

    validate_post_plot(post_plot, post_plot_kwargs)
    if extent_earth_radii < 1.05:
        raise ValueError("extent_earth_radii must be >= 1.05")
    rgba = orthographic_rgb(mode=mode, center_lon_deg=center_lon_deg, center_lat_deg=center_lat_deg, size=size)
    fig, ax = plt.subplots(figsize=(8.6, 8.8), dpi=140)
    try:
        fig.patch.set_facecolor(FIGURE_BACKGROUND_COLOR)
        ax.set_facecolor(FIGURE_BACKGROUND_COLOR)
        ax.imshow(rgba, extent=(-ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT, -ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT), interpolation="bilinear", zorder=2)
        ax.add_patch(Circle((0, 0), 1, fill=False, color=GLOBE_ATMOSPHERE_COLOR, alpha=.5, lw=1.3, zorder=4))
        if mode in ("political", "combined"):
            forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
            for c in countries():
                for ring in c["rings"]:
                    for sx, sy in _project_ring(ring, forward, east, north):
                        ax.plot(sx, sy, color=GLOBE_IMAGERY_BORDER_COLOR if mode == "combined" else GLOBE_POLITICAL_BORDER_COLOR, lw=.65, alpha=.92, zorder=5)
            if track is not None:
                for sx, sy in _project_ring(track, forward, east, north):
                    ax.plot(sx, sy, color=GLOBE_GROUND_TRACK_COLOR, lw=2.6, zorder=6)
        elif track is not None:
            forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
            for sx, sy in _project_ring(track, forward, east, north):
                ax.plot(sx, sy, color=GLOBE_GROUND_TRACK_COLOR, lw=2.6, zorder=6)
        if trajectories:
            for tr in trajectories:
                px: list[float] = []; py: list[float] = []
                for sample in tr.samples:
                    u, v, visible = project_orthographic_ecef(
                        sample.position, center_lon_deg, center_lat_deg)
                    if not visible:
                        if len(px) >= 2:
                            ax.plot(px, py, color=tr.color, lw=1.8, zorder=8)
                        px, py = [], []
                    else:
                        px.append(u); py.append(v)
                if len(px) >= 2:
                    ax.plot(px, py, color=tr.color, lw=1.8, zorder=8)
                marker = tr.samples[-1].position if at_s is None else (
                    tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
                if marker is not None:
                    u, v, visible = project_orthographic_ecef(marker, center_lon_deg, center_lat_deg)
                    if visible:
                        ax.plot([u], [v], linestyle="none", marker="o",
                                markersize=8, color=tr.color, zorder=9,
                                markeredgecolor=TRAJECTORY_MARKER_EDGE_COLOR, markeredgewidth=.75)
                        ax.annotate(tr.name, (u,v), xytext=(6,6), textcoords="offset points",
                                    fontsize=8, color=TRAJECTORY_LABEL_COLOR, zorder=10)
        ax.set(xlim=(-extent_earth_radii, extent_earth_radii), ylim=(-extent_earth_radii, extent_earth_radii), aspect="equal")
        ax.axis("off")
        fig.text(.5, .955, f"{mode.title()} Earth · Orthographic view", color=GLOBE_TITLE_COLOR, fontsize=15, ha="center", weight="bold")
        fig.text(.5, .035, f"Centered {center_lon_deg:.0f}° longitude, {center_lat_deg:.0f}° latitude  ·  Fully offline",
                 color=GLOBE_CAPTION_COLOR, fontsize=9, ha="center")
        fig.subplots_adjust(left=.015, right=.985, top=.94, bottom=.065)
        target = output_path(path)
        return finish_figure(
            fig, target, post_plot=post_plot, post_plot_kwargs=post_plot_kwargs,
            save=lambda: fig.savefig(target, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=.12), close=plt.close,
        )
    except BaseException:
        plt.close(fig)
        raise
