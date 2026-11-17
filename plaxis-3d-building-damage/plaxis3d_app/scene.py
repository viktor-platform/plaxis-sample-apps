"""3D scene helpers: pit, walls, ground, building box and displaced facade lines for a GeometryView."""
from __future__ import annotations

import re

import viktor as vkt

from .damage import CATEGORIES

CAT_COLORS = {0: (76, 175, 80), 1: (205, 220, 57), 2: (255, 193, 7), 3: (255, 112, 67), 4: (198, 40, 40)}
SETTLEMENT_BANDS = [(1.0, (76, 175, 80)), (3.0, (205, 220, 57)), (6.0, (255, 152, 0)), (float("inf"), (198, 40, 40))]


def band_color(settlement_mm: float):
    for lim, col in SETTLEMENT_BANDS:
        if settlement_mm < lim:
            return col
    return SETTLEMENT_BANDS[-1][1]


def mat(name, color, opacity=1.0):
    return vkt.Material(name, color=color, opacity=opacity, roughness=0.9, metalness=0.0)


def box(x0, x1, y0, y1, z0, z1, material, identifier=None):
    """Closed box from 12 triangles with explicit coordinates (no orientation ambiguity)."""
    P = lambda x, y, z: vkt.Point(x, y, z)
    c = [P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0),
         P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, cc, d in quads:
        tris += [vkt.Triangle(c[a], c[b], c[cc]), vkt.Triangle(c[a], c[cc], c[d])]
    return vkt.TriangleAssembly(tris, material=material, skip_duplicate_vertices_check=True, identifier=identifier)


def excavation_level(phase_name: str):
    """'Excavation to -7.5 mOD' -> -7.5 (None if the name carries no level)."""
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*m?OD", phase_name or "", re.I)
    return float(m.group(1)) if m else None


def pit_extent(plates):
    xs = [v for p in plates for v in p["bbox"][0:2]]
    ys = [v for p in plates for v in p["bbox"][2:4]]
    return (min(xs), max(xs), min(ys), max(ys)) if plates else None


def build_scene(data: dict, phase_id: str, scale: float, category: int, settlement_label: str):
    """Return (geometry list, labels). data = stored worker output + 'building' spec."""
    b = data["building"]
    pts = {p["id"]: p for p in data["points"]}
    disp = data["disp"][phase_id]
    phase_name = next(p["name"] for p in data["phases"] if p["id"] == phase_id)
    level = excavation_level(phase_name)
    geom, labels = [], []

    ext = pit_extent(data["plates"])
    xs0 = [b["x0"], b["x1"]] + ([ext[0], ext[1]] if ext else [])
    ys0 = [b["y0"], b["y1"]] + ([ext[2], ext[3]] if ext else [])
    pad = 18.0
    gx0, gx1, gy0, gy1 = min(xs0) - pad, max(xs0) + pad, min(ys0) - pad, max(ys0) + pad

    # ground slab (translucent) - the pit is drawn on top of it
    geom.append(box(gx0, gx1, gy0, gy1, -0.3, 0.0, mat("Ground", (205, 190, 160), 0.55), "Ground"))
    if ext:
        if level is not None and level < 0:
            geom.append(box(ext[0], ext[1], ext[2], ext[3], level, 0.0, mat("Excavation", (121, 85, 72), 0.45), "Excavation"))
        wall_mat = mat("Diaphragm wall", (90, 100, 120), 1.0)
        t = 0.35
        for p in data["plates"]:
            x0, x1, y0, y1, z0, z1 = p["bbox"]
            geom.append(box(x0 - t / 2 if x1 - x0 < 1e-6 else x0, x1 + t / 2 if x1 - x0 < 1e-6 else x1,
                            y0 - t / 2 if y1 - y0 < 1e-6 else y0, y1 + t / 2 if y1 - y0 < 1e-6 else y1,
                            z0, z1, wall_mat, p["name"]))
        labels.append(vkt.Label(vkt.Point((ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2, 1.5),
                                f"Excavation {('to %+.1f mOD' % level) if level is not None else '(not started)'}",
                                size_factor=0.7))

    # building box, coloured by the governing damage category
    col = CAT_COLORS[category]
    geom.append(box(b["x0"], b["x1"], b["y0"], b["y1"],
                    b["z0"], b["z0"] + b["height"], mat("Building", col, 0.35), "Building"))
    labels.append(vkt.Label(vkt.Point((b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2, b["z0"] + b["height"] + 1.5),
                            f"Building - damage category {category}", size_factor=0.8))

    # monitoring points (coloured by settlement) and the displaced facade lines (exaggerated)
    for name, f in b["facades"].items():
        line = []
        for pid in f["ids"]:
            p, u = pts[pid], disp[pid]
            sett = -u[2]
            c = vkt.Color(*band_color(sett))
            geom.append(vkt.Sphere(vkt.Point(p["x"], p["y"], p["z"]), 0.45,
                                   material=mat(f"pt-{pid}", c, 1.0), identifier=pid))
            line.append(vkt.Point(p["x"] + u[0] * scale / 1000, p["y"] + u[1] * scale / 1000,
                                  p["z"] + u[2] * scale / 1000))
        geom.append(vkt.Polyline(line, color=vkt.Color(25, 118, 210), identifier=f"displaced-{name}"))
    if settlement_label:
        labels.append(vkt.Label(vkt.Point(b["x0"], b["y0"], b["z0"] - 2.0), settlement_label, size_factor=0.7))
    return geom, labels
