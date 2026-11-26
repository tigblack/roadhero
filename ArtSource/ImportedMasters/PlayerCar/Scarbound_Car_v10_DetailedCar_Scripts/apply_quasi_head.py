import organic, parts_quasi, parts_quasi_head as ph
importlib.reload(organic); importlib.reload(parts_quasi); importlib.reload(ph)
O = bpy.data.objects
crew = O["Quasimodo"]
me = ph.build_head()
M = O["HeadMesh"].matrix_world.inverted() @ crew.matrix_world
me.transform(M)
me.update()
ob = O["HeadMesh"]
old = ob.data
replace_mesh(ob, me)
if old.users == 0:
    bpy.data.meshes.remove(old)
bpy.context.view_layer.update()
print("head", mesh_stats(me), [m.name for m in me.materials], tuple(round(v, 3) for v in ob.dimensions))
