"""Shared WGS84 geometry and explicit meter/kilometer display conversions."""
import json
from typing import Final, get_type_hints

import matplotlib.pyplot as plt
import numpy as np
import pytest

from offline_earth import constants, geodesy
from offline_earth.renderers import plotly as renderer
from offline_earth.renderers.blue_marble import IndexedTexture
from offline_earth.timeseries import matplotlib_ecef_timeseries
from offline_earth.trajectory import EcefTrajectory, read_trajectories, write_trajectories


def test_physical_and_display_constants_are_final_and_units_are_reciprocal():
    numeric_constants = {
        name for name, value in vars(constants).items()
        if name.isupper() and isinstance(value, (int, float))
    }
    hints = get_type_hints(constants)
    assert all(hints[name] == Final[float] for name in numeric_constants)
    assert constants.METERS_PER_KM == 1000.0
    assert constants.KM_PER_METERS == 0.001
    assert constants.METERS_PER_KM * constants.KM_PER_METERS == 1.0
    assert constants.EARTH_RADIUS_KM == 6371.0
    assert constants.EARTH_SPIN_RAD_S == 7.292115e-5


def test_surface_component_grids_have_semantic_names():
    surface = renderer._surface_coordinates_km((3, 5))
    assert isinstance(surface, renderer.SurfaceCoordinatesKm)
    x, y, z = surface
    assert x is surface.x_km and y is surface.y_km and z is surface.z_km
    assert x.shape == y.shape == z.shape == (3, 5)


@pytest.mark.parametrize('shape,color_count', [((3, 5), 3), ((6, 8), 5)])
def test_plotly_surface_uses_shared_geodesy_and_texture_dimensions(
    tmp_path, monkeypatch, shape, color_count,
):
    indices = np.arange(np.prod(shape), dtype=np.uint8).reshape(shape) % color_count
    scale = [[i / (color_count - 1), f'rgb({i * 20},0,0)'] for i in range(color_count)]
    monkeypatch.setattr(renderer, 'indexed_texture', lambda: IndexedTexture(indices, scale))
    monkeypatch.setattr(renderer, 'countries', lambda: [])
    assert renderer.geodetic_to_ecef is geodesy.geodetic_to_ecef
    calls = []

    def shared_conversion(lon_deg, lat_deg, height_m=0.0):
        calls.append((lon_deg, lat_deg, height_m))
        return geodesy.geodetic_to_ecef(lon_deg, lat_deg, height_m)

    monkeypatch.setattr(renderer, 'geodetic_to_ecef', shared_conversion)
    target = tmp_path / 'unused.html'
    fig = renderer.plotly_globe(target, post_plot=lambda fig, **kwargs: fig)
    assert not target.exists()
    assert calls == [
        (lon_deg, lat_deg, 0.0)
        for lat_deg in np.linspace(90.0, -90.0, shape[0])
        for lon_deg in np.linspace(-180.0, 180.0, shape[1])
    ]
    imagery, political = fig.data[:2]
    assert imagery.cmin == 0 and imagery.cmax == color_count - 1
    assert len(imagery.colorscale) == color_count
    np.testing.assert_array_equal(imagery.surfacecolor, indices)
    expected = np.array([
        [(point.x_m, point.y_m, point.z_m) for point in (
            geodesy.geodetic_to_ecef(lon_deg, lat_deg)
            for lon_deg in np.linspace(-180.0, 180.0, shape[1])
        )]
        for lat_deg in np.linspace(90.0, -90.0, shape[0])
    ]) * 0.001
    for surface in (imagery, political):
        for component, key in enumerate(('x', 'y', 'z')):
            assert np.asarray(surface[key]).shape == shape
            np.testing.assert_allclose(surface[key], expected[:, :, component], atol=1e-10)
    # Independent WGS84 reference axes catch a wrong shared scale or radius.
    assert imagery.z[0, 0] == pytest.approx(6356.752314245179, abs=1e-9)
    assert imagery.z[-1, 0] == pytest.approx(-6356.752314245179, abs=1e-9)
    if shape == (3, 5):
        assert imagery.x[1, 2] == pytest.approx(6378.137, abs=1e-9)
        assert imagery.y[1, 3] == pytest.approx(6378.137, abs=1e-9)


