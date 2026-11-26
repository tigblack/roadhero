"""Render the shared shot list from the currently opened .blend (run headless).
blender -b FILE.blend --python render_shots.py -- --out DIR [--rig asis|v11] [--shots a,b] [--samples N] [--scale 100]"""
import bpy, sys, os, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rg_cams
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--rig', default='asis')
ap.add_argument('--shots', default='')
ap.add_argument('--samples', type=int, default=24)
ap.add_argument('--scale', type=int, default=100)
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)
sc = bpy.context.scene
if a.rig == 'v11':
    import rg_light
    rg_light.setup(sc)
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = a.samples
sc.render.resolution_percentage = a.scale
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False
roof_cols = [c for c in bpy.data.collections if 'Roofs' in c.name]
wanted = set(s for s in a.shots.split(',') if s)
for name, kind, p in rg_cams.SHOTS:
    if wanted and name not in wanted: continue
    if kind == 'game':
        car = p['car']
        cam = rg_cams.game_camera('SHOT_' + name, car, p.get('floor', 0.0))
        sc.render.resolution_x, sc.render.resolution_y = rg_cams.W, rg_cams.H
    else:
        cam = rg_cams.free_camera('SHOT_' + name, p['loc'], p['look'], p.get('lens', 35))
        sc.render.resolution_x, sc.render.resolution_y = p.get('res', (1400, 900))
    hide = p.get('hide_roofs', False)
    for c in roof_cols:
        for o in c.objects: o.hide_render = hide or o.get('_was_hidden', False)
    sc.camera = cam
    sc.render.filepath = os.path.join(a.out, name + '.png')
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {name} {time.time()-t:.1f}s", flush=True)
    bpy.data.objects.remove(cam)
