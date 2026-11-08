"""Build an offline, reviewer-friendly Earth visualization gallery."""
from pathlib import Path
from examples.utilities import demo_ground_track

from trenton_offline_maps.canvas import canvas_globe

from trenton_offline_maps import save_svg
from trenton_offline_maps.renderers.matplotlib import matplotlib_globe, matplotlib_world
from trenton_offline_maps.renderers.plotly import plotly_globe

def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "earth"


def main() -> None:
    out = output_directory()
    out.mkdir(parents=True, exist_ok=True)
    track = demo_ground_track()
    save_svg(str(out / "world.svg"), tracks=[track])
    for view in ("imagery", "political", "combined"):
        matplotlib_world(out / f"map_{view}.png", mode=view, track=track)
        matplotlib_globe(out / f"globe_{view}.png", mode=view, track=track)
    plotly_globe(out / "interactive_earth_offline.html", track=track)
    canvas_globe(out / "interactive_canvas_no_webgl.html", track=track)

    # Contact sheet with actual saved output, rather than an illustrative mock-up.
    from PIL import Image, ImageDraw
    cols, rows = 3, 2
    thumb_width, thumb_height = 680, 430
    sheet = Image.new("RGB", (cols*thumb_width + 60, rows*(thumb_height+55) + 140), "#081522")
    draw = ImageDraw.Draw(sheet)
    draw.text((36, 22), "TRENTON  /  OFFLINE EARTH VISUALIZATION", fill="#f0f4fa", stroke_width=0)
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


if __name__ == "__main__":
    main()
