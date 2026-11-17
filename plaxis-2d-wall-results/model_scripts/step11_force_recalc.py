from common import connect
s_i, g_i = connect()
g_i.gotostages()
for p in g_i.Phases[:]:
    p.ShouldCalculate = True
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:90]!r}")
g_i.save()
