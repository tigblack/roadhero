from mathutils.bvhtree import BVHTree
O = bpy.data.objects
dg = bpy.context.evaluated_depsgraph_get()


def world_tree(names):
    verts, polys, off = [], [], 0
    dg = bpy.context.evaluated_depsgraph_get()
    for n in names:
        ob = O[n]
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        M = ob.matrix_world
        verts += [M @ v.co for v in me.vertices]
        polys += [[i + off for i in p.vertices] for p in me.polygons]
        off += len(me.vertices)
        eo.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0), verts


def min_dist(tree_a_verts, tree_b, step=7):
    best = 9.0
    for v in tree_a_verts[::step]:
        hit = tree_b.find_nearest(v)
        if hit[0] is not None and hit[3] < best:
            best = hit[3]
    return best


static_sets = {
    "body+cab+glass": ["Body.573"],
    "details(blower,bumpers,mirrors...)": ["Details"],
    "harpoon turret": ["TurretBase.001", "Column", "LauncherMesh", "HarpoonTip"],
    "quasimodo": ["Cloak", "HeadMesh", "UpperArmR", "UpperArmL", "ForeArmR", "ForeArmL", "HandR", "HandL", "LegMesh", "LegMesh.001"],
}
trees = {k: world_tree(v)[0] for k, v in static_sets.items()}
yaw = O["TurretYaw"]
gun_parts = ["GunMesh", "GunCradle", "Turntable"]
res = []
for deg in range(0, 360, 15):
    yaw.rotation_euler = (0, 0, math.radians(deg))
    bpy.context.view_layer.update()
    gt, gv = world_tree(gun_parts)
    row = {"yaw": deg}
    for k, t in trees.items():
        hits = gt.overlap(t)
        row[k] = len(hits)
    row["clear_body_m"] = round(min_dist(gv, trees["body+cab+glass"]), 3)
    row["clear_details_m"] = round(min_dist(gv, trees["details(blower,bumpers,mirrors...)"]), 3)
    res.append(row)
yaw.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
bad = [r for r in res if any(r[k] for k in static_sets)]
for r in res:
    print(r)
print("HOOD GUN: yaw positions with intersections:", len(bad), "of", len(res))
