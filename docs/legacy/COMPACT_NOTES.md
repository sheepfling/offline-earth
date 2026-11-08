# Compact ECEF / offline Earth showcase (v0.3.0)

This distribution is deliberately under 13 MB. It keeps the **unchanged, installable
Python wheel**, the complete source and tests, documentation, the full-resolution
Blue Marble asset in the package source, samples, the standalone offline ECEF Canvas
HTML globe, and representative PNG gallery images.

## What's deliberately excluded

- Repeated 2D imagery screenshots, SVGs with embedded JPEG, and duplicate globe renders.
- Three ~7 MB uncompressed Plotly HTML outputs with duplicated bundled JavaScript.
- Other regenerated examples not required to use or test the package.

**No renderer or application code was removed.** `showcase_ecef.py` and
`showcase_offline.py` recreate the optional output galleries when the corresponding
wheel-based optional dependencies are installed. The wheel and included Canvas HTML already
contain their own geographic assets and require no external downloads.

## Open first

- `review/ecef/00_ecef_review_gallery.png` — ECEF maps, globes, and XYZ time plot.
- `review/00_review_gallery.png` — Blue Marble, political, and combined map views.
- `review/ecef/interactive_ecef_canvas.html` — interactive ECEF playback (offline).
- `review/ecef/interactive_browser_preview.png` — actual browser screenshot.

## Wheel-only installation

```
python -m pip install --no-index --only-binary=:all: --no-deps \
  dist/trenton_offline_maps-0.3.0-py3-none-any.whl
```

To generate optional Matplotlib and Plotly outputs, pre-stage *their* wheels and
all dependency wheels for the target Python/platform before using `--no-index`.
No Plotly HTML files are necessary for library functionality; scripts regenerate them.

## Verification

The original unmodified code passed 26 tests with `PYTHONPATH=src python -m pytest -q`
on the packaging host. The compact ZIP uses the exact v0.3.0 wheel bytes from the
previous distribution. `MANIFEST_SHA256.json` lists the SHA-256 digest of each
packaged file except itself. Check it after extraction if you want content auditing.
