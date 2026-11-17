"""Plain data structures that mirror what we pull out of Plaxis 2D (Output)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

import numpy as np


@dataclass(frozen=True)
class Stage:
    """A Plaxis calculation phase (what the Phases explorer shows)."""
    id: str                      # Plaxis phase identifier, e.g. "Phase_5"
    name: str                    # e.g. "Install G0 slab"
    note: str = ""               # engineer's annotation (right-hand red text in the report)
    excavation_level: Optional[float] = None   # mOD, None if no excavation yet
    slab_installed: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} [{self.id}]"


@dataclass(frozen=True)
class Plate:
    """A Plaxis plate element (secant wall etc.)."""
    name: str
    top: float                   # mOD
    bottom: float                # mOD
    description: str = ""


@dataclass
class PlateResult:
    """Results along one plate for one stage (node values, top -> bottom)."""
    plate: str
    stage_id: str
    y: np.ndarray                # elevation [mOD]
    ux: np.ndarray               # horizontal displacement [mm]
    m: np.ndarray                # bending moment [kNm/m]
    q: np.ndarray                # shear force [kN/m]

    @property
    def summary(self) -> dict:
        return {
            "ux_max": float(self.ux.max()), "ux_min": float(self.ux.min()),
            "m_max": float(self.m.max()), "m_min": float(self.m.min()),
            "q_max": float(self.q.max()), "q_min": float(self.q.min()),
        }


@dataclass
class ProjectInfo:
    client: str = ""
    project: str = ""
    title: str = ""
    job_no: str = ""
    extra: dict = field(default_factory=dict)


class PlaxisProvider(Protocol):
    """Anything that can serve Plaxis-like results. The app only talks to this."""
    def get_project_info(self) -> ProjectInfo: ...
    def get_stages(self) -> list[Stage]: ...
    def get_plates(self) -> list[Plate]: ...
    def get_plate_results(self, plate_name: str, stage_id: str) -> PlateResult: ...
