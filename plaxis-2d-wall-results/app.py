"""PLAXIS wall results explorer - plot bending moment, shear force and displacement of a retaining wall
for every construction stage, read live from PLAXIS 2D through a VIKTOR PLAXIS worker (no dummy data)."""
from __future__ import annotations

import io
import logging
import json
from pathlib import Path

import viktor as vkt

from plaxis_demo.json_provider import JsonPlaxisProvider
from plaxis_demo.plots import QUANTITIES, combined_figure, comparison_figure

ROOT = Path(__file__).parent
WORKER_SCRIPT = ROOT / "worker" / "run_plaxis.py"
STORAGE_KEY = "plaxis_live_results.json"
DEFAULT_EXE = r"C:\Program Files\Seequent\PLAXIS 2D 2026\Plaxis2DXInput.exe"
DEFAULT_PROJECT = r"C:\path\to\olympia_demo.p2dx"  # <- set to your PLAXIS 2D project

MODE_LAUNCH, MODE_ATTACH = "launch", "attach"


# --------------------------------------------------------------------------------------- data access
def get_provider(params) -> JsonPlaxisProvider:
    """Results always come from the PLAXIS worker (stored per editor session by 'fetch_live')."""
    try:
        raw = vkt.Storage().get(STORAGE_KEY, scope="session")
    except Exception:
        raise vkt.UserError("No PLAXIS results yet - set the connection above and press "
                            "'Fetch results from PLAXIS' (needs the PLAXIS worker online in VIKTOR Desktop).")
    return JsonPlaxisProvider(data=json.loads(raw.getvalue()))


def _meta(params) -> dict:
    """Wall/stage lists saved into the params by 'fetch_live' (options must not depend on Storage)."""
    try:
        m = params.live.meta or {}
    except Exception as e:
        logging.warning("meta read failed: %r", e)
        m = {}
    return m


def _build_meta(prov) -> dict:
    plates = [p.name for p in prov.get_plates()]
    return {"plates": plates,
            "stages": {n: [[s.id, s.label] for s in prov.stages_with_results(n)] for n in plates}}


def _params_update(params, meta: dict) -> dict:
    """SetParamsResult needs a NESTED dict (not dotted keys)."""
    first = meta["plates"][0]
    stages = meta["stages"].get(first, [])
    return {
        "live": {"meta": meta, "stamp": (params.live.stamp or 0) + 1},
        "sel": {"plate": first,
                "stage": stages[-1][0] if stages else None,
                "compare": [i for i, _ in stages[-3:]]},
    }


def _plate_options(params, **kwargs):
    return list(_meta(params).get("plates", []))


def _selected_plate(params, prov):
    names = [p.name for p in prov.get_plates()]
    if not names:
        raise vkt.UserError("No wall (vertical plate) found in the results.")
    return next(p for p in prov.get_plates() if p.name == (params.sel.plate if params.sel.plate in names else names[0]))


def _stage_options(params, **kwargs):
    meta = _meta(params)
    plates = meta.get("plates", [])
    if not plates:
        return []
    sel = params.sel.plate if params.sel.plate in plates else plates[0]
    return [vkt.OptionListElement(i, l) for i, l in meta.get("stages", {}).get(sel, [])]


def _pick(params, prov, plate):
    """Return (stage list with results, chosen stage)."""
    stages = prov.stages_with_results(plate.name)
    if not stages:
        raise vkt.UserError("No results available for this wall.")
    by_id = {s.id: s for s in stages}
    return stages, by_id.get(params.sel.stage, stages[-1])


# --------------------------------------------------------------------------------------- parametrization
class Parametrization(vkt.Parametrization):
    live = vkt.Section("PLAXIS connection")
    live.intro = vkt.Text(
        "# PLAXIS wall results\n"
        "Plot **bending moment, shear force and horizontal displacement** of a retaining wall for every "
        "construction stage and compare stages. Results are read **live from PLAXIS 2D** by a VIKTOR worker.\n\n"
        "Needs a **PLAXIS worker** (VIKTOR Desktop -> Add -> Plaxis) online on a PC with PLAXIS 2D. "
        "*Launch* starts a fresh PLAXIS and opens the project; *Attach* reads the PLAXIS that is already open "
        "(enable it in PLAXIS: *Expert -> Configure remote scripting server*, then enter the port and password below)."
    )
    live.mode = vkt.OptionField(
        "Connection", options=[vkt.OptionListElement(MODE_LAUNCH, "Launch PLAXIS and open project"),
                               vkt.OptionListElement(MODE_ATTACH, "Attach to running PLAXIS")],
        default=MODE_LAUNCH,
    )
    live.project_path = vkt.TextField("Project path (.p2dx)", default=DEFAULT_PROJECT,
                                      description="Path as seen by the worker machine",
                                      visible=vkt.IsEqual(vkt.Lookup("live.mode"), MODE_LAUNCH))
    live.plaxis_exe = vkt.TextField("Plaxis2DXInput.exe", default=DEFAULT_EXE,
                                    visible=vkt.IsEqual(vkt.Lookup("live.mode"), MODE_LAUNCH))
    live.port = vkt.NumberField("Remote scripting port", default=10000, min=1, max=65535, num_decimals=0,
                                visible=vkt.IsEqual(vkt.Lookup("live.mode"), MODE_ATTACH),
                                description="PLAXIS: Expert > Configure remote scripting server")
    live.password = vkt.TextField("Remote scripting password",
                                  visible=vkt.IsEqual(vkt.Lookup("live.mode"), MODE_ATTACH),
                                  description="Sent to the worker for this job only. Leave empty to use the "
                                              "PLAXIS_PASSWORD environment variable of the worker machine.")
    live.recalculate = vkt.BooleanField("Recalculate all phases first", default=False)
    live.fetch = vkt.SetParamsButton("Fetch results from PLAXIS", method="fetch_live", longpoll=True)
    live.stamp = vkt.HiddenField("stamp")
    live.meta = vkt.HiddenField("meta")

    sel = vkt.Section("What to plot")
    sel.populate = vkt.SetParamsButton("Populate walls & stages from results", method="populate")
    sel.plate = vkt.OptionField("Wall", options=_plate_options, autoselect_single_option=True)
    sel.stage = vkt.OptionField("Stage (condition)", options=_stage_options)
    sel.compare = vkt.MultiSelectField("Stages to compare", options=_stage_options,
                                    description="Leave empty to compare the last three stages")
    sel.quantities = vkt.MultiSelectField(
        "Quantities to compare",
        options=[vkt.OptionListElement(k, v[0]) for k, v in QUANTITIES.items()], default=["ux", "m", "q"])
    sel.envelope = vkt.BooleanField("Show max/min envelope", default=True)
    sel.csv = vkt.DownloadButton("Download CSV (all stages)", method="download_csv")


