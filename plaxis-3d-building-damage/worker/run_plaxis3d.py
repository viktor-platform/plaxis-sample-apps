"""Worker script - runs ON the machine where PLAXIS 3D is installed (sent by vkt.plaxis.PlaxisAnalysis).

Reads input.json, writes output.json with, for every PLAXIS plate whose name matches the requested entity filter
(e.g. "Building"), the node coordinates and the displacements [mm] per calculated phase - plus the extent of every
plate in the model so the app can draw the pit. Nothing is typed by the user: the building is a PLAXIS entity.

input.json
    mode          "launch" | "attach"
    project_path  .p3d to open (launch mode)
    plaxis_exe    path to Plaxis3DInput.exe (launch mode)
    input_port    remote scripting port (launch: a FREE port, attach: the port set in PLAXIS)
    password      attach mode: remote scripting password (falls back to env PLAXIS_PASSWORD)
    recalculate   bool
    entities      list of name fragments, e.g. ["Building"] - plates whose name contains one are read

Needs plxscripting >= 1.0.10 (PLAXIS 2026 uses HTTPS) and the PLAXIS disclaimer accepted once on the machine.
"""
import json
import os
import re
import secrets
import socket
import subprocess
import time
from pathlib import Path

import numpy as np
from plxscripting.easy import new_server

HOST = "localhost"
WORKDIR = Path.cwd()


def log(*a):
    print("[run_plaxis3d]", *a, flush=True)


def port_open(port):
    try:
        with socket.create_connection((HOST, port), timeout=2):
            return True
    except OSError:
        return False


def connect(port, password, timeout_s=240):
    """Wait until something listens on the port, then connect (new_server() itself does not check)."""
    t0, last = time.time(), None
    while time.time() - t0 < timeout_s:
        if port_open(port):
            try:
                s, g = new_server(HOST, port, password=password, timeout=15)
                s.connection  # noqa - touch the connection
                return s, g
            except Exception as e:
                last = e
        time.sleep(3)
    raise RuntimeError(f"Could not connect to PLAXIS on port {port} ({last}). In launch mode PLAXIS 3D may refuse to "
                       "start a second instance: close any open PLAXIS 3D window or use 'Attach'.")


def resolve_project(path: str) -> str:
    """PLAXIS 3D projects are '.p3d' (+ '.p3dat' folder). Be forgiving about '.p3dx' / missing extension, and fail
    clearly instead of letting PLAXIS silently start an empty project."""
    p = Path(path)
    for cand in (p, p.with_suffix(".p3d"), Path(str(p) + ".p3d"), Path(str(p) + ".p3dx.p3d"),
                 Path(str(p.with_suffix("")) + ".p3d")):
        if cand.is_file() and cand.suffix.lower() in (".p3d", ".p3dx"):
            return str(cand)
    raise FileNotFoundError(f"PLAXIS 3D project not found: {path} (expected a .p3d file with its .p3dat folder)")


def split_ident(ident):
    m = re.match(r"(.*?)\s*\[(.+)\]$", ident)
    return (m.group(1), m.group(2)) if m else (ident, ident)


def main():
    cfg = json.loads((WORKDIR / "input.json").read_text(encoding="utf-8"))
    launched = cfg.get("mode", "launch") == "launch"
    port_i = int(cfg.get("input_port", 10000))
    proc = None
    try:
        if launched:
            if port_open(port_i):
                raise RuntimeError(f"Port {port_i} is already in use - choose a free port for the new PLAXIS.")
            password = secrets.token_urlsafe(16)
            log("launching", cfg["plaxis_exe"])
            proc = subprocess.Popen([cfg["plaxis_exe"], f"--AppServerPassword={password}",
                                     f"--AppServerPort={port_i}"])
        else:
            password = cfg.get("password") or os.environ.get("PLAXIS_PASSWORD")
            if not password:
                raise RuntimeError("No PLAXIS remote scripting password given.")
        s_i, g_i = connect(port_i, password)
        log("connected to Input")
        if cfg.get("project_path"):
            path = resolve_project(cfg["project_path"])
            log("opening", path)
            s_i.open(path)
        g_i.gotostages()
        phases = list(g_i.Phases[:])
        if cfg.get("recalculate"):
            for p in phases:
                p.ShouldCalculate = True
        if any(p.ShouldCalculate.value for p in phases):
            log("calculate()")
            g_i.calculate()
        failed = [p.Identification.value for p in phases if p.CalculationResult.value != 1]
        if failed:
            raise RuntimeError(f"PLAXIS phases not calculated successfully: {failed}")
        title = str(g_i.Project.Title.value)

        out_port = g_i.view(phases[-1])
        s_o, g_o = connect(int(out_port), password)
        log("connected to Output")
        ph_o = list(g_o.Phases[:])
        RS, RP = g_o.ResultTypes.Soil, g_o.ResultTypes.Plate

        # --- every plate: name + extent (so the app can draw walls/raft); selected plates: nodes + displacements
        wanted = [w.lower() for w in cfg.get("entities") or ["Building"]]
        entities, plates = {}, []
        for pl in g_o.Plates[:]:
            name = pl.Name.value
            try:
                X, Y, Z = (np.array(g_o.getresults(pl, ph_o[-1], getattr(RP, a), "node"), float) for a in "XYZ")
            except Exception:
                continue                                  # plate not active in the last phase
            plates.append(dict(name=name, bbox=[float(X.min()), float(X.max()), float(Y.min()), float(Y.max()),
                                                float(Z.min()), float(Z.max())]))
            if not any(w in name.lower() for w in wanted):
                continue
            key = np.round(np.stack([X, Y, Z], axis=1), 3)
            uniq, first = np.unique(key, axis=0, return_index=True)
            ent = dict(bbox=plates[-1]["bbox"], nodes=uniq.tolist(), disp={})
            for ph in ph_o[1:]:
                try:
                    comp = {a: np.array(g_o.getresults(pl, ph, getattr(RP, a), "node"), float) * 1000.0
                            for a in ("Ux", "Uy", "Uz")}           # m -> mm
                except Exception:
                    continue                                       # not active in this phase
                ent["disp"][ph.Name.value] = {a.lower(): [round(float(v), 4) for v in comp[a][first]] for a in comp}
            entities[name] = ent
            log("entity", name, len(uniq), "nodes,", len(ent["disp"]), "phases")
        if not entities:
            raise RuntimeError(f"No plate matching {wanted} found. Plates in the model: {[p['name'] for p in plates]}")

        out = dict(project=dict(title=title),
                   phases=[dict(id=p.Name.value, name=split_ident(p.Identification.value)[0]) for p in ph_o],
                   entities=entities, plates=plates)
        (WORKDIR / "output.json").write_text(json.dumps(out), encoding="utf-8")
        log("wrote output.json:", list(entities), "of", len(plates), "plates")

        if launched:
            for name, fn in (("Output close", g_o.close), ("Input kill", g_i.kill)):
                try:
                    fn()
                except Exception as e:
                    log(f"{name} failed: {type(e).__name__}: {str(e)[:120]}")
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()
