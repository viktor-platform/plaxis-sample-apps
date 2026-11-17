"""Plotly figures for plate results (PDF-style combined plot + stage comparison)."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

from .models import Plate, PlateResult, Stage

C_UX, C_M, C_Q = "#d62a4d", "#3fb3e6", "#7bc043"   # colours used in the report plots
WALL = "#0b1b6b"

QUANTITIES = {"ux": ("Horizontal displacement uₓ [mm]", "mm"),
              "m": ("Bending moment M [kNm/m]", "kNm/m"),
              "q": ("Shear force Q [kN/m]", "kN/m")}


def _sym(arr_list, pad=1.15):
    m = max(float(np.abs(a).max()) for a in arr_list) * pad
    return [-max(m, 1e-6), max(m, 1e-6)]


def combined_figure(res: PlateResult, plate: Plate, stage: Stage, title: str = "") -> go.Figure:
    """ux, M, Q on one elevation axis with three independent (zero-aligned) x axes."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 0], y=[plate.top, plate.bottom], mode="lines",
                             line=dict(color=WALL, width=5), name="Wall", hoverinfo="skip",
                             showlegend=False))
    fig.add_trace(go.Scatter(x=res.ux, y=res.y, name="uₓ [mm]", line=dict(color=C_UX, width=2.5),
                             xaxis="x", hovertemplate="uₓ=%{x:.2f} mm<br>y=%{y:.2f} mOD<extra></extra>"))
    fig.add_trace(go.Scatter(x=res.m, y=res.y, name="M [kNm/m]", line=dict(color=C_M, width=2.5),
                             xaxis="x2", hovertemplate="M=%{x:.1f} kNm/m<br>y=%{y:.2f} mOD<extra></extra>"))
    fig.add_trace(go.Scatter(x=res.q, y=res.y, name="Q [kN/m]", line=dict(color=C_Q, width=2.5),
                             xaxis="x3", hovertemplate="Q=%{x:.1f} kN/m<br>y=%{y:.2f} mOD<extra></extra>"))

    if stage.excavation_level is not None:
        fig.add_hline(y=stage.excavation_level, line=dict(color="#8b5a2b", dash="dash", width=1.5),
                      annotation_text=f"Excavation level {stage.excavation_level:+.1f} mOD",
                      annotation_position="bottom left")

    ax = lambda t, c, **kw: dict(title=dict(text=t, font=dict(color=c)), tickfont=dict(color=c),
                                 showgrid=False, zeroline=False, **kw)
    fig.update_layout(
        title=dict(text=f"{title or plate.name} – {stage.label}", x=0.01),
        height=720, template="plotly_white", margin=dict(t=110, r=30, l=70, b=60),
        yaxis=dict(title="Y [mOD]", domain=[0, 0.84], showgrid=True, gridcolor="#eee",
                   range=[plate.bottom - 1.5, plate.top + 1.5]),
        xaxis=ax("uₓ [mm]", C_UX, range=_sym([res.ux]), anchor="y", side="bottom"),
        xaxis2=ax("M [kNm/m]", C_M, range=_sym([res.m]), overlaying="x", anchor="y", side="top"),
        xaxis3=ax("Q [kN/m]", C_Q, range=_sym([res.q]), overlaying="x", anchor="free",
                  position=0.97, side="top"),
        legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
        hovermode="closest",
    )
    s = res.summary
    fig.add_annotation(xref="paper", yref="paper", x=1, y=-0.17, showarrow=False, xanchor="right",
                       font=dict(size=11, color="#555"),
                       text=(f"max uₓ = {s['ux_max']:.2f} / min {s['ux_min']:.2f} mm &nbsp;|&nbsp; "
                             f"M {s['m_min']:.0f} … {s['m_max']:.0f} kNm/m &nbsp;|&nbsp; "
                             f"Q {s['q_min']:.0f} … {s['q_max']:.0f} kN/m"))
    return fig


def comparison_figure(results: list[tuple[Stage, PlateResult]], plate: Plate,
                      envelope: bool = True, quantities=("ux", "m", "q")) -> go.Figure:
    """Side-by-side plots for several stages, coloured along the construction sequence."""
    quantities = [q for q in QUANTITIES if q in quantities] or ["m"]
    fig = make_subplots(rows=1, cols=len(quantities), shared_yaxes=True, horizontal_spacing=0.03,
                        subplot_titles=[QUANTITIES[q][0] for q in quantities])
    n = max(len(results) - 1, 1)
    for i, (stage, r) in enumerate(results):
        col = sample_colorscale("Viridis", [0.9 * i / n])[0]
        for c, key in enumerate(quantities, start=1):
            fig.add_trace(go.Scatter(x=getattr(r, key), y=r.y, name=stage.label, legendgroup=stage.id,
                                     showlegend=(c == 1), line=dict(color=col, width=2),
                                     hovertemplate=f"{stage.name}<br>%{{x:.2f}} {QUANTITIES[key][1]}"
                                                   "<br>y=%{y:.2f} mOD<extra></extra>"), row=1, col=c)
    if envelope and results:
        y = results[0][1].y
        for c, key in enumerate(quantities, start=1):
            stack = np.vstack([getattr(r, key) for _, r in results])
            for fn, nm in ((np.max, "max"), (np.min, "min")):
                fig.add_trace(go.Scatter(x=fn(stack, axis=0), y=y, name=f"Envelope {nm}",
                                         legendgroup="env", showlegend=(c == 1 and nm == "max"),
                                         line=dict(color="black", width=1.2, dash="dot")), row=1, col=c)
    fig.update_yaxes(title_text="Y [mOD]", row=1, col=1, range=[plate.bottom - 1.5, plate.top + 1.5])
    fig.update_xaxes(zeroline=True, zerolinecolor="#222", zerolinewidth=1.5)
    fig.update_layout(height=720, template="plotly_white", margin=dict(t=80, r=20, l=70, b=50),
                      title=dict(text=f"{plate.name} – stage comparison", x=0.01),
                      legend=dict(orientation="h", y=-0.12))
    return fig
