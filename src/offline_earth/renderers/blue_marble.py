"""Optional NumPy/Pillow decoding of the bundled Blue Marble image."""
from io import BytesIO
from typing import NamedTuple

import numpy as np
from PIL import Image

from ..assets import BLUE_MARBLE


def texture_rgb() -> np.ndarray:
    """Decode the bundled JPEG to RGB without accessing the network."""
    with Image.open(BytesIO(BLUE_MARBLE.read_bytes())) as image:
        return np.asarray(image.convert("RGB"))


class IndexedTexture(NamedTuple):
    """Palette-index image and its corresponding normalized Plotly colorscale."""

    indices: np.ndarray
    colorscale: list[list[float | str]]


def indexed_texture() -> IndexedTexture:
    """Return a reduced texture and 128-entry Plotly colorscale."""
    with Image.open(BytesIO(BLUE_MARBLE.read_bytes())) as image:
        small = image.convert("RGB").resize((180, 91), Image.Resampling.BILINEAR)
        indexed = small.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        colors = indexed.getpalette()[:384]
        ids = np.asarray(indexed, dtype=np.uint8)
    scale = [[i / 127, f"rgb({colors[i*3]},{colors[i*3+1]},{colors[i*3+2]})"] for i in range(128)]
    return IndexedTexture(ids, scale)
