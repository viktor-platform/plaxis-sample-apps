"""PLAXIS 3D - building damage screening, per PLAXIS entity.

The neighbouring building is a PLAXIS entity (raft plate + load) in the 3D model. A VIKTOR PLAXIS worker reads the
displacements of that entity's nodes for every construction stage. The app shows them in a table and a plan map, draws
pit + building in 3D, and estimates an indicative damage category (Burland / Boscardin & Cording).
No dummy data and no typed coordinates: everything comes from the PLAXIS model.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import viktor as vkt

from plaxis3d_app.damage import BUILDING_TYPES, facade_damage
from plaxis3d_app.entities import FACADE_LABELS, derive
from plaxis3d_app.scene import build_scene

ROOT = Path(__file__).parent
WORKER_SCRIPT = ROOT / "worker" / "run_plaxis3d.py"
STORAGE_KEY = "plaxis3d_results.json"
DEFAULT_EXE = r"C:\Program Files\Seequent\PLAXIS 3D 2026\Plaxis3DInput.exe"
DEFAULT_PROJECT = r"C:\path\to\excavation_3d_demo.p3d"  # <- set to your PLAXIS 3D project
MODE_LAUNCH, MODE_ATTACH = "launch", "attach"


# ------------------------------------------------------------------------------ stored results
def load_raw() -> dict:
    try:
        raw = vkt.Storage().get(STORAGE_KEY, scope="session")
    except Exception:
        raise vkt.UserError("No PLAXIS results yet - set the connection, then press 'Fetch building results from "
                            "PLAXIS 3D' (the PLAXIS worker must be online).")
    return json.loads(raw.getvalue())


def build_meta(raw: dict) -> dict:
    have = set().union(*(e["disp"].keys() for e in raw["entities"].values())) if raw["entities"] else set()
    return {"entities": list(raw["entities"]),
            "stages": [[p["id"], p["name"]] for p in raw["phases"] if p["id"] in have]}


def _meta(params) -> dict:
    """Entity/stage lists saved into the params by the buttons (options must not depend on Storage)."""
    try:
        return params.bld.meta or {}
    except Exception:
        return {}


def params_update(params, meta: dict) -> dict:
    """SetParamsResult needs a NESTED dict (not dotted keys)."""
    return {"bld": {"meta": meta, "stamp": (params.bld.stamp or 0) + 1},
            "assess": {"entity": meta["entities"][0],
                       "stage": meta["stages"][-1][0] if meta["stages"] else None}}


def entity_options(params, **kwargs):
    return list(_meta(params).get("entities", []))


def stage_options(params, **kwargs):
    return [vkt.OptionListElement(i, n) for i, n in _meta(params).get("stages", [])]


def facade_options(params, **kwargs):
    return [vkt.OptionListElement(k, v) for k, v in FACADE_LABELS.items()]


def load_data(params) -> dict:
    """Derived data for the selected building entity (points, displacements per stage, facades)."""
    raw = load_raw()
    names = list(raw["entities"])
    entity = params.assess.entity if params.assess.entity in names else names[0]
    return derive(raw, entity, float(params.bld.height or 12))


def pick_stage(params, data):
    avail = [p["id"] for p in data["phases"]]
    return params.assess.stage if params.assess.stage in avail else avail[-1]


def facade_arrays(data, phase_id, key):
    f = data["building"]["facades"][key]
    pts = {p["id"]: p for p in data["points"]}
    d = data["disp"][phase_id]
    ids = f["ids"]
    s = [pts[i][f["axis"]] for i in ids]
    uz = [d[i][2] for i in ids]
    h = [d[i][0 if f["axis"] == "x" else 1] for i in ids]
    return ids, np.array(s), np.array(uz), np.array(h)


def assess_all(params, data, phase_id):
    eg = BUILDING_TYPES.get(params.assess.btype or "masonry", BUILDING_TYPES["masonry"])[1]
    out = {}
    for k in data["building"]["facades"]:
        _, s, uz, h = facade_arrays(data, phase_id, k)
        out[k] = facade_damage(FACADE_LABELS[k], s, uz, h, data["building"]["height"], e_over_g=eg)
    return out


# ------------------------------------------------------------------------------ parametrization
class Parametrization(vkt.Parametrization):
    conn = vkt.Section("1. PLAXIS 3D connection")
    conn.intro = vkt.Text(
        "# PLAXIS 3D - building damage screening\n"
        "Reads the **displacements of the building entity in the PLAXIS 3D model** (a raft plate carrying the building "
        "load) for every construction stage, then estimates a damage category. Needs a **PLAXIS worker** "
        "(VIKTOR Desktop -> Add -> Plaxis) online on a PC with PLAXIS 3D. *Launch* opens the project in a fresh PLAXIS; "
        "*Attach* reads a PLAXIS that is already open (PLAXIS: *Expert -> Configure remote scripting server*). "
        "**Launch only works when no other PLAXIS 3D window is open.**"
    )
    conn.mode = vkt.OptionField(
        "Connection", options=[vkt.OptionListElement(MODE_LAUNCH, "Launch PLAXIS 3D and open project"),
                               vkt.OptionListElement(MODE_ATTACH, "Attach to running PLAXIS 3D")], default=MODE_LAUNCH)
    conn.project_path = vkt.TextField("Project path (.p3d)", default=DEFAULT_PROJECT,
                                      visible=vkt.IsEqual(vkt.Lookup("conn.mode"), MODE_LAUNCH))
    conn.plaxis_exe = vkt.TextField("Plaxis3DInput.exe", default=DEFAULT_EXE,
                                    visible=vkt.IsEqual(vkt.Lookup("conn.mode"), MODE_LAUNCH))
    conn.port = vkt.NumberField("Remote scripting port", default=10020, min=1, max=65535, num_decimals=0,
                                description="Launch: port the new PLAXIS listens on (must be free). "
                                            "Attach: the port set in PLAXIS.")
    conn.password = vkt.TextField("Remote scripting password", visible=vkt.IsEqual(vkt.Lookup("conn.mode"), MODE_ATTACH),
                                  description="Sent to the worker for this job only (leave empty to use the "
                                              "PLAXIS_PASSWORD environment variable of the worker machine).")
    conn.recalculate = vkt.BooleanField("Recalculate all phases first", default=False)

    bld = vkt.Section("2. Building entity (from the PLAXIS model)")
    bld.info = vkt.Text("The building is an **object in the PLAXIS model** (here a plate named *Building_raft*). "
                        "Enter part of its name; every plate whose name contains it is read back with its node "
                        "displacements. Nothing needs to be typed in.")
    bld.entity_filter = vkt.TextField("Entity name contains", default="Building")
    bld.height = vkt.NumberField("Building height", default=12, min=1, suffix="m",
                                 description="Not stored in the plate - used by the damage calculation.")
    bld.fetch = vkt.SetParamsButton("Fetch building results from PLAXIS 3D", method="fetch_live", longpoll=True)
    bld.stamp = vkt.HiddenField("stamp")
    bld.meta = vkt.HiddenField("meta")
    bld.populate = vkt.SetParamsButton("Populate entities & stages from stored results", method="populate")

    assess = vkt.Section("3. Assessment & display")
    assess.entity = vkt.OptionField("Building entity", options=entity_options, autoselect_single_option=True)
    assess.stage = vkt.OptionField("Construction stage", options=stage_options)
    assess.btype = vkt.OptionField("Building type",
                                   options=[vkt.OptionListElement(k, v[0]) for k, v in BUILDING_TYPES.items()],
                                   default="masonry")
    assess.exaggeration = vkt.NumberField("Displacement exaggeration in 3D", default=200, min=1, max=5000, num_decimals=0)
    assess.facade = vkt.OptionField("Facade for the profile plot", options=facade_options, default="F")
    assess.csv = vkt.DownloadButton("Download entity displacements (CSV)", method="download_csv")


# ------------------------------------------------------------------------------ controller
class Controller(vkt.Controller):
    parametrization = Parametrization

    @vkt.GeometryAndDataView("Building & pit (3D)", duration_guess=60, x_axis_to_right=True)
    def view_scene(self, params, **kwargs):
        data = load_data(params)
        ph = pick_stage(params, data)
        res = assess_all(params, data, ph)
        worst = max(res.values(), key=lambda r: r.eps_governing)
        geom, labels = build_scene(data, ph, float(params.assess.exaggeration or 200), worst.category,
                                   f"max settlement {max(r.max_settlement for r in res.values()):.1f} mm")
        name = next(p["name"] for p in data["phases"] if p["id"] == ph)
        status = [vkt.DataStatus.SUCCESS, vkt.DataStatus.SUCCESS, vkt.DataStatus.WARNING,
                  vkt.DataStatus.WARNING, vkt.DataStatus.ERROR][worst.category]
        dg = vkt.DataGroup(
            vkt.DataItem("Building entity", data["building"]["entity"]),
            vkt.DataItem("Stage", name),
            vkt.DataItem("Max settlement (front)", res["F"].max_settlement, suffix="mm", number_of_decimals=1),
            vkt.DataItem("Worst facade", worst.name),
            vkt.DataItem("Damage category", worst.category, status=status, status_message=worst.description),
            vkt.DataItem("Governing strain", worst.eps_governing, suffix="%", number_of_decimals=3),
        )
        return vkt.GeometryAndDataResult(geom, dg, labels=labels)

    @vkt.DataView("Damage assessment", duration_guess=60)
    def view_damage(self, params, **kwargs):
        data = load_data(params)
        ph = pick_stage(params, data)
        name = next(p["name"] for p in data["phases"] if p["id"] == ph)
        res = assess_all(params, data, ph)
        stat = {0: vkt.DataStatus.SUCCESS, 1: vkt.DataStatus.SUCCESS, 2: vkt.DataStatus.WARNING,
                3: vkt.DataStatus.WARNING, 4: vkt.DataStatus.ERROR}
        items = []
        for k, r in res.items():
            sub = vkt.DataGroup(
                vkt.DataItem("Length", r.length, suffix="m", number_of_decimals=1),
                vkt.DataItem("Max settlement", r.max_settlement, suffix="mm", number_of_decimals=1),
                vkt.DataItem("Max horizontal displacement", r.max_horizontal, suffix="mm", number_of_decimals=1),
                vkt.DataItem("Tilt", r.tilt, suffix="%", number_of_decimals=3),
                vkt.DataItem("Deflection ratio (" + r.mode + ")", abs(r.deflection_ratio), suffix="%", number_of_decimals=4),
                vkt.DataItem("Average horizontal strain", r.eps_h, suffix="%", number_of_decimals=4),
                vkt.DataItem("Strain - bending", r.eps_bending, suffix="%", number_of_decimals=4),
                vkt.DataItem("Strain - shear", r.eps_shear, suffix="%", number_of_decimals=4),
                vkt.DataItem("Governing tensile strain", r.eps_governing, suffix="%", number_of_decimals=4,
                             explanation_label=f"Governed by {r.governing}"),
                vkt.DataItem("Damage category", r.category, status=stat[r.category], status_message=r.description),
            )
            items.append(vkt.DataItem(r.name, f"Category {r.category} - {r.description}", subgroup=sub,
                                      status=stat[r.category]))
        head = vkt.DataGroup(vkt.DataItem("Building entity", data["building"]["entity"]),
                             vkt.DataItem("Stage", name),
                             vkt.DataItem("Indicative screening only",
                                          "Burland / Boscardin & Cording, each facade as one beam"),
                             *items)
        return vkt.DataResult(head)

    @vkt.TableView("Entity node displacements", duration_guess=60)
    def view_table(self, params, **kwargs):
        data = load_data(params)
        ph = pick_stage(params, data)
        d = data["disp"][ph]
        rows, heads = [], []
        for p in data["points"]:
            ux, uy, uz = d[p["id"]]
            rows.append([round(p["x"], 2), round(p["y"], 2), round(p["z"], 2), round(ux, 2), round(uy, 2), round(uz, 2),
                         round(math.sqrt(ux ** 2 + uy ** 2 + uz ** 2), 2)])
            heads.append(p["id"])
        return vkt.TableResult(rows, row_headers=heads, column_headers=[
            "X [m]", "Y [m]", "Z [m]", "Ux [mm]", "Uy [mm]", "Uz [mm]", "|U| [mm]"])

    @vkt.PlotlyView("Raft settlement map (plan)", duration_guess=60)
    def view_map(self, params, **kwargs):
        data = load_data(params)
        ph = pick_stage(params, data)
        b = data["building"]
        d = data["disp"][ph]
        x = [p["x"] for p in data["points"]]
        y = [p["y"] for p in data["points"]]
        sett = [-d[p["id"]][2] for p in data["points"]]
        fig = go.Figure(go.Scatter(x=x, y=y, mode="markers",
                                   marker=dict(size=14, color=sett, colorscale="RdYlGn_r", showscale=True,
                                               colorbar=dict(title="Settlement [mm]")),
                                   text=[f"{s:.1f} mm" for s in sett], hovertemplate="x=%{x:.1f} y=%{y:.1f}<br>%{text}<extra></extra>"))
        for p in data["plates"]:                                  # retaining walls in plan
            x0, x1, y0, y1 = p["bbox"][:4]
            fig.add_shape(type="line", x0=x0, x1=x1, y0=y0, y1=y1, line=dict(color="#455a64", width=5))
        name = next(p["name"] for p in data["phases"] if p["id"] == ph)
        fig.update_layout(template="plotly_white", height=620, title=f"{b['entity']} - settlement, {name}",
                          xaxis=dict(title="X [m]", scaleanchor="y"), yaxis=dict(title="Y [m]"))
        return vkt.PlotlyResult(fig.to_json())

    @vkt.PlotlyView("Settlement profile along facade", duration_guess=60)
    def view_profile(self, params, **kwargs):
        data = load_data(params)
        key = params.assess.facade if params.assess.facade in data["building"]["facades"] else "F"
        fig = go.Figure()
        for p in data["phases"]:
            _, s, uz, _ = facade_arrays(data, p["id"], key)
            o = np.argsort(s)
            fig.add_trace(go.Scatter(x=s[o], y=-uz[o], mode="lines+markers", name=p["name"], line=dict(width=2)))
        fig.update_yaxes(autorange="reversed", title="Settlement [mm] (down)")
        fig.update_xaxes(title="Position along facade [m]")
        fig.update_layout(template="plotly_white", height=560, title=f"{FACADE_LABELS[key]} facade - settlement by stage",
                          legend=dict(orientation="h", y=-0.2))
        return vkt.PlotlyResult(fig.to_json())

    # ------------------------------------------------------------------ actions
    def fetch_live(self, params, **kwargs):
        c, b = params.conn, params.bld
        frag = [t.strip() for t in (b.entity_filter or "Building").split(",") if t.strip()]
        cfg = dict(mode=c.mode, project_path=c.project_path or "", plaxis_exe=c.plaxis_exe or DEFAULT_EXE,
                   input_port=int(c.port or 10020), password=c.password or "", recalculate=bool(c.recalculate),
                   entities=frag)
        if cfg["mode"] == MODE_LAUNCH and not cfg["project_path"]:
            raise vkt.UserError("Enter the project path (.p3d) to open.")
        if cfg["mode"] == MODE_ATTACH and not cfg["password"]:
            raise vkt.UserError("Enter the remote scripting password (PLAXIS: Expert > Configure remote scripting server).")
        analysis = vkt.plaxis.PlaxisAnalysis(script=vkt.File.from_path(WORKER_SCRIPT),
                                             files=[("input.json", vkt.File.from_data(json.dumps(cfg)))],
                                             output_filenames=["output.json"])
        analysis.execute(timeout=1200)
        out = analysis.get_output_file("output.json").getvalue()
        meta = build_meta(json.loads(out))
        if not meta["entities"]:
            raise vkt.UserError("PLAXIS returned no entity matching the name filter. Check 'Entity name contains'.")
        vkt.Storage().set(STORAGE_KEY, data=vkt.File.from_data(out), scope="session")
        return vkt.SetParamsResult(params_update(params, meta))

    def populate(self, params, **kwargs):
        """Fill the entity / stage dropdowns from the results already stored by 'fetch_live'."""
        meta = build_meta(load_raw())
        if not meta["entities"]:
            raise vkt.UserError("No building entity found in the stored PLAXIS results.")
        return vkt.SetParamsResult(params_update(params, meta))

    def download_csv(self, params, **kwargs):
        data = load_data(params)
        buf = io.StringIO()
        buf.write("stage_id,stage,node,X,Y,Z,Ux_mm,Uy_mm,Uz_mm\n")
        names = {p["id"]: p["name"] for p in data["phases"]}
        for ph, d in data["disp"].items():
            for p in data["points"]:
                ux, uy, uz = d[p["id"]]
                buf.write(f'{ph},"{names[ph]}",{p["id"]},{p["x"]},{p["y"]},{p["z"]},{ux},{uy},{uz}\n')
        return vkt.DownloadResult(buf.getvalue(), "entity_displacements.csv")
