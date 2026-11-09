"""Generate a self-contained globe using only the installed core package."""
import argparse
from pathlib import Path

from offline_earth.trajectory import EcefTrajectory, geodetic_to_ecef
from offline_earth.visualize import RenderSpec, render_ecef


def main(output: str | Path = 'earth.html') -> Path:
    # An illustrative Earth-fixed path, not orbital propagation.
    points = [geodetic_to_ecef(lon, 25, 550_000) for lon in (-60, -30, 0, 30)]
    track = EcefTrajectory.from_arrays(
        'Example', [0, 60, 120, 180],
        [(p.x_m, p.y_m, p.z_m) for p in points],
    )
    return render_ecef([track], output, spec=RenderSpec(backend='canvas', at_s=60))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", type=Path, default=Path("earth.html"),
                        help="HTML output path (default: earth.html)")
    args = parser.parse_args(argv)
    print(f"Open {main(args.output)} in a local browser.")


if __name__ == '__main__':
    cli()
