"""Reproducible Canvas interaction audit using an existing local browser."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Final

from tools.browser_audit import OfflinePageAudit
from tools.browser_support import add_browser_arguments, launch_browser, resolve_browser_executable


CANVAS_PIXELS: Final[str] = """() => {
  const canvas = document.querySelector('canvas');
  const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
  let hash = 2166136261; const colors = new Set();
  for (let i = 0; i < pixels.length; i += 64) {
    const rgb = (pixels[i] << 16) | (pixels[i+1] << 8) | pixels[i+2];
    colors.add(rgb); hash = Math.imul(hash ^ rgb, 16777619);
  }
  return {width: canvas.width, height: canvas.height, colors: colors.size, hash: hash >>> 0};
}"""


def settled_pixels(page):
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    pixels = page.evaluate(CANVAS_PIXELS)
    if pixels["colors"] < 50 or min(pixels["width"], pixels["height"]) < 100:
        raise AssertionError(f"Canvas did not contain a rendered globe: {pixels}")
    return pixels


def exercise_canvas(page, *, ecef: bool) -> dict:
    page.wait_for_selector("canvas[data-ready='1']", timeout=30000)
    modes = {}
    for mode in ("political", "imagery", "combined"):
        page.locator(f"#{mode}").click()
        page.wait_for_function("mode => document.querySelector('canvas').dataset.mode === mode", arg=mode)
        modes[mode] = settled_pixels(page)
    if len({pixels["hash"] for pixels in modes.values()}) != 3:
        raise AssertionError("Layer buttons did not produce three distinct rendered images")
    result = {"mode_pixels": modes}
    if ecef:
        limits = page.locator("#time").evaluate("el => [Number(el.min), Number(el.max)]")
        if limits[1] <= limits[0]:
            raise AssertionError("ECEF playback audit needs a nonzero time span")
        target = limits[0] + .6 * (limits[1] - limits[0])
        page.locator("#time").evaluate("""(el, value) => {
            el.value = String(value); el.dispatchEvent(new Event('input', {bubbles: true}));
        }""", limits[0] + .2 * (limits[1] - limits[0]))
        before = settled_pixels(page)
        page.locator("#time").evaluate("""(el, value) => {
            el.value = String(value); el.dispatchEvent(new Event('input', {bubbles: true}));
        }""", target)
        after = settled_pixels(page)
        clock = page.locator("#clock").evaluate("el => el.value")
        if abs(float(clock.split()[0]) - target) > .1 or before["hash"] == after["hash"]:
            raise AssertionError("Time scrub did not change the rendered ECEF paths and clock")
        page.locator("#play").click()
        page.wait_for_function("t => Number(document.querySelector('#time').value) > t", arg=target)
        page.locator("#play").click()
        paused = float(page.locator("#time").input_value())
        page.wait_for_timeout(200)
        if float(page.locator("#time").input_value()) != paused:
            raise AssertionError("Pause did not stop playback")
        result.update(time_scrub_s=target, playback_advanced_s=paused, pause_verified=True)
    before_drag = settled_pixels(page)
    box = page.locator("canvas").bounding_box()
    x, y = box["x"] + box["width"]*.4, box["y"] + box["height"]*.4
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 80, y + 45, steps=6)
    page.mouse.up()
    after_drag = settled_pixels(page)
    if before_drag["hash"] == after_drag["hash"]:
        raise AssertionError("Dragging did not rotate the rendered globe")
    page.mouse.move(x + 120, y + 80)
    if settled_pixels(page)["hash"] != after_drag["hash"]:
        raise AssertionError("Rotation continued after pointer release")
    result.update(drag_changed_pixels=True, pointer_release_verified=True, final_pixels=after_drag)
    return result


def run_canvas_audit(argv=None, *, ecef: bool, paths: tuple[Path, Path, Path]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_browser_arguments(parser)
    parser.add_argument("--output-dir", type=Path, default=paths[0].parent)
    parser.add_argument("--html", type=Path, help="Audit this existing HTML instead of generating the representative scene.")
    args = parser.parse_args(argv)
    directory = args.output_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    html_path = directory / paths[0].name
    screenshot_path = directory / paths[1].name
    report_path = directory / paths[2].name
    result = {"passed": False, "scope": "Canvas ECEF interactions" if ecef else "Canvas globe interactions",
              "platform": platform.platform(), "python": platform.python_version(),
              "headless": not args.headed, "browser_arguments": args.browser_arg,
              "network_attempts": [], "script_errors": [], "console_errors": [],
              "load_mechanism": "local HTML bytes via page.set_content; page traffic blocked"}
    browser = page = audit = None
    try:
        from playwright.sync_api import sync_playwright
        from offline_earth.canvas import canvas_globe
        from examples.utilities import sample_ecef_trajectories
        if args.html is None:
            canvas_globe(html_path, mode="combined", trajectories=sample_ecef_trajectories() if ecef else (),
                         at_s=1200 if ecef else None)
        else:
            html_path = args.html.expanduser().resolve()
        html = html_path.read_text(encoding="utf-8")
        result.update(html=str(html_path), html_sha256=hashlib.sha256(html.encode()).hexdigest(),
                      playwright=version("playwright"))
        with sync_playwright() as pw:
            try:
                result["browser_executable"] = resolve_browser_executable(pw, args.browser_executable)
                browser = launch_browser(pw, args)
                result["browser_version"] = browser.version
                context = browser.new_context(viewport={"width": 1180, "height": 960}, service_workers="block")
                audit = OfflinePageAudit(context)
                page = context.new_page()
                audit.attach(page)
                audit.set_content(page, html)
                result.update(exercise_canvas(page, ecef=ecef))
                page.screenshot(path=str(screenshot_path), full_page=True)
                result["screenshot"] = str(screenshot_path)
                audit.assert_clean(page)
                result["passed"] = True
            finally:
                if audit is not None and page is not None and not page.is_closed():
                    try:
                        result.update(audit.snapshot(page))
                        if any(result[key] for key in ("network_attempts", "script_errors", "console_errors")):
                            result["passed"] = False
                            result["error"] = "Browser diagnostics were not clean at final capture"
                        if not result["passed"]:
                            page.screenshot(path=str(directory / "failure.png"), full_page=True)
                            result["failure_screenshot"] = str(directory / "failure.png")
                    except Exception as error:
                        result["capture_error"] = str(error)
                        result["passed"] = False
                elif result["passed"]:
                    result["passed"] = False
                    result["error"] = "Browser page closed before final capture"
                if browser is not None:
                    browser.close()
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["passed"] = False
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1
