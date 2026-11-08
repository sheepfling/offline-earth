"""Network-blocked smoke tests for image generation and HTML assets."""
from __future__ import annotations

import socket
from collections.abc import Iterable
from html.parser import HTMLParser
from pathlib import Path

import pytest

from trenton_offline_maps.earth import (
    blue_marble_bytes,
    matplotlib_globe,
    matplotlib_world,
    orthographic_rgb,
    plotly_globe,
)


class _Assets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external: list[str] = []

    def handle_starttag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        for key, val in attrs:
            if val and ((tag == "script" and key == "src") or
                        (tag == "link" and key == "href") or
                        (tag in ("img", "iframe") and key == "src")):
                self.external.append(val)


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network calls forbidden during render")
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def test_texture_bundled() -> None:
    assert blue_marble_bytes().startswith(b"\xff\xd8")
    assert len(blue_marble_bytes()) > 1_000_000


def test_orthographic_has_alpha_and_geometry() -> None:
    rgb = orthographic_rgb(mode="combined", size=128)
    assert rgb.shape == (128, 128, 4)
    assert rgb[0, 0, 3] == 0
    assert rgb[64, 64, 3] == 255


@pytest.mark.parametrize("mode", ["imagery", "political", "combined"])
def test_static_rendering(tmp_path: Path, mode: str) -> None:
    # These are actual PNG outputs, not merely function imports.
    world = tmp_path / "world.png"
    globe = tmp_path / "globe.png"
    matplotlib_world(world, mode=mode)  # type: ignore[arg-type]
    matplotlib_globe(globe, mode=mode, size=128)  # type: ignore[arg-type]
    assert world.read_bytes().startswith(b"\x89PNG")
    assert globe.read_bytes().startswith(b"\x89PNG")


def test_interactive_html_self_contained(tmp_path: Path) -> None:
    output = tmp_path / "earth.html"
    plotly_globe(output)
    html = output.read_text(encoding="utf-8")
    assets = _Assets()
    assets.feed(html)
    assert not assets.external
    assert "Plotly.newPlot" in html
    # Plotly's embedded JS contains dormant CDN URL constants; these are not
    # remote HTML asset tags. We assert on actual external resource references.


def test_canvas_globe_is_single_file_and_no_webgl(tmp_path: Path) -> None:
    from trenton_offline_maps.canvas import canvas_globe
    output = tmp_path / "earth_canvas.html"
    canvas_globe(output)
    html = output.read_text(encoding="utf-8")
    assets = _Assets()
    assets.feed(html)
    assert not assets.external
    assert "data:image/jpeg;base64," in html
    assert "getContext('2d'" in html
    assert "webgl" not in html.lower().replace("no webgl", "")
    assert html.count("__BLUE_MARBLE_BASE64__") == 0
    assert len(html) > 2_000_000
