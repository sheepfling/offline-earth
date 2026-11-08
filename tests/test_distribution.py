"""Keep the built core wheel small and free of development/runtime surprises."""
import email
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def test_built_core_wheel_contract(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-index',
                    '--no-deps', '--no-build-isolation', str(root),
                    '--wheel-dir', str(tmp_path)], check=True, capture_output=True)
    wheel, = tmp_path.glob('*.whl')
    assert wheel.stat().st_size < 3_000_000, 'Review unexpected wheel growth'
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert all(name.startswith(('trenton_offline_maps/',
                                    'trenton_offline_maps-')) for name in names)
        assert not any(name.startswith(('examples/', 'tests/', 'tools/', 'artifacts/'))
                       for name in names)
        metadata = email.message_from_bytes(archive.read(next(
            name for name in names if name.endswith('.dist-info/METADATA'))))
        # All requirements must be gated by an explicit extra, never core imports.
        assert all('; extra ==' in req for req in metadata.get_all('Requires-Dist', []))
        assert {'dev', 'examples', 'plot', 'interactive'} <= set(metadata.get_all('Provides-Extra', []))
        prefix = 'trenton_offline_maps/data/'
        manifest = json.loads(archive.read(prefix + 'ASSETS.json'))
        for name, item in manifest['assets'].items():
            data = archive.read(prefix + name)
            assert len(data) == item['size_bytes']
            assert hashlib.sha256(data).hexdigest() == item['sha256']
        assert any(name.endswith('BASEMAP_DATA_LGPL.txt') for name in names)
        assert any(name.endswith('BASEMAP_DATA_GPL.txt') for name in names)
        assert prefix + 'PROVENANCE.txt' in names
