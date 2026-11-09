"""Audit Canvas ECEF interactions: python -m tools.verify_ecef_browser --help."""
from pathlib import Path

from tools.canvas_browser_audit import run_canvas_audit


def output_paths() -> tuple[Path, Path, Path]:
    directory = Path(__file__).resolve().parents[1] / "artifacts" / "ecef"
    return (directory / "interactive_ecef_canvas.html",
            directory / "interactive_browser_preview.png",
            directory / "browser_ecef_audit.json")


def main(argv=None) -> int:
    return run_canvas_audit(argv, ecef=True, paths=output_paths())


if __name__ == "__main__":
    raise SystemExit(main())
