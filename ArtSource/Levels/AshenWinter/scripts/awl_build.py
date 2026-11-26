"""Ashen Winter level build: base -> props -> terrain -> roads -> structures -> arena -> jump -> landmarks -> borders
-> scatter -> dev spawns -> LOD -> the editable .blend.

    Blender -b <base.blend> --python awl_build.py -- --out <build.blend> [--steps props,terrain,...]

Reproducible: every step rebuilds its objects from code and the layout data (data/AshenWinter_layout.json and the
world metadata exported with that layout active, data/AshenWinter_world.json); the v10 source copy is never written.
"""
import argparse
import json
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import awl_lib as W  # noqa: E402
import tw_lib as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data')
SCENE_JSON = os.path.abspath(os.path.join(ROOT, '..', '..', '..', 'Exports', 'Blender', '2026-11-17', 'scene.json'))
ZONE = 'Zone_02_AshenWinter'
_W = {}


def world():
    if 'w' not in _W:
        import awl_world as AW
        _W['w'] = AW.World(DATA, SCENE_JSON)
    return _W['w']


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--steps', default='hide,props,terrain,roads,structures,bunker,arena,jump,landmarks,borders,scatter,devspawns,lod')
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def step_hide():
    import awl_world as AW
    return {'hidden': AW.hide_originals(world())}


def step_props():
    import awl_props as PR
    return PR.build_all()


def step_terrain():
    import awl_terrain as TR
    import awl_world as AW
    w = world()
    g = TR.load_grid(DATA)
    out = TR.build_ground(g, w.md, w.L, AW.coll('Terrain'))
    rebuilt = 0
    for fl in w.md['floors']:
        name = fl['name']
        if not name.startswith(('Hill2', 'RoadHill2', 'Bumps2')):
            continue
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        kind = 'Hill' if name.startswith(('Hill', 'RoadHill')) else 'Bumps'
        me = TR.build_mound(fl, kind, rebuilt + 21)
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'snow mound from the Unity MoundPiece formula')
        rebuilt += 1
    return {'tiles': len(out), 'mounds': rebuilt}


def step_roads():
    import awl_world as AW
    return AW.road_strips(world())


def step_structures():
    import awl_world as AW
    return {'recoloured': AW.restyle_structures(world())}


def step_bunker():
    import awl_world as AW
    return AW.bunker(world())


def step_arena():
    import awl_world as AW
    return AW.arena(world())


def step_jump():
    import awl_world as AW
    return AW.jump(world())


def step_landmarks():
    import awl_world as AW
    return AW.landmarks(world())


def step_borders():
    import awl_world as AW
    return AW.border_massifs(world())


def step_scatter():
    import awl_world as AW
    return AW.scatter(world())


def step_devspawns():
    import awl_world as AW
    return AW.dev_spawns(world())


LOD_PREFIXES = ('AW_CoolingTower', 'AW_Reactor_Workshop', 'AW_Massif_', 'AW_Bunker_Mound', 'AW_Viaduct', 'AW_Pylons',
                'AW_Arena_Wall', 'AW_Forest_', 'AW_Chimney', 'AW_Pipeline')


def step_lod():
    """LOD1 (50 %) / LOD2 (25 %) for heavy static meshes, as hidden children with identity transforms (ImportedLevel
    builds the LODGroups): the far, simplified versions of the landmarks."""
    import awl_world as AW
    lcoll = AW.coll('LOD')
    made, cache = 0, {}
    zone = bpy.data.collections[ZONE]
    for o in list(zone.all_objects):
        if o.type != 'MESH' or o.get('unity_lod_level') or o.get('tw_no_export') or o.get('tw_hidden'):
            continue
        if not o.name.startswith(LOD_PREFIXES) or L.tri_count(o.data) < 2500:
            continue
        for level, ratio, size in ((1, 0.5, 0.25), (2, 0.22, 0.08)):
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
            lo['editing_zone'] = 2
            lo['tw_stage'] = 'LOD of an Ashen Winter mesh'
            lo.hide_render = True
            made += 1
        o['unity_lod_screen_size'] = 0.25
    return {'lod_objects': made}


def main():
    a = args()
    W.use_textures()
    report = {'steps': {}, 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    for step in a.steps.split(','):
        t = time.time()
        res = globals()['step_' + step]()
        report['steps'][step] = {'seconds': round(time.time() - t, 1), 'result': res}
        print('AWL_BUILD step', step, report['steps'][step], flush=True)
    bpy.context.scene['aw_build_report'] = json.dumps(report)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True)
    print('AWL_BUILD saved', a.out, flush=True)


if __name__ == '__main__':
    main()
