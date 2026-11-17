"""Turn the nodes/displacements of a PLAXIS plate entity (the building raft) into facades for the damage check."""
from __future__ import annotations

import numpy as np

TOL = 1e-3
FACADE_LABELS = {"F": "Front (pit side)", "B": "Back", "W": "Side 1", "E": "Side 2"}


def pit_centre(plates, exclude: str):
    """Centre of the retaining walls (vertical plates other than the building entity)."""
    walls = [p for p in plates if p["name"] != exclude and (p["bbox"][5] - p["bbox"][4]) >= 1.0]
    if not walls:
        return None
    xs = [v for p in walls for v in p["bbox"][0:2]]
    ys = [v for p in walls for v in p["bbox"][2:4]]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def derive(raw: dict, entity: str, height: float) -> dict:
    """Build the view data (points, per-phase displacements, facades) for one entity."""
    ent = raw["entities"][entity]
    N = np.array(ent["nodes"], float)
    x0, x1 = float(N[:, 0].min()), float(N[:, 0].max())
    y0, y1 = float(N[:, 1].min()), float(N[:, 1].max())
    z0 = float(N[:, 2].mean())
    centre = pit_centre(raw["plates"], entity) or ((x0 + x1) / 2, y0 - 1)

    edges = {"ymin": ("x", y0, 1), "ymax": ("x", y1, 1), "xmin": ("y", x0, 0), "xmax": ("y", x1, 0)}
    mid = {"ymin": ((x0 + x1) / 2, y0), "ymax": ((x0 + x1) / 2, y1), "xmin": (x0, (y0 + y1) / 2), "xmax": (x1, (y0 + y1) / 2)}
    dist = {k: np.hypot(mid[k][0] - centre[0], mid[k][1] - centre[1]) for k in edges}
    front = min(dist, key=dist.get)
    opposite = {"ymin": "ymax", "ymax": "ymin", "xmin": "xmax", "xmax": "xmin"}[front]
    sides = [k for k in edges if k not in (front, opposite)]
    sides.sort(key=lambda k: mid[k])
    roles = {"F": front, "B": opposite, "W": sides[0], "E": sides[1]}

    ids = {f"N{i:03d}": i for i in range(len(N))}
    pts = [{"id": pid, "x": float(N[i, 0]), "y": float(N[i, 1]), "z": float(N[i, 2])} for pid, i in ids.items()]
    facades, used = {}, set()
    for key, edge in roles.items():
        axis, coord, col = edges[edge]
        sel = [i for i in range(len(N)) if abs(N[i, col] - coord) < TOL]
        sel.sort(key=lambda i: N[i, 0 if axis == "x" else 1])
        facades[key] = {"ids": [f"N{i:03d}" for i in sel], "axis": axis}
        used.update(sel)

    disp = {}
    for ph, u in ent["disp"].items():
        disp[ph] = {f"N{i:03d}": [u["ux"][i], u["uy"][i], u["uz"][i]] for i in range(len(N))}
    phases = [p for p in raw["phases"] if p["id"] in disp]
    # The first stage(s) can be the building's own load: PLAXIS then resets displacements, so the next stage
    # is much smaller. Drop such a stage - it is not excavation-induced movement and would give a false damage class.
    peak = {p["id"]: max(abs(v[2]) for v in disp[p["id"]].values()) for p in phases}
    while len(phases) > 2 and peak[phases[1]["id"]] < 0.3 * peak[phases[0]["id"]]:
        disp.pop(phases[0]["id"])
        phases = phases[1:]
    plates = [p for p in raw["plates"] if p["name"] != entity and (p["bbox"][5] - p["bbox"][4]) >= 1.0]
    return dict(points=pts, disp=disp, phases=phases, plates=plates,
                building=dict(entity=entity, x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, height=float(height), facades=facades,
                              front_edge=front))
