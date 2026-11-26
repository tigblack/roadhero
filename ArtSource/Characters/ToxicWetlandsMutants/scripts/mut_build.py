"""Build ToxicWetlands_Mutants_v2.blend: the seven mutants of the second zone, one collection per creature.

    Blender -b --factory-startup --python mut_build.py -- --out ../ToxicWetlands_Mutants_v2.blend
            [--only leechling,crab] [--render <dir> --res 512] [--no-finish]

Runs the atlas generator first if the texture is missing. Each creature: rigid parts at their joints (see
mut_creatures.py), vertex AO baked on the assembled rest pose, LOD1 copies (50 %) under every heavy part.
"""
import argparse
import os
import subprocess
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import mut_lib as M  # noqa: E402
import mut_creatures as MC  # noqa: E402
import mut_render as MR  # noqa: E402

ORDER = ['leechling', 'crab', 'stalker', 'toad', 'brute', 'engine', 'mother']
SPACING = 9.0


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='')
    p.add_argument('--only', default='')
    p.add_argument('--render', default='')
    p.add_argument('--res', type=int, default=512)
    p.add_argument('--views', default='front,side,back,three,game')
    p.add_argument('--no-finish', action='store_true')
    a = p.parse_args(argv)
    t0 = time.time()
    tex = os.path.join(M.ART, 'textures', M.TEX_NAME)
    if not os.path.exists(tex):
        subprocess.run([sys.executable, os.path.join(HERE, 'mut_tex.py'), os.path.dirname(tex)], check=True)
    M.clear_scene()
    only = [s for s in a.only.split(',') if s]
    names = [n for n in ORDER if n in MC.BUILDERS and (not only or n in only)]
    report = {}
    for i, n in enumerate(names):
        cr = MC.BUILDERS[n]((i * SPACING, 0, 0))
        MC.apply_shadows(cr)
        tris = cr.finish() if not a.no_finish else 0
        report[n] = (len(cr.meshes()), tris)
        print(f'MUT_BUILT {n}: parts={len(cr.meshes())} tris={tris}', flush=True)
    if a.render:
        os.makedirs(a.render, exist_ok=True)
        MR.studio()
        for r in [o for o in bpy.data.objects if o.get('mut_root')]:
            MR.render(r, a.render, a.res, a.views.split(','))
    if a.out:
        studio = bpy.data.collections.get(MR.STUDIO)
        if studio is not None:
            for o in list(studio.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(studio)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out), compress=True)
    print('MUT_BUILD_DONE', report, f'{time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()
