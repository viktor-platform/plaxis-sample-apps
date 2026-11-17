"""Worker script - runs ON the machine where PLAXIS 2D is installed (sent by vkt.plaxis.PlaxisAnalysis).

Reads  input.json  from the working directory and writes  output.json  (same schema as
data/olympia_demo_results.json) containing wall results (ux [mm], M [kNm/m], Q [kN/m]) for every phase.

input.json
    mode          "launch" | "attach"
    project_path  .p2dx to open (launch mode; optional in attach mode)
    plaxis_exe    path to Plaxis2DXInput.exe (launch mode)
    password      attach mode: remote scripting password (falls back to env PLAXIS_PASSWORD)
    recalculate   bool - force recalculation of all phases before reading results
    input_port    default 10000
    output_port   fallback 10001 (the port returned by view() is used when available)

Launch mode generates a random password. Attach mode uses the password entered in the app (or the
PLAXIS_PASSWORD environment variable on the worker machine) - PLAXIS: Expert > Configure remote scripting server.

NOTE: the PLAXIS disclaimer must have been accepted once on this machine ("Do not show again"),
otherwise g_i.view() blocks until somebody clicks 'I agree'.
Requires plxscripting >= 1.0.10 (PLAXIS 2026 uses HTTPS) - use the PLAXIS Python distribution.
"""
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from plxscripting.easy import new_server

HOST = "localhost"
WORKDIR = Path.cwd()


def log(*a):
    print("[run_plaxis]", *a, flush=True)


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
    raise RuntimeError(f"Could not connect to PLAXIS on port {port}: {last}")


def split_ident(ident):
    m = re.match(r"(.*?)\s*\[(.+)\]$", ident)
    return (m.group(1), m.group(2)) if m else (ident, ident)


def nodes(g_o, plate, phase, rtype):
    return np.atleast_1d(np.array(g_o.getresults(plate, phase, rtype, "node"), dtype=float))


def wall_results(g_o, plate, phase, y_ref):
    RT = g_o.ResultTypes.Plate
    try:
        y = nodes(g_o, plate, phase, RT.Y)
    except ValueError:                       # plate inactive in this phase -> zeros
        z = np.zeros_like(y_ref)
        return y_ref, z, z.copy(), z.copy()
    ux, m, q = nodes(g_o, plate, phase, RT.Ux) * 1000.0, nodes(g_o, plate, phase, RT.M2D), nodes(g_o, plate, phase, RT.Q2D)
    key = np.round(y, 4)                     # node values come per element -> average joints
    uniq = np.unique(key)[::-1]
    avg = lambda a: np.array([a[key == k].mean() for k in uniq])
    return uniq, avg(ux), avg(m), avg(q)


def main():
    cfg = json.loads((WORKDIR / "input.json").read_text(encoding="utf-8"))
    mode = cfg.get("mode", "launch")
    port_i = int(cfg.get("input_port", 10000))
    proc = None
    launched = mode == "launch"
    try:
        if launched:
            if port_open(port_i):
                raise RuntimeError(f"Port {port_i} is already in use - choose a free port for the new PLAXIS.")
            password = secrets.token_urlsafe(16)
            exe = cfg["plaxis_exe"]
            log("launching", exe)
            proc = subprocess.Popen([exe, f"--AppServerPassword={password}", f"--AppServerPort={port_i}"])
        else:
            password = cfg.get("password") or os.environ.get("PLAXIS_PASSWORD")
            if not password:
                raise RuntimeError("No PLAXIS remote scripting password given (input.json 'password' or "
                                   "PLAXIS_PASSWORD environment variable).")
        s_i, g_i = connect(port_i, password)
        log("connected to Input")

        if cfg.get("project_path"):
            log("opening", cfg["project_path"])
            s_i.open(cfg["project_path"])
        g_i.gotostages()
        phases = list(g_i.Phases[:])
        if cfg.get("recalculate"):
            for p in phases:
                p.ShouldCalculate = True
        if any(p.ShouldCalculate.value for p in phases):
            log("calculate()")
            g_i.calculate()                   # only computes phases that are marked
        else:
            log("all phases already calculated - skipping calculate()")
        failed = [p.Identification.value for p in phases if p.CalculationResult.value != 1]
        if failed:
            raise RuntimeError(f"PLAXIS phases not calculated successfully: {failed}")
        title = str(g_i.Project.Title.value)

        out_port = g_i.view(phases[-1])       # opens Output; returns its server port
        s_o, g_o = connect(int(out_port or cfg.get("output_port", 10001)), password)
        log("connected to Output")

        ph_o = list(g_o.Phases[:])
        RT = g_o.ResultTypes.Plate
        walls = []                            # vertical plates only (walls)
        for pl in g_o.Plates[:]:
            if np.ptp(nodes(g_o, pl, ph_o[-1], RT.X)) < 1e-6:
                y = nodes(g_o, pl, ph_o[-1], RT.Y)
                walls.append((pl.Name.value, pl, float(y.max()), float(y.min())))

        stages = []
        for p in ph_o:
            name, _ = split_ident(p.Identification.value)
            stages.append(dict(id=p.Name.value, name=name, note="", excavation_level=None, slab_installed=False))

        out = dict(project=dict(client="", project=title, title=f"PLAXIS live: {title}", job_no=""),
                   stages=stages,
                   plates=[dict(name=n, top=t, bottom=b, description=f"Plaxis object {n}") for n, _, t, b in walls],
                   results={})
        for n, pl, _, _ in walls:
            y_ref = np.unique(np.round(nodes(g_o, pl, ph_o[-1], RT.Y), 4))[::-1]
            out["results"][n] = {}
            for p in ph_o[1:]:                # skip initial phase
                y, ux, m, q = wall_results(g_o, pl, p, y_ref)
                out["results"][n][p.Name.value] = {k: [round(float(v), 6) for v in a]
                                                   for k, a in (("y", y), ("ux", ux), ("m", m), ("q", q))}
        (WORKDIR / "output.json").write_text(json.dumps(out), encoding="utf-8")
        log("wrote output.json:", [w[0] for w in walls], len(stages), "phases")

        if launched:                          # only close what we opened
            for name, fn in (("Output close", g_o.close), ("Input kill", g_i.kill)):
                try:
                    fn()
                except Exception as e:      # closing is best effort
                    log(f"{name} failed: {type(e).__name__}: {str(e)[:120]}")
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()
