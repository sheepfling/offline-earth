"""NumPy/Pillow raster projection shared by optional plotting backends."""
from __future__ import annotations

from math import pi

import numpy as np
from PIL import Image, ImageDraw

from ..assets import BLUE_MARBLE, countries
from ..constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG
from ..geometry import Degrees, GroundTrack, Vector3, ViewMode, camera_basis
from .blue_marble import texture_rgb

ORTHOGRAPHIC_EXTENT = 1.06


def _political_mask() -> np.ndarray:
    """Rasterize bundled vector land geometry for fast orthographic shading."""
    w, h = BLUE_MARBLE.preview_width_px, BLUE_MARBLE.preview_height_px
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    for c in countries():
        for ring in c["rings"]:
            if len(ring) >= 3:
                draw.polygon([((lon_deg + 180) * w / 360, (90 - lat_deg) * h / 180) for lon_deg, lat_deg in ring], fill=255)
    return np.asarray(image)

def orthographic_rgb(
    *,
    mode: ViewMode = "combined",
    center_lon_deg: Degrees = DEFAULT_CENTER_LON_DEG,
    center_lat_deg: Degrees = DEFAULT_CENTER_LAT_DEG,
    size: int = 800,
) -> np.ndarray:
    """Project local imagery to RGBA. center_lon_deg and center_lat_deg are degrees."""
    if mode not in ("imagery", "political", "combined"):
        raise ValueError(mode)
    if size < 64 or size > 4096:
        raise ValueError("size must be in 64..4096")
    u, v = np.meshgrid(np.linspace(-ORTHOGRAPHIC_EXTENT, ORTHOGRAPHIC_EXTENT, size), np.linspace(ORTHOGRAPHIC_EXTENT, -ORTHOGRAPHIC_EXTENT, size))
    valid = u*u + v*v <= 1
    depth = np.sqrt(np.clip(1 - u*u - v*v, 0, 1))
    forward, east, north = camera_basis(center_lon_deg, center_lat_deg)
    x = forward.x * depth + east.x * u + north.x * v
    y = forward.y * depth + east.y * u + north.y * v
    z = forward.z * depth + east.z * u + north.z * v
    lon_rad = np.arctan2(y, x)
    lat_rad = np.arcsin(np.clip(z, -1, 1))
    if mode == "political":
        mask = _political_mask()
        h, w = mask.shape
        ix = np.clip(((lon_rad + pi) / (2*pi) * (w-1)).astype(int), 0, w-1)
        iy = np.clip(((pi/2 - lat_rad)/pi * (h-1)).astype(int), 0, h-1)
        land = mask[iy, ix] > 127
        rgb = np.where(land[..., None], [159, 188, 165], [18, 69, 109]).astype(np.uint8)
    else:
        texture = texture_rgb()
        h, w = texture.shape[:2]
        ix = np.clip(((lon_rad + pi)/(2*pi) * (w-1)).astype(int), 0, w-1)
        iy = np.clip(((pi/2 - lat_rad)/pi * (h-1)).astype(int), 0, h-1)
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
    if not ring:
        return []
    lon_rad = np.radians(np.array([p[0] for p in ring], dtype=float))
    lat_rad = np.radians(np.array([p[1] for p in ring], dtype=float))
    xyz = np.column_stack((np.cos(lat_rad)*np.cos(lon_rad), np.cos(lat_rad)*np.sin(lon_rad), np.sin(lat_rad)))
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
