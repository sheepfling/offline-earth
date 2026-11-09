"""Generate synthetic, already-ECEF sample data and an offline renderer review gallery.

All trajectories below are demonstrations of plotting, not orbit propagation.
The LEO examples use illustrative circular parameterizations with approximate Earth
rotation; do not use them for orbit determination or operations.
"""
from __future__ import annotations

import csv
from examples.utilities import sample_ecef_trajectories
import argparse
from pathlib import Path

from offline_earth import save_svg
from offline_earth.canvas import canvas_globe
from offline_earth.trajectory import EcefTrajectory, geodetic_to_ecef, write_trajectories

def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "ecef"


def main(output_dir: str | Path | None = None, *, post_plot=None,
         post_plot_kwargs: dict | None = None) -> list:
    """Generate the gallery and return figures retained by ``post_plot``.

    With a callback, the callback owns saving/closing each figure and the contact
    sheet is skipped because the PNG files may not have been saved. SVG, canvas,
    and sample-data outputs are still written. Defaults save and close figures. If generation fails,
    already-retained Matplotlib figures are closed before the error is re-raised.
    """
    from offline_earth.renderers.matplotlib import matplotlib_globe, matplotlib_world
    from offline_earth.renderers.plotly import plotly_globe
    from offline_earth.timeseries import matplotlib_ecef_timeseries

    out = output_directory() if output_dir is None else Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figures = []

    def render(plotter, *args, **kwargs):
        figure = plotter(*args, post_plot=post_plot,
                         post_plot_kwargs=post_plot_kwargs, **kwargs)
        if figure is not None:
            figures.append(figure)

    try:
        paths = sample_ecef_trajectories()
        geo = geodetic_to_ecef(-75, 0, 35_786_000)
        geo_track = EcefTrajectory.from_arrays("GEO / -75°", [0, 6000],
                                               [[geo.x_m, geo.y_m, geo.z_m]]*2,
                                               color="#b7a6fa")
        write_trajectories(out / "sample_ecef.json", paths)
        write_trajectories(out / "sample_geo.json", (geo_track,))
        with (out / "sample_leo.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("name", "time_s", "x_m", "y_m", "z_m"))
            for sample in paths[0].samples:
                writer.writerow((paths[0].name, sample.t_s, sample.position.x_m,
                                 sample.position.y_m, sample.position.z_m))
        at_s = 3640.0
        for mode in ("imagery", "political", "combined"):
            render(matplotlib_world, out / f"world_{mode}.png", mode=mode,
                             trajectories=paths, at_s=at_s,
                             title=f"ECEF ground projections • {mode.title()} • t = {at_s:g} s")
            render(matplotlib_globe, out / f"globe_{mode}.png", mode=mode,
                             trajectories=paths, at_s=at_s,
                             center_lon_deg=-45, center_lat_deg=30, extent_earth_radii=1.33)
        render(matplotlib_ecef_timeseries, out / "ecef_xyz_vs_time.png", paths)
        save_svg(str(out / "ecef_political.svg"), trajectories=list(paths), at_s=at_s)
        save_svg(str(out / "ecef_combined.svg"), trajectories=list(paths), at_s=at_s, mode="combined")
        canvas_globe(out / "interactive_ecef_canvas.html", trajectories=paths)
        render(plotly_globe, out / "interactive_ecef_plotly.html", trajectories=paths, at_s=at_s)
        render(plotly_globe, out / "interactive_ecef_geo_plotly.html", trajectories=(geo_track,))
        print("Generated", len(tuple(out.iterdir())), "ECEF examples in", out)
        if post_plot is not None:
            return figures

        from PIL import Image, ImageDraw
        panels = [("World / Blue Marble", "world_imagery.png"),
                  ("World / political", "world_political.png"),
                  ("World / combined", "world_combined.png"),
                  ("Globe / Blue Marble", "globe_imagery.png"),
                  ("Globe / combined", "globe_combined.png"),
                  ("ECEF X,Y,Z versus time", "ecef_xyz_vs_time.png")]
        tw, th = 590, 365
        sheet = Image.new("RGB", (tw*3+56, th*2+154), "#091827")
        d=ImageDraw.Draw(sheet)
        d.text((30,20), "OFFLINE EARTH   /   TIMESTAMPED ECEF TRAJECTORIES", fill="#f0f7ff")
        d.text((30,52), "One validated metre-and-second input model • Maps, globe, components-vs-time • No network", fill="#b2c7d7")
        for index, (label, filename) in enumerate(panels):
            image = Image.open(out / filename).convert("RGB")
            image.thumbnail((tw-16,th-28), Image.Resampling.LANCZOS)
            cx=index%3;cy=index//3
            x=24+cx*tw+(tw-image.width)//2
            y=110+cy*th+(th-image.height)//2
            sheet.paste(image,(x,y))
            d.text((31+cx*tw,94+cy*th),label,fill="#f8f4e9")
        sheet.save(out / "00_ecef_review_gallery.png", optimize=True)
        return figures
    except BaseException:
        # Ownership transfers only when the whole gallery returns successfully.
        # Plotly has no close lifecycle; only release retained Matplotlib figures.
        if figures:
            from matplotlib.figure import Figure
            from matplotlib import pyplot as plt
            for figure in figures:
                if isinstance(figure, Figure):
                    plt.close(figure)
        raise


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", "-o", type=Path, default=output_directory(),
                        help="Gallery output directory (default: %(default)s)")
    args = parser.parse_args(argv)
    main(args.output_dir)


if __name__ == "__main__":
    cli()
