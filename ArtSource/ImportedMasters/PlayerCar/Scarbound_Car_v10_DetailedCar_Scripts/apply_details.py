import parts_body, parts_details, carshape
importlib.reload(carshape); importlib.reload(parts_body); importlib.reload(parts_details)
O = bpy.data.objects
b = parts_details.build()
me = b.build("playercar_pickup1_extras_detailed", sharp_deg=35.0)
ob = O["Details"]
old = ob.data
replace_mesh(ob, me)
if old.users == 0 and old != me:
    bpy.data.meshes.remove(old)
for m in [m for m in ob.modifiers if m.type == "WEIGHTED_NORMAL"]:
    ob.modifiers.remove(m)
wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"); wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
print("details", mesh_stats(me), [m.name for m in me.materials], tuple(round(v, 3) for v in ob.dimensions))
