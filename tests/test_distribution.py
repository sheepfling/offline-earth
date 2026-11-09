"""Keep the built core wheel small and free of development/runtime surprises."""
import email
import hashlib
import json
from pathlib import PurePosixPath
import subprocess
import sys
import zipfile


def test_built_core_wheel_contract(tmp_path, pytestconfig):
    root = pytestconfig.rootpath
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-index',
                    '--no-deps', '--no-build-isolation', str(root),
                    '--wheel-dir', str(tmp_path)], check=True, capture_output=True)
    wheel, = tmp_path.glob('*.whl')
    assert wheel.stat().st_size < 3_000_000, 'Review unexpected wheel growth'
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        members = [PurePosixPath(name) for name in names]
        assert all(not path.is_absolute() and '..' not in path.parts for path in members)
        assert all(path.parts[0] == 'offline_earth' or
                   (path.parts[0].startswith('offline_earth-') and
                    path.parts[0].endswith('.dist-info')) for path in members)
        assert not any(path.parts[0] in {'examples', 'tests', 'tools', 'artifacts'}
                       for path in members)
        metadata_path, = [path for path in members if path.name == 'METADATA'
                          and path.parent.suffix == '.dist-info']
        metadata = email.message_from_bytes(archive.read(str(metadata_path)))
        # All requirements must be gated by an explicit extra, never core imports.
        assert all('; extra ==' in req for req in metadata.get_all('Requires-Dist', []))
        assert {'dev', 'examples', 'plot', 'interactive'} <= set(metadata.get_all('Provides-Extra', []))
        prefix = 'offline_earth/data/'
        manifest = json.loads(archive.read(prefix + 'ASSETS.json'))
        for name, item in manifest['assets'].items():
            data = archive.read(prefix + name)
            assert len(data) == item['size_bytes']
            assert hashlib.sha256(data).hexdigest() == item['sha256']
        assert not any('BASEMAP_DATA_' in name for name in names)
        assert any(name.endswith('/licenses/README.md') for name in names)
        assert 'offline_earth/templates/canvas.html' in names
        assert prefix + 'PROVENANCE.txt' not in names
        image = manifest['assets']['blue_marble.jpg']
        assert image['source_url'].startswith('https://assets.science.nasa.gov/')
        assert image['credit'] == 'NASA Earth Observatory'
        assert image['imagery_month'] == '2004-07'
