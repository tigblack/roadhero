"""Top-down orthographic plan render with gameplay overlays (roads, floors, keep-outs, routes, spawns)
and optional candidate river / boundary polylines from data/plan_*.json."""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, imgtools, rg_level, rg_light
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]; extra = argv[1:]
X0, X1, Y0, Y1, PPM = -135.0, 135.0, -265.0, 115.0, 4.0
W, H = int((X1 - X0) * PPM), int((Y1 - Y0) * PPM)
sc = bpy.context.scene
rg_light.setup(sc)
cd = bpy.data.cameras.new('plan'); cd.type = 'ORTHO'; cd.sensor_fit = 'VERTICAL'; cd.ortho_scale = (Y1 - Y0); cd.clip_end = 2000
cam = bpy.data.objects.new('plan', cd); sc.collection.objects.link(cam)
cam.location = ((X0 + X1) / 2, (Y0 + Y1) / 2, 300); cam.rotation_euler = (0, 0, 0)
sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.resolution_percentage = 100
sc.eevee.taa_render_samples = 8
for c in bpy.data.collections:
    if 'Roofs' in c.name:
        for o in c.objects: o.hide_render = True
tmp = out.replace('.png', '_raw.png'); sc.render.filepath = tmp
bpy.ops.render.render(write_still=True)
img = imgtools.load(tmp)
def px(x, y): return (x - X0) * PPM, (Y1 - y) * PPM
def line(pts, col, w=1.5):
    for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
        a = px(xa, ya); b = px(xb, yb)
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) + 1)
        for t in np.linspace(0, 1, n + 1):
            x = a[0] + (b[0] - a[0]) * t; y = a[1] + (b[1] - a[1]) * t
            if not (w < x < W - w - 1 and w < y < H - w - 1):
                continue
            img[int(y - w):int(y + w + 1), int(x - w):int(x + w + 1), :3] = col
def rect(r, col, w=1.0):
    cx, cy = r['center'][0], r['center'][2]; hx, hy = r['half']; a = math.radians(r.get('yaw', 0))
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)):
        lx, ly = sx * hx, sy * hy
        corners.append((cx + lx * math.cos(a) + ly * math.sin(a), cy - lx * math.sin(a) + ly * math.cos(a)))
    line(corners, col, w)
lv = rg_level.Level(sc)
for pts, wdt in lv.roads:
    line([tuple(p) for p in pts], (1, 0.9, 0.2), 1.0)
for f in lv.floors: rect(f['rect'], (0.2, 0.9, 1.0), 1.0)
for k in lv.keepouts: rect(k, (1.0, 0.2, 0.9), 0.8)
for pts, wdt in lv.routes: line([tuple(p) for p in pts], (1, 1, 1), 1.5)
for (x, y, r, kind, name) in lv.spawns:
    col = (1, 0.1, 0.1) if kind in ('Foot', 'Vehicle', 'Boss') else (0.1, 0.1, 0.1)
    a = px(x, y)
    if 3 < a[0] < W - 3 and 3 < a[1] < H - 3:
        img[int(a[1]) - 2:int(a[1]) + 3, int(a[0]) - 2:int(a[0]) + 3, :3] = col
# grid every 20 m with labels
for gx in range(-120, 121, 20):
    a = px(gx, Y1); img[:, int(a[0]):int(a[0]) + 1, :3] *= 0.6
    imgtools.text(img, str(gx), int(a[0]) + 2, 4, 2)
for gy in range(-260, 111, 20):
    a = px(X0, gy); img[int(a[1]):int(a[1]) + 1, :, :3] *= 0.6
    imgtools.text(img, str(gy), 4, int(a[1]) + 2, 2)
for path in extra:
    d = json.load(open(path))
    for poly in d.get('polylines', []):
        line([tuple(p) for p in poly['pts']], tuple(poly.get('color', (0.1, 0.4, 1.0))), poly.get('w', 2.0))
imgtools.save(img, out)
os.remove(tmp)
print('PLAN', out, W, H)
