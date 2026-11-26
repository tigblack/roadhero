"""Export LOD0/LOD1/LOD2 FBX with identical hierarchy, names and pivots (RoadGame conventions from export_car.py).
Each export mesh gets the single baked material of its texture set; LOD meshes are swapped in temporarily."""
load("tsets.py")
import json, os
O = bpy.data.objects
BLEND_DIR = os.path.dirname(bpy.data.filepath)
EXP = os.path.join(BLEND_DIR, "Scarbound_Car_v10_DetailedCar_Export")
os.makedirs(EXP, exist_ok=True)
root = O["REFERENCE_PlayerCar_DoNotMerge"]
hier = [root] + list(root.children_recursive)
base = [o for o in hier if "lod_level" not in o]
set_of = {n: s for s, names in SETS.items() for n in names}
report = {}
if bpy.context.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
for level in (0, 1, 2):
    swaps, tmps = [], []
    for o in base:
        if o.type != "MESH":
            continue
        src = o.data if level == 0 else O["%s_LOD%d" % (o.name, level)].data
        tmp = src.copy()
        tmp.name = "__exp_%s_L%d" % (o.name, level)
        tmp.materials.clear()
        tmp.materials.append(bpy.data.materials["M_" + set_of[o.name]])
        tmp.polygons.foreach_set("material_index", [0] * len(tmp.polygons))
        uvn = [u.name for u in tmp.uv_layers]
        assert uvn[:2] == ["UVMap", "Unity_MaterialParams"], (o.name, uvn)
        swaps.append((o, o.data))
        o.data = tmp
        tmps.append(tmp)
    vl = bpy.context.view_layer
    for ob in vl.objects:
        ob.select_set(False)
    hidden = []
    for ob in base:
        if ob.hide_get():
            hidden.append(ob)
            ob.hide_set(False)
        ob.select_set(True)
    vl.objects.active = root
    path = os.path.join(EXP, "Scarbound_Car_v10_DetailedCar_LOD%d.fbx" % level)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"EMPTY", "MESH"},
        apply_unit_scale=True, global_scale=1.0, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True, use_custom_props=True,
        mesh_smooth_type="FACE", use_tspace=True, use_triangles=True, add_leaf_bones=False,
        bake_anim=False, path_mode="RELATIVE", embed_textures=False, colors_type="LINEAR")
    tris = sum(sum(len(p.vertices) - 2 for p in t.polygons) for t in tmps)
    for o, me in swaps:
        o.data = me
    for t in tmps:
        bpy.data.meshes.remove(t)
    for ob in hidden:
        ob.hide_set(True)
    for ob in vl.objects:
        ob.select_set(False)
    report["LOD%d" % level] = {"file": path, "bytes": os.path.getsize(path), "mesh_objects": len(swaps), "tris_before_triangulate": tris}
    print("EXPORTED", level, report["LOD%d" % level], flush=True)
json.dump(report, open(os.path.join(EXP, "export_report.json"), "w"), indent=2)
