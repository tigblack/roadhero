"""Export simplified collision proxies for the rebuilt rock masses (their LOD2 meshes, renamed *_COL) for Unity
MeshColliders / RockColliders. blender -b FILE --python export_col13.py -- OUT.fbx"""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:]; out = argv[0]
os.makedirs(os.path.dirname(out), exist_ok=True)
ROCKS = ('MesaRock', 'Plateau', 'Ridge0.001', 'Cliff', 'Cliff.001', 'Cliff.002', 'Cliff.003', 'Cliff.004', 'Cliff.011',
         'Cliff.012', 'Cliff.014', 'AP_Cliff_NorthEast')
bpy.ops.object.select_all(action='DESELECT')
sel = []
for n in ROCKS:
    lo = bpy.data.objects.get(n + '_LOD2')
    src = bpy.data.objects.get(n)
    if lo is None or src is None:
        continue
    col = bpy.data.objects.new(n + '_COL', lo.data)
    bpy.context.scene.collection.objects.link(col)
    col.matrix_world = src.matrix_world.copy()
    col['unity_collider_for'] = n
    col.hide_set(False); col.select_set(True); sel.append(col.name)
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'MESH'}, apply_unit_scale=True, global_scale=1.0,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', use_custom_props=True,
                         mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False)
print('COL13 exported', out, sel)
