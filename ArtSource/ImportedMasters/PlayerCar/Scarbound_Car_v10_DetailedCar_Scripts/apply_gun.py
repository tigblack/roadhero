import parts_gun, mats, carshape
importlib.reload(carshape); importlib.reload(parts_gun); importlib.reload(mats)
from parts_gun import BY, MUZZLE_Y, PITCH_Z, RECOIL

col = bpy.data.collections["Scarbound Car — EDITABLE"]
O = bpy.data.objects


def add_wn(ob):
    for m in [m for m in ob.modifiers if m.type == "WEIGHTED_NORMAL"]:
        ob.modifiers.remove(m)
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True


def install(obj_name, builder, mesh_name, parent=None, create=False):
    b = builder()
    me = b.build(mesh_name)
    pass
    ob = O.get(obj_name)
    if ob is None and create:
        ob = bpy.data.objects.new(obj_name, me)
        col.objects.link(ob)
        ob.parent = parent
        ob.matrix_parent_inverse.identity()
    else:
        old = ob.data
        replace_mesh(ob, me)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    add_wn(ob)
    return ob, b.tris()


report = {}
ob, n = install("HoodMount", parts_gun.mount_mesh, "hoodgun_mount_detailed"); report[ob.name] = n
ob, n = install("Turntable", parts_gun.turntable_mesh, "hoodgun_turntable_detailed"); report[ob.name] = n
O["TurretPitch"].location = (0.0, 0.0, PITCH_Z)
ob, n = install("GunMesh", parts_gun.gun_mesh, "hoodgun_gun_detailed"); report[ob.name] = n
ob, n = install("GunCradle", parts_gun.cradle_mesh, "hoodgun_cradle_detailed", parent=O["TurretPitch"], create=True); report[ob.name] = n

mz = O.get("HoodGun_Muzzle")
if mz is None:
    mz = bpy.data.objects.new("HoodGun_Muzzle", None)
    col.objects.link(mz)
mz.parent = O["Barrel0"]
mz.matrix_parent_inverse.identity()
mz.location = (0.0, MUZZLE_Y, BY)
mz.empty_display_type = "SINGLE_ARROW"
mz.empty_display_size = 0.15
mz.rotation_euler = (math.radians(-90), 0, 0)   # arrow (local Z) along the bore (+Y)

O["TurretYaw"]["pivot"] = "yaw about local +Z (Blender) = Unity +Y"
O["TurretPitch"]["pivot"] = "pitch about local X; trunnion GunPivotY = %.3f m above the plate" % PITCH_Z
O["Barrel0"]["recoil_axis"] = "-Y (Blender) = -Z (Unity)"
O["Barrel0"]["recoil_travel_m"] = RECOIL
O["Barrel0"]["GunBoreY"] = BY
O["Barrel0"]["GunMuzzleZ"] = MUZZLE_Y
mz["note"] = "muzzle point on the bore axis; arrow = firing direction (+Y Blender / +Z Unity)"
bpy.context.view_layer.update()
print(report, "muzzle world", tuple(round(v, 3) for v in mz.matrix_world.translation))
