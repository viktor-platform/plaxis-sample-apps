"""Set the activation state of every staged object explicitly in every phase (no reliance on inheritance)."""
from common import connect
s_i, g_i = connect()
g_i.gotostages()
phases = list(g_i.Phases[:])
idx = {p.Identification.value: n for n, p in enumerate(phases)}

lifts = [("Excavation 1", 5.5, 5.0), ("Excavation 2", 5.0, 4.0), ("Excavation 3", 4.0, 3.0),
         ("Excavation 4", 3.0, 2.0), ("Excavation 5", 2.0, 0.0), ("Excavation 6", 0.0, -2.0),
         ("Excavation 7", -2.0, -3.0), ("Excavation 8", -3.0, -4.2)]

def inside(bb, top, bot, x0=0.0):
    return (bb.xMin.value >= x0 - 1e-6 and bb.yMax.value <= top + 1e-6 and bb.yMin.value >= bot - 1e-6)

soils = list(g_i.Soils[:])
wall = [getattr(g_i, f"Plate_1_{k}") for k in range(1, 11)]
slab = g_i.Plate_2_1
building = g_i.LineLoad_1_1
pos = [i for i in g_i.Interfaces[:] if i.Name.value.startswith("PositiveInterface")]
neg = [i for i in g_i.Interfaces[:] if i.Name.value.startswith("NegativeInterface")]

def setstate(obj, ph, on):
    (g_i.activate if on else g_i.deactivate)(obj, ph)

for n, ph in enumerate(phases):
    if n == 0:
        continue
    setstate(building, ph, n >= idx["Existing Central Hall building"])
    wall_on = n >= idx["Install secant wall"]
    for o in wall + pos: setstate(o, ph, wall_on)
    setstate(slab, ph, n >= idx["Install G0 slab"])
    done = [l for l in lifts if l[0] in idx and idx[l[0]] <= n]
    for s in soils:
        bb = s.Parent.BoundingBox
        setstate(s, ph, not any(abs(bb.xMax.value - 30) < 1e-6 and inside(bb, t, b) for _, t, b in done))
    for i in neg:
        bb = i.Parent.BoundingBox
        setstate(i, ph, wall_on and not any(inside(bb, t, b, x0=-1) for _, t, b in done))

print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value} {str(p.LogInfo.value)[:90]!r}")
g_i.save()
