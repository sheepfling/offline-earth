# ECEF trajectory interface

## Coordinate and time contract

- **Position:** WGS84 Earth-Centered, Earth-Fixed Cartesian coordinates in **metres**, not ECI, TEME, GCRS, or kilometres. Right-handed: X through the equator at Greenwich, Y through 90° east, Z toward the north pole.
- **Time:** strictly increasing finite floating-point seconds `time_s` relative to a *caller-defined* origin. Optional `epoch_utc` records the origin as an ISO-8601 datetime with UTC offset. If multiple tracks provide an epoch, they must all provide the same instant. No UTC/UT1, leap-second, Earth rotation, or inertial-frame conversions are silently performed.
- **Geometry:** WGS84 `a=6378137 m`, `1/f=298.257223563`. Convert ground projection with `ecef_to_geodetic`. The time-series plots preserve raw x/y/z, without geodetic conversion.
- **Interpolation:** piecewise linear between adjacent ECEF samples at requested `at_s`. This is an interpolation method, **not** an orbital propagator. Extrapolation is rejected. A sparse sampled trajectory is drawn as straight chords; high-curvature paths require adequate sampling.
- **Occlusion:** orthographic globe checks visibility of each sampled ECEF point using a WGS84 ellipsoid ray test. In other words, an orbit behind Earth is not drawn through the planet; a high-altitude point can be visible beyond the limb. Rendering paths are polyline approximations; visibility transitions between sparse samples are not clipped to exact tangent points.

## Input files

`offline-earth --ecef file.json` expects:

```json
{
  "frame": "ECEF",
  "units": "metres",
  "time_units": "seconds",
  "trajectories": [
    {
      "name": "Object A",
      "color": "#ffbd69",
      "epoch_utc": "2026-11-07T00:00:00+00:00",
      "samples": [
        {"time_s": 0.0, "ecef_m": [6878137, 0, 0]},
        {"time_s": 30.0, "ecef_m": [6860000, 495000, 100000]}
      ]
    }
  ]
}
```

Or use long-format CSV:

```csv
name,time_s,x_m,y_m,z_m
Object A,0,6878137,0,0
Object A,30,6860000,495000,100000
```

One file may contain multiple trajectories. Repeated `--ecef` arguments merge trajectories in the same scene. No input file can cause the package to fetch a URL; only local files are accepted.

## Programmatic use

```python
from offline_earth import EcefTrajectory
from offline_earth.visualize import RenderSpec, render_ecef

track = EcefTrajectory.from_arrays(
    name="Example spacecraft",
    time_s=[0.0, 10.0, 20.0],
    xyz_m=[
        [6878137.0, 0.0, 0.0],
        [6860000.0, 420000.0, 90000.0],
        [6800000.0, 835000.0, 180000.0],
    ],
    color="#ffbd69",
)

render_ecef([track], "world.png", spec=RenderSpec(backend="map", mode="combined", at_s=10.0))
render_ecef([track], "globe.png", spec=RenderSpec(backend="globe", mode="combined", at_s=10.0))
render_ecef([track], "interactive.html", spec=RenderSpec(backend="canvas"))
render_ecef([track], "ecef_xyz.png", spec=RenderSpec(backend="timeseries"))
render_ecef([track], "earth.html", spec=RenderSpec(backend="plotly"))
render_ecef([track], "map.svg", spec=RenderSpec(backend="svg", mode="combined"))
```

The SVG and Canvas backends need **only** the core wheel. Matplotlib and Plotly adapters are optional extras. The HTML Canvas view has a time scrubber, Play/Pause, draggable viewpoint, and imagery/political/both selector. The Plotly view renders true 3D ECEF paths with a static marker at `at_s`; it is not yet an animated time-series player.

## Renderer geometry differences

| Backend | Earth surface | Trajectory | Animation |
|---|---|---|---|
| SVG | 2D equirectangular Blue Marble / borders | WGS84 ground projection | No |
| Matplotlib world | 2D equirectangular Blue Marble / borders | WGS84 ground projection | Snapshot at `at_s` |
| Matplotlib globe | Approximate spherical orthographic Earth | ECEF altitude-aware with WGS84 visibility | Snapshot at `at_s` |
| Canvas globe | Approximate spherical image mapping | ECEF altitude-aware with WGS84 visibility | Interactive slider + Play/Pause |
| Plotly globe | WGS84 ellipsoid visual mesh | True ECEF 3D coordinates | Snapshot marker at `at_s` (3D interaction) |
| Matplotlib XYZ/t | No Earth image | Raw ECEF X,Y,Z by time | Static |

The Matplotlib and Canvas Earth image projection is intentionally spherical for speed/portability. Use the coordinates and WGS84 transforms from the core for calculations, not screen pixels. The Plotly ellipsoid mesh is suitable for visualization, not a terrain model.

## Offline and wheel-only contract

- Wheel contains the country vectors and Blue Marble JPEG as Python package data.
- No network calls or automatic dataset downloads are built into the library.
- Only Python wheels may be installed; the optional display packages must already exist in an **offline platform-specific wheelhouse** when installing air-gapped.
- Core wheel can install with `pip install --no-index --only-binary=:all: --no-deps path/to/offline_earth-0.3.1-py3-none-any.whl`.
- Tests block socket and DNS operations while actually rendering. A separate browser test intercepts and aborts every external request and checks Canvas mode, time scrubber, Play/Pause and dragging.

## Known gaps

No orbit dynamics or ECI→ECEF conversion, terrain, satellite imagery by date, state/province/county borders, local elevation model, ellipsoidal horizon limb clipping for every line segment, or high-accuracy atmospheric refraction. Borders are simplified Natural Earth country geometries and some disputed boundaries may be represented differently in other datasets.

## JSON metadata validation

At both the document wrapper and individual trajectory level, explicitly supplied
`frame`, `units`, and `time_units` must be exactly `"ECEF"`, `"metres"`, and
`"seconds"`, respectively. Conflicting values, alternate spellings/case and null
values raise `ValueError` before positions are interpreted. No conversion is
performed. Legacy JSON omitting any or all metadata remains supported and uses
ECEF metres and elapsed seconds, as also expressed by `ecef_m` and `time_s`.
This applies to wrapped trajectory collections and single-trajectory JSON.

## Public paths and coordinate types

All public file inputs/outputs accept `PathInput` (`str | os.PathLike[str]`).
Shared I/O helpers normalize to `pathlib.Path`; writers create parent directories.
`EcefTrajectory.from_arrays` accepts iterables, including one-shot generators for
times and coordinate rows. Their lengths must match; no values are silently
discarded. `read_trajectories` returns a mutable list so callers can append,
remove or reorder tracks. Each validated trajectory retains an immutable tuple
of samples; construct a new trajectory to change its positions or times.
`center_lon_deg` and `center_lat_deg` always mean **degrees**, not radians, in Python and
CLI APIs (`--center-lon-deg`, `--center-lat-deg`). Their `Degrees` annotations carry
that unit. Internal trigonometry uses explicitly named `_rad` variables.

Ground-track points are `LonLatDegrees(lon_deg, lat_deg)`; time ranges expose
`start_s`/`end_s`, and projected points expose Earth-radius coordinates and visibility.
These named tuples preserve unpacking/indexing and ordinary tuple input compatibility.
Assets, physical/display constants, and camera/seam geometry are independent shared
modules. Renderers consume them; Canvas does not import the optional Earth renderer.
WGS84 coordinate types, conversions and horizon projection live in `geodesy`.
Existing coordinate imports from `trajectory` and the package root remain available.
