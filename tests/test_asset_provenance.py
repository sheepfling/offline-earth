"""Bundled image metadata and attribution have one inspectable source of truth."""
import hashlib
from importlib.resources import files
from io import BytesIO
import json
from urllib.parse import urlparse

from PIL import Image

from offline_earth.assets import BLUE_MARBLE


def test_nasa_image_matches_manifest_and_renderer_metadata():
    data = files('offline_earth').joinpath('data')
    record = json.loads(data.joinpath('ASSETS.json').read_text())['assets']['blue_marble.jpg']
    image_bytes = BLUE_MARBLE.read_bytes()
    assert len(image_bytes) == record['size_bytes']
    assert hashlib.sha256(image_bytes).hexdigest() == record['sha256']
    with Image.open(BytesIO(image_bytes)) as image:
        assert image.format == 'JPEG' and image.mode == 'RGB'
        assert image.size == (record['width_px'], record['height_px'])
        assert image.size == (BLUE_MARBLE.width_px, BLUE_MARBLE.height_px)
    assert tuple(record['extent_deg']) == BLUE_MARBLE.extent_deg
    assert record['origin'] == BLUE_MARBLE.origin


def test_manifest_preserves_direct_source_credit_and_country_uncertainty():
    data = files('offline_earth').joinpath('data')
    manifest = json.loads(data.joinpath('ASSETS.json').read_text())
    image = manifest['assets']['blue_marble.jpg']
    assert urlparse(image['source_url']).hostname == 'assets.science.nasa.gov'
    assert urlparse(image['source_index_url']).hostname == 'science.nasa.gov'
    assert urlparse(image['license_source']).hostname == 'www.nasa.gov'
    assert image['credit'] == 'NASA Earth Observatory'
    assert 'unchanged' in image['acquisition']
    assert image['limitations']
    country = manifest['assets']['countries.json']
    assert 'Not recorded' in country['upstream_version']
    assert country['license_source'] and country['limitations']
    assert not data.joinpath('PROVENANCE.txt').is_file()
