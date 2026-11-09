"""UTF-8 files must not depend on the host's default text encoding."""
from contextlib import contextmanager
from importlib.resources import files
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def cp1252_text_default(monkeypatch):
    """Model Windows text-file defaults, without changing PYTHONUTF8 or the OS.

    Path.open/read_text/write_text use io.open. Explicit encodings pass through;
    omitted encodings (including pathlib's 'locale' sentinel) become cp1252.
    Binary I/O is unaffected. Keep optional dependency imports outside the scope.
    """
    original = io.open
    original_text_encoding = io.text_encoding

    def windows_text_encoding(encoding, stacklevel=2):
        if encoding in (None, "locale"):
            return "cp1252"
        return original_text_encoding(encoding, stacklevel)

    def windows_open(file, mode='r', buffering=-1, encoding=None, errors=None,
                     newline=None, closefd=True, opener=None):
        if 'b' not in mode and encoding in (None, 'locale'):
            encoding = 'cp1252'
        return original(file, mode, buffering, encoding, errors, newline, closefd, opener)

    @contextmanager
    def simulated_default():
        with monkeypatch.context() as patch:
            # pathlib resolves omitted encodings before opening under UTF-8 mode.
            patch.setattr(io, 'text_encoding', windows_text_encoding)
            patch.setattr(io, 'open', windows_open)
            yield

    return simulated_default


def test_simulated_default_is_not_utf8(tmp_path, cp1252_text_default):
    path = tmp_path / 'probe.txt'
    path.write_bytes('é'.encode('utf-8'))
    with cp1252_text_default():
        # Intentionally unspecified: prove the regression harness changes defaults.
        assert path.read_text() == 'Ã©'
        assert path.read_text(encoding='utf-8') == 'é'
        with pytest.raises(UnicodeEncodeError):
            path.write_text('▶')


def test_real_canvas_template_and_assets_under_cp1252(tmp_path, cp1252_text_default):
    from offline_earth.assets import countries
    from offline_earth.canvas import canvas_globe
    from offline_earth.trajectory import EcefTrajectory, read_trajectories, write_trajectories

    track = EcefTrajectory.from_arrays('地球 café ▶', [0, 1], [(7e6, 0, 0), (7e6, 1, 1)])
    html = tmp_path / 'earth.html'
    data = tmp_path / 'track.json'
    with cp1252_text_default():
        assert len(countries()) == 177
        write_trajectories(data, [track])
        assert read_trajectories(data)[0].name == track.name
        canvas_globe(html, trajectories=[track])
    text = html.read_bytes().decode('utf-8')
    assert '▶' in text and '❚' in text
    assert json.dumps(track.name) in text
    assert 'data:image/jpeg;base64,' in text


def test_showcase_preserves_utf8_manifest_and_html(tmp_path, monkeypatch, cp1252_text_default):
    # Rendering is covered elsewhere. Here exercise the real catalog's resource
    # copy, template, output files and archive without expensive optional renders.
    pytest.importorskip('matplotlib')
    from examples import final_showcase
    import offline_earth.svg as svg
    import offline_earth.timeseries as timeseries
    import offline_earth.visualize as visualize

    def render_stub(*args, **kwargs):
        path = kwargs.get('path', args[0] if args else None)
        Path(path).write_bytes(b'rendered output')

    monkeypatch.setattr(visualize, 'render_ecef', lambda data, path, **kw: render_stub(path))
    monkeypatch.setattr(svg, 'save_svg', render_stub)
    monkeypatch.setattr(timeseries, 'matplotlib_ecef_timeseries', render_stub)
    monkeypatch.setattr(final_showcase, 'version', lambda name: 'test')
    expected_manifest = files('offline_earth').joinpath('data/ASSETS.json').read_text(encoding='utf-8')
    out = tmp_path / 'catalog'
    with cp1252_text_default():
        archive = final_showcase.build_showcase(out)
    assert archive.is_file()
    assert (out / 'ASSETS.json').read_text(encoding='utf-8') == expected_manifest
    html = (out / 'index.html').read_bytes().decode('utf-8')
    assert '°' in html and '±' in html and '−' in html
    assert '__RENDERER_ROWS__' not in html
