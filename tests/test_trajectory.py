"""ECEF geometry, time consistency, and local-file adapter contract tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from trenton_offline_maps.visualize import RenderSpec, render_ecef
from trenton_offline_maps import save_svg, svg_map
from trenton_offline_maps.canvas import canvas_globe
from trenton_offline_maps.earth import matplotlib_globe, matplotlib_world, plotly_globe
from trenton_offline_maps.timeseries import matplotlib_ecef_timeseries
from test_rendering_offline import _Assets

import csv
import math
import socket
import os
import subprocess
import sys
from pathlib import Path

import pytest

from trenton_offline_maps.trajectory import (
    EcefPosition, EcefTrajectory, ecef_to_geodetic, geodetic_to_ecef,
    project_orthographic_ecef, read_trajectories, split_antimeridian,
    write_trajectories,
)


@pytest.mark.parametrize("lon,lat,height", [
    (0, 0, 0), (45, 60, 500), (-80, -28, 500_000),
    (180, 0, 35_786_000), (0, 90, 0), (50, -90, 10_000),
])
def test_wgs84_round_trip(lon: float, lat: float, height: float) -> None:
    point = geodetic_to_ecef(lon, lat, height)
    recovered = ecef_to_geodetic(point)
    if abs(lat) != 90:
        assert recovered.lon_deg == pytest.approx(lon, abs=1e-8)
    assert recovered.lat_deg == pytest.approx(lat, abs=1e-8)
    assert recovered.height_m == pytest.approx(height, abs=1e-4)


def test_time_interpolation_and_no_extrapolation() -> None:
    tr = EcefTrajectory.from_arrays("A", [5, 15], [(10, 20, 30), (30, 60, 90)])
    assert tr.at(10) == EcefPosition(20, 40, 60)
    assert tr.at(5) == EcefPosition(10, 20, 30)
    assert tr.at(15) == EcefPosition(30, 60, 90)
    with pytest.raises(ValueError, match="outside"):
        tr.at(4)
    with pytest.raises(ValueError, match="outside"):
        tr.at(16)


def test_reject_invalid_input() -> None:
    with pytest.raises(ValueError, match="increasing"):
        EcefTrajectory.from_arrays("A", [2, 2], [(1, 2, 3), (4, 5, 6)])
    with pytest.raises(ValueError, match="finite"):
        EcefTrajectory.from_arrays("A", [2], [(math.nan, 2, 3)])
    with pytest.raises(ValueError, match="match"):
        EcefTrajectory.from_arrays("A", [2, 3], [(1, 2, 3)])
    with pytest.raises(ValueError, match="centre"):
        ecef_to_geodetic(EcefPosition(0, 0, 0))
    with pytest.raises(ValueError, match="color"):
        EcefTrajectory.from_arrays("A", [2], [(1,2,3)], color="red")


def test_earth_occlusion_preserves_altitude() -> None:
    _, _, near = project_orthographic_ecef(geodetic_to_ecef(0, 0, 500_000), 0, 0)
    _, _, far = project_orthographic_ecef(geodetic_to_ecef(180, 0, 500_000), 0, 0)
    u, _, above_limb = project_orthographic_ecef(geodetic_to_ecef(90, 0, 500_000), 0, 0)
    assert near and not far and above_limb and u > 1


def test_antimeridian_split() -> None:
    segments = split_antimeridian([(170,0), (175,1), (-178,2), (-170,3)])
    assert len(segments) == 2
    assert segments[0] == [(170,0), (175,1)]


def test_local_json_and_csv(tmp_path: Path) -> None:
    tr = EcefTrajectory.from_arrays("Demo", [0, 1], [(2, 3, 4), (3, 4, 5)])
    j = tmp_path / "local.json"
    write_trajectories(j, [tr])
    assert read_trajectories(j) == (tr,)
    c = tmp_path / "local.csv"
    with c.open("w", encoding="utf-8", newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(["name", "time_s", "x_m", "y_m", "z_m"])
        writer.writerow(["Demo",0,2,3,4])
        writer.writerow(["Demo",1,3,4,5])
    assert read_trajectories(c) == (tr,)


def test_all_outputs_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network not permitted")
    monkeypatch.setattr(socket,"socket", blocked)
    monkeypatch.setattr(socket,"getaddrinfo", blocked)
    monkeypatch.setattr(socket,"create_connection", blocked)
    tr = EcefTrajectory.from_arrays("Demo", [0, 2], [
        (6_800_000, 0, 0), (0, 6_800_000, 0)])
    save_svg(str(tmp_path / "map.svg"), trajectories=[tr], at_s=1)
    matplotlib_world(tmp_path / "map.png", trajectories=[tr], at_s=1)
    matplotlib_globe(tmp_path / "globe.png", size=128, trajectories=[tr], at_s=1)
    matplotlib_ecef_timeseries(tmp_path / "components.png", [tr])
    canvas_globe(tmp_path / "canvas.html", trajectories=[tr])
    plotly_globe(tmp_path / "plotly.html", trajectories=[tr], at_s=1)
    assert (tmp_path / "map.svg").read_text().count("polyline") > 0
    for name in ("map.png", "globe.png", "components.png"):
        assert (tmp_path / name).read_bytes().startswith(b"\x89PNG")
    canvas = (tmp_path / "canvas.html").read_text()
    assert 'const ecefTrajectories = [' in canvas and 'id="time"' in canvas
    assert "https://" not in canvas and "http://" not in canvas
    plotly = (tmp_path / "plotly.html").read_text()
    parser = _Assets()
    parser.feed(plotly)
    assert not parser.external


def test_unified_render_interface_and_epoch_consistency(tmp_path: Path) -> None:
    tr = EcefTrajectory.from_arrays("object", [0, 1], [(6_800_000,0,0),(6_799_000,20,20)])
    assert render_ecef([tr], tmp_path / "world.svg", spec=RenderSpec(backend="svg")) .exists()
    assert render_ecef([tr], tmp_path / "globe.html", spec=RenderSpec(backend="canvas")).exists()
    with pytest.raises(ValueError, match="epoch"):
        render_ecef([tr, EcefTrajectory.from_arrays("other",[0],[(-6_800_000,0,0)],
            epoch_utc=datetime(2026,11,7,tzinfo=timezone.utc))], tmp_path / "bad.svg")
    with pytest.raises(ValueError, match="at_s"):
        RenderSpec(at_s=float("nan"))


def test_svg_imagery_combined_embeds_local_jpeg() -> None:
    combined = svg_map(mode="combined", width=400, height=200)
    imagery = svg_map(mode="imagery", width=400, height=200)
    assert 'href="data:image/jpeg;base64,' in combined
    assert 'href="data:image/jpeg;base64,' in imagery
    assert "<polygon" in combined
    assert "<polygon" not in imagery


def test_canvas_escapes_html_sensitive_names(tmp_path: Path) -> None:
    malicious = EcefTrajectory.from_arrays("</script><script>bad()</script>",
                    [0], [(7_000_000, 0, 0)])
    output = tmp_path / "safe.html"
    canvas_globe(output, trajectories=[malicious])
    html = output.read_text()
    assert "<script>bad()" not in html
    assert "\\u003cscript" in html


@pytest.mark.parametrize("location", ["document", "entry", "single"])
@pytest.mark.parametrize("key,bad", [
    ("frame", "ECI"), ("units", "kilometres"), ("time_units", "days"),
    ("frame", None), ("units", None), ("time_units", None),
])
def test_json_rejects_conflicting_metadata(tmp_path: Path, location, key, bad) -> None:
    tr = EcefTrajectory.from_arrays("Demo", [0, 1], [(7e6, 0, 0), (7e6, 1, 1)])
    entry = tr.to_dict()
    raw = {"frame": "ECEF", "units": "metres", "time_units": "seconds",
           "trajectories": [entry]}
    if location == "document":
        raw[key] = bad
    elif location == "entry":
        entry[key] = bad
    else:
        raw = entry
        raw[key] = bad
    path = tmp_path / "conflicting.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=f"JSON {key} must be"):
        read_trajectories(path)


def test_json_metadata_round_trip(tmp_path: Path) -> None:
    tr = EcefTrajectory.from_arrays("Demo", [0, 1], [(7e6, 0, 0), (7e6, 1, 1)],
                                   epoch_utc=datetime(2026, 1, 1, tzinfo=timezone.utc))
    path = tmp_path / "roundtrip.json"
    write_trajectories(path, [tr])
    raw = json.loads(path.read_text())
    assert {key: raw[key] for key in ("frame", "units", "time_units")} == {
        "frame": "ECEF", "units": "metres", "time_units": "seconds"}
    assert read_trajectories(path) == (tr,)


@pytest.mark.parametrize("wrapped", [False, True])
def test_json_legacy_missing_metadata(tmp_path: Path, wrapped: bool) -> None:
    tr = EcefTrajectory.from_arrays("Legacy", [0], [(7e6, 0, 0)])
    entry = tr.to_dict()
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"trajectories": [entry]} if wrapped else entry))
    assert read_trajectories(path) == (tr,)


@pytest.mark.parametrize('lon,lat,expected', [
    (0, 0, (6378137.0, 0, 0)),
    (90, 0, (0, 6378137.0, 0)),
    (0, 90, (0, 0, 6356752.314245179)),
])
def test_wgs84_reference_axes(lon, lat, expected):
    # Independent WGS84 reference values, not constants imported from production.
    # Unlike a round trip, this catches matching mistakes in both conversions.
    actual = geodetic_to_ecef(lon, lat)
    assert (actual.x_m, actual.y_m, actual.z_m) == pytest.approx(expected, abs=1e-6)


def test_trajectory_record_shape_and_copy_isolation():
    tr = EcefTrajectory.from_arrays('record', [0], [(7e6, 1, 2)])
    record = tr.to_dict()
    assert record == {'name': 'record', 'color': '#ffbd69', 'epoch_utc': None,
                      'samples': [{'time_s': 0, 'ecef_m': [7e6, 1, 2]}]}
    record['samples'][0]['ecef_m'][0] = 0
    assert tr.samples[0].position.x_m == 7e6


def test_optional_backends_cold_import_and_render_without_network(tmp_path, pytestconfig):
    # A fresh interpreter prevents collection/other tests from warming imports.
    # Audit hooks preserve socket's class identity (required by ssl imports).
    code = r"""
