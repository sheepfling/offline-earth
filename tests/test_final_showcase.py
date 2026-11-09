"""Functional option coverage without publication or browser claims."""
import builtins
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import socket
from typing import get_args
import zipfile

import pytest

from examples import final_showcase
from offline_earth.visualize import Backend, RenderSpec


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.images, self.scripts = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a': self.links.append(attrs.get('href'))
        if tag == 'img':
            assert attrs.get('alt')
            self.images.append(attrs.get('src'))
        if tag == 'script': self.scripts.append(attrs)


def test_import_is_safe(monkeypatch):
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in {'matplotlib', 'plotly', 'numpy', 'PIL', 'playwright'}:
            pytest.fail(f'Optional import on module load: {name}')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(Path, 'mkdir', lambda *a, **kw: pytest.fail('Import created files'))
    spec = importlib.util.spec_from_file_location('catalog_import', final_showcase.__file__)
    module = importlib.util.module_from_spec(spec)
    # NamedTuple needs normal module registration for its annotations.
    import sys
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert module.output_directory().name == 'final-showcase'


def test_cli_selects_output(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(final_showcase, 'build_showcase', lambda p: seen.append(p) or tmp_path/'catalog.zip')
    assert final_showcase.main(['--output-dir', str(tmp_path)]) == 0
    assert seen == [tmp_path]


def test_catalog_matches_cli_flags_and_defaults(capsys):
    from offline_earth.cli import main
    with pytest.raises(SystemExit) as error:
        main(['--help'])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    template = Path(final_showcase.__file__).with_name('templates').joinpath('showcase.html').read_text(encoding='utf-8')
    for flag in ('--renderer', '--mode', '--ecef', '--at-s', '--center-lon-deg', '--center-lat-deg', '--extent-earth-radii'):
        assert flag in help_text and flag in template
    assert '{svg,map,globe,interactive,canvas,timeseries}' in help_text
    assert RenderSpec().backend == 'map'
    assert RenderSpec().center_lon_deg == -30
    assert RenderSpec().center_lat_deg == 22
    assert RenderSpec().extent_earth_radii == 1.35


def test_actual_catalog_covers_all_backends_and_inputs_offline(tmp_path, monkeypatch):
    from offline_earth.trajectory import read_trajectories
    def denied(*a, **kw): raise AssertionError('Catalog generation attempted networking')
    for method in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, method, denied)
    out = tmp_path/'catalog'
    out.mkdir()
    (out/'unrelated.txt').write_text('Do not include', encoding='utf-8')
    archive = final_showcase.build_showcase(out)
    manifest = json.loads((out/'showcase-manifest.json').read_text(encoding='utf-8'))
    cases = manifest['examples']
    assert len(cases) == 18
    assert {c['backend'] for c in cases} == set(get_args(Backend))
    for backend in ('svg', 'map', 'globe'):
        assert {c['mode'] for c in cases if c['backend'] == backend} >= set(final_showcase.MODES)
    assert sum(c['backend'] == 'canvas' for c in cases) == 1
    assert sum(c['backend'] == 'plotly' for c in cases) == 1
    assert all(c['mode'] is None for c in cases if c['backend'] == 'timeseries')
    assert 'extent_earth_radii' not in manifest['main_canvas_camera']
    assert manifest['plotly_camera'] == 'Default Plotly 3D perspective'
    assert 'Not verified' in manifest['browser_validation']
    html = (out/'index.html').read_text(encoding='utf-8')
    parser = Links(); parser.feed(html)
    assert not parser.scripts
    assert 'One planet' not in html and 'Every perspective' not in html
    assert 'metre' not in html.lower()
    for path in parser.links + parser.images:
        assert not path.startswith(('http:', 'https:', '//'))
        assert (out/path).is_file()
    for name, item in manifest['files'].items():
        raw=(out/name).read_bytes()
        assert len(raw)==item['size_bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
    assert json.loads((out/'sample-ecef.json').read_text(encoding='utf-8'))['units'] == 'meters'
    assert json.loads((out/'sample-high-altitude.json').read_text(encoding='utf-8'))['units'] == 'meters'
    json_tracks=read_trajectories(out/'sample-ecef.json')
    csv_tracks=read_trajectories(out/'sample-ecef.csv')
    assert [t.samples for t in json_tracks]==[t.samples for t in csv_tracks]
    assert [t.name for t in json_tracks]==[t.name for t in csv_tracks]
    assert [t.color for t in json_tracks]!=[t.color for t in csv_tracks]
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == {'offline-earth-options/'+name for name in [*manifest['files'], 'showcase-manifest.json']}
    assert archive.stat().st_size < 20_000_000
