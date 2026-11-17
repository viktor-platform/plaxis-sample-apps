"""Serve results previously exported from PLAXIS (no PLAXIS needed). See worker/run_plaxis.py."""
from __future__ import annotations

import json

import numpy as np

from .models import Plate, PlateResult, ProjectInfo, Stage


class JsonPlaxisProvider:
    def __init__(self, path: str | None = None, data: dict | None = None):
        if data is None:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        self.d = data

    def get_project_info(self) -> ProjectInfo:
        return ProjectInfo(**self.d["project"])

    def get_stages(self) -> list[Stage]:
        return [Stage(**s) for s in self.d["stages"]]

    def stages_with_results(self, plate_name: str) -> list[Stage]:
        have = self.d["results"].get(plate_name, {})
        return [s for s in self.get_stages() if s.id in have]

    def get_plates(self) -> list[Plate]:
        return [Plate(**p) for p in self.d["plates"]]

    def get_plate_results(self, plate_name: str, stage_id: str) -> PlateResult:
        r = self.d["results"][plate_name][stage_id]
        return PlateResult(plate_name, stage_id, *(np.array(r[k]) for k in ("y", "ux", "m", "q")))
