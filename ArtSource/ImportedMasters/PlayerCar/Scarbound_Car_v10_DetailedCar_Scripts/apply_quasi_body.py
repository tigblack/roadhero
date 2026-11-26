import parts_quasi as pq
importlib.reload(pq)
O = bpy.data.objects
crew = O["Quasimodo"]
CI = crew.matrix_world.inverted()


def crew_pos(name, local=(0, 0, 0)):
    return CI @ (O[name].matrix_world @ Vector(local))


rig = {"shR": crew_pos("UpperArmR"), "elR": crew_pos("ForeArmR"), "haR": crew_pos("HandR"),
       "shL": crew_pos("UpperArmL"), "elL": crew_pos("ForeArmL"), "haL": crew_pos("HandL")}


def to_local(b, obj):
    M = obj.matrix_world.inverted() @ crew.matrix_world
    b.co = [tuple(M @ Vector(p)) for p in b.co]
    if M.determinant() < 0:
        b.faces = [f[::-1] for f in b.faces]
        b.fuv = [u[::-1] for u in b.fuv]


b = pq.body_build(rig)
to_local(b, O["Cloak"])
me = b.build("quasimodo_body_detailed", sharp_deg=60.0)
ob = O["Cloak"]
old = ob.data
replace_mesh(ob, me)
if old.users == 0:
    bpy.data.meshes.remove(old)
bpy.context.view_layer.update()
print("cloak", mesh_stats(me), [m.name for m in me.materials], tuple(round(v, 3) for v in ob.dimensions))
