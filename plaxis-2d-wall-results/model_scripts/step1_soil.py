from common import connect
s_i, g_i = connect()
assert not g_i.Soils or True
g_i.gotosoil()
g_i.SoilContour.initializerectangular(-60, -30, 30, 6)
bh = g_i.borehole(0)
print("borehole:", bh)
mats = {}
def soil(name, gu, gs, E, nu, c, phi):
    mats[name] = g_i.soilmat("Identification", name, "SoilModel", 2, "gammaUnsat", gu, "gammaSat", gs,
                             "Eref", E, "nu", nu, "cRef", c, "phi", phi, "psi", 0)
soil("Made ground", 18, 19, 15000, 0.3, 1, 28)
soil("Terrace gravel", 19, 20, 40000, 0.3, 0.1, 35)
soil("London clay", 19.5, 20, 60000, 0.3, 5, 25)
# three layers: ground 5.5 -> 3.0 -> -1.0 -> bottom (-30)
for _ in range(3):
    g_i.soillayer(0)
g_i.setsoillayerlevel(bh, 0, 5.5)
g_i.setsoillayerlevel(bh, 1, 3.0)
g_i.setsoillayerlevel(bh, 2, -1.0)
g_i.setsoillayerlevel(bh, 3, -30)
layers = g_i.Soillayers[:]
print("layers:", [l.Name.value for l in layers])
for l, name in zip(layers, ["Made ground", "Terrace gravel", "London clay"]):
    l.Soil.Material = mats[name]
print("done")
