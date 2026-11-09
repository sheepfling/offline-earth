"""Public units/path contracts and renderer-independent domain utilities."""

from offline_earth.timeseries import matplotlib_ecef_timeseries
from offline_earth.renderers.matplotlib import matplotlib_world, matplotlib_globe
from offline_earth.renderers.plotly import plotly_globe
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import get_type_hints

import pytest

from offline_earth import EcefTrajectory, save_svg
from offline_earth.canvas import canvas_globe
from offline_earth.constants import EARTH_RADIUS_M, WGS84_A_M, WGS84_B_M
from offline_earth.geometry import (
    Degrees, LonLatDegrees, TimeRangeSeconds, camera_basis, camera_to_world,
    split_antimeridian,
)
from offline_earth.paths import PathInput, input_path, output_path
from offline_earth.trajectory import (
    geodetic_to_ecef, project_orthographic_ecef, read_trajectories, write_trajectories,
)
from offline_earth.visualize import RenderSpec, render_ecef


class UserPath:
    def __init__(self, path):
        self.path = path

    def __fspath__(self):
        return str(self.path)


@pytest.mark.parametrize('backend,extension', [
    ('svg','svg'), ('canvas','html'), ('map','png'), ('globe','png'),
    ('plotly','html'), ('timeseries','png'),
])
def test_all_public_renderers_accept_pathlike_and_create_parent(tmp_path, backend, extension):
    tr = EcefTrajectory.from_arrays('demo', [0, 1], [[7e6,0,0],[7e6,100,100]])
    target = tmp_path / backend / ('result.' + extension)
    # Exercise direct backends too, not only the dispatcher normalization.
    if backend == 'svg':save_svg(UserPath(target), trajectories=[tr])
    elif backend == 'canvas':canvas_globe(UserPath(target), trajectories=[tr])
    elif backend == 'timeseries':
        matplotlib_ecef_timeseries(UserPath(target), [tr])
    else:
        function = {'map':matplotlib_world, 'globe':matplotlib_globe,
                    'plotly':plotly_globe}[backend]
        function(UserPath(target), trajectories=[tr])
    assert target.stat().st_size > 0


def test_path_contract_and_trajectory_io(tmp_path):
    tr = EcefTrajectory.from_arrays('demo', [0], [[7e6,0,0]])
    path = UserPath(tmp_path / 'nested' / 'tracks.json')
    write_trajectories(path, [tr])
    assert read_trajectories(path) == [tr]
    assert isinstance(input_path(path), Path)
    assert isinstance(output_path(path), Path)
    assert get_type_hints(canvas_globe)['path'] == PathInput
    assert get_type_hints(render_ecef)['output'] == PathInput


def test_canvas_import_does_not_depend_on_optional_renderer():
    code = "import sys; import offline_earth.canvas; assert 'offline_earth.earth' not in sys.modules; assert 'numpy' not in sys.modules"
    subprocess.run([sys.executable, '-c', code], check=True)
    assert get_type_hints(canvas_globe)['trajectories']  # No unresolved forward references.


def test_semantic_tracks_keep_tuple_compatibility():
    tr = EcefTrajectory.from_arrays('demo', [0,2], [[7e6,0,0],[0,7e6,0]])
    assert isinstance(tr.time_range, TimeRangeSeconds)
    assert tr.time_range.start_s == 0 and tr.time_range.end_s == 2
    point = tr.ground_track()[0]
    assert isinstance(point, LonLatDegrees) and point.lon_deg == 0
    assert point == (0,0)
    parts = split_antimeridian([(170,0),(175,1),(-178,2),(-170,3)])
    assert parts[0] == [(170,0),(175,1)]
    assert parts[1][0].lon_deg == -178


def test_shared_camera_math_uses_degrees():
    basis = camera_basis(90,0)
    assert basis.forward == pytest.approx((0,1,0))
    assert camera_to_world(0,0,1,basis) == pytest.approx((0,1,0))
    projected = project_orthographic_ecef(geodetic_to_ecef(90,0),90,0)
    assert projected.east_earth_radii == pytest.approx(0,abs=1e-10)
    assert projected.visible
    hints = get_type_hints(RenderSpec,include_extras=True)
    assert hints['center_lon_deg'] == Degrees and hints['center_lat_deg'] == Degrees


def test_canvas_physical_constants_are_serialized_from_shared_source(tmp_path):
    p=tmp_path/'canvas.html'
    canvas_globe(p)
    data=json.loads(p.read_text(encoding='utf-8').split('const earthConstants = ')[1].split(';')[0])
    assert data['radius_m'] == EARTH_RADIUS_M
    assert data['a_m'] == WGS84_A_M and data['b_m'] == WGS84_B_M


def test_canvas_scene_can_use_an_alternate_presentation(tmp_path, monkeypatch):
    from offline_earth.canvas_scene import load_canvas_scene
    from offline_earth.canvas import render_canvas_html
    scene = load_canvas_scene(center_lon_deg=12, center_lat_deg=-20)
    def forbidden(*args, **kwargs):
        raise AssertionError('Presentation must not reload assets')
    monkeypatch.setattr('offline_earth.canvas.files', forbidden)
    html = render_canvas_html(scene, template='<script>const config=__INITIAL_CONFIG__;</script>')
    assert json.loads(html.split('=', 1)[1].split(';', 1)[0])['center_lon_deg'] == 12


def test_camera_vector_return_contract():
    from offline_earth.geometry import Vector3
    assert get_type_hints(camera_to_world)['return'] is Vector3
    assert isinstance(camera_to_world(0, 0, 1, camera_basis(0, 0)), Vector3)


def test_blue_marble_metadata_and_country_ring_semantics():
    from offline_earth.assets import BLUE_MARBLE, countries
    assert (BLUE_MARBLE.width_px, BLUE_MARBLE.height_px) == (5400, 2700)
    assert (BLUE_MARBLE.preview_width_px, BLUE_MARBLE.preview_height_px) == (1800, 900)
    assert BLUE_MARBLE.extent_deg == (-180, 180, -90, 90)
    assert all(ring[0] == ring[-1] for country in countries() for ring in country['rings'])


def test_optional_renderer_imports_are_isolated():
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockMatplotlib(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'matplotlib':
            raise AssertionError('Plotly backend must not import Matplotlib')
sys.meta_path.insert(0, BlockMatplotlib())
import offline_earth.renderers.plotly
assert 'matplotlib' not in sys.modules
"""
    subprocess.run([sys.executable, '-c', code], check=True)