import sys
import socket
from pathlib import Path

roots = ('trenton_offline_maps', 'numpy', 'PIL', 'matplotlib', 'plotly')
assert not any(name.split('.')[0] in roots for name in sys.modules)
attempts = []
def deny_network(event, args):
    if event.startswith('socket.'):
        attempts.append(event)
        raise AssertionError('Network operation forbidden: ' + event)
sys.addaudithook(deny_network)
# Prove that both socket creation and DNS are intercepted before imports.
for probe in (socket.socket, lambda: socket.getaddrinfo('localhost', 80)):
    try:
        probe()
    except AssertionError:
        pass
    else:
        raise AssertionError('Network guard did not intercept probe')
assert len(attempts) == 2
attempts.clear()
sys.path.insert(0, sys.argv[1])
from trenton_offline_maps.trajectory import EcefTrajectory
from trenton_offline_maps.visualize import RenderSpec, render_ecef
tr = EcefTrajectory.from_arrays('cold offline', [0, 2], [(7e6, 0, 0), (7e6, 100, 100)])
out = Path(sys.argv[2])
for backend, extension in [('map', 'png'), ('globe', 'png'),
                           ('timeseries', 'png'), ('plotly', 'html')]:
    target = render_ecef([tr], out / (backend + '.' + extension),
                        spec=RenderSpec(backend=backend, at_s=1))
    data = target.read_bytes()
    assert len(data) > 1000
    if extension == 'png':
        assert data.startswith(b'\x89PNG')
    else:
        assert b'Plotly.newPlot' in data
assert all(root in sys.modules for root in roots)
assert not attempts, attempts  # Also catches attempted network swallowed by a dependency.
print('PASS: cold optional imports and four renders; zero socket/DNS attempts')
"""
    environment = dict(os.environ, MPLCONFIGDIR=str(tmp_path / 'mpl-cache'))
    result = subprocess.run(
        [sys.executable, '-I', '-c', code, str(pytestconfig.rootpath / 'src'), str(tmp_path)],
        env=environment, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'zero socket/DNS attempts' in result.stdout
