"""Render validated local scene data with a bundled, replaceable HTML template."""
from __future__ import annotations
import base64
import json
import re
from importlib.resources import files
from typing import Sequence
from .assets import BLUE_MARBLE
from .canvas_scene import CanvasScene, load_canvas_scene
from .paths import PathInput, output_path
from .geometry import Degrees, GroundTrack, ViewMode
from .trajectory import EcefTrajectory
from .constants import (DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG,
                        EARTH_RADIUS_M, WGS84_A_M, WGS84_B_M)

def _script_json(value: object) -> str:
    """Serialize JSON for an inline script, not an HTML attribute or executable code.

    json.dumps handles JSON quoting; these escapes prevent HTML's parser from
    interpreting script terminators or markup, including nested caller data.
    """
    encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
    return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_canvas_html(scene: CanvasScene, *, template: str | None = None) -> str:
    """Present an already-loaded scene; custom templates use the same data slots."""
    if template is None:
        template = files('trenton_offline_maps').joinpath('templates/canvas.html').read_text(encoding='utf-8')
    config = dict(mode=scene.mode, at_s=scene.at_s, center_lon_deg=scene.center_lon_deg,
                  center_lat_deg=scene.center_lat_deg)
    constants = dict(radius_m=EARTH_RADIUS_M, a_m=WGS84_A_M, b_m=WGS84_B_M,
                     texture_width=BLUE_MARBLE.preview_width_px, texture_height=BLUE_MARBLE.preview_height_px)
    ecef = [{'name': tr.name, 'color': tr.color, 'samples': [
        [sm.t_s, sm.position.x_m, sm.position.y_m, sm.position.z_m]
        for sm in tr.samples]} for tr in scene.trajectories]
    replacements = {
        '__EARTH_CONSTANTS__': _script_json(constants),
        '__INITIAL_CONFIG__': _script_json(config),
        '__BLUE_MARBLE_BASE64__': base64.b64encode(scene.imagery_jpeg).decode('ascii'),
        '__BORDERS_JSON__': _script_json(scene.country_rings_deg),
        '__TRACK_JSON__': _script_json(list(scene.track_deg)),
        '__ECEF_JSON__': _script_json(ecef),
    }
    # One pass: caller data containing a token must never be substituted again.
    return re.sub('|'.join(re.escape(token) for token in replacements),
                  lambda match: replacements[match.group()], template)


def canvas_globe(path: PathInput, *, track: GroundTrack | None = None,
                 trajectories: Sequence[EcefTrajectory] = (),
                 mode: ViewMode = 'combined', at_s: float | None = None,
                 center_lon_deg: Degrees = DEFAULT_CENTER_LON_DEG,
                 center_lat_deg: Degrees = DEFAULT_CENTER_LAT_DEG) -> None:
    """Write a self-contained HTML globe from local data; camera angles are degrees."""
    scene = load_canvas_scene(track=track, trajectories=trajectories, mode=mode,
                              at_s=at_s, center_lon_deg=center_lon_deg,
                              center_lat_deg=center_lat_deg)
    output_path(path).write_text(render_canvas_html(scene), encoding='utf-8')
