"""Named domain values, iterable inputs, and coordinate module boundaries."""
from dataclasses import FrozenInstanceError, is_dataclass
import subprocess
import sys
from typing import get_args, get_type_hints

import pytest

from offline_earth import EcefPosition, EcefSample, EcefTrajectory
from offline_earth.assets import BLUE_MARBLE, GeographicExtentDegrees
from offline_earth.geometry import VIEW_MODES, ViewMode
from offline_earth.trajectory import read_trajectories, write_trajectories


def test_extent_names_preserve_unpacking_and_asset_dataclass():
    extent = BLUE_MARBLE.extent_deg
    assert isinstance(extent, GeographicExtentDegrees)
    assert (extent.west_deg, extent.east_deg, extent.south_deg, extent.north_deg) == (
        -180, 180, -90, 90)
    assert tuple(extent) == (-180, 180, -90, 90)
    assert is_dataclass(BLUE_MARBLE)


def test_indexed_texture_names_preserve_unpacking():
    from offline_earth.renderers.blue_marble import IndexedTexture, indexed_texture
    texture = indexed_texture()
    assert isinstance(texture, IndexedTexture)
    indices, colorscale = texture
    assert indices is texture.indices and colorscale is texture.colorscale
    assert indices.shape == (91, 180)
    assert len(colorscale) == 128
    assert int(indices.max()) < len(colorscale)
    assert get_type_hints(indexed_texture)['return'] is IndexedTexture


def test_view_modes_derive_from_literal():
    assert VIEW_MODES == get_args(ViewMode)
    from offline_earth.svg import svg_map
    assert get_type_hints(svg_map)['mode'] == ViewMode


@pytest.mark.parametrize('renderer', ['svg', 'canvas', 'raster'])
def test_renderers_reject_unknown_mode(renderer):
    from offline_earth.svg import svg_map
    from offline_earth.canvas_scene import load_canvas_scene
    from offline_earth.renderers.raster import orthographic_rgb
    function = {'svg': svg_map, 'canvas': load_canvas_scene, 'raster': orthographic_rgb}[renderer]
    with pytest.raises(ValueError):
        function(mode='unknown')


def test_generators_and_nested_iterators_are_accepted():
    times = (t for t in [0, 2])
    rows = (iter(row) for row in [(1, 2, 3), (3, 4, 5)])
    track = EcefTrajectory.from_arrays('iterable', times, rows)
    assert track.at(1) == EcefPosition(2, 3, 4)


@pytest.mark.parametrize('times,rows', [
    ([0, 1], [(1, 2, 3)]), ([0], [(1, 2, 3), (4, 5, 6)]),
    ([], [(1, 2, 3)]), ([0], []),
])
def test_generators_cannot_silently_truncate(times, rows):
    with pytest.raises(ValueError, match='lengths must match'):
        EcefTrajectory.from_arrays('bad', iter(times), iter(rows))


@pytest.mark.parametrize('row', [[], [1, 2], [1, 2, 3, 4]])
def test_iterable_rows_validate_coordinate_count(row):
    with pytest.raises(ValueError, match='contain x,y,z'):
        EcefTrajectory.from_arrays('bad', iter([0]), iter([iter(row)]))


def test_trajectory_copies_mutable_sample_collection():
    samples = [EcefSample(0, EcefPosition(1, 2, 3))]
    track = EcefTrajectory('safe', samples)
    samples.clear()
    assert isinstance(track.samples, tuple) and len(track.samples) == 1
    with pytest.raises(FrozenInstanceError):
        track.samples = ()
    with pytest.raises(TypeError, match='EcefSample'):
        EcefTrajectory('bad', [object()])


@pytest.mark.parametrize('extension', ['json', 'csv'])
def test_read_returns_editable_collection_of_immutable_tracks(tmp_path, extension):
    path = tmp_path / ('tracks.' + extension)
    track = EcefTrajectory.from_arrays('safe', [0], [(1, 2, 3)])
    if extension == 'json':
        write_trajectories(path, [track])
    else:
        path.write_text('name,time_s,x_m,y_m,z_m\nsafe,0,1,2,3\n', encoding='utf-8')
    tracks = read_trajectories(path)
    assert tracks == [track] and isinstance(tracks, list)
    tracks.append(track)
    tracks.reverse()
    tracks.pop()
    assert tracks == [track]
    assert isinstance(tracks[0].samples, tuple)


def test_geodesy_preserves_legacy_public_imports():
    import offline_earth
    from offline_earth import geodesy, trajectory
    for name in ('EcefPosition', 'GeodeticPosition', 'ecef_to_geodetic', 'geodetic_to_ecef'):
        assert getattr(offline_earth, name) is getattr(geodesy, name)
        assert getattr(trajectory, name) is getattr(geodesy, name)
    assert trajectory.project_orthographic_ecef is geodesy.project_orthographic_ecef


def test_geodesy_has_no_optional_dependencies():
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockOptional(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'PIL', 'matplotlib', 'plotly'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, BlockOptional())
from offline_earth.geodesy import geodetic_to_ecef, ecef_to_geodetic
assert ecef_to_geodetic(geodetic_to_ecef(0, 0)).height_m == 0
"""
    subprocess.run([sys.executable, '-c', code], check=True)


@pytest.mark.parametrize('size', [63, 4097])
def test_raster_output_size_budget_is_independent_of_texture(monkeypatch, size):
    from offline_earth.renderers import raster
    def forbidden():
        raise AssertionError('Invalid output size must fail before decoding imagery')
    monkeypatch.setattr(raster, 'texture_rgb', forbidden)
    with pytest.raises(ValueError, match='size'):
        raster.orthographic_rgb(size=size)
