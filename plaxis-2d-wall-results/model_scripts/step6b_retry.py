import sys, os
from common import connect
s_i, g_i = connect()
load = float(sys.argv[1]); mesh = float(sys.argv[2])
g_i.gotostructures()
g_i.LineLoads[0].qy_start = -load
g_i.gotomesh()
print(g_i.mesh(mesh))
g_i.gotostages()
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:70]!r}")
