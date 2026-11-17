from common import connect
s_i, g_i = connect()
# interface material: default rigid; Rinter via soil materials default 1.0 (rigid) - OK for demo
g_i.gotomesh()
print(g_i.mesh(0.06))
print("mesh status:", g_i.Model.MeshStatus if hasattr(g_i.Model,'MeshStatus') else '')
g_i.gotostages()
print("phases:", [p.Name.value for p in g_i.Phases[:]])
ss = g_i.Soils[:]
print(len(ss), [s.Name.value for s in ss])
