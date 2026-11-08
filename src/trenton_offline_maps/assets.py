"""Read immutable, bundled resources; independent of every renderer."""
import json
from importlib.resources import files
from typing import Any

def countries() -> list[dict[str, Any]]:
    """Return bundled simplified Natural Earth country polygon rings in lon/lat degrees."""
    resource = files('trenton_offline_maps').joinpath('data/countries.json')
    return json.loads(resource.read_text(encoding='utf-8'))

def blue_marble_bytes() -> bytes:
    """Return bundled JPEG bytes without fetching or caching external resources."""
    return files('trenton_offline_maps').joinpath('data/blue_marble.jpg').read_bytes()
