"""DustFlats v12 'River' pass — runs on the CURRENTLY OPEN file (the v11 scene incl. live changes).

  live session:  exec(open('.../build_v12.py').read())  with BUILD_ARGS = {...}
  headless:      Blender -b ArtPass_v12/source/v11_live_snapshot.blend --python ArtPass_v12/scripts/build_v12.py -- --save X.blend
"""
import bpy, sys, os, time, json, importlib
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else globals().get('BUILD_HERE')
sys.path.insert(0, HERE)
import rg_lib as L, rg_level, rg_layout12 as LY
for m in ('rg_lib', 'rg_kit', 'rg_rocks', 'rg_level', 'rg_layout12'):
    importlib.reload(sys.modules[m]) if m in sys.modules else None

STEPS = ['materials', 'outline', 'river', 'bridges', 'ramps', 'buildings', 'props', 'presentation', 'finalize']
args = globals().get('BUILD_ARGS') or {}
if '--' in sys.argv:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--save', default=''); ap.add_argument('--steps', default=','.join(STEPS))
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:]); args = dict(save=a.save, steps=a.steps)
steps = [s for s in args.get('steps', ','.join(STEPS)).split(',') if s]
root = os.path.dirname(os.path.dirname(HERE))
sc = bpy.context.scene
zone = bpy.data.collections['Zone_00_DustFlats + Intro']
ctx = dict(root=root, here=HERE, level=rg_level.Level(sc), stats={}, zone=zone,
           roofs=bpy.data.collections['Zone_00_DustFlats + Intro — Roofs (toggle to inspect interiors)'],
           coll_rocks=L.ensure_collection('Zone_00 v11 — Rock scree', zone),
           coll_ground=L.ensure_collection('Zone_00 v11 — Ground drifts & ruts', zone),
           coll_river=L.ensure_collection('Zone_00 v12 — River & bridges', zone),
           river=LY.River(0.5))
_R = ctx['river']; _b = [i for i, k in enumerate(_R.kind) if k in ('bridge', 'bridge2')]
ctx['bridge_s'] = [float(_R.s[i]) for i in _b[::10]]
ctx['mats'] = {k: bpy.data.materials[k] for k in ('Toon', 'Ground', 'Road0', 'Rock_Strata', 'Trim_Structures') if k in bpy.data.materials}
import step_ground as SG
ctx['ground_sampler'] = SG.GroundSampler(bpy.data.objects['Ground'])
import rg_baseline
ctx['rock_objects'] = []
t0 = time.time()
ctx['baseline'] = rg_baseline.capture(ctx)
for s in STEPS:
    if s not in steps:
        continue
    t = time.time()
    mod = importlib.import_module('step12_' + s)
    importlib.reload(mod)
    mod.run(ctx)
    print(f'BUILD12 step {s} {time.time() - t:.1f}s', flush=True)
sc['artpass_v12_stats'] = json.dumps(ctx['stats'], default=str)
if args.get('save'):
    path = args['save'] if os.path.isabs(args['save']) else os.path.join(root, args['save'])
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True, relative_remap=True)
    print('BUILD12 saved', path, flush=True)
print(f'BUILD12 total {time.time() - t0:.1f}s', flush=True)
