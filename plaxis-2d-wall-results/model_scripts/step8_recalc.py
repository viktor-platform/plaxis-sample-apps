from common import connect
s_i, g_i = connect()
g_i.gotostages()
slab_mat = next(m for m in g_i.Materials[:] if m.Identification.value == "G0 slab 0.5m")
slab_mat.setproperties("w", 0)      # slab acts as a prop: self weight carried by (unmodelled) bearing piles
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:90]!r}")
g_i.save()
