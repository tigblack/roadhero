"""Export the v11 geometry to FBX (meshes + empties of the level hierarchy; PREVIEW cameras/lights excluded).
Same axis/unit settings as Tools/Blender/import_level.py so Unity receives it like the v10 FBX."""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
os.makedirs(os.path.dirname(out), exist_ok=True)
prev = bpy.data.collections.get('PREVIEW — cameras and lights (not exported)')
excluded = set(prev.all_objects) if prev else set()
bpy.ops.object.select_all(action='DESELECT')
n = 0
for o in bpy.context.scene.objects:
    if o.type in {'MESH', 'EMPTY'} and o not in excluded:
        o.hide_set(False); o.select_set(True); n += 1
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'EMPTY', 'MESH'},
                         apply_unit_scale=True, global_scale=1.0, apply_scale_options='FBX_SCALE_UNITS',
                         axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True, use_custom_props=True,
                         mesh_smooth_type='OFF', use_tspace=False, add_leaf_bones=False, bake_anim=False,
                         path_mode='RELATIVE', colors_type='LINEAR', prioritize_active_color=True)
print('FBX exported', out, 'objects', n, 'excluded', len(excluded))
