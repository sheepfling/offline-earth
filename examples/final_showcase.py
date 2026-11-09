"""Generate a plain catalog of Offline Earth's actual rendering options."""
from __future__ import annotations

import argparse
import csv
import hashlib
from html import escape
import json
import platform
import re
import zipfile
from importlib.metadata import version
from pathlib import Path
from typing import Final, NamedTuple


class OutputExample(NamedTuple):
    filename: str
    label: str
    backend: str
    mode: str | None
    at_s: float | None


MODES: Final = ('imagery', 'political', 'combined')
CAMERA: Final = {'center_lon_deg': -65.0, 'center_lat_deg': 25.0,
                 'extent_earth_radii': 1.25}
SNAPSHOT_S: Final[float] = 4800.0


def output_directory() -> Path:
    return Path(__file__).resolve().parents[1] / 'artifacts' / 'final-showcase'


def render_index(examples: list[OutputExample]) -> str:
    """Fill the checkout-only template with links to generated files."""
    lookup = {(item.backend, item.mode): item for item in examples[:12]}
    rows = []
    for backend, description in (
        ('svg', 'SVG world map; ground projection; no Python dependencies.'),
        ('map', 'Matplotlib world map; ground projection with axes and labels.'),
        ('globe', 'Matplotlib globe; altitude-aware ECEF projection and Earth occlusion.'),
    ):
        cells = []
        for mode in MODES:
            example = lookup[backend, mode]
            link = escape('outputs/' + example.filename, quote=True)
            cells.append(f'<td><a href="{link}"><img src="{link}" alt="{backend} {mode}">{mode}</a></td>')
        rows.append(f'<tr><th>{backend}<small>{description}</small></th>{"".join(cells)}</tr>')
    extra = []
    for item in examples[12:]:
        name = escape('outputs/' + item.filename, quote=True)
        extra.append(f'<li><a href="{name}">{escape(item.label)}</a></li>')
    template = Path(__file__).with_name('templates') / 'showcase.html'
    text = template.read_text(encoding='utf-8')
    replacements = {'__RENDERER_ROWS__': '\n'.join(rows), '__ADDITIONAL_OUTPUTS__': '\n'.join(extra)}
    for token, replacement in replacements.items():
        if token not in text:
            raise ValueError(f'Missing catalog template token: {token}')
        text = text.replace(token, replacement)
    if re.search(r'__[A-Z_0-9]+__', text):
        raise ValueError('Unfilled catalog template token')
    return text


def save_compact_figure(fig, *, path) -> None:
    """Keep normal renderer appearance; save smaller review PNGs."""
    fig.savefig(path, dpi=100, facecolor=fig.get_facecolor(), bbox_inches='tight')


