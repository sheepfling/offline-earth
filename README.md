# Offline Earth

Offline-only Python Earth visualization: Blue Marble, political boundaries, or both,
with timestamped **ECEF trajectories in metres**.

## Recommended path

The core wheel has **zero third-party runtime dependencies**. It contains the JPEG,
country geometry, provenance, asset checksums and upstream license notices. Generate an
interactive, self-contained Canvas HTML globe or an SVG using only Python's standard library.
Canvas supports drag-to-rotate, layer selection, time scrubbing and Play/Pause. No tiles,
CDNs, API keys, dataset cache, delayed downloads, telemetry or remote services are used.
Its HTML also includes a policy denying network connections and external resources.

```sh
python -m pip install --no-index --only-binary=:all: --no-deps \
  dist/offline_earth-0.3.1-py3-none-any.whl
offline-earth earth.html --renderer canvas --mode combined \
  --ecef examples/data/sample_ecef.json --at-s 3600
offline-earth earth.svg --renderer svg --mode political \
  --ecef examples/data/sample_ecef.json
```

For a small Python example, run `python examples/quickstart.py` after installing
only the core wheel. It creates `earth.html` with an illustrative ECEF path and
time controls; no `[examples]` extra or plotting dependencies are needed. The
larger gallery scripts are opt-in and are not included in the installed wheel.
Use `python examples/quickstart.py --output results/earth.html` to choose its path.

Open `earth.html` directly in a local browser. No server is needed. Build the wheel first
from a checkout (see below); wheels are not committed or automatically released.

## Python API

```python
from offline_earth.trajectory import EcefTrajectory
from offline_earth.visualize import RenderSpec, render_ecef

track = EcefTrajectory.from_arrays(
    "Example", [0, 10, 20],
    [[7_000_000, 0, 0], [6_990_000, 300_000, 100_000], [6_970_000, 600_000, 200_000]],
)
render_ecef([track], "earth.html", spec=RenderSpec(
    backend="canvas", mode="combined", at_s=10, center_lon_deg=0, center_lat_deg=20))
```

ECEF is Earth-fixed, right-handed: +X at 0° longitude/equator, +Y at 90°E/equator,
+Z north. Time is elapsed seconds from a common caller-defined origin; optional UTC epochs
must agree across tracks. Positions interpolate linearly, not through an orbit propagator.
See [coordinate/time contract](docs/ECEF_CONTRACT.md).

## Optional renderers

- `map`, `globe`, `timeseries`: NumPy, Matplotlib and Pillow wheels.
- `interactive` (Python `plotly` backend): NumPy, Pillow and Plotly wheels; embeds JS.
- `svg`, `canvas`: no optional packages. Canvas is the preferred portable interactive path.

```sh
# ONLINE staging, on a machine matching the target Python/OS/architecture:
python -m pip download --only-binary=:all: --dest wheelhouse \
  './dist/offline_earth-0.3.1-py3-none-any.whl[plot,interactive]'
# OFFLINE installation after transferring the entire wheelhouse:
python -m pip install --no-index --only-binary=:all: --find-links=wheelhouse \
  'offline-earth[plot,interactive]==0.3.1'
```

Wheel acquisition is separate from offline runtime. A successful wheel download for one
platform does not certify another. No complete platform-specific wheelhouse is shipped.
For a reproducible deployment, retain wheel filenames and SHA-256 hashes and pin the chosen
versions. Browser binaries are separately installed desktop software, not Python assets.

Optional APIs live in explicit modules: `renderers.matplotlib`, `renderers.plotly`,
`renderers.raster`, and `timeseries`. Importing one loads its declared dependencies;
core `visualize` dispatches only the selected backend. Demo generators belong to
`examples.utilities`, not the production package.

