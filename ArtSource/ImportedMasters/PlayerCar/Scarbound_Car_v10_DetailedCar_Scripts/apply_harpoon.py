import parts_harpoon as ph
importlib.reload(ph)
O = bpy.data.objects
rep = {}
for obj, fn, name in (("TurretBase.001", ph.base_mesh, "harpoonturret_base_detailed"), ("Column", ph.column_mesh, "harpoonturret_column_detailed"),
                      ("LauncherMesh", ph.launcher_mesh, "harpoonturret_launcher_detailed"), ("HarpoonTip", ph.harpoon_tip_mesh, "harpoonhead_detailed")):
    b = fn()
    me = b.build(name, sharp_deg=38)
    ob = O[obj]
    old = ob.data
    replace_mesh(ob, me)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for m in [m for m in ob.modifiers if m.type == "WEIGHTED_NORMAL"]:
        ob.modifiers.remove(m)
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"); wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
    rep[obj] = mesh_stats(me)
bpy.context.view_layer.update()
print(rep)
print({o: tuple(round(v, 3) for v in O[o].dimensions) for o in ("TurretBase.001", "Column", "LauncherMesh", "HarpoonTip")})
