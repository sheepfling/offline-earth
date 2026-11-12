"""Surface self-intersections must not hide a later Earth exit intersection."""
import json
from decimal import Decimal, localcontext
from random import Random
from math import inf, nextafter, sqrt
import shutil
import subprocess

import pytest

from offline_earth.constants import EARTH_RADIUS_M, WGS84_A_M, WGS84_B_M
from offline_earth.geodesy import EcefPosition, geodetic_to_ecef, project_orthographic_ecef
from offline_earth.geometry import camera_basis


A, B = WGS84_A_M, WGS84_B_M
# name, ECEF meters, camera longitude/latitude degrees, expected visibility
CASES = [
    ('near_surface', (A, 0, 0), 0, 0, True),
    ('far_surface', (-A, 0, 0), 0, 0, False),
    ('far_surface_rounding_out', (nextafter(-A, -inf), 0, 0), 0, 0, False),
    ('far_surface_rounding_in', (nextafter(-A, 0), 0, 0), 0, 0, False),
    ('far_entry_within_tolerance', (-A - 0.5, 0, 0), 0, 0, False),
    ('far_inside', (-A + 0.5, 0, 0), 0, 0, False),
    ('near_inside_within_tolerance', (A - 0.5, 0, 0), 0, 0, True),
    ('near_inside_beyond_tolerance', (A - 2, 0, 0), 0, 0, False),
    ('inside_earth', (0, 0, 0), 0, 0, False),
    ('near_satellite', (2 * A, 0, 0), 0, 0, True),
    ('far_satellite', (-2 * A, 0, 0), 0, 0, False),
    ('above_limb', (-A, A + 1, 0), 0, 0, True),
    ('below_limb', (-A, A - 1, 0), 0, 0, False),
    ('limb_self_contact', (0, A, 0), 0, 0, True),
    ('tangent_contact_ahead', (-A, A, 0), 0, 0, False),
    ('tangent_contact_behind', (A, A, 0), 0, 0, True),
    ('near_pole', (0, 0, B), 0, 90, True),
    ('far_pole', (0, 0, -B), 0, 90, False),
    ('rotated_far_surface', (A, 0, 0), 180, 0, False),
]
for lon, lat in ((17, 23), (-95, -51), (132, 80)):
    surface = geodetic_to_ecef(lon, lat)
    xyz = (surface.x_m, surface.y_m, surface.z_m)
    CASES.extend([
        (f'near_surface_{lon}_{lat}', xyz, lon, lat, True),
        (f'far_surface_{lon}_{lat}', tuple(-value for value in xyz), lon, lat, False),
    ])


# A tangent to the scaled unit sphere maps back to an ellipsoid tangent.
# Include the exact operation order from the reported longitude-1 regression.
for lon, lat in ((0, 0), (1, 0), (17, 23), (-95, -51), (132, 80), (37, 90)):
    forward, east, _ = camera_basis(lon, lat)
    scaled_east = (east[0], east[1], 0.0)
    length = sqrt(sum(value*value for value in scaled_east))
    tangent = (A*scaled_east[0]/length, A*scaled_east[1]/length, 0.0)
    # East is perpendicular to forward even after ellipsoid scaling.
    for distance in (A, 42_164_000.0):
        for offset, visible in ((-1, False), (-0.001, False), (0, False),
                                (0.001, True), (1, True)):
            xyz = tuple(-distance*f + t*(1+offset/A) for f, t in zip(forward, tangent))
            CASES.append((f'limb_{lon}_{lat}_{distance}_{offset}', xyz, lon, lat, visible))
    # Tangencies at/behind the sample still do not block sight.
    for distance in (-A, 0.0, 0.5, 2.0):
        xyz = tuple(-distance*f+t for f, t in zip(forward, tangent))
        CASES.append((f'tangent_distance_{lon}_{lat}_{distance}', xyz, lon, lat, distance <= 1))


