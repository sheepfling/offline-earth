"""Fast smoke-audit contract tests; these do not certify browser rendering."""
import builtins
import importlib.util
import json
import ntpath
from pathlib import Path

import pytest

from tools import verify_plotly_browser as audit


def test_import_is_safe_without_optional_dependencies(monkeypatch):
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in {'playwright', 'plotly', 'numpy', 'PIL', 'offline_earth', 'examples'}:
            raise AssertionError(f'Optional import at module load: {name}')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(Path, 'mkdir', lambda *a, **kw: pytest.fail('Import created directory'))
    spec = importlib.util.spec_from_file_location('plotly_audit_import_test', audit.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.output_directory().parts[-3:] == ('artifacts', 'browser', 'plotly')


def test_pixel_metrics_rejects_blank_and_invisible_trajectories(tmp_path):
    Image = pytest.importorskip('PIL.Image')
    a, b = tmp_path / 'a.png', tmp_path / 'b.png'
    Image.new('RGB', (120, 120), '#061522').save(a)
    Image.new('RGB', (120, 120), '#061522').save(b)
    with pytest.raises(AssertionError, match='blank'):
        audit.validate_pixels(audit.pixel_metrics(a, b))
    image = Image.new('RGB', (120, 120))
    image.putdata([(x % 256, y % 256, (x+y) % 256) for y in range(120) for x in range(120)])
    image.save(a)
    image.save(b)
    with pytest.raises(AssertionError, match='trajectory'):
        audit.validate_pixels(audit.pixel_metrics(a, b))
    image.paste((255, 0, 0), (10, 10, 30, 30))
    image.save(b)
    audit.validate_pixels(audit.pixel_metrics(a, b))


def test_failure_writes_reviewable_report_and_returns_nonzero(monkeypatch, tmp_path):
    def fail(args, report):
        report['script_errors'].append('Injected JavaScript failure')
        raise AssertionError('Injected audit failure')
    monkeypatch.setattr(audit, 'run_audit', fail)
    assert audit.main(['--output-dir', str(tmp_path)]) == 1
    result = json.loads((tmp_path / 'plotly_browser_audit.json').read_text(encoding='utf-8'))
    assert result['status'] == 'failed'
    assert result['script_errors'] == ['Injected JavaScript failure']
    assert 'Injected audit failure' in result['error']


def test_success_report(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, 'run_audit', lambda args, report: report.update(scene={'verified': True}))
    assert audit.main(['--output-dir', str(tmp_path)]) == 0
    assert json.loads((tmp_path / 'plotly_browser_audit.json').read_text(encoding='utf-8'))['status'] == 'passed'


def test_scene_uses_public_data_and_actual_webgl_metrics():
    assert '_fullLayout' not in audit.SCENE_METRICS_JS
    assert 'drawingBufferWidth' in audit.SCENE_METRICS_JS
    assert 'isContextLost' in audit.SCENE_METRICS_JS
    assert 'ECEF coordinate mismatch' in audit.SCENE_METRICS_JS


def test_fixed_layout_disables_autorange_and_preserves_camera():
    layout = audit.scene_layout([{'xyz_km': [[-8000, 100, 6000], [10, 20, 30]]}])
    for axis in 'xyz':
        assert layout[f'scene.{axis}axis.range'] == [-8800, 8800]
        assert layout[f'scene.{axis}axis.autorange'] is False
    assert layout['scene.aspectmode'] == 'manual'
    assert layout['scene.camera']['eye'] == {'x': 1.25, 'y': 1.25, 'z': 1.25}


@pytest.mark.parametrize('timeout', ['0', '-1'])
def test_nonpositive_timeout_rejected_before_output(tmp_path, timeout):
    out = tmp_path / 'not-created'
    with pytest.raises(SystemExit) as error:
        audit.main(['--output-dir', str(out), '--timeout-ms', timeout])
    assert error.value.code == 2
    assert not out.exists()


@pytest.mark.parametrize('home_expansion', ['native', 'windows'])
def test_output_normalized_and_failure_keeps_runtime_metadata(monkeypatch, tmp_path, home_expansion):
    # pathlib uses HOME on POSIX but USERPROFILE on Windows.
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    if home_expansion == 'windows':
        monkeypatch.setattr(Path, 'expanduser', lambda path: Path(ntpath.expanduser(str(path))))
    seen = []
    def fail(args, report):
        seen.append(args.output_dir)
        raise RuntimeError('Browser unavailable')
    monkeypatch.setattr(audit, 'run_audit', fail)
    assert audit.main(['--output-dir', '~/audit', '--browser-arg=--example']) == 1
    assert seen == [tmp_path / 'audit']
    report = json.loads((tmp_path / 'audit' / 'plotly_browser_audit.json').read_text(encoding='utf-8'))
    assert report['runtime']['platform']
    assert report['runtime']['python']
    assert report['runtime']['headless'] is True
    assert report['runtime']['launch_args'] == ['--example']
    assert set(report['runtime']['packages']) == {'playwright', 'plotly', 'numpy', 'pillow'}


def test_snapshot_failure_is_secondary():
    class DeadPageAudit:
        def snapshot(self, page):
            raise RuntimeError('Page crashed')
    report = {'error': 'Original failure'}
    audit.capture_snapshot(DeadPageAudit(), None, report)
    assert report['error'] == 'Original failure'
    assert report['snapshot_error'] == 'RuntimeError: Page crashed'


def test_launch_failure_preserves_html_hash_and_selected_executable(monkeypatch, tmp_path):
    from argparse import Namespace
    from contextlib import nullcontext
    import hashlib
    from tools import browser_support
    sync_api = pytest.importorskip('playwright.sync_api')
    def generate(target):
        target.write_text('<html>embedded scene</html>', encoding='utf-8')
        return [{'xyz_km': [[7000, 0, 0]]}]
    def fail_launch(pw, args):
        raise RuntimeError('Injected launch failure')
    monkeypatch.setattr(audit, 'generate_scene', generate)
    monkeypatch.setattr(sync_api, 'sync_playwright', lambda: nullcontext(object()))
    monkeypatch.setattr(browser_support, 'resolve_browser_executable', lambda pw, path: '/test/chromium')
    monkeypatch.setattr(browser_support, 'launch_browser', fail_launch)
    report = {'runtime': {}}
    with pytest.raises(RuntimeError, match='Injected launch failure'):
        audit.run_audit(Namespace(output_dir=tmp_path, browser_executable=None), report)
    assert report['html_sha256'] == hashlib.sha256(b'<html>embedded scene</html>').hexdigest()
    assert report['runtime']['browser_executable'] == '/test/chromium'


def test_colorful_trajectories_cannot_mask_blank_earth_baseline(tmp_path):
    Image = pytest.importorskip('PIL.Image')
    scene, baseline = tmp_path / 'scene.png', tmp_path / 'baseline.png'
    image = Image.new('RGB', (120, 120))
    image.putdata([(x, y, (x+y) % 256) for y in range(120) for x in range(120)])
    image.save(scene)
    Image.new('RGB', image.size, 'black').save(baseline)
    metrics = audit.pixel_metrics(scene, baseline)
    assert metrics['trajectory_changed_pixels'] > 20
    assert metrics['distinct_colors'] > 32
    with pytest.raises(AssertionError, match='Earth-only baseline'):
        audit.validate_pixels(metrics)


def test_scene_requires_public_visible_surface_evidence():
    assert "t.type === 'surface'" in audit.SCENE_METRICS_JS
    assert "No visible Earth surface trace" in audit.SCENE_METRICS_JS


@pytest.mark.parametrize('kind', ['network_attempts', 'script_errors', 'console_errors'])
def test_final_recorded_errors_never_pass(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(audit, 'run_audit', lambda args, report: report[kind].append('Late failure'))
    assert audit.main(['--output-dir', str(tmp_path)]) == 1
    result = json.loads((tmp_path / 'plotly_browser_audit.json').read_text(encoding='utf-8'))
    assert result['status'] == 'failed'
    assert result[kind] == ['Late failure']
