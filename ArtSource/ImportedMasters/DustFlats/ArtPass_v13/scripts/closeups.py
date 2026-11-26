"""Render close-ups of named objects (headless). -- --out DIR --names a,b,c [--rig v11]"""
import bpy, sys, os, argparse, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
argv = sys.argv[sys.argv.index('--') + 1:]
ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--names'); ap.add_argument('--rig', default='asis')
ap.add_argument('--dir', default='-0.6,-1.0,0.75'); ap.add_argument('--fill', type=float, default=1.0)
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)
sc = bpy.context.scene
if a.rig == 'v11':
    import rg_light; rg_light.setup(sc)
sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = 900, 700
d = Vector([float(x) for x in a.dir.split(',')]).normalized()
for nm in a.names.split(','):
    o = bpy.data.objects.get(nm)
    if not o: print('MISSING', nm); continue
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    for ch in o.children_recursive:
        if ch.type == 'MESH': pts += [ch.matrix_world @ Vector(c) for c in ch.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (mn + mx) / 2; r = (mx - mn).length / 2 * a.fill
    cd = bpy.data.cameras.new('cu'); cd.lens = 40; cd.clip_end = 5000
    cam = bpy.data.objects.new('cu', cd); sc.collection.objects.link(cam)
    dist = r / math.tan(cd.angle / 2) * 1.05
    cam.location = c + d * dist
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(a.out, nm.replace('/', '_') + '.png')
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    print('CU', nm)
