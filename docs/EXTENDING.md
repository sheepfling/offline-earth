# Extending Offline Earth

Start with `examples/quickstart.py`, then follow one output through the modules
below. The core package needs no third-party runtime dependencies. Example
generators and gallery scripts stay outside the wheel.

## Source map

- `trajectory.py`: validated timestamped tracks and CSV/JSON input/output.
- `geodesy.py`: WGS84 coordinate types, conversions and horizon visibility.
- `constants.py`: shared physical and display defaults.
- `geometry.py`: semantic coordinate tuples, camera vectors, map seams and the
  `ViewMode` Literal. `VIEW_MODES` is derived from that Literal for validation.
- `assets.py`: local asset access and metadata, including named geographic extent.
- `visualize.py`: `RenderSpec` and the explicit renderer selection boundary.
- `canvas_scene.py` → `canvas.py` → `templates/canvas.html`: load data, serialize
  it safely, then present it as a self-contained page.
- `renderers/`: optional Matplotlib, Plotly, image decoding and raster projection.
- `figures.py`: common callback and ownership rules, without plotting imports.
- `examples/utilities/constants.py`: approximate physical values for examples.
- `examples/utilities/trajectories.py`: synthetic generators and sampling defaults.

For a new backend, add its explicit module, extend the `Backend` Literal and
dispatcher in `visualize.py`, and cover its imports and actual output in tests.
Do not import optional plotting packages from core modules. A new CLI renderer
also needs an entry in `cli.py`; its `interactive` option names the Plotly backend.

## Customize the HTML

The template is a real source file included in the wheel. Copy it into your
project rather than editing a generated multi-megabyte HTML output. It contains
the page markup, CSS and Canvas JavaScript. Changes to labels and styling are
separate from Python's scene loading and JSON serialization.

```python
from importlib.resources import files
from pathlib import Path

from offline_earth.canvas import render_canvas_html
from offline_earth.canvas_scene import load_canvas_scene

template_path = Path("my_canvas.html")
if not template_path.exists():
    template_path.write_text(
        files("offline_earth").joinpath("templates/canvas.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
# Edit my_canvas.html, then rerun this code.
scene = load_canvas_scene(center_lon_deg=12, center_lat_deg=30)
html = render_canvas_html(scene, template=template_path.read_text(encoding="utf-8"))
Path("custom_earth.html").write_text(html, encoding="utf-8")
```

`template` is HTML text, not a filename. The same loaded scene can be rendered
with several templates without loading the assets again. This uses one-pass
placeholder replacement, with no template engine or network access.

The data slots are:

- `__INITIAL_CONFIG__`: JSON object with `mode`, nullable `at_s`,
  `center_lon_deg` and `center_lat_deg`.
- `__EARTH_CONSTANTS__`: JSON object with `radius_m`, WGS84 `a_m` and `b_m`,
  and preview `texture_width` and `texture_height`.
- `__BORDERS_JSON__`: countries → rings → `[longitude_deg, latitude_deg]` pairs.
- `__TRACK_JSON__`: an array of ground-track `[longitude_deg, latitude_deg]` pairs.
- `__ECEF_JSON__`: an array of objects with `name`, `color`, and `samples`.
  Each sample is `[elapsed_seconds, x_metres, y_metres, z_metres]`.
- `__BLUE_MARBLE_BASE64__`: JPEG bytes encoded as base64 for the existing data URL.

JSON slots are serialized for inline script values, not HTML attributes or
executable code. Keep their existing contexts when copying the template. A custom
template may use only the slots it needs; unknown or misspelled slots are not
validated. Keep the content security policy and embedded resources when preserving
the offline contract. External scripts, styles or images would break that contract.

## Keep, save or close figures

Matplotlib world/globe/time-series plotters and the Plotly plotter accept
`post_plot` and `post_plot_kwargs`. With no callback, they save the requested file,
close Matplotlib figures, and return `None`. They never open a browser automatically.

A callback replaces that default action. It receives the figure, a normalized
`pathlib.Path` as keyword `path`, and your additional keyword arguments. It must
return a figure from the same backend or `None`:

- Return the original figure to retain it for editing or display.
- Return a replacement figure to retain that instead.
- Return `None` to discard it. The renderer closes its original Matplotlib figure.

Matplotlib originals also close if drawing, saving or the callback raises. A
retained figure belongs to the caller. If a callback creates other figures,
it is responsible for cleaning those up. The `path` keyword is reserved.
Select a Matplotlib GUI backend before importing its renderers to display windows;
use `MPLBACKEND=Agg` for headless rendering.

```python
import matplotlib.pyplot as plt
from offline_earth.visualize import RenderSpec, render_ecef

figures = []

def keep_figure(fig, *, path, title):
    fig.suptitle(title)
    # Saving is optional here because the callback replaces default saving.
    fig.savefig(path)
    return fig

for mode in ("imagery", "political"):
    render_ecef(
        [], f"earth_{mode}.png",
        spec=RenderSpec(backend="map", mode=mode),
        post_plot=keep_figure,
        post_plot_kwargs={"title": mode.title()},
        figures=figures,
    )

# Inspect or filter figures here; plt.show() displays them with a GUI backend.
for fig in figures:
    plt.close(fig)
```

`render_ecef` still returns the output path. A callback may choose not to create
that file. Its optional `figures` collection receives only retained figures, not
`None`. Direct plotters return their retained figure. SVG and Canvas produce
documents rather than figures and reject post-plot callbacks.

Both showcase `main(output_dir=..., post_plot=..., post_plot_kwargs=...)`
functions return a list of retained figures. Their callback must handle both
Matplotlib and Plotly figures. With a custom callback they skip the PNG contact
sheet, since the callback may not save PNGs; SVG, Canvas and sample-data outputs
are still generated. There is no global figure registry.
If a gallery fails before returning, it closes the Matplotlib figures it had
already collected so they are not left open without a returned owner.

## Check a change

Run `python -m pytest -q` with the development extras installed. Focused tests
cover template substitution, named coordinate values, iterable inputs, callback
ownership and example CLIs. The distribution test builds and inspects the wheel.
See the README for the separate clean offline installation and browser checks.
Python tests alone do not certify browser interaction or Plotly WebGL behavior.
