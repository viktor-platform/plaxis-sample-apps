"""Shared helpers for talking to a running PLAXIS 2D 2026 (Input on 10000)."""
import os
from plxscripting.easy import new_server

PLAXIS_PY = r"C:\ProgramData\Seequent\PLAXIS Python Distribution V3\python\python.exe"
HOST = "localhost"
PORT_INPUT = int(os.environ.get("PLX_PORT", 10000))
PASSWORD = os.environ["PLX_PASSWORD"]          # never hard-code; set per session


def connect():
    return new_server(HOST, PORT_INPUT, password=PASSWORD, timeout=15)
