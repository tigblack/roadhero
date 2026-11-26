"""Character sheet renders: builds the characters into a copy of the base and renders each type alone.

    Blender -b <base.blend> --python tw_preview_chars.py -- --out DIR [--models Scav,Raider] [--save X.blend]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tw_lib as L  # noqa: E402
import tw_present as PR  # noqa: E402
import tw_chars as CH  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--models', default='')
ap.add_argument('--save', default='')
ap.add_argument('--tex', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'textures'))
ap.add_argument('--views', default='front,back,game')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
os.makedirs(a.out, exist_ok=True)
L.TEX_DIR = os.path.abspath(a.tex)
models = [m for m in a.models.split(',') if m] or list(CH.BUILDERS)
rep = CH.build_all(models)
PR.setup(48)
floor = PR.ground_plane(400, (0.17, 0.165, 0.11))
for model in models:
    roots = CH.spawn_roots(model)
    if not roots:
        continue
    root = roots[0]
    keep = set([root] + list(root.children_recursive))
    for o in bpy.data.objects:
        if o.type in ('MESH', 'EMPTY'):
            o.hide_render = o not in keep and o != floor
    floor.location = (root.matrix_world.translation.x, root.matrix_world.translation.y, root.matrix_world.translation.z - 0.002)
    pts = [o.matrix_world @ Vector(c) for o in keep if o.type == 'MESH' for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (mn + mx) / 2
    size = max(mx - mn)
    fwd = root.matrix_world.to_3x3() @ Vector((0, 1, 0))
    fwd.z = 0
    fwd.normalize()
    right = fwd.cross(Vector((0, 0, 1)))
    views = {
        'front': c + (fwd * 1.0 + right * 0.55 + Vector((0, 0, 0.42))).normalized() * size * 1.9,
        'back': c + (-fwd * 1.0 - right * 0.6 + Vector((0, 0, 0.5))).normalized() * size * 1.9,
        'game': c + Vector((0, -math.cos(math.radians(54)), math.sin(math.radians(54)))) * size * 3.2,
    }
    for vn in a.views.split(','):
        cam = PR.free_camera('cam_' + vn, views[vn], c, lens=55 if vn != 'game' else 40)
        PR.render(cam, os.path.join(a.out, f'{model}_{vn}.png'), (900, 900))
    print('TW_PREVIEW', model, rep.get(model), flush=True)
for o in bpy.data.objects:
    if o.type in ('MESH', 'EMPTY') and o != floor:
        o.hide_render = False
if floor is not None:
    bpy.data.objects.remove(floor)
if a.save:
    bpy.ops.wm.save_as_mainfile(filepath=a.save, compress=True)
