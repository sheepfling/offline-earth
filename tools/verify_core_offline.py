"""Run using a clean installed-wheel interpreter; stdlib only, sockets denied."""
import json
import socket
import tempfile
from pathlib import Path
from importlib.resources import files

def denied(*args, **kwargs):
    raise AssertionError('Network access attempted')
socket.socket = socket.create_connection = socket.getaddrinfo = denied
from trenton_offline_maps import countries
from trenton_offline_maps.trajectory import EcefTrajectory
from trenton_offline_maps.visualize import RenderSpec, render_ecef

tr = EcefTrajectory.from_arrays('offline smoke', [0,10], [[7e6,0,0],[0,7e6,0]])
with tempfile.TemporaryDirectory() as d:
    for mode in ('imagery','political','combined'):
        for backend, extension in [('svg','svg'),('canvas','html')]:
            p = render_ecef([tr], Path(d)/f'{mode}-{backend}.{extension}',
                            spec=RenderSpec(backend=backend, mode=mode,at_s=5))
            assert p.stat().st_size > 1000
    data = files('trenton_offline_maps').joinpath('data')
    manifest = json.loads(data.joinpath('ASSETS.json').read_text())
    import hashlib
    for name, entry in manifest['assets'].items():
        assert hashlib.sha256(data.joinpath(name).read_bytes()).hexdigest() == entry['sha256']
assert len(countries()) == 177
print('PASS: installed wheel; six SVG/Canvas renders; assets verified; Python socket/DNS calls blocked')