# --------------------------------------------------------------------------------------- controller
class Controller(vkt.Controller):
    parametrization = Parametrization

    # -- views
    @vkt.PlotlyView("Wall at one stage", duration_guess=60)
    def view_stage(self, params, **kwargs):
        prov = get_provider(params)
        plate = _selected_plate(params, prov)
        _, stage = _pick(params, prov, plate)
        return vkt.PlotlyResult(combined_figure(prov.get_plate_results(plate.name, stage.id), plate, stage,
                                                title=prov.get_project_info().title).to_json())

    @vkt.PlotlyView("Compare stages", duration_guess=60)
    def view_compare(self, params, **kwargs):
        prov = get_provider(params)
        plate = _selected_plate(params, prov)
        stages, _ = _pick(params, prov, plate)
        chosen = [s for s in stages if s.id in (params.sel.compare or [])] or stages[-3:]
        results = [(s, prov.get_plate_results(plate.name, s.id)) for s in chosen]
        return vkt.PlotlyResult(comparison_figure(results, plate, bool(params.sel.envelope),
                                                  tuple(params.sel.quantities or ["m"])).to_json())

    @vkt.TableView("Summary per stage", duration_guess=60)
    def view_summary(self, params, **kwargs):
        prov = get_provider(params)
        plate = _selected_plate(params, prov)
        stages, _ = _pick(params, prov, plate)
        rows, heads = [], []
        for s in stages:
            r = prov.get_plate_results(plate.name, s.id).summary
            heads.append(s.label)
            rows.append([round(r["ux_max"], 2), round(r["ux_min"], 2), round(r["m_max"], 1), round(r["m_min"], 1),
                         round(r["q_max"], 1), round(r["q_min"], 1)])
        return vkt.TableResult(rows, row_headers=heads, column_headers=[
            "uₓ max [mm]", "uₓ min [mm]", "M max [kNm/m]", "M min [kNm/m]", "Q max [kN/m]", "Q min [kN/m]"])

    # -- actions
    def fetch_live(self, params, **kwargs):
        """Run the PLAXIS worker and keep the result for this editor session."""
        cfg = dict(mode=params.live.mode, project_path=params.live.project_path or "",
                   plaxis_exe=params.live.plaxis_exe or DEFAULT_EXE, recalculate=bool(params.live.recalculate),
                   input_port=int(params.live.port or 10000), password=params.live.password or "")
        if cfg["mode"] == MODE_LAUNCH and not cfg["project_path"]:
            raise vkt.UserError("Enter the project path (.p2dx) to open.")
        if cfg["mode"] == MODE_ATTACH and not cfg["password"]:
            raise vkt.UserError("Enter the remote scripting password (PLAXIS: Expert > Configure remote "
                                "scripting server) and make sure the server is enabled.")
        analysis = vkt.plaxis.PlaxisAnalysis(
            script=vkt.File.from_path(WORKER_SCRIPT),
            files=[("input.json", vkt.File.from_data(json.dumps(cfg)))],
            output_filenames=["output.json"],
        )
        analysis.execute(timeout=900)
        out = analysis.get_output_file("output.json")
        raw = out.getvalue()
        meta = _build_meta(JsonPlaxisProvider(data=json.loads(raw)))
        logging.info("PLAXIS walls: %s; stages: %s", meta["plates"],
                     {n: len(st) for n, st in meta["stages"].items()})
        if not meta["plates"]:
            raise vkt.UserError("PLAXIS returned no vertical Plate walls. Check the Output model and wall geometry.")
        vkt.Storage().set(STORAGE_KEY, data=vkt.File.from_data(raw), scope="session")
        return vkt.SetParamsResult(_params_update(params, meta))

    def populate(self, params, **kwargs):
        """Fill the Wall / Stage dropdowns from the results already stored by 'fetch_live'."""
        meta = _build_meta(get_provider(params))
        if not meta["plates"]:
            raise vkt.UserError("No walls found in the stored PLAXIS results.")
        return vkt.SetParamsResult(_params_update(params, meta))

    def download_csv(self, params, **kwargs):
        prov = get_provider(params)
        plate = _selected_plate(params, prov)
        buf = io.StringIO()
        buf.write("stage_id,stage,y_mOD,ux_mm,M_kNm_per_m,Q_kN_per_m\n")
        for s in prov.stages_with_results(plate.name):
            r = prov.get_plate_results(plate.name, s.id)
            for y, ux, m, q in zip(r.y, r.ux, r.m, r.q):
                buf.write(f'{s.id},"{s.name}",{y:.3f},{ux:.4f},{m:.3f},{q:.3f}\n')
        return vkt.DownloadResult(buf.getvalue(), "wall_results.csv")
