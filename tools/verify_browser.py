"""Audit the Canvas globe: python -m tools.verify_browser --help."""
from pathlib import Path

from tools.canvas_browser_audit import run_canvas_audit


def output_paths() -> tuple[Path, Path, Path]:
    directory = Path(__file__).resolve().parents[1] / "artifacts" / "earth"
    return (directory / "interactive_canvas_no_webgl.html",
            directory / "interactive_canvas_browser.png",
            directory / "browser_audit.json")


def main(argv=None) -> int:
    return run_canvas_audit(argv, ecef=False, paths=output_paths())


if __name__ == "__main__":
    raise SystemExit(main())
