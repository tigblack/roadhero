"""Toxic Wetlands build: base -> characters -> terrain -> environment -> save the editable .blend.

    Blender -b <base.blend> --python tw_build.py -- --out ToxicWetlands_Zone01.blend [--steps chars,terrain,...]

Reproducible: every step rebuilds its objects from code and the layout data; the v10 source copy is never written.
"""
import argparse
import json
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tw_lib as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..'))
SCENE_JSON = os.path.abspath(os.path.join(ROOT, '..', '..', '..', 'Exports', 'Blender', '2026-11-17', 'scene.json'))
ZONE = 'Zone_01_ToxicWetlands'


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--steps', default='chars,props,terrain,roads,structures,arena,borders,scatter,lod')
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def hide_original(name_prefix, note):
    n = 0
    for o in bpy.data.objects:
        if o.type == 'MESH' and (o.name == name_prefix or o.name.startswith(name_prefix + '.')) and o.get('unity_id'):
            o['tw_hidden'] = True
            o['tw_stage'] = note
            o.hide_render = True
            o.hide_viewport = True
            n += 1
    return n


def step_chars():
    import tw_chars as CH
    return CH.build_all()


def step_terrain():
    import tw_terrain as TR
    md = json.load(open(SCENE_JSON))['metadata']
    g = TR.load_grid(os.path.join(ROOT, 'data'))
    zone = bpy.data.collections[ZONE]
    gcoll = L.ensure_collection('Zone_01 — Ground & water (Toxic Wetlands)', zone)
    hide_original('Ground', 'replaced by TW_Ground tiles (swamp heightfield)')
    TR.build_ground(g, md, gcoll)
    TR.build_water(g, gcoll)
    rebuilt = 0
    for fl in md['floors']:
        if fl.get('type') != 'MoundPiece' or not (95 <= fl['rect']['center'][2] <= 305):
            continue
        o = bpy.data.objects.get(fl['name'])
        if o is None:
            continue
        kind = 'Hill' if fl['name'].startswith(('Hill', 'RoadHill')) else 'Bumps'
        me = TR.build_mound(fl, kind, rebuilt + 11)
        # the mound mesh is built in world coordinates; the v10 objects sit at the origin with identity transforms
        mw = o.matrix_world.inverted()
        me.transform(mw)
        L.swap_mesh(o, me, 'rebuilt from the Unity MoundPiece formula (swamp mound)')
        rebuilt += 1
    return {'mounds': rebuilt}


def step_props():
    import tw_props as PRP
    return PRP.build_all()


_SC = {}


def scene():
    if 'sc' not in _SC:
        import tw_structures as ST
        _SC['sc'] = ST.Scene(SCENE_JSON)
    return _SC['sc']


def step_roads():
    """Roads keep their v10 ribbons (same driving surface); the material becomes muddy swamp asphalt."""
    mat = L.get_material('TW_RoadMud')
    n = 0
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.split('.')[0] == 'Road' and o.get('unity_id') and ZONE in [c.name for c in o.users_collection]:
            me = o.data.copy()
            me.name = o.data.name + '_swamp'
            me.materials.clear()
            me.materials.append(mat)
            L.swap_mesh(o, me, 'swamp asphalt material (same ribbon)')
            n += 1
    return {'roads': n}


def step_structures():
    import tw_structures as ST
    sc = scene()
    rep = {'tunnel': ST.rock_tunnel(sc)}
    ST.pipeline(sc)
    rep['palisades'] = ST.palisades(sc)
    ST.billboard(sc)
    ST.gate2(sc)
    rep['hill_decor'] = ST.hill_decor(sc)
    hide_original('Decor', 'replaced by the merged swamp decor tiles (TW_Decor_*)')
    return rep


def step_arena():
    import tw_arena as AR
    return AR.build(scene())


def step_borders():
    import numpy as np
    import tw_borders as BO
    prof = np.load(os.path.join(ROOT, 'data', 'ToxicWetlands_dam_profile.npy'))
    return BO.build(scene(), prof)


def step_scatter():
    import tw_scatter as SCT
    return SCT.build(SCENE_JSON)


LOD_PREFIXES = ('TW_SouthDam_', 'TW_FloodWall', 'TW_LeveeWall', 'TW_Berm', 'TW_Arena_PumpTower', 'TW_Arena_Tank',
                'TW_Arena_PumpHouse', 'TW_Tank_', 'TW_SlagMound', 'TW_ArenaFloor')


def step_lod():
    """LOD1 (50 %) / LOD2 (25 %) for heavy static meshes, as hidden children with identity transforms
    (unity_lod_of / unity_lod_level / unity_lod_screen_size: ImportedLevel builds the LODGroups, like v13)."""
    zone = bpy.data.collections[ZONE]
    lcoll = L.ensure_collection('Zone_01 — LODs (Unity LODGroup levels)', zone)
    lcoll.hide_render = True
    made, cache = 0, {}
    for o in list(zone.all_objects):
        if o.type != 'MESH' or o.get('unity_lod_level') or o.get('tw_no_export') or o.get('tw_hidden'):
            continue
        name_ok = o.name.startswith(LOD_PREFIXES) or (o.data and o.data.name.startswith(LOD_PREFIXES))
        if not name_ok or L.tri_count(o.data) < 2500:
            continue
        for level, ratio, size in ((1, 0.5, 0.25), (2, 0.25, 0.10)):
            key = (o.data.name, level)
            if key not in cache:
                cache[key] = L.lod_copy(o.data, ratio, o.data.name + '_LOD%d' % level)
            lo = bpy.data.objects.new(o.name + '_LOD%d' % level, cache[key])
            lcoll.objects.link(lo)
            lo.parent = o
            lo.matrix_parent_inverse.identity()
            lo['unity_lod_of'] = o.name
            lo['unity_lod_level'] = level
            lo['unity_lod_screen_size'] = size
            lo['editing_zone'] = 1
            lo.hide_render = True
            made += 1
        o['unity_lod_screen_size'] = 0.25
    return {'lod_objects': made, 'lod_meshes': len(cache)}


def main():
    a = args()
    L.TEX_DIR = os.path.join(ROOT, 'textures')
    report = {'steps': {}, 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    for step in a.steps.split(','):
        t = time.time()
        res = globals()['step_' + step]()
        report['steps'][step] = {'seconds': round(time.time() - t, 1), 'result': res}
        print('TW_BUILD step', step, report['steps'][step], flush=True)
    bpy.context.scene['tw_build_report'] = json.dumps(report)
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True)
    print('TW_BUILD saved', a.out, flush=True)


if __name__ == '__main__':
    main()
