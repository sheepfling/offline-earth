"""Examples and browser helpers are import-safe and compute output paths on demand."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize('relative', [
    'examples/showcase_ecef.py', 'examples/showcase_offline.py',
    'tools/verify_ecef_browser.py', 'tools/verify_browser.py',
])
def test_helper_import_has_no_filesystem_side_effects(relative, monkeypatch, pytestconfig):
    root = pytestconfig.rootpath
    path = root / relative
    def forbidden(*args, **kwargs):
        raise AssertionError('Import must not create output directories')
    monkeypatch.setattr(Path, 'mkdir', forbidden)
    spec = importlib.util.spec_from_file_location('helper_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not any(name in vars(module) for name in ('ROOT','OUT','PAGE','HTML','SCREENSHOT','RESULT'))
    output = module.output_directory() if hasattr(module, 'output_directory') else module.output_paths()[0]
    assert output.is_relative_to(root / 'artifacts')
    assert callable(module.main)
