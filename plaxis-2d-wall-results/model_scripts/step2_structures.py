from common import connect
s_i, g_i = connect()
g_i.gotostructures()

# --- secant wall: x = 0, +5.5 -> -26.5 mOD (EI reduced for secant/cracking)
r = g_i.plate((0, 5.5), (0, -26.5))
print("plate returns:", r)
