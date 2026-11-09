"""Exercise Windows newline behavior without changing the host platform."""
from pathlib import Path

from offline_earth.trajectory import EcefTrajectory, read_trajectories, write_trajectories


def test_trajectory_json_uses_lf_under_windows_default_translation(tmp_path, monkeypatch):
    native_open = Path.open

    def windows_open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "w" in mode and "b" not in mode and newline is None:
            newline = "\r\n"
        return native_open(path, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", windows_open)
    # Confirm the simulation translates unspecified newlines as Windows does.
    control = tmp_path / "control.txt"
    control.write_text("one\ntwo\n", encoding="utf-8")
    assert control.read_bytes() == b"one\r\ntwo\r\n"
    track = EcefTrajectory.from_arrays("Example", [0, 1], [[7e6, 0, 0], [7e6, 1, 2]])
    output = tmp_path / "trajectory.json"
    write_trajectories(output, [track])
    assert b"\n" in output.read_bytes()
    assert b"\r" not in output.read_bytes()
    assert read_trajectories(output) == [track]
