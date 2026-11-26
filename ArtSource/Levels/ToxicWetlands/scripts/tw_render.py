"""Presentation renders of the Toxic Wetlands pass (EEVEE, Blender only; the .blend is not saved).

    Blender -b ToxicWetlands_Zone01_v1.blend --python tw_render.py -- --out DIR [--samples 64]

Writes: zone overview, arena overview, the Sludge Baron close-up, a studio shot of each of the six enemies (front and
game-camera height) and game-camera views of the zone. Lighting / tonemapping: tw_present (v13 recipe).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tw_chars as CH  # noqa: E402
import tw_present as PR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--samples', type=int, default=64)
ap.add_argument('--only', default='')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
os.makedirs(a.out, exist_ok=True)
only = set(x for x in a.only.split(',') if x)
PR.setup(a.samples)


def want(name):
    return not only or name in only


def render(cam, name, res):
    PR.render(cam, os.path.join(a.out, name + '.png'), res)
    print('TW_RENDER', name, flush=True)


# Unity (x, z) -> Blender (x, y)
if want('zone_overview'):
    render(PR.free_camera('R_overview', (95.0, 70.0, 150.0), (-5.0, 205.0, 0.0), lens=30), 'zone_overview', (1800, 1200))
if want('zone_top'):
    render(PR.free_camera('R_top', (0.0, 200.0, 320.0), (0.0, 200.01, 0.0), ortho=212.0), 'zone_top', (1600, 1600))
if want('arena_overview'):
    render(PR.free_camera('R_arena', (16.0, 222.0, 34.0), (-15.6, 264.0, 1.0), lens=30), 'arena_overview', (1800, 1200))
if want('arena_low'):
    render(PR.free_camera('R_arena_low', (-2.0, 232.0, 7.5), (-18.0, 268.0, 4.0), lens=28), 'arena_low', (1800, 1000))
if want('entry'):
    render(PR.free_camera('R_entry', (40.0, 108.0, 22.0), (0.0, 150.0, 0.0), lens=30), 'entry_dam', (1800, 1100))

# game camera (Unity CameraRig: pitch 54, vFOV 46, 540 x 1170)
GAME = {'game_01_entry': (22, 116), 'game_02_camp_west': (-46, 160), 'game_03_pipe_tunnel': (-14.5, 172),
        'game_04_underpass': (14, 196), 'game_05_camp_east': (50, 200), 'game_06_arena': (-12, 250),
        'game_07_north_east': (36, 272), 'game_08_ford': (-60, 128), 'game_09_moat_west': (-44, 262)}
for name, (x, z) in GAME.items():
    if want(name) or want('game'):
        render(PR.game_camera('R_' + name, (x, z)), name, (540, 1170))

# the boss in his arena
boss_roots = CH.spawn_roots('BossBaron')
if boss_roots and (want('boss_close') or want('boss')):
    b = boss_roots[0]
    c = b.matrix_world.translation + Vector((0, 0, 5.2))
    fwd = (b.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
    side = fwd.cross(Vector((0, 0, 1)))
    render(PR.free_camera('R_boss', c + fwd * 13.5 + side * 6.0 + Vector((0, 0, 1.8)), c, lens=50), 'boss_close', (1400, 1400))
    render(PR.free_camera('R_boss_back', c - fwd * 12.0 + side * 7.0 + Vector((0, 0, 4.0)), c, lens=50), 'boss_back', (1400, 1400))

# enemies: move one instance of each type to a studio plot west of the zone (not saved)
if want('enemies'):
    floor = PR.ground_plane(60, (0.16, 0.155, 0.10))
    floor.location = (-300.0, 0.0, 0.0)
    studio = Vector((-300.0, 0.0, 0.0))
    models = ['Scav', 'Raider', 'Spearman', 'Crossbow', 'Brute', 'Buggy']
    roots = {m: CH.spawn_roots(m)[0] for m in models}
    keep = set([floor])
    for m, r in roots.items():
        keep.add(r)
        keep.update(r.children_recursive)
    for o in bpy.data.objects:
        if o.type in ('MESH', 'EMPTY'):
            o.hide_render = o not in keep
    for m, r in roots.items():
        for o in roots.values():
            for x in [o] + list(o.children_recursive):
                if x.type == 'MESH':
                    x.hide_render = o is not r
        r.location = studio
        r.rotation_euler = Euler((0, 0, math.radians(180.0)))       # face the camera at -y
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in [r] + list(r.children_recursive) if o.type == 'MESH' for c in o.bound_box]
        mn = Vector([min(p[i] for p in pts) for i in range(3)])
        mx = Vector([max(p[i] for p in pts) for i in range(3)])
        c = (mn + mx) / 2
        size = max(mx - mn)
        cam = PR.free_camera('R_en_' + m, c + Vector((size * 0.8, -size * 1.7, size * 0.85)), c, lens=50)
        render(cam, 'enemy_%s' % m, (900, 900))
        cam2 = PR.free_camera('R_eng_' + m, c + Vector((0.0, -size * 1.9, size * 2.6)), c + Vector((0, 0, -size * 0.1)), lens=50)
        render(cam2, 'enemy_%s_top' % m, (900, 900))
