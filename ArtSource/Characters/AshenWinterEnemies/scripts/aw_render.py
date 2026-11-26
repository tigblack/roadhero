"""Presentation renders of the Ashen Winter enemies (EEVEE): front / side / back turnaround, a 3/4 hero view, the
concept sheet's own angle for every creature (for side-by-side comparison) and the game camera's angle (54 deg).

    Blender -b AshenWinter_Enemies_v1.blend --python aw_render.py -- --out <dir> [--res 768] [--only pecker,...]
            [--views front,side,back,three,concept,game] [--silhouettes]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import aw_lib as A  # noqa: E402,F401  (puts the mutant kit on sys.path)
import mut_render as MR  # noqa: E402

VIEWS = ('front', 'side', 'back', 'three', 'concept', 'game')
# direction from the creature to the camera (creature faces +y), lens, distance factor: the concept sheet's angle
CONCEPT_VIEW = {
    'AW_AshPecker':      (Vector((1.0, 0.3, 0.3)), 55, 2.3),
    'AW_SnowReaper':     (Vector((0.55, 1.0, 0.55)), 50, 2.0),
    'AW_NeedleWalker':   (Vector((-1.0, 0.35, 0.22)), 50, 1.9),
    'AW_BoilerSpitter':  (Vector((0.45, 1.0, 0.42)), 50, 2.0),
    'AW_Executioner':    (Vector((0.55, 1.0, 0.35)), 50, 1.9),
    'AW_WhiteoutRaider': (Vector((-0.75, 1.0, 0.45)), 50, 1.65),
    'AW_BlackReactor':   (Vector((0.4, 1.0, 0.18)), 45, 1.7),
}


def studio():
    """The concept sheet's stage: cold light grey world, soft cool key, snowy ground."""
    cam = MR.studio(bg=(0.80, 0.82, 0.85), ground=(0.78, 0.79, 0.82))
    key = bpy.data.objects.get('MUT_Key')
    if key is not None:
        key.data.color = (0.98, 0.98, 1.0)
        key.data.energy = 2.3
    w = bpy.context.scene.world
    if w is not None and w.node_tree is not None:
        w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.95
    return cam


def render(root, out_dir, res=768, views=VIEWS):
    sc = bpy.context.scene
    cam = sc.camera
    out = []
    plain = [v for v in views if v != 'concept']
    if plain:
        out += MR.render(root, out_dir, res, plain)
    if 'concept' in views and root.name in CONCEPT_VIEW:
        roots = [o for o in bpy.data.objects if o.get('mut_root')]
        for r in roots:
            for o in [r] + list(r.children_recursive):
                o.hide_render = (r != root) or bool(o.get('unity_lod_level'))
        lo, hi = MR.bounds(root)
        ctr = (lo + hi) * 0.5
        size = hi - lo
        d, lens, k = CONCEPT_VIEW[root.name]
        sc.render.resolution_x = res
        sc.render.resolution_y = res
        cam.data.type = 'PERSP'
        cam.data.lens = lens
        cam.data.clip_start = 0.05
        cam.data.clip_end = 400
        span = max(size.x, size.y, size.z)
        MR.aim(cam, ctr, d, span * k + 0.6)
        path = os.path.join(out_dir, f'{root.name}_concept.png')
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
        for r in roots:
            for o in [r] + list(r.children_recursive):
                o.hide_render = bool(o.get('unity_lod_level'))
    return out


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--res', type=int, default=768)
    p.add_argument('--only', default='')
    p.add_argument('--views', default=','.join(VIEWS))
    p.add_argument('--silhouettes', action='store_true')
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    studio()
    only = [s for s in a.only.split(',') if s]
    for r in [o for o in bpy.data.objects if o.get('mut_root')]:
        if only and not any(k.lower() in r.name.lower() for k in only):
            continue
        render(r, a.out, a.res, a.views.split(','))
        print('AW_RENDER', r.name, flush=True)
    if a.silhouettes:
        MR.silhouettes(a.out)
        print('AW_SILHOUETTES', flush=True)


if __name__ == '__main__':
    main()
