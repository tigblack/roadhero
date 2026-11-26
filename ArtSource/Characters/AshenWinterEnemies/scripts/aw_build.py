"""Build AshenWinter_Enemies_v1.blend: the seven enemies of the third zone, one collection per creature.

    Blender -b --factory-startup --python aw_build.py -- --out ../AshenWinter_Enemies_v1.blend
            [--only pecker,reaper] [--render <dir> --res 768 --views concept,three] [--no-finish]

Runs the atlas generator first if the texture is missing. Each creature: rigid parts at their joints (see
aw_creatures.py), vertex AO baked on the assembled rest pose, LOD1 copies (50 %) under every heavy part.
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

import aw_lib as A  # noqa: E402
import aw_creatures as AC  # noqa: E402
import aw_render as AR  # noqa: E402

ORDER = ['pecker', 'reaper', 'walker', 'boiler', 'executioner', 'raider', 'reactor']
SPACING = {'pecker': 5.0, 'reaper': 7.0, 'walker': 7.0, 'boiler': 7.0, 'executioner': 8.0, 'raider': 9.0, 'reactor': 14.0}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='')
    p.add_argument('--only', default='')
    p.add_argument('--render', default='')
    p.add_argument('--res', type=int, default=768)
    p.add_argument('--views', default='front,side,back,three,concept,game')
    p.add_argument('--no-finish', action='store_true')
    a = p.parse_args(argv)
    t0 = time.time()
    tex = os.path.join(A.ART, 'textures', A.TEX_NAME)
    if not os.path.exists(tex):
        subprocess.run([sys.executable, os.path.join(HERE, 'aw_enemy_tex.py'), os.path.dirname(tex)], check=True)
    A.clear_scene()
    A.use_textures()
    only = [s for s in a.only.split(',') if s]
    names = [n for n in ORDER if n in AC.BUILDERS and (not only or n in only)]
    report = {}
    x = 0.0
    for n in names:
        cr = AC.BUILDERS[n]((x, 0, 0))
        x += SPACING[n]
        A.mirror_x(cr)
        AC.apply_shadows(cr)
        tris = cr.finish(ao=0.55, ao_dist=0.35 if n != 'reactor' else 0.9) if not a.no_finish else 0
        report[n] = (len(cr.meshes()), tris)
        print(f'AW_BUILT {n}: parts={len(cr.meshes())} tris={tris}', flush=True)
    if a.render:
        os.makedirs(a.render, exist_ok=True)
        AR.studio()
        for r in [o for o in bpy.data.objects if o.get('mut_root')]:
            AR.render(r, a.render, a.res, a.views.split(','))
    if a.out:
        studio = bpy.data.collections.get('MUT_Studio')
        if studio is not None:
            for o in list(studio.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(studio)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out), compress=True)
    print('AW_BUILD_DONE', report, f'{time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()
