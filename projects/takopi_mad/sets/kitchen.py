"""Set: the empty kitchen at night (Shizuka's home). Modelled after c16_p17_p02.
blender -b --factory-startup -P sets/kitchen.py -- still out.png FRAME | anim out_dir F0 F1
"""
import math
import os
import sys

sys.path.insert(0, os.environ.get("MAD_BLENDER", "/home/user/.claude/skills/mad-blender/scripts"))
import toonkit as T  # noqa: E402

A = T.args()
T.reset(res=(1280, 720), fps=24)
T.world_color("#06080c", 1.0)

wall = T.toon("wall", "#b9b7a6", "#5e6264")
floor = T.toon("floor", "#6e5440", "#352a24")
ceil = T.toon("ceil", "#8a8a84", "#40423f")
cab = T.toon("cabinet", "#d6cfbc", "#6c6c66")
counter = T.toon("counter", "#9a9c98", "#4a4c4c")
steel = T.toon("steel", "#b8bcc0", "#5a5e64")
tbl = T.toon("table", "#a88a62", "#5a4632")
seat = T.toon("seat", "#6f8488", "#33404a")
dark = T.toon("dark", "#2a2a30", "#101014")
fridge = T.toon("fridge", "#c8ccc8", "#5c605e")
glass = T.glow_mat("night_glass", "#1a2a46", 1.2)

# room 4.2 x 3.6 x 2.4
T.room("k", 4.2, 3.6, 2.4, wall, floor, ceil, skirting=dark)
# floor boards (thin strips for the manga plank lines)
for i in range(14):
    T.box(f"plank{i}", (0.004, 3.6, 0.002), (-2.1 + i * 0.3, 1.8, 0.0), dark)
# window on the back wall, night outside
back = [o for o in T.D.objects if o.name == "k_back"][0]
T.window_hole(back, 1.2, 1.0, 1.1, 0.9)
T.plane("night", 1.4, 1.2, (1.2, 3.75, 1.45), (90, 0, 0), glass)
T.box("win_frame_h", (1.12, 0.06, 0.04), (1.2, 3.58, 1.43), dark)
T.box("win_frame_v", (0.04, 0.06, 0.9), (1.2, 3.58, 1.0), dark)
# kitchen run along the back wall: lower cabinets, counter, upper cabinets, sink, hood
for i in range(5):
    x = -1.9 + i * 0.6
    if 0.6 < x < 1.8:
        continue
    T.box(f"lowcab{i}", (0.58, 0.6, 0.82), (x + 0.3, 3.28, 0.0), cab, bevel=0.005)
    T.box(f"handle{i}", (0.18, 0.02, 0.02), (x + 0.3, 2.97, 0.72), steel)
T.box("counter", (4.2, 0.64, 0.04), (0, 3.28, 0.82), counter)
T.box("sink", (0.6, 0.42, 0.02), (-0.4, 3.3, 0.86), steel)
T.cylinder("tap", 0.02, 0.28, (-0.4, 3.52, 0.86), steel)
for i in range(4):
    T.box(f"upcab{i}", (0.58, 0.36, 0.7), (-1.6 + i * 0.6, 3.42, 1.5), cab, bevel=0.005)
# fridge in the left corner
T.box("fridge", (0.7, 0.68, 1.8), (-1.75, 2.6, 0.0), fridge, bevel=0.01)
T.box("fridge_line", (0.7, 0.005, 0.01), (-1.75, 2.255, 1.15), dark)
# table + 3 chairs, a remote on the table (nobody home)
T.table("table", 1.3, 0.85, 0.72, (0.2, 1.6, 0), tbl, tbl, rot=-6)
T.chair("chair_a", (0.25, 2.25, 0), 180, seat, dark)
T.chair("chair_b", (-0.75, 1.55, 0), 90, seat, dark)
T.chair("chair_c", (1.15, 1.5, 0), -90, seat, dark)
T.box("remote", (0.18, 0.05, 0.02), (0.35, 1.5, 0.72), dark, rot=(0, 0, 8))
# ceiling lamp (off)
T.cylinder("lamp", 0.28, 0.08, (0.2, 1.6, 2.28), fridge)

# light: cold moonlight through the window + faint fill
# moonlight enters through the window and throws its frame across the floor and table
T.sun(energy=4.0, rot=(-60, 0, 0), color="#b8c8ff", angle=1.5)
T.area((0.2, 0.3, 2.2), (0, 0, 0), size=3.0, energy=12, color="#7080a0")
T.ink_lines(2.2, "#0e0c10")

fps = 24
cam = T.camera([(1, (-1.2, -0.9, 1.35), (0.3, 2.0, 0.8), -1.5),
                (6 * fps, (0.2, -0.2, 1.15), (0.35, 1.7, 0.75), 1.0)], fov=46)

if A and A[0] == "export":
    print(T.export_scene(A[1], 1, 6 * fps))
elif A and A[0] == "still":
    T.still(A[1], int(A[2]) if len(A) > 2 else 1)
elif A and A[0] == "anim":
    T.render(A[1], int(A[2]), int(A[3]))
