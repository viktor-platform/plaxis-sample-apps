from common import connect
s_i, g_i = connect()
g_i.gotostructures()
for l in list(g_i.LineLoads[:]): g_i.delete(l)
ld = g_i.lineload((-27, 5.5), (-1, 5.5))[-1]
ld.qy_start = -40
mg = next(m for m in g_i.Materials[:] if m.Identification.value == "Made ground")
mg.setproperties("cRef", 5, "phi", 30, "Eref", 25000)
g_i.gotomesh(); print(g_i.mesh(0.04))
g_i.gotostages()
g_i.activate(g_i.LineLoads[0], g_i.Phases[1])
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:60]!r}")
