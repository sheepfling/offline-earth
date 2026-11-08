from math import isclose
from offline_earth.earth import sphere_xyz
from offline_earth.constants import EARTH_RADIUS_KM
from examples.utilities import demo_ground_track

def test_equator():
    x, y, z = sphere_xyz(0, 0)
    assert isclose(x, EARTH_RADIUS_KM)
    assert abs(y) < 1e-8 and abs(z) < 1e-8

def test_pole():
    x, y, z = sphere_xyz(0, 90)
    assert abs(x) < 1e-8 and abs(y) < 1e-8
    assert isclose(z, EARTH_RADIUS_KM)

def test_track():
    assert len(demo_ground_track()) == 240
