"""Optional NumPy/Pillow decoding of the bundled Blue Marble image."""
from io import BytesIO
from typing import Final, NamedTuple

import numpy as np
from PIL import Image

from ..assets import BLUE_MARBLE

# Renderer budgets, not properties of NASA's 5400x2700 source image. Roughly
# two-degree samples keep the Plotly globe near 16,000 vertices; a 128-color
# palette trades some imagery detail for a smaller self-contained HTML file.
# These are tunable defaults, not a measured optimum or geodetic precision limit.
PLOTLY_TEXTURE_WIDTH_PX: Final[int] = 180
PLOTLY_TEXTURE_HEIGHT_PX: Final[int] = 91
PLOTLY_PALETTE_COLORS: Final[int] = 128
RGB_CHANNEL_COUNT: Final[int] = 3


def texture_rgb() -> np.ndarray:
    """Decode the bundled JPEG to RGB without accessing the network."""
    with Image.open(BytesIO(BLUE_MARBLE.read_bytes())) as image:
        return np.asarray(image.convert("RGB"))


class IndexedTexture(NamedTuple):
    """Palette-index image and its corresponding normalized Plotly colorscale."""

    indices: np.ndarray
    colorscale: list[list[float | str]]


def indexed_texture(
    *, width_px: int = PLOTLY_TEXTURE_WIDTH_PX,
    height_px: int = PLOTLY_TEXTURE_HEIGHT_PX,
    palette_colors: int = PLOTLY_PALETTE_COLORS,
) -> IndexedTexture:
    """Reduce imagery to an indexed Plotly surface within explicit render budgets.

    Bilinear resizing smooths the photograph before median-cut quantization picks
    up to ``palette_colors`` representative colors. This helper accepts 2..256
    colors. RGB triples and normalized colorscale positions are derived from the
    returned palette, including images with fewer colors than requested.
    """
    for name, value in (("width_px", width_px), ("height_px", height_px),
                        ("palette_colors", palette_colors)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise ValueError(f"{name} must be an integer of at least 2")
    if palette_colors > 256:
        raise ValueError("palette_colors must be in 2..256")
    with Image.open(BytesIO(BLUE_MARBLE.read_bytes())) as image:
        small = image.convert("RGB").resize((width_px, height_px), Image.Resampling.BILINEAR)
        indexed = small.quantize(colors=palette_colors, method=Image.Quantize.MEDIANCUT)
        palette = indexed.getpalette()
        if palette is None:
            raise ValueError("Quantized image has no RGB palette")
        ids = np.asarray(indexed, dtype=np.uint8)
    colors = [palette[start:start + RGB_CHANNEL_COUNT]
              for start in range(0, len(palette), RGB_CHANNEL_COUNT)]
    # Plotly needs both endpoints even when every source pixel has one color.
    if len(colors) == 1:
        colors.append(colors[0])
    last_index = len(colors) - 1
    scale = [[i / last_index, f"rgb({red},{green},{blue})"]
             for i, (red, green, blue) in enumerate(colors)]
    return IndexedTexture(ids, scale)
