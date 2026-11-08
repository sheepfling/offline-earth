"""Optional static Matplotlib Earth maps and orthographic globes."""
from __future__ import annotations

from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Circle

from ..assets import BLUE_MARBLE, countries
from ..constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII
from ..geometry import Degrees, GroundTrack, ViewMode, camera_basis, split_antimeridian
from ..paths import PathInput, output_path
from ..trajectory import EcefTrajectory, ecef_to_geodetic, project_orthographic_ecef
from .blue_marble import texture_rgb
from .raster import ORTHOGRAPHIC_EXTENT, orthographic_rgb, _project_ring


def matplotlib_world(
    path: PathInput,
    *,
    mode: ViewMode = "combined",
    track: GroundTrack | None = None,
    title: str | None = None,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
) -> None:
    """Render a 2D equirectangular world map as PNG/SVG/PDF through Matplotlib."""

    if mode not in ("imagery", "political", "combined"):
        raise ValueError(f"Unknown mode: {mode!r}")
    fig, ax = plt.subplots(figsize=(14.4, 7.5), dpi=140)
    fig.patch.set_facecolor("#071522")
    ax.set_facecolor("#143454")
    if mode in ("imagery", "combined"):
        ax.imshow(texture_rgb(), extent=BLUE_MARBLE.extent_deg, origin=BLUE_MARBLE.origin, zorder=0, interpolation="bilinear")
    if mode == "political":
        polygons = [ring for c in countries() for ring in c["rings"] if len(ring) >= 3]
        ax.add_collection(PolyCollection(polygons, facecolors="#a0bdb1", edgecolors="#27495e", linewidths=.5, zorder=1))
    elif mode == "combined":
        polygons = [ring for c in countries() for ring in c["rings"] if len(ring) >= 3]
        ax.add_collection(PolyCollection(polygons, facecolors="none", edgecolors="#fff2c1", linewidths=.38, alpha=.88, zorder=2))
    if track is not None:
        for segment in split_antimeridian(track):
            ax.plot([p[0] for p in segment], [p[1] for p in segment], color="#ffb65e", linewidth=2.0, zorder=5)
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
                        markeredgecolor="white", markeredgewidth=.85)
                ax.annotate(tr.name, (geo.lon_deg, geo.lat_deg), xytext=(7, 8),
                            textcoords="offset points", fontsize=8, color="#ffffff")
    ax.set(xlim=(-180, 180), ylim=(-90, 90), xlabel="Longitude", ylabel="Latitude",
           title=title or f"{mode.title()} · Global Earth visualization (offline)")
    ax.tick_params(colors="#bdcbd6", labelsize=9)
    ax.title.set_color("#f1f5fa")
    ax.xaxis.label.set_color("#b4c8d9")
    ax.yaxis.label.set_color("#b4c8d9")
    ax.grid(color="white", alpha=.13, linewidth=.5)
    ax.set_aspect("equal")
    fig.tight_layout(pad=2.2)
    fig.savefig(output_path(path), facecolor=fig.get_facecolor())
    plt.close(fig)

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
) -> None:
    """Render a Blue Marble orthographic globe with optional vector borders and tracks."""

    rgba = orthographic_rgb(mode=mode, center_lon_deg=center_lon_deg, center_lat_deg=center_lat_deg, size=size)
    fig, ax = plt.subplots(figsize=(8.6, 8.8), dpi=140)
    fig.patch.set_facecolor("#071522")
    ax.set_facecolor("#071522")
    ax.imshow(rgba, extent=(-ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT, -ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT), interpolation="bilinear", zorder=2)
    ax.add_patch(Circle((0, 0), 1, fill=False, color="#69a9d4", alpha=.5, lw=1.3, zorder=4))
    if mode in ("political", "combined"):
        forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
        for c in countries():
            for ring in c["rings"]:
                for sx, sy in _project_ring(ring, forward, east, north):
                    ax.plot(sx, sy, color="#fff0c2" if mode == "combined" else "#2c5364", lw=.65, alpha=.92, zorder=5)
        if track is not None:
            for sx, sy in _project_ring(track, forward, east, north):
                ax.plot(sx, sy, color="#ffb160", lw=2.6, zorder=6)
    elif track is not None:
        forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
        for sx, sy in _project_ring(track, forward, east, north):
            ax.plot(sx, sy, color="#ffb160", lw=2.6, zorder=6)
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
                            markeredgecolor="white", markeredgewidth=.75)
                    ax.annotate(tr.name, (u,v), xytext=(6,6), textcoords="offset points",
                                fontsize=8, color="white", zorder=10)
    if extent_earth_radii < 1.05:
        raise ValueError("extent_earth_radii must be >= 1.05")
    ax.set(xlim=(-extent_earth_radii, extent_earth_radii), ylim=(-extent_earth_radii, extent_earth_radii), aspect="equal")
    ax.axis("off")
    fig.text(.5, .955, f"{mode.title()} Earth · Orthographic view", color="#e8f4ff", fontsize=15, ha="center", weight="bold")
    fig.text(.5, .035, f"Centered {center_lon_deg:.0f}° longitude, {center_lat_deg:.0f}° latitude  ·  Fully offline",
             color="#8baec4", fontsize=9, ha="center")
    fig.subplots_adjust(left=.015, right=.985, top=.94, bottom=.065)
    fig.savefig(output_path(path), facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=.12)
    plt.close(fig)