Canvas data loading is separate from presentation: `load_canvas_scene` in
`canvas_scene` returns local scene data; `render_canvas_html` in `canvas` consumes it.
The default presentation is the inspectable wheel resource `templates/canvas.html`.
A caller may supply an alternate template without reloading assets.
See [extending the package](docs/EXTENDING.md) for the source map, template slots,
and post-plot callbacks that retain, save, close or collect figures.

## Build and test

Install normal development extras while online (includes build, test, example and
browser-audit Python dependencies):

```sh
python -m pip install --only-binary=:all: -e '.[dev]'
python -m pytest -q
```

For examples alone, use `pip install --only-binary=:all: -e '.[examples]'`.
The editable project is local source; all third-party dependencies must be wheels.
Generate galleries with `python -m examples.showcase_offline` or
`python -m examples.showcase_ecef`; outputs go under ignored `artifacts/`.
Both accept `--output-dir PATH`. Sample CSV/JSON inputs live in `examples/data/`.
The checked-in ECEF JSON is a small, coarse example. Generate a more densely sampled
version with the core package alone:

```sh
python -m examples.generate_samples --output artifacts/ecef/sample_ecef.json --sample-count 151
```

The generator defaults to 151 samples per LEO track over 0–6000 seconds; the
small checked-in JSON uses 13. These are illustrative paths, not orbit propagation.
Neither importing examples nor
importing browser-audit helpers creates files or launches a browser.

Build itself does not need network access once the development tools are installed:

```sh
python -m pip wheel --no-deps --no-build-isolation --no-index . -w dist
PYTHONPATH=src python -m pytest -q
python -m venv /tmp/earth-clean
/tmp/earth-clean/bin/pip install --no-index --no-deps --only-binary=:all: dist/*.whl
/tmp/earth-clean/bin/python tools/verify_core_offline.py
```

The `[dev]` extra covers the full test suite. The installed-wheel
smoke script needs only stdlib and blocks Python socket/DNS calls while rendering all three
modes with both core renderers. After generating the ECEF gallery, `python tools/verify_ecef_browser.py`
uses Playwright from `[dev]` plus a preinstalled Chromium; it intercepts external
page requests. The browser binary is not downloaded automatically.
For headless Matplotlib runs, set `MPLBACKEND=Agg`; the library respects the caller's
backend rather than changing it during import.

## Assets, inspection, licenses

- `data/blue_marble.jpg`: an ordinary viewable JPEG downloaded directly from NASA's
  Blue Marble Next Generation base-map collection, July 2004. The official
  5400×2700 image is bundled unchanged. This is human-viewable imagery, **not text data**.
- `data/countries.json`: human-readable JSON geometry, 177 simplified Natural Earth countries.
- `data/ASSETS.json`: the single provenance record, with direct source URLs, sizes,
  hashes, image metadata, credits, reuse terms and limitations. The exact upstream
  country-data version was not recorded in the input archive and remains unknown.
- `licenses/README.md`: points to the bundled asset record; also included in the wheel.

Inspect wheels with any ZIP reader. No opaque asset-fetching library is required.
NASA imagery credit: NASA Earth Observatory (Reto Stöckli). NASA imagery is generally
not subject to US copyright; follow its [Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/),
including acknowledgment and no implied endorsement. Natural Earth is public domain.
Asset terms are not a blanket license for this project's code. **No project-wide code
license has been chosen yet.** Review provenance/licensing before public distribution.

## Limitations

Country borders are simplified and not authoritative, with no admin-1/admin-2 data.
Canvas/Matplotlib Earth appearance is spherical; ECEF transforms and visibility calculations
use WGS84. Plotly uses an ellipsoid mesh but has not been browser-certified here. No terrain,
ECI-to-ECEF conversion, orbit propagation, dated imagery, or high-precision limb clipping.
Canvas uses fixed view extent; `extent_earth_radii` currently applies to the Matplotlib globe.
The Plotly initial display choices are more limited than Canvas; its imagery layer may include
borders. No promise that arbitrary future optional-dependency releases remain offline-safe.