def _decimal_visible(xyz, lon, lat):
    """Independent 90-digit quadratic oracle for the supplied binary64 inputs."""
    forward, _, _ = camera_basis(lon, lat)
    with localcontext() as context:
        context.prec = 90
        p = [Decimal.from_float(float(x)) for x in xyz]
        f = [Decimal.from_float(x) for x in forward]
        axes = [Decimal.from_float(x) for x in (A, A, B)]
        aa = sum((v/a)**2 for v, a in zip(f, axes))
        bb = 2 * sum(x*v/a**2 for x, v, a in zip(p, f, axes))
        cc = sum((x/a)**2 for x, a in zip(p, axes)) - 1
        determinant = bb*bb - 4*aa*cc
        return determinant < 0 or (-bb + determinant.sqrt())/(2*aa) <= 1


# Non-grazing randomized surface-to-GEO cases have an independent high precision
# expectation, not a second binary64 copy of the production algorithm.
_rng = Random(20261110)
for index in range(150):
    lon, lat = _rng.uniform(-180, 180), _rng.uniform(-90, 90)
    position = geodetic_to_ecef(_rng.uniform(-180, 180), _rng.uniform(-90, 90),
                               _rng.uniform(-100, 42_164_000))
    xyz = (position.x_m, position.y_m, position.z_m)
    CASES.append((f'decimal_oracle_{index}', xyz, lon, lat, _decimal_visible(xyz, lon, lat)))


def test_near_limb_offsets_agree_with_high_precision_geometry():
    for name, xyz, lon, lat, visible in CASES:
        if name.startswith('limb_') and not name.endswith('_0'):
            assert _decimal_visible(xyz, lon, lat) is visible, name


@pytest.mark.parametrize('xyz,lon,lat,visible', [case[1:] for case in CASES],
                         ids=[case[0] for case in CASES])
def test_python_horizon_intersections(xyz, lon, lat, visible):
    projected = project_orthographic_ecef(EcefPosition(*xyz), lon, lat)
    assert projected.visible is visible


@pytest.mark.parametrize('display_radius', [EARTH_RADIUS_M / 2, EARTH_RADIUS_M * 2])
def test_visibility_tolerance_is_in_meters_not_display_radii(display_radius):
    point = EcefPosition(-A - 0.5, 0, 0)
    assert not project_orthographic_ecef(point, 0, 0, display_radius_m=display_radius).visible


def test_canvas_horizon_matches_python_and_expected_geometry():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js is optional development tooling for executing Canvas math')
    from importlib.resources import files
    template = files('offline_earth').joinpath('templates/canvas.html').read_text(encoding='utf-8')
    # Execute the actual packaged functions, not a second implementation of the math.
    basis = template[template.index('function basis()'):template.index('function drawRings(')]
    visibility = template[template.index('function xyzVisible('):template.index('function ecefAt(')]
    constants = {'radius_m': EARTH_RADIUS_M, 'a_m': A, 'b_m': B}
    payload = [{'name': name, 'sample': [0, *xyz], 'lon': lon, 'lat': lat}
               for name, xyz, lon, lat, _ in CASES]
    script = (
        'const earthConstants=' + json.dumps(constants) + ';\n'
        'let center_lon_rad=0,center_lat_rad=0;\n' + basis + visibility + '\n'
        'const cases=' + json.dumps(payload) + ';\n'
        'console.log(JSON.stringify(cases.map(c=>{'
        'center_lon_rad=c.lon*Math.PI/180;center_lat_rad=c.lat*Math.PI/180;'
        'return xyzVisible(c.sample,basis());})));'
    )
    result = subprocess.run([node, '-e', script], capture_output=True, text=True,
                            encoding='utf-8', check=True, timeout=30)
    projected = json.loads(result.stdout)
    assert len(projected) == len(CASES)
    for (name, xyz, lon, lat, visible), canvas in zip(CASES, projected):
        python = project_orthographic_ecef(EcefPosition(*xyz), lon, lat)
        assert canvas['visible'] is visible, name
        assert canvas['visible'] is python.visible, name
        assert canvas['u'] == pytest.approx(python.east_earth_radii), name
        assert canvas['v'] == pytest.approx(python.north_earth_radii), name
