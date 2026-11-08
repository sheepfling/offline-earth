"""Offline Earth visualization CLI; all ECEF inputs are explicit local files."""
from __future__ import annotations

import argparse
from pathlib import Path

from .earth import demo_ground_track, matplotlib_globe, matplotlib_world, plotly_globe
from .trajectory import EcefTrajectory, read_trajectories
from .visualize import RenderSpec, render_ecef


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Offline political/Blue Marble Earth + ECEF trajectories")
    parser.add_argument("output", nargs="?", default="world.svg", help="Destination output file")
    parser.add_argument("--renderer", choices=("svg", "map", "globe", "interactive", "canvas", "timeseries"), default="svg")
    parser.add_argument("--mode", choices=("imagery", "political", "combined"), default="combined")
    parser.add_argument("--track", action="store_true", help="Overlay a synthetic illustrative ground track")
    parser.add_argument("--ecef", type=Path, action="append", default=[], metavar="CSV_OR_JSON",
                        help="Local ECEF trajectory file (repeatable); never interpreted as ECI")
    parser.add_argument("--at-s", type=float, default=None, help="Snapshot marker time, seconds from epoch")
    parser.add_argument("--center-lon", type=float, default=-30.)
    parser.add_argument("--center-lat", type=float, default=22.)
    parser.add_argument("--extent-earth-radii", type=float, default=1.35)
    args = parser.parse_args(argv)
    trajectories: list[EcefTrajectory] = []
    for source in args.ecef:
        trajectories.extend(read_trajectories(source))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
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
            from .canvas import canvas_globe
            canvas_globe(path, track=track, mode=args.mode,
                         center_lon=args.center_lon, center_lat=args.center_lat)
        elif args.renderer == "svg":
            from . import save_svg
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
