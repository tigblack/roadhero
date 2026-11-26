import organic, parts_quasi, parts_quasi_limbs as pl
importlib.reload(organic); importlib.reload(parts_quasi); importlib.reload(pl)
O = bpy.data.objects
report = {}


def install(obj_name, me, sharp=None):
    ob = O[obj_name]
    old = ob.data
    if sharp is not None:
        me.set_sharp_from_angle(angle=math.radians(sharp))
    replace_mesh(ob, me)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    report[obj_name] = mesh_stats(me)["tris"]


install("UpperArmR", pl.upper_arm(11).build("quasimodo_upperarm_R_detailed", sharp_deg=60))
install("UpperArmL", pl.upper_arm(17).build("quasimodo_upperarm_L_detailed", sharp_deg=60))
install("ForeArmR", pl.fore_arm(13, 1).build("quasimodo_forearm_R_detailed", sharp_deg=60))
install("ForeArmL", pl.fore_arm(19, -1).build("quasimodo_forearm_L_detailed", sharp_deg=60))
L = O["Launcher"]
for i, hn in enumerate(("HandR", "HandL")):
    Hm = O[hn].matrix_world
    ax = (Hm.to_3x3().inverted() @ L.matrix_world.to_3x3().col[0]).normalized()
    me = pl.hand(i, ax)
    me.name = "quasimodo_hand_%s_detailed" % ("R" if i == 0 else "L")
    install(hn, me, sharp=70)
for obj, s, nm in (("LegMesh", 1, "R"), ("LegMesh.001", -1, "L")):
    me = pl.leg(s)
    me.name = "quasimodo_leg_%s_detailed" % nm
    install(obj, me, sharp=55)
bpy.context.view_layer.update()
print(report)
