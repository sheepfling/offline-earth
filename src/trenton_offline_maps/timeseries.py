"""Optional Matplotlib ECEF coordinate-vs-time renderer (all units explicit)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence
from .trajectory import EcefTrajectory


def matplotlib_ecef_timeseries(
    path: str | Path, trajectories: Sequence[EcefTrajectory], *,
    unit: str = "km", title: str = "ECEF position vs time",
) -> None:
    """Plot x(t), y(t), z(t) without transforming or propagating inputs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if not trajectories:
        raise ValueError("At least one trajectory required")
    factor = {"m": 1.0, "km": 1000.0}.get(unit)
    if factor is None:
        raise ValueError("unit must be m or km")
    fig, axes = plt.subplots(3, 1, figsize=(12, 8.2), sharex=True, dpi=145)
    fig.patch.set_facecolor("#091827")
    for axis, axis_name, key in zip(axes, ("X", "Y", "Z"), ("x_m", "y_m", "z_m")):
        axis.set_facecolor("#0d2134")
        for tr in trajectories:
            axis.plot([s.t_s for s in tr.samples],
                      [getattr(s.position, key) / factor for s in tr.samples],
                      label=tr.name, color=tr.color, linewidth=1.7)
        axis.set_ylabel(f"ECEF {axis_name} ({unit})", color="#d9e6f0")
        axis.tick_params(colors="#bdcedb")
        axis.grid(alpha=.2, color="#c6dae7")
        axis.spines[:].set_color("#40566c")
    axes[0].legend(facecolor="#15293f", labelcolor="white", loc="upper right")
    axes[-1].set_xlabel("Time relative to epoch (s)", color="#d9e6f0")
    fig.suptitle(title, color="#ecf4ff", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0,0,1,.96))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
