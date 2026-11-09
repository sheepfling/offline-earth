"""Presentation-independent, validated input for the offline Canvas renderer."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Sequence
from .assets import CountryBoundaryRing, countries, blue_marble_bytes
from .geometry import Degrees, GroundTrack, ViewMode, VIEW_MODES
from .trajectory import EcefTrajectory
from .constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG

@dataclass(frozen=True)
class CanvasScene:
    """Local assets and caller data; may be consumed by an alternate presentation."""
    imagery_jpeg: bytes
    country_rings_deg: list[list[CountryBoundaryRing]]
    track_deg: GroundTrack
    trajectories: tuple[EcefTrajectory, ...]
    mode: ViewMode
    at_s: float | None
    center_lon_deg: Degrees
    center_lat_deg: Degrees


def load_canvas_scene(*, track: GroundTrack | None = None,
                      trajectories: Sequence[EcefTrajectory] = (),
                      mode: ViewMode = 'combined', at_s: float | None = None,
                      center_lon_deg: Degrees = DEFAULT_CENTER_LON_DEG,
                      center_lat_deg: Degrees = DEFAULT_CENTER_LAT_DEG) -> CanvasScene:
    """Load bundled assets and validate camera/time choices, without writing HTML."""
    if mode not in VIEW_MODES:
        raise ValueError('Unrecognized Earth display mode')
    if not all(isfinite(v) for v in (center_lon_deg, center_lat_deg)) or not -90 <= center_lat_deg <= 90:
        raise ValueError('Invalid camera coordinates')
    if at_s is not None and not isfinite(at_s):
        raise ValueError('at_s must be finite')
    times = [s.t_s for tr in trajectories for s in tr.samples]
    if at_s is not None and times and not min(times) <= at_s <= max(times):
        raise ValueError('at_s outside trajectory time range')
    return CanvasScene(blue_marble_bytes(), [c['rings'] for c in countries()],
                       tuple(track or ()), tuple(trajectories), mode, at_s,
                       center_lon_deg, center_lat_deg)
