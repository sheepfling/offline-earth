"""Purely offline Earth visualization: bundled texture and political boundaries.

Computations use a spherical Earth for display, not precision navigation.
All image/geometry assets are loaded from the installed wheel.
"""
from __future__ import annotations

from io import BytesIO
from math import cos, pi, radians, sin
from .paths import PathInput, output_path
from .geometry import Degrees, GroundTrack
from .constants import (DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII)
from typing import Literal, Sequence
from .trajectory import EcefTrajectory, ecef_to_geodetic, geodetic_to_ecef, project_orthographic_ecef

from .assets import countries

from .assets import blue_marble_bytes
from .constants import (EARTH_RADIUS_KM, METRES_PER_KM, WGS84_A_M, WGS84_E2,
                        TEXTURE_WIDTH_PX, TEXTURE_HEIGHT_PX, ORTHOGRAPHIC_EXTENT)
from .geometry import Vector3, LonLatDegrees, camera_basis, camera_to_world, split_antimeridian
from .geometry import ViewMode
Track = GroundTrack


def sphere_xyz(lon_deg: float, lat_deg: float, radius: float = EARTH_RADIUS_KM) -> Vector3:
    lon, lat = radians(lon_deg), radians(lat_deg)
    return Vector3(radius * cos(lat) * cos(lon), radius * cos(lat) * sin(lon), radius * sin(lat))


def demo_ground_track(samples: int = 240, inclination_deg: Degrees = 51.6) -> list[LonLatDegrees]:
    """Synthetic illustrative track, NOT derived from orbital propagation."""
    if samples < 2:
        raise ValueError("samples must be at least 2")
    return [LonLatDegrees(-180 + 360 * i / (samples - 1), inclination_deg * sin(4 * pi * i / (samples - 1))) for i in range(samples)]


def _texture_rgb() -> "np.ndarray":
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(BytesIO(blue_marble_bytes())).convert("RGB"))


def matplotlib_world(
    path: PathInput,
    *,
    mode: ViewMode = "combined",
    track: Track | None = None,
    title: str | None = None,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
) -> None:
    """Render a 2D equirectangular world map as PNG/SVG/PDF through Matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    if mode not in ("imagery", "political", "combined"):
        raise ValueError(f"Unknown mode: {mode!r}")
    fig, ax = plt.subplots(figsize=(14.4, 7.5), dpi=140)
    fig.patch.set_facecolor("#071522")
    ax.set_facecolor("#143454")
    if mode in ("imagery", "combined"):
        ax.imshow(_texture_rgb(), extent=(-180, 180, -90, 90), origin="upper", zorder=0, interpolation="bilinear")
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


def _political_mask() -> "np.ndarray":
    """Rasterize bundled vector land geometry for fast orthographic shading."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h = TEXTURE_WIDTH_PX, TEXTURE_HEIGHT_PX
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    for c in countries():
        for ring in c["rings"]:
            if len(ring) >= 3:
                draw.polygon([((lon + 180) * w / 360, (90 - lat) * h / 180) for lon, lat in ring], fill=255)
    return np.asarray(image)


