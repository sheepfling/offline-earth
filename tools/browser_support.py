"""Installed-only Chromium discovery shared by the optional browser audits.

Selection order: explicit CLI path, OFFLINE_EARTH_BROWSER_EXECUTABLE, known
system/user locations, PATH, then Playwright's existing Chromium executable.
Nothing in this module installs or downloads a browser. Launch failures are not
retried with a different browser or weaker security settings.
"""
from __future__ import annotations

import ntpath
import os
import posixpath
import shutil
import sys
from collections.abc import Callable, Mapping
from typing import Final

BROWSER_ENV: Final[str] = "OFFLINE_EARTH_BROWSER_EXECUTABLE"


class BrowserConfigurationError(RuntimeError):
    """No usable local browser was found, or its launch failed."""


def add_browser_arguments(parser) -> None:
    """Add common options without importing Playwright or inspecting the host."""
    parser.add_argument(
        "--browser-executable", metavar="PATH",
        help=f"Installed Chromium/Chrome/Edge executable (overrides {BROWSER_ENV}).",
    )
    parser.add_argument(
        "--browser-arg", action="append", default=[], metavar="ARG",
        help="Extra launch argument; repeat as --browser-arg=--flag. No flags added by this helper.",
    )
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")


def _candidates(platform: str, environ: Mapping[str, str]):
    """Yield deterministic system paths, user paths, and finally PATH names."""
    if platform == "win32":
        suffixes = (
            r"Google\Chrome\Application\chrome.exe",
            r"Chromium\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
        )
        # Environment variable names are case-insensitive on Windows. Plain test
        # mappings and callers need the same behavior as os.environ there.
        env = {key.upper(): value for key, value in environ.items()}
        roots = [env.get(key) for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for root in roots:
            if root:
                for suffix in suffixes:
                    yield ntpath.join(root, suffix), False
        names = ("chrome.exe", "chromium.exe", "msedge.exe")
    elif platform == "darwin":
        home = environ.get("HOME", os.path.expanduser("~"))
        for root in ("/Applications", posixpath.join(home, "Applications")):
            for app, binary in (("Google Chrome", "Google Chrome"), ("Chromium", "Chromium"),
                                ("Microsoft Edge", "Microsoft Edge")):
                yield f"{root}/{app}.app/Contents/MacOS/{binary}", False
        names = ("chromium", "chromium-browser", "google-chrome", "chrome", "microsoft-edge")
    else:
        home = environ.get("HOME", os.path.expanduser("~"))
        names = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
                 "microsoft-edge", "microsoft-edge-stable")
        for root in ("/usr/bin", "/usr/local/bin", "/snap/bin", posixpath.join(home, ".local/bin")):
            for name in names:
                yield posixpath.join(root, name), False
        for path in ("/opt/google/chrome/chrome", "/opt/microsoft/msedge/msedge"):
            yield path, False
    for name in names:
        yield name, True


def resolve_browser_executable(
    playwright, executable: str | None = None, *, platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    is_file: Callable[[str], bool] | None = None,
    access: Callable[[str, int], bool] | None = None,
    which: Callable[..., str | None] | None = None,
) -> str:
    """Resolve an installed executable, with injectable host probes for tests.

    Explicit values must name files (absolute or relative), not PATH commands.
    A bad explicit value is an error even if another browser is installed.
    Windows does not use POSIX executable permission bits.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    is_file = os.path.isfile if is_file is None else is_file
    access = os.access if access is None else access
    which = shutil.which if which is None else which

    def usable(path):
        return bool(path) and is_file(path) and (platform == "win32" or access(path, os.X_OK))

    explicit = executable if executable is not None else environ.get(BROWSER_ENV)
    if explicit is not None:
        if not usable(explicit):
            source = "--browser-executable" if executable is not None else BROWSER_ENV
            raise BrowserConfigurationError(
                f"{source} does not name an existing executable file: {explicit!r}. "
                "Correct the path; automatic discovery is disabled for explicit configuration."
            )
        path_module = ntpath if platform == "win32" else posixpath
        return path_module.abspath(explicit)

    for candidate, on_path in _candidates(platform, environ):
        path = which(candidate, path=environ.get("PATH", "")) if on_path else candidate
        if usable(path):
            return path
    # executable_path is only a local path lookup, not Playwright installation.
    bundled = playwright.chromium.executable_path
    if usable(bundled):
        return bundled
    raise BrowserConfigurationError(
        "No installed Chromium, Google Chrome, or Microsoft Edge executable found. "
        f"Set --browser-executable PATH or {BROWSER_ENV} to an existing browser. "
        "No browser was downloaded or installed."
    )


def launch_browser(playwright, args):
    """Launch the selected browser once; preserve sandboxing unless opted out."""
    executable = resolve_browser_executable(playwright, args.browser_executable)
    try:
        return playwright.chromium.launch(
            executable_path=executable, headless=not args.headed,
            args=list(args.browser_arg), chromium_sandbox=True,
        )
    except Exception as exc:
        raise BrowserConfigurationError(
            f"Could not launch installed browser {executable!r}: {exc}. "
            "Check browser compatibility, permissions, and display/sandbox support. "
            "Use --headed or explicit --browser-arg=VALUE only if your environment needs it. "
            "No alternate browser or weaker security settings were tried."
        ) from exc
