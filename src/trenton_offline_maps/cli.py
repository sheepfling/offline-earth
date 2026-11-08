"""Offline Earth visualization CLI; all ECEF inputs are explicit local files."""
from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Sequence
from .paths import output_path
from .constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII

from .trajectory import EcefTrajectory, read_trajectories
from .visualize import RenderSpec, render_ecef


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Offline political/Blue Marble Earth + ECEF trajectories")
    parser.add_argument("output", nargs="?", default="world.svg", help="Destination output file")
    parser.add_argument("--renderer", choices=("svg", "map", "globe", "interactive", "canvas", "timeseries"), default="svg")
    parser.add_argument("--mode", choices=("imagery", "political", "combined"), default="combined")
    parser.add_argument("--ecef", type=Path, action="append", default=[], metavar="CSV_OR_JSON",
                        help="Local ECEF trajectory file (repeatable); never interpreted as ECI")
    parser.add_argument("--at-s", type=float, default=None, help="Snapshot marker time, seconds from epoch")
    parser.add_argument("--center-lon-deg", type=float, default=DEFAULT_CENTER_LON_DEG, help="Camera longitude in degrees")
    parser.add_argument("--center-lat-deg", type=float, default=DEFAULT_CENTER_LAT_DEG, help="Camera latitude in degrees")
    parser.add_argument("--extent-earth-radii", type=float, default=DEFAULT_EXTENT_EARTH_RADII)
    args = parser.parse_args(argv)
    trajectories: list[EcefTrajectory] = []
    for source in args.ecef:
        trajectories.extend(read_trajectories(source))
    path = output_path(args.output)
    try:
        spec = RenderSpec(
            backend="plotly" if args.renderer == "interactive" else args.renderer,
            mode=args.mode, at_s=args.at_s,
            center_lon_deg=args.center_lon_deg, center_lat_deg=args.center_lat_deg,
            extent_earth_radii=args.extent_earth_radii,
        )
        render_ecef(trajectories, path, spec=spec)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