def build_showcase(output_dir: str | Path | None = None) -> Path:
    from importlib.resources import files
    from examples.utilities import sample_ecef_trajectories
    from offline_earth.geodesy import geodetic_to_ecef
    from offline_earth.svg import save_svg
    from offline_earth.timeseries import matplotlib_ecef_timeseries
    from offline_earth.trajectory import EcefTrajectory, write_trajectories
    from offline_earth.visualize import RenderSpec, render_ecef

    out = output_directory() if output_dir is None else Path(output_dir).expanduser().resolve()
    rendered = out / 'outputs'
    rendered.mkdir(parents=True, exist_ok=True)
    tracks = sample_ecef_trajectories()
    examples: list[OutputExample] = []
    commands = []

    def generate(backend, mode, filename, *, data=tracks, at_s=SNAPSHOT_S, camera=CAMERA, label=None):
        kwargs = {'post_plot': save_compact_figure} if backend in ('map', 'globe', 'timeseries') else {}
        render_ecef(data, rendered / filename, spec=RenderSpec(backend=backend, mode=mode, at_s=at_s, **camera), **kwargs)
        examples.append(OutputExample(filename, label or f'{backend}: {mode}', backend, None if backend == 'timeseries' else mode, at_s))

    for backend, extension in (('svg', 'svg'), ('map', 'png'), ('globe', 'png')):
        for mode in MODES:
            generate(backend, mode, f'{backend}-{mode}.{extension}')
    generate('canvas', 'combined', 'canvas.html')
    generate('plotly', 'combined', 'plotly.html')
    generate('timeseries', 'combined', 'timeseries-km.png', at_s=None)
    # Supplemental examples show distinct options, not every redundant combination.
    for at_s in (3600.0, 6000.0):
        generate('globe', 'combined', f'globe-time-{int(at_s)}.png', at_s=at_s,
                 label=f'Snapshot at {at_s:g} s (compare with globe combined at 4800 s)')
    generate('globe', 'combined', 'globe-camera-default.png', camera={},
             label='Default globe camera and extent: -30°, 22°, 1.35 Earth radii')
    point = geodetic_to_ecef(-75, 0, 35_786_000)
    geo = EcefTrajectory.from_arrays('High-altitude fixed ECEF point', [0, 6000],
                                    [[point.x_m, point.y_m, point.z_m]]*2, color='#b7a6fa')
    write_trajectories(out / 'sample-high-altitude.json', [geo])
    generate('globe', 'combined', 'globe-extent-8.png', data=[geo],
             camera={**CAMERA, 'extent_earth_radii': 8.0},
             label='High-altitude fixed ECEF point with globe extent 8 Earth radii')
    save_svg(rendered / 'svg-tracks-stations.svg', width=1000, height=500, mode='political',
             tracks=[[(-120, 30), (-90, 45), (-60, 35)]], stations=[(-86.59, 34.72)])
    examples.append(OutputExample('svg-tracks-stations.svg', 'Direct SVG API: raw lon/lat track, station, custom dimensions', 'svg', 'political', None))
    matplotlib_ecef_timeseries(rendered / 'timeseries-m.png', tracks, unit='m',
                              post_plot=save_compact_figure)
    examples.append(OutputExample('timeseries-m.png', 'Direct time-series API: meters instead of kilometers', 'timeseries', None, None))

    write_trajectories(out / 'sample-ecef.json', tracks)
    with (out / 'sample-ecef.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['name', 'time_s', 'x_m', 'y_m', 'z_m'])
        for track in tracks:
            for sample in track.samples:
                writer.writerow([track.name, sample.t_s, sample.position.x_m, sample.position.y_m, sample.position.z_m])
    for backend in ('svg', 'map', 'globe', 'canvas', 'interactive', 'timeseries'):
        extension = 'html' if backend in ('canvas', 'interactive') else 'svg' if backend == 'svg' else 'png'
        commands.append(f'offline-earth example-{backend}.{extension} --renderer {backend} --mode combined --ecef sample-ecef.json --at-s 4800 --center-lon-deg -65 --center-lat-deg 25 --extent-earth-radii 1.25')
    commands += [
        '# Three distinct initial modes for svg/map/globe/canvas: --mode imagery|political|combined',
        '# Plotly imagery and combined initialize identically; use its Blue Marble button for imagery alone.',
        '# timeseries ignores mode/time/camera/extent. CLI units are km; use its direct Python API for meters.',
        '# Camera angles affect globe/canvas only. Extent affects globe only.',
        '# For no trajectories, omit --ecef (all Earth views; timeseries requires data).',
        '# Multiple files: repeat --ecef FILE. CSV loses custom color and epoch metadata.',
    ]
    (out / 'commands.txt').write_text('\n'.join(commands)+'\n', encoding='utf-8')
    (out / 'index.html').write_text(render_index(examples), encoding='utf-8')
    (out / 'README.txt').write_text(
        'Offline Earth options\n\nExtract the whole ZIP and open index.html.\n'
        'The index lists all six backends, layer modes, time/camera behavior, input formats, CLI flags and direct Python options.\n'
        'outputs/ contains 18 generated examples. The single Canvas and Plotly pages each contain all three layer buttons.\n'
        'sample-ecef.json and sample-ecef.csv contain the same positions/times; CSV does not preserve colors or epochs.\n'
        'No server or Python installation is needed to view the supplied files. Plotly requires WebGL.\n'
        'Generation is offline. Browser interactions, WebGL and HTML layout remain unverified in this environment.\n'
        'Rebuild from a checkout with installed wheel-only [examples] dependencies: python -m examples.final_showcase\n'
        'Use MPLBACKEND=Agg for headless Matplotlib. All catalog code/templates/outputs stay outside the wheel.\n'
        'The paths are illustrative data, not orbit propagation. Asset provenance is in ASSETS.json.\n'
        'No code-license decision, publication, merge, release or PR closure is performed.\n', encoding='utf-8')
    (out / 'ASSETS.json').write_text(files('offline_earth').joinpath('data/ASSETS.json').read_text(), encoding='utf-8')
    filenames = ['index.html', 'README.txt', 'commands.txt', 'ASSETS.json',
                 'sample-ecef.json', 'sample-ecef.csv', 'sample-high-altitude.json']
    filenames += ['outputs/' + item.filename for item in examples]
    manifest = {
        'format': 'offline-earth-options-v2', 'python': platform.python_version(),
        'packages': {name: version(name) for name in ('numpy', 'matplotlib', 'pillow', 'plotly')},
        'main_example_time_s': SNAPSHOT_S, 'main_static_camera': CAMERA,
        'main_canvas_camera': {key: value for key, value in CAMERA.items() if key != 'extent_earth_radii'},
        'plotly_camera': 'Default Plotly 3D perspective',
        'examples': [item._asdict() for item in examples],
        'browser_validation': 'Not verified: the execution environment could not launch the audit browser.',
        'files': {name: {'size_bytes': (out/name).stat().st_size,
                         'sha256': hashlib.sha256((out/name).read_bytes()).hexdigest()} for name in filenames},
    }
    (out / 'showcase-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    archive = out.parent / f'{out.name}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in [*filenames, 'showcase-manifest.json']:
            bundle.write(out/name, arcname='offline-earth-options/'+name)
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=output_directory())
    args = parser.parse_args(argv)
    print(build_showcase(args.output_dir))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
