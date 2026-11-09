"""Explicit callback ownership, aggregation, and failure cleanup contracts."""
import subprocess
import sys

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import pytest

from offline_earth.renderers import matplotlib as mpl
from offline_earth.timeseries import matplotlib_ecef_timeseries
from offline_earth.trajectory import EcefTrajectory
from offline_earth.visualize import RenderSpec, render_ecef


@pytest.fixture(autouse=True)
def lightweight_assets(monkeypatch):
    monkeypatch.setattr(mpl, 'texture_rgb', lambda: np.zeros((2, 4, 3)))
    monkeypatch.setattr(mpl, 'countries', lambda: [])
    monkeypatch.setattr(mpl, 'orthographic_rgb', lambda **kw: np.zeros((4, 4, 3)))
    before = set(plt.get_fignums())
    yield
    leaked = set(plt.get_fignums()) - before
    for number in leaked:
        plt.close(number)
    assert not leaked, f'Figures leaked: {leaked}'


@pytest.fixture(params=['map', 'globe', 'timeseries'])
def plotter(request):
    if request.param == 'map':
        return mpl.matplotlib_world
    if request.param == 'globe':
        return mpl.matplotlib_globe
    tr = EcefTrajectory.from_arrays('demo', [0, 1], [(7e6, 0, 0), (7e6, 1, 1)])
    return lambda path, **kw: matplotlib_ecef_timeseries(path, [tr], **kw)


def test_defaults_save_and_close(plotter, tmp_path):
    target = tmp_path / 'figure.png'
    assert plotter(target) is None
    assert target.stat().st_size > 0


def test_callback_receives_kwargs_and_can_retain(plotter, tmp_path):
    target = tmp_path / 'figure.png'
    seen = []
    def retain(fig, *, path, label):
        seen.append((fig, path, label))
        return fig
    figure = plotter(target, post_plot=retain, post_plot_kwargs={'label': 'demo'})
    try:
        assert seen == [(figure, target, 'demo')]
        assert plt.fignum_exists(figure.number)
        assert not target.exists()  # The callback replaces default saving.
    finally:
        plt.close(figure)


def test_callback_replacement_closes_original(plotter, tmp_path):
    replacement = plt.figure()
    originals = []
    def replace(fig, **kwargs):
        originals.append(fig)
        return replacement
    try:
        assert plotter(tmp_path / 'unused.png', post_plot=replace) is replacement
        assert not plt.fignum_exists(originals[0].number)
    finally:
        plt.close(replacement)


def test_callback_saves_and_discards(plotter, tmp_path):
    def save(fig, *, path):
        fig.savefig(path)
        plt.close(fig)
        return None
    target = tmp_path / 'callback.png'
    assert plotter(target, post_plot=save) is None
    assert target.exists()


@pytest.mark.parametrize('failure', ['callback', 'save', 'drawing', 'invalid_return'])
def test_failures_close_original(plotter, tmp_path, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise RuntimeError('expected failure')
    kw = {}
    if failure == 'callback':
        kw['post_plot'] = fail
    elif failure == 'save':
        monkeypatch.setattr(Figure, 'savefig', fail)
    elif failure == 'drawing':
        monkeypatch.setattr(Figure, 'set_facecolor', fail)
    else:
        kw['post_plot'] = lambda fig, **kwargs: 'not a figure'
    with pytest.raises((RuntimeError, TypeError)):
        plotter(tmp_path / 'unused.png', **kw)


def test_reserved_path_rejected_before_allocation(plotter, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail('Allocated a figure before validating callback kwargs')
    monkeypatch.setattr(plt, 'subplots', fail)
    with pytest.raises(ValueError, match='reserved'):
        plotter(tmp_path / 'unused.png', post_plot=lambda f, **kw: f,
                post_plot_kwargs={'path': 'other.png'})


def test_dispatch_aggregates_only_survivors(tmp_path):
    figures = []
    target = tmp_path / 'retained.png'
    try:
        assert render_ecef([], target, figures=figures, post_plot=lambda f, **kw: f) == target
        assert len(figures) == 1
        render_ecef([], tmp_path / 'discarded.png', figures=figures,
                    post_plot=lambda f, **kw: None)
        assert len(figures) == 1
        render_ecef([], tmp_path / 'default.png', figures=figures)
        assert len(figures) == 1
    finally:
        for figure in figures:
            plt.close(figure)


@pytest.mark.parametrize('backend', ['svg', 'canvas'])
def test_nonfigure_backend_rejects_callback(tmp_path, backend):
    with pytest.raises(ValueError, match='figure backend'):
        render_ecef([], tmp_path / 'unused', spec=RenderSpec(backend=backend),
                    post_plot=lambda f, **kw: f)


def test_plotly_defaults_and_callback(tmp_path, monkeypatch):
    from offline_earth.renderers import plotly as renderer
    monkeypatch.setattr(renderer, 'countries', lambda: [])
    monkeypatch.setattr(renderer, 'indexed_texture',
                        lambda: (np.zeros((91, 180)), [[0, 'black'], [1, 'white']]))
    import webbrowser
    monkeypatch.setattr(webbrowser, 'open', lambda *a, **kw: pytest.fail('Browser opened'))
    target = tmp_path / 'globe.html'
    assert renderer.plotly_globe(target) is None
    assert target.stat().st_size > 0
    seen = []
    def retain(fig, *, path, label):
        seen.append((path, label))
        return fig
    figure = renderer.plotly_globe(target, post_plot=retain, post_plot_kwargs={'label': 'ok'})
    assert isinstance(figure, renderer.go.Figure)
    assert seen == [(target, 'ok')]
    replacement = renderer.go.Figure()
    assert renderer.plotly_globe(target, post_plot=lambda f, **kw: replacement) is replacement
    with pytest.raises(TypeError, match='same backend'):
        renderer.plotly_globe(target, post_plot=lambda f, **kw: 1)
    def fail(fig, **kwargs):
        raise RuntimeError('callback error')
    with pytest.raises(RuntimeError, match='callback error'):
        renderer.plotly_globe(target, post_plot=fail)
    figures = []
    assert render_ecef([], target, spec=RenderSpec(backend='plotly'),
                       post_plot=retain, post_plot_kwargs={'label': 'aggregate'},
                       figures=figures) == target
    assert len(figures) == 1 and isinstance(figures[0], renderer.go.Figure)


def test_imports_preserve_backend_and_dependency_free_dispatch():
    subprocess.run([sys.executable, '-c', '''
import sys
import offline_earth.visualize
assert 'matplotlib' not in sys.modules
assert 'plotly' not in sys.modules
import matplotlib
matplotlib.use('svg')
import offline_earth.renderers.matplotlib
import offline_earth.timeseries
assert matplotlib.get_backend().lower() == 'svg'
'''], check=True)


@pytest.mark.parametrize('kwargs,error', [
    ({'post_plot_kwargs': {'label': 'unused'}}, ValueError),
    ({'post_plot': 42}, TypeError),
    ({'post_plot': lambda f, **kw: f, 'post_plot_kwargs': []}, TypeError),
])
def test_invalid_callback_options_rejected(plotter, tmp_path, monkeypatch, kwargs, error):
    monkeypatch.setattr(plt, 'subplots', lambda *a, **kw: pytest.fail('Allocated figure'))
    with pytest.raises(error):
        plotter(tmp_path / 'unused.png', **kwargs)
