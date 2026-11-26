import parts_body, carshape
importlib.reload(carshape); importlib.reload(parts_body)

O = bpy.data.objects


def cleanup(me, dist=2e-5):
    bm = bmesh.new()
    bm.from_mesh(me)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=dist)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n0 - len(me.vertices)


b = parts_body.build()
me = b.build("playercar_pickup1_detailed", sharp_deg=40.0)
removed = cleanup(me)
me.set_sharp_from_angle(angle=math.radians(40.0))
ob = O["Body.573"]
old = ob.data
replace_mesh(ob, me)
if old.users == 0 and old.name != "playercar_pickup1_detailed":
    bpy.data.meshes.remove(old)
print("body", mesh_stats(me), "welded", removed, "mats", [m.name for m in me.materials], "dims", tuple(round(v, 3) for v in ob.dimensions))
