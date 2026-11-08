"""Optional browser integration audit, all external requests explicitly blocked."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "review" / "ecef" / "interactive_ecef_canvas.html"
SCREENSHOT = ROOT / "review" / "ecef" / "interactive_browser_preview.png"
RESULT = ROOT / "review" / "ecef" / "browser_ecef_audit.json"


def main() -> None:
    attempts: list[str] = []
    script_errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                                     args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1180, "height": 950})
        page.route("**/*", lambda route: (attempts.append(route.request.url), route.abort()))
        page.on("pageerror", lambda err: script_errors.append(str(err)))
        page.set_content(HTML.read_text(encoding="utf-8"), wait_until="domcontentloaded",
                         timeout=30000)
        page.wait_for_selector("canvas[data-ready='1']", timeout=30000)
        for value in ("political", "imagery", "combined"):
            page.locator(f"#{value}").click()
            page.wait_for_function(f'document.querySelector("canvas").dataset.mode==="{value}"')
        page.locator("#time").evaluate("""(el) => {
            el.value = "3600"; el.dispatchEvent(new Event("input", {bubbles: true}));
        }""")
        page.wait_for_timeout(180)
        scrub_time = page.locator("#clock").evaluate("(el) => el.value")
        page.locator("#play").evaluate("(el) => el.click()")
        page.wait_for_timeout(240)
        playback_time = float(page.locator("#time").input_value())
        page.locator("#play").evaluate("(el) => el.click()")
        page.locator("canvas").drag_to(page.locator("canvas"),
                                       source_position={"x": 210, "y": 230},
                                       target_position={"x": 270, "y": 260})
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        assert not attempts, f"Browser network attempted: {attempts}"
        assert not script_errors, f"JS exceptions: {script_errors}"
        assert playback_time > 3600, "Play did not advance time"
        result = {"browser": "Chromium (headless)", "browser_rendered": True,
                  "view_buttons_tested": ["political", "imagery", "combined"],
                  "time_scrubber_tested": scrub_time,
                  "playback_advanced_s": playback_time,
                  "drag_tested": True, "network_attempts": attempts,
                  "script_errors": script_errors,
                  "scope": "Canvas only; Plotly WebGL not browser certified",
                  "load_mechanism": "page.set_content (local file navigation restricted)"}
        browser.close()
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
