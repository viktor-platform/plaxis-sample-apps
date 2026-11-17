from common import connect
s_i, g_i = connect()
g_i.gotostages()
assert len(g_i.Phases[:]) == 1, "phases already created - reset first"

wall, slab = g_i.Plates[0], g_i.Plates[1]
building = g_i.LineLoads[0]
ifaces = list(g_i.Interfaces[:])
print("interfaces:", [i.Name.value for i in ifaces])

def lift(top, bot):
    out = []
    for s in g_i.Soils[:]:
        b = s.Parent.BoundingBox
        if b.xMin.value >= -1e-6 and abs(b.xMax.value - 30) < 1e-6 \
           and b.yMax.value <= top + 1e-6 and b.yMin.value >= bot - 1e-6:
            out.append(s)
    return out

def new_phase(prev, ident):
    p = g_i.phase(prev)
    p.Identification = ident
    p.DeformCalcType = "Plastic"
    return p

init = g_i.Phases[0]
ph = new_phase(init, "Existing Central Hall building")
g_i.activate(building, ph)

ph = new_phase(ph, "Install secant wall")
ph.Deform.ResetDisplacementsToZero = True
g_i.activate(wall, ph)
for i in ifaces: g_i.activate(i, ph)

plan = [("Excavation 1", 5.5, 5.0, False), ("Install G0 slab", None, None, True),
        ("Excavation 2", 5.0, 4.0, False), ("Excavation 3", 4.0, 3.0, False),
        ("Excavation 4", 3.0, 2.0, False), ("Excavation 5", 2.0, 0.0, False),
        ("Excavation 6", 0.0, -2.0, False), ("Excavation 7", -2.0, -3.0, False),
        ("Excavation 8", -3.0, -4.2, False)]
for name, top, bot, is_slab in plan:
    ph = new_phase(ph, name)
    if is_slab:
        g_i.activate(slab, ph)
    else:
        cl = lift(top, bot)
        assert cl, (name, top, bot)
        for s in cl: g_i.deactivate(s, ph)
        print(name, "->", [s.Name.value for s in cl])

print([(p.Name.value, p.Identification.value) for p in g_i.Phases[:]])
