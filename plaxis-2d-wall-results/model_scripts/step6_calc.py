import os
from common import connect
s_i, g_i = connect()
g_i.gotostages()
os.makedirs("model", exist_ok=True)
path = os.path.abspath("model/olympia_demo.p2dx")
g_i.save(path)
print("saved", path)
print(g_i.calculate())
for p in g_i.Phases[:]:
    print(f"{p.Name.value:9} {p.Identification.value:32} result={p.CalculationResult.value}  | {str(p.LogInfo.value)[:80]!r}")
g_i.save(path)
