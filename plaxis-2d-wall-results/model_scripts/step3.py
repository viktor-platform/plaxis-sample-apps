from common import connect
s_i, g_i = connect()
g_i.gotostructures()
wall = g_i.Plates[0]

def plate_mat(name, EA, EI, d, w):
    m = next((x for x in g_i.Materials[:] if x.Identification.value == name), None) \
        or g_i.platemat("Identification", name)
    m.setproperties("MaterialType", "Elastic", "w", w, "Isotropic", True,
                    "EA1", EA, "EI", EI, "StructNu", 0.15)
    return m

wall.Material = plate_mat("Secant wall 1.0m", 7.5e6, 3.1e5, 0.70, 12)   # cracked/secant-reduced
slab_mat = plate_mat("G0 slab 0.5m", 7.5e6, 1.6e5, 0.5, 12)

slab = g_i.plate((0, 5.0), (30, 5.0))[-1]
slab.Material = slab_mat
ld = g_i.lineload((-27, 5.5), (0, 5.5))
ld[-1].qy_start = -60            # kN/m2 existing Central Hall building load

for lvl in (4.0, 3.0, 2.0, 0.0, -2.0, -3.0, -4.2):
    g_i.line((0, lvl), (30, lvl))

print("interfaces:", g_i.posinterface(wall), g_i.neginterface(wall))
print("plates:", [p.Name.value for p in g_i.Plates[:]])
print("polygons:", len(g_i.Polygons[:]), "soils:", len(g_i.Soils[:]))
