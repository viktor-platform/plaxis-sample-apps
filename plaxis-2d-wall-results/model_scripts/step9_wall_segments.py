from common import connect
s_i, g_i = connect()
g_i.gotostages()
ph2 = next(p for p in g_i.Phases[:] if p.Identification.value == "Install secant wall")
for k in range(1, 11):
    g_i.activate(getattr(g_i, f"Plate_1_{k}"), ph2)
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:90]!r}")
g_i.save()