def orthographic_rgb(
    *,
    mode: ViewMode = "combined",
    center_lon: Degrees = DEFAULT_CENTER_LON_DEG,
    center_lat: Degrees = DEFAULT_CENTER_LAT_DEG,
    size: int = 800,
) -> "np.ndarray":
    """Project local imagery to RGBA. center_lon and center_lat are degrees."""
    import numpy as np
    if mode not in ("imagery", "political", "combined"):
        raise ValueError(mode)
    if size < 64 or size > 4096:
        raise ValueError("size must be in 64..4096")
    u, v = np.meshgrid(np.linspace(-ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT, size), np.linspace(ORTHOGRAPHIC_EXTENT, -ORTHOGRAPHIC_EXTENT, size))
    valid = u*u + v*v <= 1
    depth = np.sqrt(np.clip(1 - u*u - v*v, 0, 1))
    x, y, z = camera_to_world(u, v, depth, camera_basis(center_lon, center_lat))
    lon = np.arctan2(y, x)
    lat = np.arcsin(np.clip(z, -1, 1))
    if mode == "political":
        mask = _political_mask()
        h, w = mask.shape
        ix = np.clip(((lon + pi) / (2*pi) * (w-1)).astype(int), 0, w-1)
        iy = np.clip(((pi/2 - lat)/pi * (h-1)).astype(int), 0, h-1)
        land = mask[iy, ix] > 127
        rgb = np.where(land[..., None], [159, 188, 165], [18, 69, 109]).astype(np.uint8)
    else:
        texture = _texture_rgb()
        h, w = texture.shape[:2]
        ix = np.clip(((lon + pi)/(2*pi) * (w-1)).astype(int), 0, w-1)
        iy = np.clip(((pi/2 - lat)/pi * (h-1)).astype(int), 0, h-1)
        rgb = texture[iy, ix]
    # Gentle spherical shading for legibility; illustrative illumination, not solar ephemeris.
    light = .68 + .32*np.clip(.8*depth + .3*u + .2*v, 0, 1)
    rgb = np.clip(rgb.astype(float) * light[..., None], 0, 255).astype(np.uint8)
    rgba = np.empty((size, size, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = np.where(valid, 255, 0)
    return rgba


def _project_ring(
    ring: GroundTrack,
    forward: Vector3, east: Vector3, north: Vector3,
) -> list[tuple[list[float], list[float]]]:
    """Split orthographic boundary paths at the horizon (simple visible-segment clipping)."""
    import numpy as np
    if not ring:
        return []
    lon = np.radians(np.array([p[0] for p in ring], dtype=float))
    lat = np.radians(np.array([p[1] for p in ring], dtype=float))
    xyz = np.column_stack((np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)))
    visibility = xyz @ forward > 0.002
    u, v = xyz @ east, xyz @ north
    segments: list[tuple[list[float], list[float]]] = []
    sx: list[float] = []
    sy: list[float] = []
    for k, visible in enumerate(visibility):
        if visible:
            sx.append(float(u[k])); sy.append(float(v[k]))
        else:
            if len(sx) > 1:
                segments.append((sx, sy))
            sx, sy = [], []
    if len(sx) > 1:
        segments.append((sx, sy))
    return segments


def matplotlib_globe(
    path: PathInput,
    *,
    mode: ViewMode = "combined",
    center_lon: Degrees = DEFAULT_CENTER_LON_DEG,
    center_lat: Degrees = DEFAULT_CENTER_LAT_DEG,
    track: Track | None = None,
    size: int = 780,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
    extent_earth_radii: float = 1.33,
) -> None:
    """Render a Blue Marble orthographic globe with optional vector borders and tracks."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    rgba = orthographic_rgb(mode=mode, center_lon=center_lon, center_lat=center_lat, size=size)
    fig, ax = plt.subplots(figsize=(8.6, 8.8), dpi=140)
    fig.patch.set_facecolor("#071522")
    ax.set_facecolor("#071522")
    ax.imshow(rgba, extent=(-ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT, -ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT), interpolation="bilinear", zorder=2)
    ax.add_patch(Circle((0, 0), 1, fill=False, color="#69a9d4", alpha=.5, lw=1.3, zorder=4))
    if mode in ("political", "combined"):
        forward, east, north = camera_basis(center_lon, center_lat)
        for c in countries():
            for ring in c["rings"]:
                for sx, sy in _project_ring(ring, forward, east, north):
                    ax.plot(sx, sy, color="#fff0c2" if mode == "combined" else "#2c5364", lw=.65, alpha=.92, zorder=5)
        if track is not None:
            for sx, sy in _project_ring(track, forward, east, north):
                ax.plot(sx, sy, color="#ffb160", lw=2.6, zorder=6)
    elif track is not None:
        forward, east, north = camera_basis(center_lon, center_lat)
        for sx, sy in _project_ring(track, forward, east, north):
            ax.plot(sx, sy, color="#ffb160", lw=2.6, zorder=6)
    if trajectories:
        for tr in trajectories:
            px: list[float] = []; py: list[float] = []
            for sample in tr.samples:
                u, v, visible = project_orthographic_ecef(
                    sample.position, center_lon, center_lat)
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
                u, v, visible = project_orthographic_ecef(marker, center_lon, center_lat)
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
    fig.text(.5, .035, f"Centered {center_lon:.0f}° longitude, {center_lat:.0f}° latitude  ·  Fully offline",
             color="#8baec4", fontsize=9, ha="center")
    fig.subplots_adjust(left=.015, right=.985, top=.94, bottom=.065)
    fig.savefig(output_path(path), facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=.12)
    plt.close(fig)


def plotly_globe(
    path: PathInput,
    *,
    track: Track | None = None,
    include_imagery: bool = True,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
) -> None:
    """Self-contained interactive 3D globe with three toggleable visualization modes.

    Uses Pillow color quantization to encode the local RGB raster as a Plotly
    surface colorscale. The HTML embeds all JS and all geometry; no CDN.
    """
    import numpy as np
    from PIL import Image
    import plotly.graph_objects as go

    with Image.open(BytesIO(blue_marble_bytes())) as im:
        small = im.convert("RGB").resize((180, 91), Image.Resampling.BILINEAR)
        indexed = small.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        colors = indexed.getpalette()[:384]
        ids = np.asarray(indexed, dtype=np.uint8)
    scale = [[i / 127, f"rgb({colors[i*3]},{colors[i*3+1]},{colors[i*3+2]})"] for i in range(128)]
    lat = np.linspace(pi/2, -pi/2, 91)
    lon = np.linspace(-pi, pi, 180)
    lon2, lat2 = np.meshgrid(lon, lat)
    n = WGS84_A_M / np.sqrt(1 - WGS84_E2 * np.sin(lat2)**2)
    x = n * np.cos(lat2)*np.cos(lon2) / METRES_PER_KM
    y = n * np.cos(lat2)*np.sin(lon2) / METRES_PER_KM
    z = n * (1-WGS84_E2) * np.sin(lat2) / METRES_PER_KM
    fig = go.Figure()
    fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=ids.astype(float),
                             cmin=0, cmax=127, colorscale=scale, showscale=False,
                             hoverinfo="skip", lighting=dict(ambient=.8, diffuse=.7), name="Blue Marble", visible=include_imagery))
    fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=np.zeros_like(x),
                             cmin=0, cmax=1, colorscale=[[0, "#1a527b"], [1, "#1a527b"]],
                             showscale=False, hoverinfo="skip", name="Political", visible=not include_imagery))
    # Group borders into one trace, rather than one trace for each of 177 countries.
    bx: list[float | None] = []; by: list[float | None] = []; bz: list[float | None] = []
    for c in countries():
        for ring in c["rings"]:
            for llon, llat in ring:
                ecef = geodetic_to_ecef(llon, llat, 7_000.0)
                bx.append(ecef.x_m / METRES_PER_KM); by.append(ecef.y_m / METRES_PER_KM);
                bz.append(ecef.z_m / METRES_PER_KM)
            bx.append(None); by.append(None); bz.append(None)
    fig.add_trace(go.Scatter3d(x=bx, y=by, z=bz, mode="lines", name="Political borders",
                               line=dict(color="#fce3a3", width=2), hoverinfo="skip", visible=True))
    if track is not None:
        xx: list[float | None] = []; yy: list[float | None] = []; zz: list[float | None] = []
        for segment in split_antimeridian(track):
            for lon_deg, lat_deg in segment:
                ecef = geodetic_to_ecef(lon_deg, lat_deg, 95_000.0)
                xx.append(ecef.x_m / METRES_PER_KM); yy.append(ecef.y_m / METRES_PER_KM);
                zz.append(ecef.z_m / METRES_PER_KM)
            xx.append(None); yy.append(None); zz.append(None)
        fig.add_trace(go.Scatter3d(x=xx, y=yy, z=zz, mode="lines", name="Illustrative track",
                                   line=dict(color="#ffab58", width=6), hoverinfo="skip"))
    # True 3D ECEF paths in kilometres (NOT draped ground tracks).
    for tr in trajectories:
        xx = [s.position.x_m / METRES_PER_KM for s in tr.samples]
        yy = [s.position.y_m / METRES_PER_KM for s in tr.samples]
        zz = [s.position.z_m / METRES_PER_KM for s in tr.samples]
        fig.add_trace(go.Scatter3d(x=xx, y=yy, z=zz, mode="lines", name=tr.name,
                                   line=dict(color=tr.color, width=5),
                                   text=[f"{s.t_s:.1f} s" for s in tr.samples],
                                   hovertemplate=f"{tr.name}: %{{text}}<br>ECEF km: (%{{x:.1f}}, %{{y:.1f}}, %{{z:.1f}})<extra></extra>"))
        marker = tr.samples[-1].position if at_s is None else (
            tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
        if marker is not None:
            fig.add_trace(go.Scatter3d(
                x=[marker.x_m / METRES_PER_KM], y=[marker.y_m / METRES_PER_KM], z=[marker.z_m / METRES_PER_KM],
                mode="markers+text", name=f"{tr.name} position", text=[tr.name],
                textposition="top center", marker=dict(color=tr.color, size=5),
            ))
    count = len(fig.data)
    buttons = [
        dict(label="Blue Marble", method="update", args=[{"visible": [True, False, False] + [True]*(count-3)}]),
        dict(label="Political", method="update", args=[{"visible": [False, True, True] + [True]*(count-3)}]),
        dict(label="Both", method="update", args=[{"visible": [True, False, True] + [True]*(count-3)}]),
    ]
    fig.update_layout(template="plotly_dark", title="Offline Earth · Switch: Imagery / Political / Both",
                      paper_bgcolor="#061522", plot_bgcolor="#061522", showlegend=True,
                      scene=dict(aspectmode="data", xaxis=dict(visible=False), yaxis=dict(visible=False),
                                 zaxis=dict(visible=False), bgcolor="#061522"),
                      updatemenus=[dict(type="buttons", direction="right", buttons=buttons,
                                       x=.03, y=1.08, xanchor="left", bgcolor="#29445e", font=dict(color="#fff"))],
                      margin=dict(l=5, r=5, b=5, t=95))
    fig.write_html(str(output_path(path)), include_plotlyjs=True, full_html=True, auto_open=False)
