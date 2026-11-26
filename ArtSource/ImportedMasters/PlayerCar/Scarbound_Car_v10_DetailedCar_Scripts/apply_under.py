import parts_details, parts_under
importlib.reload(parts_details); importlib.reload(parts_under)
O = bpy.data.objects
col = bpy.data.collections["Scarbound Car — EDITABLE"]
me = parts_under.build().build("playercar_underbody_detailed", sharp_deg=38)
_bm = bmesh.new(); _bm.from_mesh(me)
bmesh.ops.dissolve_degenerate(_bm, edges=_bm.edges[:], dist=1e-6)
_bm.to_mesh(me); _bm.free(); me.update()
ob = O.get("Underbody")
if ob is None:
    ob = bpy.data.objects.new("Underbody", me)
    col.objects.link(ob)
    ob.parent = O["Body.573"]
    ob.matrix_parent_inverse.identity()
else:
    old = ob.data
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
bpy.context.view_layer.update()
print("underbody", mesh_stats(me), tuple(round(v, 3) for v in ob.dimensions))
bpy.ops.wm.save_mainfile()
