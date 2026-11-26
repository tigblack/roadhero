"""v13 step: LODs for the heavy meshes (after the full-quality models).

LOD1 = 50 %, LOD2 = 25 % of the triangles, quadric collapse (silhouette kept: the rounded bevel segments and the
dense rock rows go first). One LOD mesh per source mesh (instancing kept: every instance gets LOD objects that share
it). LOD objects: '<name>_LOD1', '<name>_LOD2', children of the source object with an identity local transform,
collection 'Zone_00 v13 — LODs (Unity LODGroup levels)', hidden in the viewport / renders, custom props
unity_lod_of, unity_lod_level, unity_lod_screen_size (0.25 / 0.10); same material slots and pipeline attributes."""
import bpy, math
import numpy as np
from mathutils import Matrix
import rg_lib as L

MIN_TRIS = 6000
SKIP = ('Ground', 'AP_Ground_Backdrop', 'AP_Backdrop_Mesas', 'AP_River_Water')
COLL = 'Zone_00 v13 — LODs (Unity LODGroup levels)'


def lod_mesh(src_ob, ratio, name):
    tmp = bpy.data.objects.new('__lod_tmp', src_ob.data)
    bpy.context.scene.collection.objects.link(tmp)
    m = tmp.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = ratio; m.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    bpy.data.objects.remove(tmp)
    me.name = name
    try:
        me.normals_split_custom_set([])
    except Exception:
        pass
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(40.0))
    return me


def run(ctx):
    zone = ctx['zone']
    coll = L.ensure_collection(COLL, zone)
    # clear LODs of a previous run
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    done = {}
    st = {}
    chars = {'ArmL', 'ArmR', 'LegL', 'LegR', 'Head', 'Torso', 'Gun', 'Wheel'}
    for ob in list(zone.all_objects):
        if ob.type != 'MESH' or ob.name in SKIP or ob.name.endswith(('_LOD1', '_LOD2')):
            continue
        if any(ob.name.startswith(c) for c in chars) or (ob.parent and ob.parent.name.startswith(('Spawn_0918', 'Spawn_0960', 'Spawn_0950'))):
            continue
        me = ob.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if nt < MIN_TRIS:
            continue
        key = me.name
        if key not in done:
            done[key] = (lod_mesh(ob, 0.5, me.name + '_LOD1'), lod_mesh(ob, 0.25, me.name + '_LOD2'))
            for m_ in done[key]:
                m_.calc_loop_triangles()
            st[key] = (nt, len(done[key][0].loop_triangles), len(done[key][1].loop_triangles))
        for lvl, lme in ((1, done[key][0]), (2, done[key][1])):
            lo = bpy.data.objects.new(f'{ob.name}_LOD{lvl}', lme)
            coll.objects.link(lo)
            lo.parent = ob; lo.matrix_parent_inverse = Matrix(); lo.matrix_basis = Matrix()
            for i, s in enumerate(ob.material_slots):
                if i >= len(lo.material_slots):
                    break
            L.set_object_materials(lo, [s.material for s in ob.material_slots])
            lo['unity_lod_of'] = ob.name; lo['unity_lod_level'] = lvl; lo['unity_lod_screen_size'] = 0.25 if lvl == 1 else 0.10
            lo['editing_zone'] = ob.get('editing_zone', 0)
            lo['artpass_v13'] = f'v13 LOD{lvl} of {ob.name} ({"50" if lvl == 1 else "25"} % quadric collapse)'
            lo.hide_viewport = True; lo.hide_render = True
    ctx['stats']['lod'] = st
    print('STEP13 lod meshes', len(st), 'objects', len(coll.objects), flush=True)