@pytest.mark.parametrize('at_s,marker_km', [
    (None, (7100.0, -4.0, 9.0)),
    (1.0, (7050.0, -3.0, 6.0)),
    (3.0, None),
])
def test_plotly_converts_all_ecef_layers_to_kilometers(tmp_path, monkeypatch, at_s, marker_km):
    monkeypatch.setattr(renderer, 'indexed_texture', lambda: IndexedTexture(
        np.zeros((3, 5), dtype=np.uint8), [[0, 'black'], [1, 'white']],
    ))
    ring = [(-45.0, 60.0), (25.0, -30.0)]
    monkeypatch.setattr(renderer, 'countries', lambda: [{'rings': [ring]}])
    trajectory = EcefTrajectory.from_arrays(
        'sample', [0, 2], [(7_000_000, -2000, 3000), (7_100_000, -4000, 9000)],
    )
    fig = renderer.plotly_globe(
        tmp_path / 'unused.html', track=ring, trajectories=[trajectory], at_s=at_s,
        post_plot=lambda fig, **kwargs: fig,
    )
    traces = {trace.name: trace for trace in fig.data}
    for name, height_m in [('Political borders', 7000.0), ('Illustrative track', 95_000.0)]:
        trace = traces[name]
        assert (trace.x[-1], trace.y[-1], trace.z[-1]) == (None, None, None)
        actual = list(zip(trace.x[:-1], trace.y[:-1], trace.z[:-1]))
        expected = []
        for lon_deg, lat_deg in ring:
            point = geodesy.geodetic_to_ecef(lon_deg, lat_deg, height_m)
            expected.append((point.x_m * 0.001, point.y_m * 0.001, point.z_m * 0.001))
        np.testing.assert_allclose(actual, expected, atol=1e-10)
    trace = traces['sample']
    np.testing.assert_allclose(list(zip(trace.x, trace.y, trace.z)),
                               [(7000.0, -2.0, 3.0), (7100.0, -4.0, 9.0)])
    if marker_km is None:
        assert 'sample position' not in traces
    else:
        marker = traces['sample position']
        assert (marker.x[0], marker.y[0], marker.z[0]) == pytest.approx(marker_km)


@pytest.mark.parametrize('unit,factor', [('m', 1.0), ('km', 0.001)])
def test_timeseries_units_scale_all_components_and_keep_timestamps(tmp_path, unit, factor):
    xyz_m = np.array([(7_000_000, -2000, 3000), (7_100_000, -4000, 9000)])
    trajectory = EcefTrajectory.from_arrays('sample', [0, 2], xyz_m)
    target = tmp_path / 'unused.png'
    fig = matplotlib_ecef_timeseries(
        target, [trajectory], unit=unit, post_plot=lambda fig, **kwargs: fig,
    )
    try:
        assert not target.exists()
        for component, (axis, name) in enumerate(zip(fig.axes, ('X', 'Y', 'Z'))):
            np.testing.assert_array_equal(axis.lines[0].get_xdata(), [0, 2])
            np.testing.assert_allclose(axis.lines[0].get_ydata(), xyz_m[:, component] * factor)
            assert axis.get_ylabel() == f'ECEF {name} ({unit})'
    finally:
        plt.close(fig)


def test_json_serializes_meters_and_preserves_coordinates(tmp_path):
    trajectory = EcefTrajectory.from_arrays('sample', [0], [(7_000_000, -2000, 3000)])
    target = tmp_path / 'trajectory.json'
    write_trajectories(target, [trajectory])
    assert json.loads(target.read_text(encoding='utf-8'))['units'] == 'meters'
    assert read_trajectories(target) == [trajectory]


def test_user_facing_docs_and_examples_use_meter_spelling(pytestconfig):
    root = pytestconfig.rootpath
    paths = [root / "README.md", *root.joinpath("docs").rglob("*.md"),
             *root.joinpath("examples").rglob("*.html"),
             *root.joinpath("examples/data").glob("*.json")]
    for path in paths:
        assert "metre" not in path.read_text(encoding="utf-8").lower(), path
