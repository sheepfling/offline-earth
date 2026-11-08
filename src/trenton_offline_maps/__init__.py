"""Offline-first political border visualization with a zero-dependency SVG core."""
from __future__ import annotations
import json
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Literal
if TYPE_CHECKING:
    from .trajectory import EcefTrajectory

def countries() -> list[dict[str, Any]]:
    """Return bundled simplified Natural Earth country polygon rings in lon/lat degrees."""
    resource = files('trenton_offline_maps').joinpath('data/countries.json')
    return json.loads(resource.read_text(encoding='utf-8'))

def svg_map(*, width: int = 1200, height: int = 620,
            tracks: list[list[tuple[float,float]]] | None = None,
            stations: list[tuple[float,float]] | None = None,
            trajectories: list["EcefTrajectory"] | None = None,
            at_s: float | None = None,
            mode: Literal["political", "imagery", "combined"] = "political") -> str:
    """Render self-contained SVG; no web, plotting package, or external asset needed."""
    def xy(lon: float,lat: float) -> tuple[float,float]:
        return ((lon+180)*width/360, (90-lat)*height/180)
    if mode not in ("political", "imagery", "combined"):
        raise ValueError("Unknown Earth display mode")
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#102a43"/>']
    if mode in ("imagery", "combined"):
        import base64
        data = files("trenton_offline_maps").joinpath("data/blue_marble.jpg").read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        parts.append(f'<image x="0" y="0" width="{width}" height="{height}" '
                     f'preserveAspectRatio="none" href="data:image/jpeg;base64,{encoded}"/>')
    if mode != "imagery":
        for c in countries():
            for ring in c['rings']:
                if len(ring)<3:continue
                pts=' '.join(f'{x:.1f},{y:.1f}' for lon,lat in ring for x,y in [xy(lon,lat)])
                fill = "none" if mode == "combined" else "#d9e2d0"
                stroke = "#ffe0a2" if mode == "combined" else "#5d7385"
                parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="0.65"/>')
    for track in tracks or []:
        # caller should split dateline-crossing paths before passing them
        pts=' '.join(f'{x:.1f},{y:.1f}' for lon,lat in track for x,y in [xy(lon,lat)])
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#ff9e45" stroke-width="2.5"/>')
    if trajectories:
        from .trajectory import ecef_to_geodetic, split_antimeridian
        for tr in trajectories:
            for segment in split_antimeridian(tr.ground_track()):
                pts = ' '.join(f'{x:.1f},{y:.1f}' for lon,lat in segment for x,y in [xy(lon,lat)])
                parts.append(f'<polyline points="{pts}" fill="none" stroke="{tr.color}" stroke-width="2.1"/>')
            marker = tr.samples[-1].position if at_s is None else (
                tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
            if marker is not None:
                geo = ecef_to_geodetic(marker)
                x,y=xy(geo.lon_deg,geo.lat_deg)
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{tr.color}" stroke="white" stroke-width="1.2"/>')
    for lon,lat in stations or []:
        x,y=xy(lon,lat)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#e23d46" stroke="white" stroke-width="1.5"/>')
    parts.append('</svg>')
    return '\n'.join(parts)

def save_svg(path: str, **kwargs: Any) -> None:
    from pathlib import Path
    Path(path).write_text(svg_map(**kwargs),encoding='utf-8')

from .trajectory import (
    EcefPosition, EcefSample, EcefTrajectory, GeodeticPosition,
    ecef_to_geodetic, geodetic_to_ecef, read_trajectories, write_trajectories,
)

__all__ = [
    "EcefPosition", "EcefSample", "EcefTrajectory", "GeodeticPosition",
    "ecef_to_geodetic", "geodetic_to_ecef", "read_trajectories",
    "write_trajectories", "countries", "save_svg", "svg_map",
]
