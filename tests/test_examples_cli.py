"""Examples are import-safe, configurable, and runnable without network access."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def run_example(root, module, *args, cwd=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / 'src'))),
               PYTHONIOENCODING='utf-8')
    return subprocess.run([sys.executable, '-m', module, *map(str, args)],
                          cwd=cwd or root, env=env, capture_output=True, text=True, encoding='utf-8')


@pytest.mark.parametrize('module, option', [
    ('examples.quickstart', '--output'),
    ('examples.showcase_ecef', '--output-dir'),
    ('examples.showcase_offline', '--output-dir'),
    ('examples.generate_samples', '--sample-count'),
])
def test_help(module, option, tmp_path, pytestconfig):
    result = run_example(pytestconfig.rootpath, module, '--help', cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert option in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_quickstart_explicit_output(tmp_path, pytestconfig):
    output = tmp_path / 'nested' / 'globe.html'
    result = run_example(pytestconfig.rootpath, 'examples.quickstart', '--output', output)
    assert result.returncode == 0, result.stderr
    assert '<html' in output.read_text(encoding='utf-8').lower()


def test_generate_samples(tmp_path, pytestconfig):
    output = tmp_path / 'nested' / 'samples.json'
    result = run_example(pytestconfig.rootpath, 'examples.generate_samples',
                         '--output', output, '--sample-count', '13')
    assert result.returncode == 0, result.stderr
    reference = (pytestconfig.rootpath / 'examples/data/sample_ecef.json').read_text(encoding='utf-8')
    assert output.read_text(encoding='utf-8') == reference
    assert b'\r\n' not in output.read_bytes()
    # Git may check out text fixtures with CRLF on Windows.
    crlf_reference = tmp_path / 'crlf-reference.json'
    crlf_reference.write_bytes(reference.replace('\n', '\r\n').encode('utf-8'))
    assert output.read_text(encoding='utf-8') == crlf_reference.read_text(encoding='utf-8')
    data = json.loads(output.read_text(encoding='utf-8'))
    assert [len(t['samples']) for t in data['trajectories']] == [13, 13, 2]
    assert data['trajectories'][0]['samples'][-1]['time_s'] == 6000
    result = run_example(pytestconfig.rootpath, 'examples.generate_samples',
                         '--output', output, '--sample-count', '1')
    assert result.returncode == 2
    assert 'must be at least 2' in result.stderr


def test_imports_need_no_plotting_dependencies_or_io(tmp_path, pytestconfig):
    code = '''
import sys
from pathlib import Path
class NoPlotImports:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'matplotlib', 'plotly', 'PIL', 'numpy'}:
            raise AssertionError(f'Optional dependency imported: {fullname}')
sys.meta_path.insert(0, NoPlotImports())
def forbidden(*args, **kwargs):
    raise AssertionError('Import must not create directories')
Path.mkdir = forbidden
import examples.quickstart
import examples.showcase_ecef
import examples.showcase_offline
import examples.generate_samples
import examples.utilities.constants
import examples.utilities.trajectories
'''
    root = pytestconfig.rootpath
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / 'src'))),
               PYTHONIOENCODING='utf-8')
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('module_name', ['examples.showcase_ecef', 'examples.showcase_offline'])
def test_showcase_cli_output_argument(module_name, tmp_path, monkeypatch):
    module = importlib.import_module(module_name)
    seen = []
    monkeypatch.setattr(module, 'main', lambda output_dir: seen.append(output_dir))
    module.cli(['--output-dir', str(tmp_path)])
    assert seen == [tmp_path]


def test_sample_generator_defaults_and_validation():
    from examples.utilities import sample_ecef_trajectories
    tracks = sample_ecef_trajectories()
    assert [len(t.samples) for t in tracks] == [151, 151, 2]
    assert tracks[0].time_range == (0, 6000)
    with pytest.raises(ValueError, match='at least 2'):
        sample_ecef_trajectories(1)


@pytest.mark.parametrize('module_name, count', [
    ('examples.showcase_ecef', 9), ('examples.showcase_offline', 7),
])
def test_showcase_collects_survivors_without_saved_pngs(module_name, count, tmp_path, monkeypatch):
    from types import ModuleType
    module = importlib.import_module(module_name)
    calls = []
    retained = object()

    def callback(figure, *, path, label):
        assert label == 'custom'
        assert path.parent == tmp_path
        calls.append(figure)
        return retained if len(calls) % 2 else None

    def plotter(path, *args, post_plot=None, post_plot_kwargs=None, **kwargs):
        return post_plot(object(), path=path, **post_plot_kwargs)

    for name, functions in [
        ('offline_earth.renderers.matplotlib', ['matplotlib_world', 'matplotlib_globe']),
        ('offline_earth.renderers.plotly', ['plotly_globe']),
        ('offline_earth.timeseries', ['matplotlib_ecef_timeseries']),
    ]:
        stub = ModuleType(name)
        for function in functions:
            setattr(stub, function, plotter)
        monkeypatch.setitem(sys.modules, name, stub)
    monkeypatch.setattr(module, 'save_svg', lambda *a, **kw: None)
    monkeypatch.setattr(module, 'canvas_globe', lambda *a, **kw: None)
    result = module.main(tmp_path, post_plot=callback, post_plot_kwargs={'label': 'custom'})
    assert len(calls) == count
    assert result == [retained] * ((count + 1) // 2)
    assert not list(tmp_path.glob('*.png'))


@pytest.mark.parametrize('module_name', ['examples.showcase_ecef', 'examples.showcase_offline'])
@pytest.mark.parametrize('replacement', [False, True])
@pytest.mark.parametrize('failure', ['callback', 'output'])
def test_showcase_failure_closes_retained_figures(
        module_name, replacement, failure, tmp_path, monkeypatch):
    from types import ModuleType
    import matplotlib.pyplot as plt
    from offline_earth.figures import finish_figure
    from plotly.graph_objects import Figure as PlotlyFigure

    module = importlib.import_module(module_name)
    baseline = set(plt.get_fignums())
    retained = []
    calls = []

    def callback(figure, *, path):
        calls.append(figure)
        if failure == 'callback' and len(calls) == 2:
            raise RuntimeError('callback failure')
        if replacement:
            figure = PlotlyFigure() if isinstance(figure, PlotlyFigure) else plt.figure()
        retained.append(figure)
        return figure

    def plotter(path, *args, post_plot=None, post_plot_kwargs=None, **kwargs):
        # In ECEF the final Plotly output fails after an earlier Plotly survivor;
        # in the other gallery, canvas export fails after all figures survive.
        if failure == 'output' and path.name == 'interactive_ecef_geo_plotly.html':
            raise RuntimeError('output failure')
        is_plotly = path.suffix == '.html'
        figure = PlotlyFigure() if is_plotly else plt.figure()
        return finish_figure(figure, path, post_plot=post_plot,
                             post_plot_kwargs=post_plot_kwargs, save=lambda: None,
                             close=(lambda fig: None) if is_plotly else plt.close)

    for name, functions in [
        ('offline_earth.renderers.matplotlib', ['matplotlib_world', 'matplotlib_globe']),
        ('offline_earth.renderers.plotly', ['plotly_globe']),
        ('offline_earth.timeseries', ['matplotlib_ecef_timeseries']),
    ]:
        stub = ModuleType(name)
        for function in functions:
            setattr(stub, function, plotter)
        monkeypatch.setitem(sys.modules, name, stub)
    monkeypatch.setattr(module, 'save_svg', lambda *a, **kw: None)

    def canvas(*args, **kwargs):
        if failure == 'output' and module_name.endswith('showcase_offline'):
            raise RuntimeError('output failure')
    monkeypatch.setattr(module, 'canvas_globe', canvas)
    with pytest.raises(RuntimeError, match=f'{failure} failure'):
        module.main(tmp_path, post_plot=callback)
    assert retained
    assert set(plt.get_fignums()) == baseline
    if failure == 'output':
        assert any(isinstance(fig, PlotlyFigure) for fig in retained)
