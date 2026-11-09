"""Bundled geographic resources and their metadata, independent of renderers."""
from dataclasses import dataclass
from importlib.resources import files
import json
from typing import Annotated, Literal, NamedTuple, TypeAlias, TypedDict, cast

# Keep the JSON-compatible list representation while documenting coordinate order.
LongitudeLatitudeDegrees: TypeAlias = Annotated[list[float], "[longitude, latitude] in degrees"]
CountryBoundaryRing: TypeAlias = Annotated[
    list[LongitudeLatitudeDegrees], "closed country polygon boundary; first vertex repeated last"
]


class Country(TypedDict):
    """A country and its closed boundary paths in geographic degrees.

    Each ring traces one polygon boundary, not an orbital or latitude ring.
    Multiple rings represent separate boundary paths (for example islands).
    The compact source format does not encode polygon/hole relationships;
    consumers must not infer that topology from this flat collection.
    """

    name: str
    rings: list[CountryBoundaryRing]


class GeographicExtentDegrees(NamedTuple):
    """Equirectangular coverage, ordered west/east/south/north in degrees."""

    west_deg: float
    east_deg: float
    south_deg: float
    north_deg: float


@dataclass(frozen=True)
class BlueMarbleAsset:
    """Bundled equirectangular JPEG and its geographic/raster conventions.

    Width and height describe the stored image, not Earth physics. Preview
    dimensions are a rendering budget, distinct from the source resolution.
    Extent order is (west, east, south, north), in longitude/latitude degrees.
    The top image row faces north.
    """

    resource_name: str = 'data/blue_marble.jpg'
    width_px: int = 5400
    height_px: int = 2700
    preview_width_px: int = 1800
    preview_height_px: int = 900
    extent_deg: GeographicExtentDegrees = GeographicExtentDegrees(-180.0, 180.0, -90.0, 90.0)
    origin: Literal['upper'] = 'upper'

    def read_bytes(self) -> bytes:
        """Read the installed JPEG without fetching or caching external resources."""
        return files('offline_earth').joinpath(self.resource_name).read_bytes()


BLUE_MARBLE = BlueMarbleAsset()


def countries() -> list[Country]:
    """Read simplified Natural Earth country boundaries as closed lon/lat rings."""
    resource = files('offline_earth').joinpath('data/countries.json')
    return cast(list[Country], json.loads(resource.read_text(encoding='utf-8')))


def blue_marble_bytes() -> bytes:
    """Read the bundled Blue Marble JPEG using its resource metadata."""
    return BLUE_MARBLE.read_bytes()
