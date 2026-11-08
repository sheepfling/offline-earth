"""Offline Earth visualization CLI; all ECEF inputs are explicit local files."""
from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Sequence
from .canvas import canvas_globe
from .svg import save_svg
from .paths import output_path
from .constants import DEFAULT_CENTER_LON_DEG, DEFAULT_CENTER_LAT_DEG, DEFAULT_EXTENT_EARTH_RADII

from .earth import demo_ground_track, matplotlib_globe, matplotlib_world, plotly_globe
from .trajectory import EcefTrajectory, read_trajectories
from .visualize import RenderSpec, render_ecef


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Offline political/Blue Marble Earth + ECEF trajectories")
    parser.add_argument("output", nargs="?", default="world.svg", help="Destination output file")
    parser.add_argument("--renderer", choices=("svg", "map", "globe", "interactive", "canvas", "timeseries"), default="svg")
    parser.add_argument("--mode", choices=("imagery", "political", "combined"), default="combined")
    parser.add_argument("--track", action="store_true", help="Overlay a synthetic illustrative ground track")
    parser.add_argument("--ecef", type=Path, action="append", default=[], metavar="CSV_OR_JSON",
                        help="Local ECEF trajectory file (repeatable); never interpreted as ECI")
    parser.add_argument("--at-s", type=float, default=None, help="Snapshot marker time, seconds from epoch")
    parser.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON_DEG, help="Camera longitude in degrees")
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT_DEG, help="Camera latitude in degrees")
    parser.add_argument("--extent-earth-radii", type=float, default=DEFAULT_EXTENT_EARTH_RADII)
    args = parser.parse_args(argv)
    trajectories: list[EcefTrajectory] = []
    for source in args.ecef:
        trajectories.extend(read_trajectories(source))
    path = output_path(args.output)
    if args.track:
        # Compatibility mode for the older ground-track demo. ECEF paths use
        # the unified, typed trajectory model instead of this legacy overlay.
        track = demo_ground_track()
        if trajectories:
            parser.error("--track is a legacy illustration; don't combine with --ecef")
        if args.renderer == "map":
            matplotlib_world(path, mode=args.mode, track=track)
        elif args.renderer == "globe":
            matplotlib_globe(path, mode=args.mode, track=track,
                             center_lon=args.center_lon, center_lat=args.center_lat)
        elif args.renderer == "interactive":
            plotly_globe(path, track=track, include_imagery=(args.mode != "political"))
        elif args.renderer == "canvas":
            canvas_globe(path, track=track, mode=args.mode,
                         center_lon=args.center_lon, center_lat=args.center_lat)
        elif args.renderer == "svg":
            save_svg(str(path), tracks=[track], mode=args.mode)
        else:
            parser.error("--track cannot produce time series: no timestamps supplied")
    else:
        try:
            spec = RenderSpec(
                backend="plotly" if args.renderer == "interactive" else args.renderer,
                mode=args.mode, at_s=args.at_s,
                center_lon=args.center_lon, center_lat=args.center_lat,
                extent_earth_radii=args.extent_earth_radii,
            )
            render_ecef(trajectories, path, spec=spec)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
