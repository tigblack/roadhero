"""Render v13 comparison shots. blender -b FILE --python render13.py -- --out DIR [--clay 1] [--shots a,b] [--samples N] [--closeups 1]
Clay = neutral grey override material on the whole view layer (shape check without colour/texture)."""
import bpy, sys, os, argparse, time, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rg_cams, rg_light, rg_shots13
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--shots', default=''); ap.add_argument('--samples', type=int, default=24)
ap.add_argument('--clay', type=int, default=0); ap.add_argument('--closeups', type=int, default=0); ap.add_argument('--relight', type=int, default=1)
ap.add_argument('--names', default=''); ap.add_argument('--cams_from', default='')
a = ap.parse_args(argv); os.makedirs(a.out, exist_ok=True)
sc = bpy.context.scene
if a.relight:
    rg_light.setup(sc)
sc.eevee.taa_render_samples = a.samples
sc.render.image_settings.file_format = 'PNG'
vl = bpy.context.view_layer
if a.clay:
    m = bpy.data.materials.get('AP_Clay_Neutral') or bpy.data.materials.new('AP_Clay_Neutral')
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (0.40, 0.40, 0.40, 1)
    b.inputs['Roughness'].default_value = 0.72
    b.inputs['Specular IOR Level'].default_value = 0.35
    vl.material_override = m
roofs = [c for c in bpy.data.collections if 'Roofs' in c.name]
# hide presentation backdrop in clay (it is not level geometry)
want = set(x for x in a.shots.split(',') if x)
if not a.closeups:
    for name, kind, p in rg_shots13.SHOTS_V13:
        if want and name not in want:
            continue
        if kind == 'game':
            cam = rg_cams.game_camera('R13_' + name, p['car'], p.get('floor', 0.0)); sc.render.resolution_x, sc.render.resolution_y = rg_cams.W, rg_cams.H
        else:
            cam = rg_cams.free_camera('R13_' + name, p['loc'], p['look'], p.get('lens', 35)); sc.render.resolution_x, sc.render.resolution_y = p.get('res', (1400, 900))
        for c in roofs:
            for o in c.objects:
                o.hide_render = bool(p.get('hide_roofs'))
        sc.camera = cam; sc.render.filepath = os.path.join(a.out, name + '.png')
        t = time.time(); bpy.ops.render.render(write_still=True); print('R13', name, round(time.time() - t, 1), flush=True)
        bpy.data.objects.remove(cam)
else:
    import json
    names = [n for n in a.names.split(',') if n] or rg_shots13.CLOSEUPS_V13
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    fixed = json.load(open(a.cams_from)) if a.cams_from else {}
    used = {}
    d = Vector((-0.6, -1.0, 0.75)).normalized()
    for nm in names:
        o = bpy.data.objects.get(nm)
        if not o:
            print('MISSING', nm); continue
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
        c = (mn + mx) / 2; r = (mx - mn).length / 2
        cd = bpy.data.cameras.new('cu13'); cd.lens = 40; cd.clip_start = 0.05; cd.clip_end = 5000
        cam = bpy.data.objects.new('cu13', cd); sc.collection.objects.link(cam)
        dist = r / math.tan(cd.angle / 2) * 1.05
        if nm in fixed:
            cam.location = Vector(fixed[nm][0]); cam.rotation_euler = fixed[nm][1]
        else:
            cam.location = c + d * dist
            cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        used[nm] = [list(cam.location), list(cam.rotation_euler)]
        sc.camera = cam
        sc.render.filepath = os.path.join(a.out, nm.replace('/', '_') + '.png')
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam)
        print('CU13', nm, flush=True)
    json.dump(used, open(os.path.join(a.out, '_closeup_cams.json'), 'w'), indent=1)
