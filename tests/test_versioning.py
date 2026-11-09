"""SCM versions must survive offline source and wheel handoffs."""
import email
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import venv
import zipfile

from packaging.version import Version
import pytest


def clean_env(**updates):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('SETUPTOOLS_SCM_') and key != 'PYTHONPATH'}
    env.update(PYTHONIOENCODING='utf-8', PIP_NO_INDEX='1', **updates)
    return env


def run(args, cwd, *, check=True, env=None):
    return subprocess.run(args, cwd=cwd, env=env or clean_env(), check=check,
                          capture_output=True, text=True, encoding='utf-8', timeout=120)


@pytest.fixture
def source(tmp_path, pytestconfig):
    root = pytestconfig.rootpath
    source = tmp_path / 'source'
    source.mkdir()
    for name in ('pyproject.toml', 'README.md', '.gitignore'):
        shutil.copyfile(root / name, source / name)
    shutil.copytree(root / 'src', source / 'src',
                    ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    return source


@pytest.fixture
def repository(source):
    git = shutil.which('git')
    if git is None:
        pytest.skip('Version-history tests require Git, not the installed library')
    run([git, 'init', '-b', 'main'], source)
    run([git, 'config', 'user.name', 'Packaging test'], source)
    run([git, 'config', 'user.email', 'packaging@example.invalid'], source)
    run([git, 'config', 'commit.gpgsign', 'false'], source)
    run([git, 'config', 'tag.gpgsign', 'false'], source)
    run([git, 'add', '.'], source)
    run([git, 'commit', '-m', 'Initial test source'], source)
    return source, git


def build(source, kind, out, *, check=True, env=None):
    # Call the PEP 517 backend with installed build tools. No isolation environment
    # or dependency acquisition is created, and Python network calls are denied.
    script = '''
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
def deny_network(event, args):
    if event.startswith('socket.'):
        raise AssertionError('Build attempted network: ' + event)
sys.addaudithook(deny_network)
from setuptools import build_meta
print(getattr(build_meta, 'build_' + sys.argv[1])(sys.argv[2]))
'''
    result = run([sys.executable, '-c', script, kind, str(out)], source,
                 check=check, env=env)
    if check:
        suffix = '*.whl' if kind == 'wheel' else '*.tar.gz'
        artifact, = out.glob(suffix)
        return artifact
    return result


def wheel_metadata(wheel):
    with zipfile.ZipFile(wheel) as archive:
        name, = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
        return email.message_from_bytes(archive.read(name))


def test_untagged_checkout_is_development_version(repository, tmp_path):
    source, _ = repository
    metadata = wheel_metadata(build(source, 'wheel', tmp_path / 'wheel'))
    version = Version(metadata['Version'])
    assert version.base_version == '0.1'
    assert version.dev == 1
    assert version.local.startswith('g')
    assert 'setuptools-scm' not in '\n'.join(
        req for req in metadata.get_all('Requires-Dist', []) if 'extra ==' not in req)


def test_tag_commit_and_dirty_versions(repository, tmp_path):
    source, git = repository
    # Tags exist only in this disposable fixture, never in the project repository.
    run([git, 'tag', 'v0.0.1'], source)
    with (source / 'README.md').open('a', encoding='utf-8') as stream:
        stream.write('\nChanges for the next version.\n')
    run([git, 'commit', '-am', 'Changes after the previous squash'], source)
    before_tag = wheel_metadata(build(source, 'wheel', tmp_path / 'before-tag'))['Version']
    assert Version(before_tag).public == '0.0.2.dev1'
    run([git, 'tag', 'v0.0.2'], source)
    wheel = build(source, 'wheel', tmp_path / 'tagged')
    assert wheel.name == 'offline_earth-0.0.2-py3-none-any.whl'
    assert wheel_metadata(wheel)['Version'] == '0.0.2'
    with (source / 'README.md').open('a', encoding='utf-8') as stream:
        stream.write('\nTest commit after the tag.\n')
    run([git, 'commit', '-am', 'Next test commit'], source)
    version = Version(wheel_metadata(build(source, 'wheel', tmp_path / 'next'))['Version'])
    assert version.public == '0.0.3.dev1'
    assert version.local.startswith('g') and '.d' not in version.local
    with (source / 'README.md').open('a', encoding='utf-8') as stream:
        stream.write('\nUncommitted test change.\n')
    dirty = Version(wheel_metadata(build(source, 'wheel', tmp_path / 'dirty'))['Version'])
    assert dirty.public == version.public
    assert dirty.local.startswith(version.local + '.d')


@pytest.mark.parametrize('tagged', [False, True])
def test_sdist_preserves_version_without_git(repository, tmp_path, tagged):
    source, git = repository
    if tagged:
        run([git, 'tag', 'v0.0.2'], source)
    sdist = build(source, 'sdist', tmp_path / 'sdist')
    unpacked = tmp_path / 'unpacked'
    with tarfile.open(sdist) as archive:
        assert all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                   for name in archive.getnames())
        options = {'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}
        archive.extractall(unpacked, **options)
    extracted, = unpacked.iterdir()
    assert not (extracted / '.git').exists()
    version = email.message_from_bytes((extracted / 'PKG-INFO').read_bytes())['Version']
    assert version == '0.0.2' if tagged else Version(version).is_devrelease
    # An empty PATH prevents Git discovery, proving that sdist metadata suffices.
    wheel = build(extracted, 'wheel', tmp_path / 'rebuilt', env=clean_env(PATH=''))
    assert wheel_metadata(wheel)['Version'] == version


def test_installed_wheel_needs_no_git_or_scm(repository, tmp_path):
    source, _ = repository
    wheel = build(source, 'wheel', tmp_path / 'wheel')
    version = wheel_metadata(wheel)['Version']
    environment = tmp_path / 'installed'
    # Use the test runner's pip: minimal Python installations may omit ensurepip.
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    site = run([str(python), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'],
               tmp_path).stdout.strip()
    run([sys.executable, '-m', 'pip', 'install', '--target', site, '--no-index', '--no-deps',
         '--only-binary=:all:', str(wheel)], tmp_path)
    script = '''
import sys
from importlib.metadata import version
from importlib.util import find_spec
assert find_spec('setuptools_scm') is None
assert version('offline-earth') == sys.argv[1]
def deny_network(event, args):
    if event.startswith('socket.'):
        raise AssertionError('Runtime attempted network: ' + event)
sys.addaudithook(deny_network)
from offline_earth.canvas import canvas_globe
canvas_globe('earth.html')
from pathlib import Path
assert Path('earth.html').stat().st_size > 1000
'''
    run([str(python), '-I', '-c', script, version], tmp_path, env=clean_env(PATH=''))


def test_unversioned_source_fails_instead_of_inventing_release(source, tmp_path):
    result = build(source, 'wheel', tmp_path / 'wheel', check=False, env=clean_env(PATH=''))
    assert result.returncode != 0
    assert 'unable to detect version' in result.stdout + result.stderr


def test_shallow_checkout_fails_without_fetching(repository, tmp_path):
    source, git = repository
    shallow = tmp_path / 'shallow'
    run([git, 'clone', '--depth=1', source.as_uri(), str(shallow)], tmp_path)
    assert run([git, 'rev-parse', '--is-shallow-repository'], shallow).stdout.strip() == 'true'
    result = build(shallow, 'wheel', tmp_path / 'wheel', check=False)
    assert result.returncode != 0
    assert 'is shallow' in result.stdout + result.stderr
    assert run([git, 'rev-parse', '--is-shallow-repository'], shallow).stdout.strip() == 'true'
