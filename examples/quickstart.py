"""Generate a self-contained globe using only the installed core package."""
from pathlib import Path

from trenton_offline_maps.trajectory import EcefTrajectory, geodetic_to_ecef
from trenton_offline_maps.visualize import RenderSpec, render_ecef


def main(output: str | Path = 'earth.html') -> Path:
    # An illustrative Earth-fixed path, not orbital propagation.
    points = [geodetic_to_ecef(lon, 25, 550_000) for lon in (-60, -30, 0, 30)]
    track = EcefTrajectory.from_arrays(
        'Example', [0, 60, 120, 180],
        [(p.x_m, p.y_m, p.z_m) for p in points],
    )
    return render_ecef([track], output, spec=RenderSpec(backend='canvas', at_s=60))


if __name__ == '__main__':
    print(f'Open {main()} in a local browser.')
