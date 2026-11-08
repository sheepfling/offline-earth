"""Optional Chromium smoke test. Tests Canvas offline without requiring WebGL.

Requires locally installed Chromium and Playwright (test-only; not library deps).
Run: python tools/verify_browser.py
"""
from __future__ import annotations

import json
from pathlib import Path

def output_paths() -> tuple[Path, Path]:
    directory = Path(__file__).resolve().parents[1] / "artifacts" / "earth"
    return (directory / "interactive_canvas_no_webgl.html",
            directory / "interactive_canvas_browser.png")


def main() -> None:
    from playwright.sync_api import sync_playwright
    html_path, screenshot_path = output_paths()
    attempts: list[str] = []
    errors: list[str] = []
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                                         args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1180, "height": 960})
        page.route("**/*", lambda route: (attempts.append(route.request.url), route.abort()))
        page.on("pageerror", lambda err: errors.append(str(err)))
        # file:// navigation is forbidden by this runner's sandbox. Inject HTML bytes
        # directly: the same DOM/scripts execute, with the network blocked.
        page.set_content(html_path.read_text(encoding="utf-8"), wait_until="domcontentloaded", timeout=25000)
        page.wait_for_selector("canvas[data-ready='1']", timeout=25000)
        page.screenshot(path=str(screenshot_path), full_page=True)
        assert page.locator("canvas").get_attribute("data-mode") == "combined"
        for value in ("political", "imagery", "combined"):
            page.get_by_role("button", name={"political":"Political", "imagery":"Blue Marble",
                                                  "combined":"Both"}[value]).click()
            page.wait_for_function(f'document.querySelector("canvas").dataset.mode==="{value}"')
        page.locator("canvas").drag_to(page.locator("canvas"), source_position={"x": 220, "y": 250},
                                       target_position={"x": 350, "y": 310})
        assert not attempts, f"Unexpected remote request: {attempts}"
        assert not errors, f"Browser script error: {errors}"
        browser.close()
    print(json.dumps({"browser": "Chromium", "dom_rendered": True, "all_modes_tested": True,
                      "drag_tested": True, "attempted_network_requests": attempts,
                      "script_errors": errors, "screenshot": str(screenshot_path)}, indent=2))


if __name__ == "__main__":
    main()
