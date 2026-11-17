"""Live PLAXIS 2D provider (reads the *Output* remote scripting server).

Verified against PLAXIS 2D 2026 (HTTPS server, plxscripting 1.0.10 from the PLAXIS Python
distribution - the PyPI plxscripting 1.0.4 cannot talk to 2026 servers).

Usage (inside PLAXIS' python):  PlaxisRemoteProvider(password, output_port=10001)
Output must be running: call g_i.view(last_phase) from the Input server first.
"""
from __future__ import annotations

import re

import numpy as np

from .models import Plate, PlateResult, ProjectInfo, Stage


class PlaxisRemoteProvider:
    def __init__(self, password: str, output_port: int = 10001, host: str = "localhost",
                 plate_names: dict | None = None, stage_meta: dict | None = None):
        from plxscripting.easy import new_server
        self.s_o, self.g_o = new_server(host, output_port, password=password, timeout=60)
        self.plate_names = plate_names or {}      # {"Plate_1": "Secant wall"}
        self.stage_meta = stage_meta or {}        # {"Phase_3": dict(note=..., excavation_level=..., slab_installed=...)}
        self._plates = {}                         # friendly name -> Plaxis plate object

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _split(identification: str):
        m = re.match(r"(.*?)\s*\[(.+)\]$", identification)
        return (m.group(1), m.group(2)) if m else (identification, identification)

    def _phase(self, stage_id):
        return next(p for p in self.g_o.Phases[:] if p.Name.value == stage_id)

    def _nodes(self, plate, phase, rtype):
        return np.atleast_1d(np.array(self.g_o.getresults(plate, phase, rtype, "node"), dtype=float))

    # ---- PlaxisProvider API ---------------------------------------------------
    def get_project_info(self) -> ProjectInfo:
        return ProjectInfo(title="PLAXIS 2D live model")

    def get_stages(self) -> list[Stage]:
        out = []
        for p in self.g_o.Phases[:]:
            name, sid = self._split(p.Identification.value)
            out.append(Stage(id=p.Name.value, name=name, **self.stage_meta.get(p.Name.value, {})))
        return out

    def get_plates(self) -> list[Plate]:
        RT, last, out = self.g_o.ResultTypes.Plate, self.g_o.Phases[-1], []
        for pl in self.g_o.Plates[:]:
            x = self._nodes(pl, last, RT.X)
            if np.ptp(x) > 1e-6:                  # only vertical plates (walls); skip slabs
                continue
            y = self._nodes(pl, last, RT.Y)
            name = self.plate_names.get(pl.Name.value, pl.Name.value)
            self._plates[name] = pl
            out.append(Plate(name, float(y.max()), float(y.min()), f"Plaxis object {pl.Name.value}"))
        return out

    def get_plate_results(self, plate_name: str, stage_id: str) -> PlateResult:
        if plate_name not in self._plates:
            self.get_plates()
        pl, ph, RT = self._plates[plate_name], self._phase(stage_id), self.g_o.ResultTypes.Plate
        try:
            self._nodes(pl, ph, RT.Y)
        except ValueError:                        # plate not active in this phase -> no results
            y = np.unique(np.round(self._nodes(pl, self.g_o.Phases[-1], RT.Y), 4))[::-1]
            z = np.zeros_like(y)
            return PlateResult(plate_name, stage_id, y, z, z.copy(), z.copy())
        y, ux = self._nodes(pl, ph, RT.Y), self._nodes(pl, ph, RT.Ux) * 1000.0   # m -> mm
        m, q = self._nodes(pl, ph, RT.M2D), self._nodes(pl, ph, RT.Q2D)
        # Plaxis returns node values per element -> average duplicates at element joints
        key = np.round(y, 4)
        uniq = np.unique(key)[::-1]               # top -> bottom
        avg = lambda a: np.array([a[key == k].mean() for k in uniq])
        return PlateResult(plate_name, stage_id, uniq, avg(ux), avg(m), avg(q))
