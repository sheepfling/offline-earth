"""Optional, offline Plotly/WebGL smoke audit; no browser or I/O on import.

Run from the checkout with PYTHONPATH=src:. python -m tools.verify_plotly_browser.
Requires installed interactive extras, Pillow, Playwright and Chromium. Never
installs dependencies. Browser execution is separate from the core test suite.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final


def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "browser" / "plotly"


def generate_scene(target: Path) -> list[dict]:
    from examples.utilities import sample_ecef_trajectories
    from offline_earth.constants import KM_PER_METERS
    from offline_earth.visualize import RenderSpec, render_ecef
    trajectories = sample_ecef_trajectories(sample_count=61)
    render_ecef(trajectories, target, spec=RenderSpec(backend="plotly", at_s=3000))
    return [{"name": tr.name, "xyz_km": [
        [s.position.x_m * KM_PER_METERS, s.position.y_m * KM_PER_METERS, s.position.z_m * KM_PER_METERS]
        for s in tr.samples]} for tr in trajectories]


def scene_layout(expected: list[dict]) -> dict:
    """Fix geometry framing so hiding tracks cannot rescale the Earth baseline."""
    from offline_earth.constants import EARTH_RADIUS_M, KM_PER_METERS
    extent = max(EARTH_RADIUS_M * KM_PER_METERS,
                 max(abs(value) for trace in expected for xyz in trace["xyz_km"] for value in xyz)) * 1.1
    layout = {f"scene.{axis}axis.range": [-extent, extent] for axis in "xyz"}
    layout.update({f"scene.{axis}axis.autorange": False for axis in "xyz"})
    layout.update({"scene.aspectmode": "manual", "scene.aspectratio": {"x": 1, "y": 1, "z": 1},
                   "scene.camera": {"eye": {"x": 1.25, "y": 1.25, "z": 1.25},
                                    "center": {"x": 0, "y": 0, "z": 0},
                                    "up": {"x": 0, "y": 0, "z": 1}},
                   "scene.domain": {"x": [0, 0.8], "y": [0, 1]}})
    return layout


def runtime_metadata(args: argparse.Namespace) -> dict:
    packages = {}
    for package in ("playwright", "plotly", "numpy", "pillow"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    return {"platform": platform.platform(), "python": platform.python_version(),
            "packages": packages, "headless": not args.headed,
            "launch_args": list(args.browser_arg), "chromium_sandbox": True,
            "browser_executable_requested": args.browser_executable}


def capture_snapshot(audit, page, report: dict) -> None:
    """A dead page must not replace the original rendering failure."""
    try:
        report.update(audit.snapshot(page))
    except Exception as error:
        report["snapshot_error"] = f"{type(error).__name__}: {error}"


def pixel_metrics(rendered: Path, hidden: Path) -> dict:
    """Measure visible scene content and the effect of hiding ECEF trajectories."""
    from PIL import Image, ImageChops
    with Image.open(rendered) as source, Image.open(hidden) as other:
        first, second = source.convert("RGB"), other.convert("RGB")
        if first.size != second.size:
            raise AssertionError("Scene dimensions changed during trajectory comparison")
        colors = first.getcolors(first.width * first.height) or []
        dominant = max((count for count, _ in colors), default=0)
        baseline_colors = second.getcolors(second.width * second.height) or []
        baseline_dominant = max((count for count, _ in baseline_colors), default=0)
        red, green, blue = ImageChops.difference(first, second).split()
        maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        changed = sum(maximum.histogram()[13:])
        return {"width": first.width, "height": first.height,
                "distinct_colors": len(colors),
                "non_dominant_pixels": first.width * first.height - dominant,
                "trajectory_changed_pixels": changed,
                "baseline_distinct_colors": len(baseline_colors),
                "baseline_non_dominant_pixels": second.width * second.height - baseline_dominant}


def validate_pixels(metrics: dict) -> None:
    if metrics["width"] < 100 or metrics["height"] < 100:
        raise AssertionError("WebGL canvas has no usable drawing area")
    if metrics["distinct_colors"] < 32 or metrics["non_dominant_pixels"] < 1000:
        raise AssertionError("WebGL scene is blank or lacks rendered Earth content")
    if metrics["baseline_distinct_colors"] < 32 or metrics["baseline_non_dominant_pixels"] < 1000:
        raise AssertionError("Earth-only baseline is blank or lacks rendered Earth content")
    if metrics["trajectory_changed_pixels"] < 20:
        raise AssertionError("No visible ECEF trajectory pixel evidence")


# Public graph data and browser Canvas/WebGL APIs only: no _fullLayout/_scene.
SCENE_METRICS_JS: Final[str] = """(expected) => {
    const gd = document.querySelector('.js-plotly-plot');
    if (!gd || !Array.isArray(gd.data)) throw Error('Plotly graph data missing');
    const surfaces = gd.data.filter(t => t.type === 'surface' && t.visible !== false && t.visible !== 'legendonly');
    if (!surfaces.length) throw Error('No visible Earth surface trace');
    const indices = expected.map(e => {
        const i = gd.data.findIndex(t => t.name === e.name && t.type === 'scatter3d' && t.mode === 'lines');
        if (i < 0) throw Error('Missing ECEF trajectory: ' + e.name);
        const t = gd.data[i];
        if (t.visible === false || t.visible === 'legendonly') throw Error('Hidden ECEF trajectory');
        for (const [axis, k] of [['x', 0], ['y', 1], ['z', 2]]) {
            if (t[axis].length !== e.xyz_km.length) throw Error('Trajectory length mismatch');
            e.xyz_km.forEach((xyz, j) => {
                if (!Number.isFinite(t[axis][j]) || Math.abs(t[axis][j] - xyz[k]) > 1e-7)
                    throw Error('ECEF coordinate mismatch: ' + e.name);
            });
        }
        return i;
    });
    const canvases = [...gd.querySelectorAll('canvas')].map((canvas, i) => {
        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        return {index: i, width: canvas.width, height: canvas.height, webgl: !!gl,
            context_lost: gl ? gl.isContextLost() : null,
            drawing_width: gl ? gl.drawingBufferWidth : 0,
            drawing_height: gl ? gl.drawingBufferHeight : 0};
    });
    return {plotly_version: Plotly.version, trace_count: gd.data.length,
        visible_surfaces: surfaces.map(t => ({name: t.name, type: t.type})),
        trajectory_indices: indices, trajectories: expected.map(e => ({name:e.name, samples:e.xyz_km.length})), canvases};
}"""


def assert_report_clean(report: dict) -> None:
    """Validate the same final snapshot that will be written to the report."""
    defects = {key: report.get(key) for key in
               ("network_attempts", "script_errors", "console_errors", "snapshot_error", "browser_close_error")
               if report.get(key)}
    if defects:
        raise AssertionError(f"Browser audit detected errors or external requests: {defects}")


def run_audit(args: argparse.Namespace, report: dict) -> None:
    from playwright.sync_api import sync_playwright
    from tools.browser_support import launch_browser, resolve_browser_executable
    from tools.browser_audit import OfflinePageAudit
    out = Path(args.output_dir)
    html = out / "plotly_ecef.html"
    expected = generate_scene(html)
    report["html"] = str(html)
    report["html_sha256"] = hashlib.sha256(html.read_bytes()).hexdigest()
    fixed_layout = scene_layout(expected)
    report["fixed_scene_layout"] = fixed_layout
    with sync_playwright() as pw:
        report["runtime"]["browser_executable"] = resolve_browser_executable(pw, args.browser_executable)
        browser = launch_browser(pw, args)
        try:
            report["browser"] = {"name": "Chromium", "version": browser.version}
            context = browser.new_context(viewport={"width": 1180, "height": 950}, device_scale_factor=1, service_workers="block")
            audit = OfflinePageAudit(context)
            page = context.new_page()
            audit.attach(page)
            try:
                audit.set_content(page, html.read_text(encoding="utf-8"), timeout=args.timeout_ms)
                page.wait_for_function("window.Plotly && document.querySelector('.js-plotly-plot')?.data?.length > 0", timeout=args.timeout_ms)
                page.wait_for_selector('.js-plotly-plot canvas', timeout=args.timeout_ms)
                # Public relayout fixes axes/aspect/camera for both pixel captures.
                page.evaluate("async layout => { await Plotly.relayout(document.querySelector('.js-plotly-plot'), layout); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }", fixed_layout)
                scene = page.evaluate(SCENE_METRICS_JS, expected)
                report["scene"] = scene
                ready = [c for c in scene["canvases"] if c["webgl"] and not c["context_lost"] and c["drawing_width"] > 0 and c["drawing_height"] > 0]
                if not ready:
                    raise AssertionError("No initialized, non-lost WebGL drawing buffer")
                canvas = page.locator('.js-plotly-plot canvas').nth(ready[0]["index"])
                rendered, hidden = out / "scene.png", out / "scene_without_trajectories.png"
                # Borders must not masquerade as Earth pixels when the surface fails.
                # Remove them from BOTH captures, so only ECEF trajectories differ.
                page.evaluate("async () => { const gd = document.querySelector('.js-plotly-plot'); const indices = gd.data.map((t,i) => t.name === 'Political borders' ? i : -1).filter(i => i >= 0); if (indices.length) await Plotly.restyle(gd, {visible:false}, indices); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }")
                report["pixel_comparison_scope"] = "Earth surface plus trajectories versus Earth surface only; borders hidden in both"
                canvas.screenshot(path=str(rendered))
                # Include position traces; only Earth surfaces remain in the baseline.
                indices = page.evaluate("names => document.querySelector('.js-plotly-plot').data.map((t,i) => names.some(n => t.name === n || t.name === n + ' position') ? i : -1).filter(i => i >= 0)", [tr["name"] for tr in expected])
                page.evaluate("async indices => { await Plotly.restyle(document.querySelector('.js-plotly-plot'), {visible:false}, indices); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }", indices)
                canvas.screenshot(path=str(hidden))
                page.evaluate("async indices => { await Plotly.restyle(document.querySelector('.js-plotly-plot'), {visible:true}, indices); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }", indices)
                report["pixels"] = pixel_metrics(rendered, hidden)
                validate_pixels(report["pixels"])
                report["screenshots"] = [str(rendered), str(hidden), str(out / "plotly_browser.png")]
                page.screenshot(path=str(out / "plotly_browser.png"), full_page=True)
                report.update(audit.snapshot(page))
                assert_report_clean(report)
            except Exception:
                capture_snapshot(audit, page, report)
                try:
                    page.screenshot(path=str(out / "failure.png"), full_page=True, timeout=5000)
                    report["failure_screenshot"] = str(out / "failure.png")
                except Exception as error:
                    report["failure_screenshot_error"] = str(error)
                raise
        finally:
            try:
                browser.close()
            except Exception as error:
                report["browser_close_error"] = str(error)


def main(argv: list[str] | None = None) -> int:
    from tools.browser_support import add_browser_arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=output_directory())
    parser.add_argument("--timeout-ms", type=int, default=60000)
    add_browser_arguments(parser)
    args = parser.parse_args(argv)
    if args.timeout_ms <= 0:
        parser.error("--timeout-ms must be positive")
    args.output_dir = args.output_dir.expanduser().resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"status": "failed", "scope": "Plotly WebGL smoke, generated representative ECEF trajectories",
              "load_mechanism": "page.set_content; embedded local HTML", "network_attempts": [],
              "script_errors": [], "console_errors": [], "runtime": runtime_metadata(args)}
    try:
        run_audit(args, report)
        assert_report_clean(report)
        report["status"] = "passed"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    payload = json.dumps(report, indent=2)
    (args.output_dir / "plotly_browser_audit.json").write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
