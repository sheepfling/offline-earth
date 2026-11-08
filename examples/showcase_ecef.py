"""Generate synthetic, already-ECEF sample data and an offline renderer review gallery.

All trajectories below are demonstrations of plotting, not orbit propagation.
The LEO examples use illustrative circular parameterizations with approximate Earth
rotation; do not use them for orbit determination or operations.
"""
from __future__ import annotations

import csv
from examples.utilities import synthetic_orbit, stationary_ground
from pathlib import Path

from offline_earth import save_svg
from offline_earth.canvas import canvas_globe
from offline_earth.renderers.matplotlib import matplotlib_globe, matplotlib_world
from offline_earth.renderers.plotly import plotly_globe
from offline_earth.timeseries import matplotlib_ecef_timeseries
from offline_earth.trajectory import EcefTrajectory, geodetic_to_ecef, write_trajectories

def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "ecef"


def main() -> None:
    out = output_directory()
    out.mkdir(parents=True, exist_ok=True)
    paths = (
        synthetic_orbit("LEO / 55°", inclination_deg=55, period_s=5700,
                        height_m=550_000, phase_deg=18, color="#ffbd69"),
        synthetic_orbit("LEO / 97°", inclination_deg=97, period_s=6100,
                        height_m=740_000, phase_deg=135, color="#63d8fc"),
        stationary_ground("Ground site", lon_deg=-86.59, lat_deg=34.72, color="#ec87b2"),
    )
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
        matplotlib_world(out / f"world_{mode}.png", mode=mode,
                         trajectories=paths, at_s=at_s,
                         title=f"ECEF ground projections • {mode.title()} • t = {at_s:g} s")
        matplotlib_globe(out / f"globe_{mode}.png", mode=mode,
                         trajectories=paths, at_s=at_s,
                         center_lon_deg=-45, center_lat_deg=30, extent_earth_radii=1.33)
    matplotlib_ecef_timeseries(out / "ecef_xyz_vs_time.png", paths)
    save_svg(str(out / "ecef_political.svg"), trajectories=list(paths), at_s=at_s)
    save_svg(str(out / "ecef_combined.svg"), trajectories=list(paths), at_s=at_s, mode="combined")
    canvas_globe(out / "interactive_ecef_canvas.html", trajectories=paths)
    plotly_globe(out / "interactive_ecef_plotly.html", trajectories=paths, at_s=at_s)
    plotly_globe(out / "interactive_ecef_geo_plotly.html", trajectories=(geo_track,))
    print("Generated", len(tuple(out.iterdir())), "ECEF examples in", out)
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

if __name__ == "__main__":
    main()
