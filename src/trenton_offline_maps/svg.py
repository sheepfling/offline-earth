"""Dependency-free SVG renderer."""
from __future__ import annotations
import base64
from typing import Any, Literal, Sequence
from .geometry import GroundTrack, LonLatInput
from .assets import countries, blue_marble_bytes
from .paths import PathInput, output_path
from .trajectory import EcefTrajectory, ecef_to_geodetic, split_antimeridian

def svg_map(*, width: int = 1200, height: int = 620,
            tracks: Sequence[GroundTrack] | None = None,
            stations: Sequence[LonLatInput] | None = None,
            trajectories: Sequence[EcefTrajectory] | None = None,
            at_s: float | None = None,
            mode: Literal["political", "imagery", "combined"] = "political") -> str:
    """Render self-contained SVG; no web, plotting package, or external asset needed."""
    def xy(lon_deg: float,lat_deg: float) -> tuple[float,float]:
        return ((lon_deg+180)*width/360, (90-lat_deg)*height/180)
    if mode not in ("political", "imagery", "combined"):
        raise ValueError("Unknown Earth display mode")
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#102a43"/>']
    if mode in ("imagery", "combined"):
        data = blue_marble_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        parts.append(f'<image x="0" y="0" width="{width}" height="{height}" '
                     f'preserveAspectRatio="none" href="data:image/jpeg;base64,{encoded}"/>')
    if mode != "imagery":
        for c in countries():
            for ring in c['rings']:
                if len(ring)<3:continue
                pts=' '.join(f'{x:.1f},{y:.1f}' for lon_deg,lat_deg in ring for x,y in [xy(lon_deg,lat_deg)])
                fill = "none" if mode == "combined" else "#d9e2d0"
                stroke = "#ffe0a2" if mode == "combined" else "#5d7385"
                parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="0.65"/>')
    for track in tracks or []:
        # caller should split dateline-crossing paths before passing them
        pts=' '.join(f'{x:.1f},{y:.1f}' for lon_deg,lat_deg in track for x,y in [xy(lon_deg,lat_deg)])
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#ff9e45" stroke-width="2.5"/>')
    if trajectories:
        for tr in trajectories:
            for segment in split_antimeridian(tr.ground_track()):
                pts = ' '.join(f'{x:.1f},{y:.1f}' for lon_deg,lat_deg in segment for x,y in [xy(lon_deg,lat_deg)])
                parts.append(f'<polyline points="{pts}" fill="none" stroke="{tr.color}" stroke-width="2.1"/>')
            marker = tr.samples[-1].position if at_s is None else (
                tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
            if marker is not None:
                geo = ecef_to_geodetic(marker)
                x,y=xy(geo.lon_deg,geo.lat_deg)
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{tr.color}" stroke="white" stroke-width="1.2"/>')
    for lon_deg,lat_deg in stations or []:
        x,y=xy(lon_deg,lat_deg)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#e23d46" stroke="white" stroke-width="1.5"/>')
    parts.append('</svg>')
    return '\n'.join(parts)

def save_svg(path: PathInput, **kwargs: Any) -> None:
    output_path(path).write_text(svg_map(**kwargs),encoding='utf-8')

