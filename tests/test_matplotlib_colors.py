"""Semantic color roles preserve the existing world and globe appearance."""

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import numpy as np
import pytest

from offline_earth.renderers import matplotlib as renderer
from offline_earth.trajectory import EcefTrajectory


@pytest.fixture(autouse=True)
def lightweight_assets(monkeypatch):
    monkeypatch.setattr(renderer, "texture_rgb", lambda: np.zeros((2, 4, 3)))
    monkeypatch.setattr(renderer, "orthographic_rgb", lambda **kwargs: np.zeros((4, 4, 4)))
    monkeypatch.setattr(renderer, "countries", lambda: [{
        "rings": [[(-10, -10), (10, -10), (10, 10), (-10, 10), (-10, -10)]],
    }])
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


@pytest.fixture
def trajectories():
    # The hidden middle point exercises both flushed and final globe segments.
    positions = [(7e6, 0, 0), (7e6, 1e6, 0), (-7e6, 0, 0),
                 (7e6, 2e6, 0), (7e6, 3e6, 0)]
    return [EcefTrajectory.from_arrays(name, range(5), positions, color=color)
            for name, color in [("Alpha", "#c129a3"), ("Beta", "#376b22")]]


def assert_color(actual, expected, *, alpha=None):
    assert to_rgba(actual) == pytest.approx(to_rgba(expected, alpha=alpha))


@pytest.mark.parametrize("mode", ["imagery", "political", "combined"])
def test_world_artist_color_roles(tmp_path, trajectories, mode):
    figure = renderer.matplotlib_world(
        tmp_path / "unused.png", mode=mode, track=[(0, 0), (15, 10)],
        trajectories=trajectories, post_plot=lambda figure, **kwargs: figure,
    )
    axes = figure.axes[0]
    assert_color(figure.get_facecolor(), "#071522")
    assert_color(axes.get_facecolor(), "#143454")
    assert_color(axes.title.get_color(), "#f1f5fa")
    for axis in (axes.xaxis, axes.yaxis):
        assert_color(axis.label.get_color(), "#b4c8d9")
        for tick in axis.get_major_ticks():
            assert_color(tick.label1.get_color(), "#bdcbd6")
            assert_color(tick.tick1line.get_color(), "#bdcbd6")
            assert_color(tick.gridline.get_color(), "white")
            assert tick.gridline.get_alpha() == .13

    if mode == "political":
        land = axes.collections[0]
        assert_color(land.get_facecolors()[0], "#a0bdb1")
        assert_color(land.get_edgecolors()[0], "#27495e")
    elif mode == "combined":
        borders = axes.collections[0]
        assert len(borders.get_facecolors()) == 0
        assert_color(borders.get_edgecolors()[0], "#fff2c1", alpha=.88)
    else:
        assert not axes.collections

    ground_track = [line for line in axes.lines if line.get_zorder() == 5]
    assert ground_track
    for line in ground_track:
        assert_color(line.get_color(), "#ffb65e")
    trajectory_lines = [line for line in axes.lines if line.get_zorder() == 6]
    assert {line.get_label() for line in trajectory_lines} == {"Alpha", "Beta"}
    for trajectory in trajectories:
        for line in trajectory_lines:
            if line.get_label() == trajectory.name:
                assert_color(line.get_color(), trajectory.color)

    markers = [line for line in axes.lines if line.get_marker() == "o"]
    assert len(markers) == len(trajectories)
    for marker, trajectory in zip(markers, trajectories):
        assert_color(marker.get_color(), trajectory.color)
        assert_color(marker.get_markerfacecolor(), trajectory.color)
        assert_color(marker.get_markeredgecolor(), "white")
    assert {label.get_text() for label in axes.texts} == {"Alpha", "Beta"}
    for label in axes.texts:
        assert_color(label.get_color(), "#ffffff")


@pytest.mark.parametrize("mode", ["imagery", "political", "combined"])
def test_globe_artist_color_roles(tmp_path, trajectories, mode):
    figure = renderer.matplotlib_globe(
        tmp_path / "unused.png", mode=mode, center_lon_deg=0, center_lat_deg=0,
        track=[(0, 0), (15, 10)], trajectories=trajectories,
        post_plot=lambda figure, **kwargs: figure,
    )
    axes = figure.axes[0]
    assert_color(figure.get_facecolor(), "#071522")
    assert_color(axes.get_facecolor(), "#071522")
    assert_color(figure.texts[0].get_color(), "#e8f4ff")
    assert_color(figure.texts[1].get_color(), "#8baec4")
    atmosphere = axes.patches[0]
    assert not atmosphere.get_fill()
    assert_color(atmosphere.get_edgecolor(), "#69a9d4", alpha=.5)

    borders = [line for line in axes.lines if line.get_zorder() == 5]
    if mode == "imagery":
        assert not borders
    else:
        assert borders
        for border in borders:
            assert_color(border.get_color(), "#fff0c2" if mode == "combined" else "#2c5364")
            assert border.get_alpha() == .92
    ground_track = [line for line in axes.lines if line.get_zorder() == 6]
    assert ground_track
    for line in ground_track:
        assert_color(line.get_color(), "#ffb160")

    trajectory_lines = [line for line in axes.lines if line.get_zorder() == 8]
    assert len(trajectory_lines) == 2 * len(trajectories)
    for trajectory in trajectories:
        matching = [line for line in trajectory_lines if line.get_color() == trajectory.color]
        assert len(matching) == 2
    markers = [line for line in axes.lines if line.get_marker() == "o"]
    assert len(markers) == len(trajectories)
    for marker, trajectory in zip(markers, trajectories):
        assert_color(marker.get_color(), trajectory.color)
        assert_color(marker.get_markerfacecolor(), trajectory.color)
        assert_color(marker.get_markeredgecolor(), "white")
    assert {label.get_text() for label in axes.texts} == {"Alpha", "Beta"}
    for label in axes.texts:
        assert_color(label.get_color(), "white")
