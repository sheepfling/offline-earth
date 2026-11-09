"""Build an offline, reviewer-friendly Earth visualization gallery."""
import argparse
from pathlib import Path
from examples.utilities import demo_ground_track

from offline_earth.canvas import canvas_globe

from offline_earth import save_svg

def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "earth"


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

    out = output_directory() if output_dir is None else Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figures = []

    def render(plotter, *args, **kwargs):
        figure = plotter(*args, post_plot=post_plot,
                         post_plot_kwargs=post_plot_kwargs, **kwargs)
        if figure is not None:
            figures.append(figure)

    try:
        track = demo_ground_track()
        save_svg(str(out / "world.svg"), tracks=[track])
        for view in ("imagery", "political", "combined"):
            render(matplotlib_world, out / f"map_{view}.png", mode=view, track=track)
            render(matplotlib_globe, out / f"globe_{view}.png", mode=view, track=track)
        render(plotly_globe, out / "interactive_earth_offline.html", track=track)
        canvas_globe(out / "interactive_canvas_no_webgl.html", track=track)

        # Contact sheet with actual saved output, rather than an illustrative mock-up.
        if post_plot is not None:
            return figures

        from PIL import Image, ImageDraw
        cols, rows = 3, 2
        thumb_width, thumb_height = 680, 430
        sheet = Image.new("RGB", (cols*thumb_width + 60, rows*(thumb_height+55) + 140), "#081522")
        draw = ImageDraw.Draw(sheet)
        draw.text((36, 22), "OFFLINE EARTH  /  OFFLINE EARTH VISUALIZATION", fill="#f0f4fa", stroke_width=0)
        draw.text((36, 53), "Three rendering modes  •  Political borders, Blue Marble, and both  •  Local wheel assets", fill="#aac3d1")
        for idx, view in enumerate(("imagery", "political", "combined")):
            for row_idx, prefix in enumerate(("map", "globe")):
                src = Image.open(out / f"{prefix}_{view}.png").convert("RGB")
                src.thumbnail((thumb_width-24, thumb_height-12), Image.Resampling.LANCZOS)
                x = 30 + idx*thumb_width + (thumb_width - src.width)//2
                y = 115 + row_idx*(thumb_height+55) + (thumb_height - src.height)//2
                sheet.paste(src, (x, y))
                draw.text((42 + idx*thumb_width, 100 + row_idx*(thumb_height+55)),
                          f"{('2D map' if row_idx == 0 else '3D globe')}  /  {view.title()}", fill="#f2f4f7")
        sheet.save(out / "00_review_gallery.png", optimize=True)
        print("Generated:")
        for p in sorted(out.iterdir()):
            print(f"  {p.name} ({p.stat().st_size // 1024:,} KB)")
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
