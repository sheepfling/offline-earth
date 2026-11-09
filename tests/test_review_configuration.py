"""Explicit physical constants, editable example output and texture budgets."""
from io import BytesIO
from types import SimpleNamespace
from typing import Final, get_origin, get_type_hints

import numpy as np
from PIL import Image
import pytest

from examples.utilities import constants as example_constants
from examples.utilities import trajectories
from offline_earth import constants
from offline_earth.renderers import blue_marble


def test_examples_use_final_shared_earth_values():
    for name in ('EARTH_RADIUS_M', 'EARTH_SPIN_RAD_S'):
        assert getattr(example_constants, name) == getattr(constants, name)
        assert get_origin(get_type_hints(example_constants)[name]) is Final
        assert get_origin(get_type_hints(constants)[name]) is Final
    for name in ('DEMO_STEP_S', 'DEMO_SAMPLE_COUNT'):
        assert get_origin(get_type_hints(trajectories)[name]) is Final
    assert not hasattr(example_constants, 'DEMO_EARTH_RADIUS_M')
    assert not hasattr(example_constants, 'DEMO_EARTH_SPIN_RAD_S')


def test_generated_sample_collection_is_fresh_and_editable():
    first = trajectories.sample_ecef_trajectories(3)
    second = trajectories.sample_ecef_trajectories(3)
    assert isinstance(first, list) and first == second
    assert first is not second
    first.reverse()
    first.append(first.pop())
    first.clear()
    assert len(second) == 3
    assert [len(track.samples) for track in second] == [3, 3, 2]


def test_indexed_texture_custom_budgets():
    texture = blue_marble.indexed_texture(width_px=24, height_px=13, palette_colors=16)
    assert texture.indices.shape == (13, 24)
    assert texture.indices.dtype == np.uint8
    assert 2 <= len(texture.colorscale) <= 16
    assert int(texture.indices.max()) < len(texture.colorscale)
    assert [position for position, _ in texture.colorscale] == [
        i / (len(texture.colorscale) - 1) for i in range(len(texture.colorscale))]


def test_indexed_texture_flat_image_has_valid_colorscale(monkeypatch):
    buffer = BytesIO()
    Image.new('RGB', (8, 4), (12, 34, 56)).save(buffer, format='PNG')
    monkeypatch.setattr(blue_marble, 'BLUE_MARBLE',
                        SimpleNamespace(read_bytes=lambda: buffer.getvalue()))
    texture = blue_marble.indexed_texture(width_px=8, height_px=4, palette_colors=16)
    assert np.all(texture.indices == 0)
    assert texture.colorscale == [[0.0, 'rgb(12,34,56)'], [1.0, 'rgb(12,34,56)']]


@pytest.mark.parametrize('options', [
    {'width_px': 1}, {'height_px': 0}, {'width_px': 3.5}, {'height_px': True},
    {'palette_colors': 1}, {'palette_colors': 257}, {'palette_colors': False},
])
def test_invalid_texture_budget_fails_before_loading(monkeypatch, options):
    def forbidden():
        raise AssertionError('Invalid budgets must fail before loading the image')
    monkeypatch.setattr(blue_marble, 'BLUE_MARBLE', SimpleNamespace(read_bytes=forbidden))
    with pytest.raises(ValueError):
        blue_marble.indexed_texture(**options)
