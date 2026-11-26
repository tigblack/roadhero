"""Presentation renders of the Ashen Winter zone (EEVEE): the concept sheet's panorama angle, its three insets (the
jump ramp, the bunker, the arena) and views from the game camera's angle (pitch 54 deg).

    Blender -b AshenWinter_Zone02_v1.blend --python awl_render.py -- --out <dir> [--res 1280] [--only overview,...]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STAGE = 'AWL_Stage'
# name: (camera position, look-at point, lens) in Blender coordinates (x, y = Unity z, z up)
VIEWS = {
    'overview':   ((-34.0, 286.0, 62.0), (8.0, 420.0, 0.0), 30),
    'overview_n': ((-60.0, 398.0, 70.0), (10.0, 470.0, 0.0), 32),
    'ramp':       ((8.0, 304.0, 10.5), (29.0, 333.0, 1.0), 28),
    'bunker':     ((4.0, 338.0, 4.2), (3.0, 368.0, 4.0), 30),
    'arena':      ((9.0, 414.0, 16.0), (8.0, 470.0, 3.0), 30),
    'landmarks':  ((-10.0, 430.0, 30.0), (-20.0, 490.0, 8.0), 28),
    'viaduct':    ((-60.0, 340.0, 14.0), (-88.0, 380.0, 6.0), 28),
}
GAME = {'game_bunker': (3.0, 366.0), 'game_arena': (8.0, 450.0), 'game_ramp': (28.0, 326.0), 'game_tower': (-30.0, 470.0),
        'game_camp': (-55.0, 400.0)}


def stage():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.view_settings.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = -0.1
    try:
        sc.eevee.taa_render_samples = 32
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    w = bpy.data.worlds.get('AWL_World') or bpy.data.worlds.new('AWL_World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.62, 0.66, 0.72, 1.0)
    bg.inputs['Strength'].default_value = 0.9
    coll = bpy.data.collections.get(STAGE)
    if coll is None:
        coll = bpy.data.collections.new(STAGE)
        sc.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sun = bpy.data.objects.new('AWL_Sun', bpy.data.lights.new('AWL_Sun', 'SUN'))
    sun.data.energy = 2.6
    sun.data.angle = math.radians(12)
    sun.data.color = (0.97, 0.98, 1.0)
    sun.rotation_euler = (math.radians(48), math.radians(-14), math.radians(-30))
    coll.objects.link(sun)
    cam = bpy.data.objects.new('AWL_Cam', bpy.data.cameras.new('AWL_Cam'))
    coll.objects.link(cam)
    sc.camera = cam
    enemy = ('_Scav', '_Raider', '_Spearman', '_Crossbow', '_Brute', '_Buggy', '_BossColossus')
    for o in bpy.data.objects:
        if o.get('tw_hidden') or o.get('unity_lod_level') or (o.users_collection and any(c.name in ('Collision', 'LOD') for c in o.users_collection)):
            o.hide_render = True
        # the snapshot's generated enemies (the game swaps them for the Ashen Winter creatures): not part of the level
        if o.name.startswith('Spawn_2') and o.name.split('.')[0].endswith(enemy):
            for c in [o] + list(o.children_recursive):
                c.hide_render = True
    return cam


def aim(cam, pos, look, lens):
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.clip_start = 0.3
    cam.data.clip_end = 900


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--res', type=int, default=1280)
    p.add_argument('--only', default='')
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    cam = stage()
    sc = bpy.context.scene
    only = [s for s in a.only.split(',') if s]
    for name, (pos, look, lens) in VIEWS.items():
        if only and name not in only:
            continue
        sc.render.resolution_x = a.res
        sc.render.resolution_y = int(a.res * 9 / 16)
        aim(cam, pos, look, lens)
        sc.render.filepath = os.path.join(a.out, f'AW_{name}.png')
        bpy.ops.render.render(write_still=True)
        print('AWL_RENDER', name, flush=True)
    for name, (x, z) in GAME.items():
        if only and name not in only:
            continue
        pitch = math.radians(54)
        dist = 46.0
        focus = Vector((x, z, 0.0))
        pos = focus + Vector((0, -math.cos(pitch) * dist, math.sin(pitch) * dist))
        sc.render.resolution_x = int(a.res * 0.5)
        sc.render.resolution_y = int(a.res * 0.5 * 19.5 / 9)
        aim(cam, pos, focus, 32)
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.angle_y = math.radians(46)
        sc.render.filepath = os.path.join(a.out, f'AW_{name}.png')
        bpy.ops.render.render(write_still=True)
        cam.data.sensor_fit = 'AUTO'
        print('AWL_RENDER', name, flush=True)


if __name__ == '__main__':
    main()
