import json
import pytest
from trenton_offline_maps.canvas import canvas_globe
from trenton_offline_maps.trajectory import EcefTrajectory
from trenton_offline_maps.visualize import RenderSpec, render_ecef

@pytest.mark.parametrize('mode', ['imagery','political','combined'])
def test_canvas_respects_initial_settings(tmp_path, mode):
    tr = EcefTrajectory.from_arrays('demo', [0, 10], [[7e6,0,0],[0,7e6,0]])
    p = render_ecef([tr], tmp_path/'test.html', spec=RenderSpec(
        backend='canvas', mode=mode, at_s=3, center_lon=40, center_lat=50))
    html = p.read_text()
    config = json.loads(html.split('const initial = ')[1].split(';')[0])
    assert config == dict(mode=mode,at_s=3,center_lon=40,center_lat=50)
    assert "connect-src 'none'" in html
    assert '__INITIAL_CONFIG__' not in html

@pytest.mark.parametrize('kwargs', [{'mode':'bad'},{'at_s':float('nan')},
    {'center_lat':91},{'center_lon':float('inf')},{'at_s':11}])
def test_canvas_rejects_invalid_settings(tmp_path, kwargs):
    tr = EcefTrajectory.from_arrays('demo', [0,10], [[7e6,0,0],[0,7e6,0]])
    with pytest.raises(ValueError):
        canvas_globe(tmp_path/'test.html', trajectories=[tr], **kwargs)
