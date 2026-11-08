"""Optional Plotly globe; independent of Matplotlib."""
from __future__ import annotations

from math import pi
from typing import Sequence

import numpy as np
import plotly.graph_objects as go

from ..assets import countries
from ..constants import METRES_PER_KM, WGS84_A_M, WGS84_E2
from ..geometry import GroundTrack, split_antimeridian
from ..paths import PathInput, output_path
from ..trajectory import EcefTrajectory, geodetic_to_ecef
from .blue_marble import indexed_texture


def plotly_globe(
    path: PathInput,
    *,
    track: GroundTrack | None = None,
    include_imagery: bool = True,
    trajectories: Sequence[EcefTrajectory] = (),
    at_s: float | None = None,
) -> None:
    """Self-contained interactive 3D globe with three toggleable visualization modes.

    Uses Pillow color quantization to encode the local RGB raster as a Plotly
    surface colorscale. The HTML embeds all JS and all geometry; no CDN.
    """

    ids, scale = indexed_texture()
    lat_rad = np.linspace(pi/2, -pi/2, 91)
    lon_rad = np.linspace(-pi, pi, 180)
    lon_grid_rad, lat_grid_rad = np.meshgrid(lon_rad, lat_rad)
    n = WGS84_A_M / np.sqrt(1 - WGS84_E2 * np.sin(lat_grid_rad)**2)
    x = n * np.cos(lat_grid_rad)*np.cos(lon_grid_rad) / METRES_PER_KM
    y = n * np.cos(lat_grid_rad)*np.sin(lon_grid_rad) / METRES_PER_KM
    z = n * (1-WGS84_E2) * np.sin(lat_grid_rad) / METRES_PER_KM
    fig = go.Figure()
    fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=ids.astype(float),
                             cmin=0, cmax=127, colorscale=scale, showscale=False,
                             hoverinfo="skip", lighting=dict(ambient=.8, diffuse=.7), name="Blue Marble", visible=include_imagery))
    fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=np.zeros_like(x),
                             cmin=0, cmax=1, colorscale=[[0, "#1a527b"], [1, "#1a527b"]],
                             showscale=False, hoverinfo="skip", name="Political", visible=not include_imagery))
    # Group borders into one trace, rather than one trace for each of 177 countries.
    bx: list[float | None] = []; by: list[float | None] = []; bz: list[float | None] = []
    for c in countries():
        for ring in c["rings"]:
            for lon_deg, lat_deg in ring:
                ecef = geodetic_to_ecef(lon_deg, lat_deg, 7_000.0)
                bx.append(ecef.x_m / METRES_PER_KM); by.append(ecef.y_m / METRES_PER_KM);
                bz.append(ecef.z_m / METRES_PER_KM)
            bx.append(None); by.append(None); bz.append(None)
    fig.add_trace(go.Scatter3d(x=bx, y=by, z=bz, mode="lines", name="Political borders",
                               line=dict(color="#fce3a3", width=2), hoverinfo="skip", visible=True))
    if track is not None:
        xx: list[float | None] = []; yy: list[float | None] = []; zz: list[float | None] = []
        for segment in split_antimeridian(track):
            for lon_deg, lat_deg in segment:
                ecef = geodetic_to_ecef(lon_deg, lat_deg, 95_000.0)
                xx.append(ecef.x_m / METRES_PER_KM); yy.append(ecef.y_m / METRES_PER_KM);
                zz.append(ecef.z_m / METRES_PER_KM)
            xx.append(None); yy.append(None); zz.append(None)
        fig.add_trace(go.Scatter3d(x=xx, y=yy, z=zz, mode="lines", name="Illustrative track",
                                   line=dict(color="#ffab58", width=6), hoverinfo="skip"))
    # True 3D ECEF paths in kilometres (NOT draped ground tracks).
    for tr in trajectories:
        xx = [s.position.x_m / METRES_PER_KM for s in tr.samples]
        yy = [s.position.y_m / METRES_PER_KM for s in tr.samples]
        zz = [s.position.z_m / METRES_PER_KM for s in tr.samples]
        fig.add_trace(go.Scatter3d(x=xx, y=yy, z=zz, mode="lines", name=tr.name,
                                   line=dict(color=tr.color, width=5),
                                   text=[f"{s.t_s:.1f} s" for s in tr.samples],
                                   hovertemplate=f"{tr.name}: %{{text}}<br>ECEF km: (%{{x:.1f}}, %{{y:.1f}}, %{{z:.1f}})<extra></extra>"))
        marker = tr.samples[-1].position if at_s is None else (
            tr.at(at_s) if tr.time_range[0] <= at_s <= tr.time_range[1] else None)
        if marker is not None:
            fig.add_trace(go.Scatter3d(
                x=[marker.x_m / METRES_PER_KM], y=[marker.y_m / METRES_PER_KM], z=[marker.z_m / METRES_PER_KM],
                mode="markers+text", name=f"{tr.name} position", text=[tr.name],
                textposition="top center", marker=dict(color=tr.color, size=5),
            ))
    count = len(fig.data)
    buttons = [
        dict(label="Blue Marble", method="update", args=[{"visible": [True, False, False] + [True]*(count-3)}]),
        dict(label="Political", method="update", args=[{"visible": [False, True, True] + [True]*(count-3)}]),
        dict(label="Both", method="update", args=[{"visible": [True, False, True] + [True]*(count-3)}]),
    ]
    fig.update_layout(template="plotly_dark", title="Offline Earth · Switch: Imagery / Political / Both",
                      paper_bgcolor="#061522", plot_bgcolor="#061522", showlegend=True,
                      scene=dict(aspectmode="data", xaxis=dict(visible=False), yaxis=dict(visible=False),
                                 zaxis=dict(visible=False), bgcolor="#061522"),
                      updatemenus=[dict(type="buttons", direction="right", buttons=buttons,
                                       x=.03, y=1.08, xanchor="left", bgcolor="#29445e", font=dict(color="#fff"))],
                      margin=dict(l=5, r=5, b=5, t=95))
    fig.write_html(str(output_path(path)), include_plotlyjs=True, full_html=True, auto_open=False)
