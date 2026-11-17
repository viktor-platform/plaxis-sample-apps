"""Deactivate wall interface on the excavated (right/negative) side for every lift, then calculate all."""
from common import connect
s_i, g_i = connect()
g_i.gotostages()
lifts = {"Excavation 1": (5.5, 5.0), "Excavation 2": (5.0, 4.0), "Excavation 3": (4.0, 3.0),
         "Excavation 4": (3.0, 2.0), "Excavation 5": (2.0, 0.0), "Excavation 6": (0.0, -2.0),
         "Excavation 7": (-2.0, -3.0), "Excavation 8": (-3.0, -4.2)}
neg = [i for i in g_i.Interfaces[:] if i.Name.value.startswith("NegativeInterface")]
for ph in g_i.Phases[:]:
    if ph.Identification.value in lifts:
        top, bot = lifts[ph.Identification.value]
        sel = [i for i in neg
               if i.Parent.BoundingBox.yMax.value <= top + 1e-6 and i.Parent.BoundingBox.yMin.value >= bot - 1e-6]
        for i in sel: g_i.deactivate(i, ph)
        print(ph.Identification.value, [i.Name.value for i in sel])
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:60]!r}")
g_i.save()
