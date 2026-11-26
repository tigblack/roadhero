"""DustFlats v13 'SmoothPass' — runs on the CURRENTLY OPEN file (v12 River scene incl. live changes).

  live session:  exec(open('.../build_v13.py').read())  with BUILD_ARGS = {...}
  headless:      Blender -b ArtPass_v13/source/v12_live_snapshot.blend --python ArtPass_v13/scripts/build_v13.py -- --save X.blend --steps a,b
"""
import bpy, sys, os, time, json, importlib
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else globals().get('BUILD_HERE')
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for m in ('rg_lib', 'rg_kit', 'rg_rocks', 'rg_level', 'rg_layout12', 'rg_sculpt', 'rg_round'):
    if m in sys.modules:
        importlib.reload(sys.modules[m])
import rg_lib as L, rg_level, rg_layout12 as LY

STEPS = ['terrain', 'roads', 'massif', 'perimeter', 'ramps', 'buildings', 'props', 'river', 'lod', 'finalize']
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
ctx['mats'] = {k: bpy.data.materials[k] for k in ('Toon', 'Ground', 'Road0', 'Rock_Strata', 'Trim_Structures', 'ToonFlat') if k in bpy.data.materials}
import step_ground as SG
ctx['ground_sampler'] = SG.GroundSampler(bpy.data.objects['Ground'])
t0 = time.time()
for s in STEPS:
    if s not in steps:
        continue
    t = time.time()
    mod = importlib.import_module('step13_' + s)
    importlib.reload(mod)
    mod.run(ctx)
    print(f'BUILD13 step {s} {time.time() - t:.1f}s', flush=True)
prev = json.loads(sc.get('artpass_v13_stats', '{}') or '{}')
prev.update(ctx['stats'])
sc['artpass_v13_stats'] = json.dumps(prev, default=str)
if args.get('save'):
    path = args['save'] if os.path.isabs(args['save']) else os.path.join(root, args['save'])
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True, relative_remap=True)
    print('BUILD13 saved', path, flush=True)
print(f'BUILD13 total {time.time() - t0:.1f}s', flush=True)
