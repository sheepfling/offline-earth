"""Portable discovery tests use fake hosts; never launch/install a browser."""
import argparse
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import browser_support as support


def runner(path="/cache/playwright/chrome"):
    return SimpleNamespace(chromium=SimpleNamespace(executable_path=path, launch=Mock()))


def resolve(files=(), *, executable=None, platform="linux", env=None, paths=None,
            executable_files=None, playwright=None):
    files = set(files)
    executable_files = files if executable_files is None else set(executable_files)
    paths = {} if paths is None else paths
    return support.resolve_browser_executable(
        runner() if playwright is None else playwright, executable,
        platform=platform, environ={} if env is None else env,
        is_file=lambda path: path in files,
        access=lambda path, mode: path in executable_files,
        which=lambda name, path: paths.get(name),
    )


def test_cli_options_are_import_safe_and_explicit():
    parser = argparse.ArgumentParser()
    support.add_browser_arguments(parser)
    defaults = parser.parse_args([])
    assert vars(defaults) == {"browser_executable": None, "browser_arg": [], "headed": False}
    args = parser.parse_args(["--browser-executable", "/my browser/chrome", "--headed",
                              "--browser-arg=--no-sandbox", "--browser-arg=--disable-gpu"])
    assert args.browser_executable == "/my browser/chrome"
    assert args.headed
    assert args.browser_arg == ["--no-sandbox", "--disable-gpu"]


def test_cli_overrides_environment_and_discovery():
    assert resolve(["/cli", "/env", "/usr/bin/chromium"], executable="/cli",
                   env={support.BROWSER_ENV: "/env"}) == "/cli"


def test_environment_overrides_discovery():
    assert resolve(["/env", "/usr/bin/chromium"], env={support.BROWSER_ENV: "/env"}) == "/env"


@pytest.mark.parametrize("value", ["", "/missing", "/not-executable"])
@pytest.mark.parametrize("source", ["cli", "environment"])
def test_bad_explicit_config_never_falls_back(value, source):
    with pytest.raises(support.BrowserConfigurationError, match="automatic discovery is disabled"):
        resolve(["/usr/bin/chromium", "/not-executable"],
                executable=value if source == "cli" else None,
                env={support.BROWSER_ENV: value} if source == "environment" else {},
                executable_files=["/usr/bin/chromium"])


@pytest.mark.parametrize("platform,env,path", [
    ("linux", {}, "/usr/bin/chromium"),
    ("linux", {}, "/usr/local/bin/google-chrome"),
    ("linux", {}, "/snap/bin/chromium"),
    ("linux", {"HOME": "/home/test"}, "/home/test/.local/bin/microsoft-edge"),
    ("linux", {}, "/opt/google/chrome/chrome"),
    ("darwin", {}, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ("darwin", {"HOME": "/Users/test"}, "/Users/test/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ("darwin", {}, "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ("win32", {"ProgramFiles": r"C:\Program Files"}, r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("win32", {"PROGRAMFILES(X86)": r"C:\Program Files (x86)"}, r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("win32", {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}, r"C:\Users\test\AppData\Local\Chromium\Application\chrome.exe"),
])
def test_known_platform_locations(platform, env, path):
    assert resolve([path], platform=platform, env=env) == path


@pytest.mark.parametrize("platform,name,path", [
    ("linux", "chromium", "/custom/chromium"),
    ("darwin", "google-chrome", "/custom/chrome"),
    ("win32", "msedge.exe", r"D:\custom\msedge.exe"),
])
def test_path_discovery(platform, name, path):
    assert resolve([path], platform=platform, paths={name: path}) == path


def test_known_locations_and_browser_priority_are_stable():
    files = ["/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/local/bin/chromium", "/custom/chrome"]
    assert resolve(reversed(files), paths={"chromium": "/custom/chrome"}) == "/usr/bin/chromium"


def test_windows_does_not_require_posix_execute_bits():
    path = r"C:\Browser\chrome.exe"
    assert resolve([path], executable=path, platform="win32", executable_files=[]) == path


def test_unexecutable_discovered_candidate_is_skipped():
    assert resolve(["/usr/bin/chromium", "/usr/bin/google-chrome"],
                   executable_files=["/usr/bin/google-chrome"]) == "/usr/bin/google-chrome"


def test_existing_playwright_binary_is_last_resort():
    assert resolve(["/cache/playwright/chrome"]) == "/cache/playwright/chrome"
    assert resolve(["/cache/playwright/chrome", "/custom/chrome"],
                   paths={"chromium": "/custom/chrome"}) == "/custom/chrome"


def test_missing_browser_has_actionable_no_download_error():
    with pytest.raises(support.BrowserConfigurationError, match="No browser was downloaded or installed"):
        resolve([])


@pytest.mark.parametrize("headed,extra", [(False, []), (True, ["--no-sandbox", "--disable-gpu"])])
def test_launch_only_forwards_explicit_options(monkeypatch, headed, extra):
    playwright = runner()
    monkeypatch.setattr(support, "resolve_browser_executable", lambda p, executable: "/chosen")
    args = SimpleNamespace(browser_executable=None, headed=headed, browser_arg=extra)
    assert support.launch_browser(playwright, args) is playwright.chromium.launch.return_value
    playwright.chromium.launch.assert_called_once_with(
        executable_path="/chosen", headless=not headed, args=extra, chromium_sandbox=True)


def test_launch_error_is_not_retried(monkeypatch):
    playwright = runner()
    playwright.chromium.launch.side_effect = RuntimeError("sandbox unavailable")
    monkeypatch.setattr(support, "resolve_browser_executable", lambda p, executable: "/chosen")
    args = SimpleNamespace(browser_executable=None, headed=False, browser_arg=[])
    with pytest.raises(support.BrowserConfigurationError, match="No alternate browser"):
        support.launch_browser(playwright, args)
    assert playwright.chromium.launch.call_count == 1
