"""Building damage screening from ground displacements (Burland & Wroth 1974 / Boscardin & Cording 1989).

Simplified, indicative screening for ONE facade treated as a single beam. It is not a replacement for a full
assessment (XDisp, corner effects, building stiffness, ...).

Units: displacements in mm, coordinates in m, strains returned in %.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Burland (1977) / Boscardin & Cording (1989) limiting tensile strain classes, in %
CATEGORIES = [  # (upper limit %, category, description)
    (0.05, 0, "Negligible"),
    (0.075, 1, "Very slight"),
    (0.15, 2, "Slight"),
    (0.30, 3, "Moderate"),
    (math.inf, 4, "Severe to very severe (4-5)"),
]

BUILDING_TYPES = {"masonry": ("Load-bearing masonry wall (E/G = 2.6)", 2.6),
                  "frame": ("Framed building with infill (E/G = 12.5)", 12.5)}


def category(eps_pct: float):
    for lim, cat, desc in CATEGORIES:
        if eps_pct < lim:
            return cat, desc
    return 4, CATEGORIES[-1][2]


@dataclass
class FacadeResult:
    name: str
    length: float                 # m
    n_points: int
    max_settlement: float         # mm (positive down)
    max_horizontal: float         # mm (total horizontal displacement magnitude)
    tilt: float                   # % (end-to-end slope of settlement)
    max_slope: float              # % (steepest slope between adjacent points)
    deflection_ratio: float       # % (delta/L, signed: + sagging, - hogging)
    mode: str                     # "sagging" | "hogging"
    eps_h: float                  # % (average horizontal strain along the facade, + tension)
    eps_bending: float            # % (eps_bt)
    eps_shear: float              # % (eps_dt)
    eps_governing: float          # % (max of the two)
    governing: str                # "bending" | "shear"
    category: int
    description: str


def facade_damage(name: str, s: np.ndarray, uz: np.ndarray, h: np.ndarray, height: float,
                  e_over_g: float = 2.6, nu: float = 0.3) -> FacadeResult:
    """s: coordinate along the facade [m]; uz: vertical displacement [mm, + up]; h: horizontal displacement
    along the facade axis [mm, + in the direction of increasing s]; height: building height [m]."""
    s, uz, h = (np.asarray(a, float) for a in (s, uz, h))
    o = np.argsort(s)
    s, uz, h = s[o], uz[o], h[o]
    L = float(s[-1] - s[0])
    w = -uz / 1000.0                                            # settlement [m], positive down
    chord = w[0] + (w[-1] - w[0]) * (s - s[0]) / L
    dev = w - chord
    k = int(np.argmax(np.abs(dev)))
    delta = float(abs(dev[k]))
    sagging = dev[k] >= 0                                       # more settlement mid-span than the chord
    dr = delta / L
    slopes = np.diff(w) / np.diff(s)
    tilt = (w[-1] - w[0]) / L
    eps_h = (h[-1] - h[0]) / 1000.0 / L                         # + = lengthening

    H = float(height)
    t = H / 2 if sagging else H                                 # neutral axis: middle (sagging) / bottom (hogging)
    I = H ** 3 / 12.0
    eg = float(e_over_g)
    eps_b = dr / (L / (12 * t) + 3 * I * eg / (2 * t * L * H)) if dr > 0 else 0.0
    eps_d = dr / (1 + H * L ** 2 / (18 * I * eg)) if dr > 0 else 0.0
    eps_bt = eps_b + eps_h
    eps_dt = eps_h * (1 - nu) / 2 + math.sqrt((eps_h * (1 + nu) / 2) ** 2 + eps_d ** 2)
    gov = max(eps_bt, eps_dt, 0.0) * 100
    cat, desc = category(gov)
    return FacadeResult(
        name=name, length=L, n_points=len(s), max_settlement=float(w.max() * 1000), max_horizontal=float(np.abs(h).max()),
        tilt=tilt * 100, max_slope=float(np.abs(slopes).max() * 100), deflection_ratio=dr * 100 * (1 if sagging else -1),
        mode="sagging" if sagging else "hogging", eps_h=eps_h * 100, eps_bending=eps_bt * 100, eps_shear=eps_dt * 100,
        eps_governing=gov, governing="bending" if eps_bt >= eps_dt else "shear", category=cat, description=desc)
