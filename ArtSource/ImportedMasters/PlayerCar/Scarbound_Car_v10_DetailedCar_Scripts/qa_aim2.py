from mathutils.bvhtree import BVHTree
O = bpy.data.objects


def world_tree(names):
    verts, polys, off = [], [], 0
    dg = bpy.context.evaluated_depsgraph_get()
    for n in names:
        ob = O[n]; eo = ob.evaluated_get(dg); me = eo.to_mesh(); M = ob.matrix_world
        verts += [M @ v.co for v in me.vertices]; polys += [[i + off for i in p.vertices] for p in me.polygons]
        off += len(me.vertices); eo.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


car = world_tree(["Body.573", "Details"])
# 1) hood gun pitched: -15 deg (up) and +5 deg (down) over all yaws
yaw, pitch = O["TurretYaw"], O["TurretPitch"]
out = {}
for pdeg in (-15, 5):
    bad = []
    for deg in range(0, 360, 15):
        yaw.rotation_euler = (0, 0, math.radians(deg)); pitch.rotation_euler = (math.radians(pdeg), 0, 0)
        bpy.context.view_layer.update()
        n = len(world_tree(["GunMesh", "GunCradle"]).overlap(car))
        if n: bad.append(deg)
    out["gun pitch %+d" % pdeg] = bad
yaw.rotation_euler = (0, 0, 0); pitch.rotation_euler = (0, 0, 0)
# 2) harpoon turret + operator orbiting the column: every 30 deg
hy = O["TurretYaw.001"]
q_parts = ["Cloak", "HeadMesh", "UpperArmR", "UpperArmL", "ForeArmR", "ForeArmL", "HandR", "HandL", "LegMesh", "LegMesh.001"]
h_parts = ["Column", "LauncherMesh", "HarpoonTip"]
gun_tree_parts = ["GunMesh", "GunCradle", "Turntable", "HoodMount"]
hb = []
for deg in range(0, 360, 30):
    hy.rotation_euler = (0, 0, math.radians(deg)); bpy.context.view_layer.update()
    qt, ht = world_tree(q_parts), world_tree(h_parts)
    hb.append((deg, len(qt.overlap(car)), len(ht.overlap(car)), len(ht.overlap(world_tree(gun_tree_parts)))))
hy.rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
print(out)
print("harpoon yaw, quasimodo-vs-car, launcher-vs-car, launcher-vs-hoodgun:")
for r in hb: print("  ", r)
