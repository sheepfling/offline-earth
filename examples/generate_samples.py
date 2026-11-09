"""Generate synthetic ECEF JSON with the core package only; no orbit propagation."""
import argparse
from pathlib import Path

from examples.utilities import DEMO_SAMPLE_COUNT, sample_ecef_trajectories
from offline_earth.trajectory import write_trajectories


def main(output: str | Path = 'artifacts/ecef/sample_ecef.json',
         sample_count: int = DEMO_SAMPLE_COUNT) -> Path:
    tracks = sample_ecef_trajectories(sample_count)
    path = Path(output)
    write_trajectories(path, tracks)
    return path


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', '-o', type=Path,
                        default=Path('artifacts/ecef/sample_ecef.json'),
                        help='JSON output path (default: %(default)s)')
    parser.add_argument('--sample-count', type=int, default=DEMO_SAMPLE_COUNT,
                        help='Samples per LEO trajectory, at least 2 (default: %(default)s)')
    args = parser.parse_args(argv)
    if args.sample_count < 2:
        parser.error('--sample-count must be at least 2')
    print(f'Generated {main(args.output, args.sample_count)}')


if __name__ == '__main__':
    cli()
