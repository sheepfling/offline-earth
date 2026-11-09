import json

from offline_earth.canvas import _script_json
import pytest
from offline_earth.canvas import canvas_globe
from offline_earth.trajectory import EcefTrajectory
from offline_earth.visualize import RenderSpec, render_ecef

@pytest.mark.parametrize('mode', ['imagery','political','combined'])
def test_canvas_respects_initial_settings(tmp_path, mode):
    tr = EcefTrajectory.from_arrays('demo', [0, 10], [[7e6,0,0],[0,7e6,0]])
    p = render_ecef([tr], tmp_path/'test.html', spec=RenderSpec(
        backend='canvas', mode=mode, at_s=3, center_lon_deg=40, center_lat_deg=50))
    html = p.read_text(encoding='utf-8')
    config = json.loads(html.split('const initial = ')[1].split(';')[0])
    assert config == dict(mode=mode,at_s=3,center_lon_deg=40,center_lat_deg=50)
    assert "connect-src 'none'" in html
    assert '__INITIAL_CONFIG__' not in html

@pytest.mark.parametrize('kwargs', [{'mode':'bad'},{'at_s':float('nan')},
    {'center_lat_deg':91},{'center_lon_deg':float('inf')},{'at_s':11}])
def test_canvas_rejects_invalid_settings(tmp_path, kwargs):
    tr = EcefTrajectory.from_arrays('demo', [0,10], [[7e6,0,0],[0,7e6,0]])
    with pytest.raises(ValueError):
        canvas_globe(tmp_path/'test.html', trajectories=[tr], **kwargs)


def test_script_json_escapes_nested_values_without_changing_data():
    original = {'nested': ['</script><script>alert(1)</script>', '&<>', 'quote"', '\u2028']}
    encoded = _script_json(original)
    assert '<' not in encoded and '>' not in encoded and '&' not in encoded
    assert json.loads(encoded) == original


def test_canvas_escapes_all_caller_track_json(tmp_path):
    # Even malformed non-numeric input must not terminate the surrounding script.
    attack = '</script><img src=x onerror=alert(1)>'
    p = tmp_path / 'track.html'
    canvas_globe(p, track=[(attack, 0)])
    html = p.read_text(encoding='utf-8')
    assert attack not in html
    assert html.count('</script>') == 1
    assert '\\u003c/script\\u003e' in html


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_script_json_rejects_nonfinite_numbers(bad):
    with pytest.raises(ValueError):
        _script_json({'coordinate': bad})


def test_canvas_template_replacement_does_not_reinterpret_data(tmp_path):
    tr = EcefTrajectory.from_arrays('__TRACK_JSON__', [0], [(7e6, 0, 0)])
    path = tmp_path / 'tokens.html'
    canvas_globe(path, trajectories=[tr])
    assert '"name":"__TRACK_JSON__"' in path.read_text(encoding='utf-8')
