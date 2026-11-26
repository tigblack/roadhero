"""Render v12 review shots. -- --out DIR [--shots a,b] [--samples N]"""
import bpy, sys, os, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rg_cams, rg_light
argv = sys.argv[sys.argv.index('--') + 1:]
ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--shots', default=''); ap.add_argument('--samples', type=int, default=24)
ap.add_argument('--relight', type=int, default=1)
a = ap.parse_args(argv); os.makedirs(a.out, exist_ok=True)
sc = bpy.context.scene
if a.relight:
    rg_light.setup(sc)
sc.eevee.taa_render_samples = a.samples
roofs = [c for c in bpy.data.collections if 'Roofs' in c.name]
want = set(x for x in a.shots.split(',') if x)
for name, kind, p in rg_cams.SHOTS_V12:
    if want and name not in want:
        continue
    if kind == 'game':
        cam = rg_cams.game_camera('R_' + name, p['car'], p.get('floor', 0.0)); sc.render.resolution_x, sc.render.resolution_y = rg_cams.W, rg_cams.H
    elif kind == 'ortho':
        cd = bpy.data.cameras.new('R_' + name); cd.type = 'ORTHO'; cd.ortho_scale = p['scale']; cd.sensor_fit = 'VERTICAL'; cd.clip_end = 3000
        cam = bpy.data.objects.new('R_' + name, cd); sc.collection.objects.link(cam)
        cam.location = (p['center'][0], p['center'][1], 400); cam.rotation_euler = (0, 0, 0)
        sc.render.resolution_x, sc.render.resolution_y = p['res']
    else:
        cam = rg_cams.free_camera('R_' + name, p['loc'], p['look'], p.get('lens', 35)); sc.render.resolution_x, sc.render.resolution_y = p.get('res', (1400, 900))
    for c in roofs:
        for o in c.objects:
            o.hide_render = bool(p.get('hide_roofs'))
    sc.camera = cam; sc.render.filepath = os.path.join(a.out, name + '.png')
    t = time.time(); bpy.ops.render.render(write_still=True); print('R12', name, round(time.time() - t, 1), flush=True)
    bpy.data.objects.remove(cam)
