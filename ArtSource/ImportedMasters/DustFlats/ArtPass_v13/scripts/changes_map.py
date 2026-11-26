"""Changed-areas map: v11 outline (red) vs v12 outline (white), river corridor (blue), water edge (cyan),
fords (green), bridges (orange), moved spawn roots (magenta arrows)."""
import json, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rg_layout12 as LY
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = LY.River(0.5); poly = LY.boundary_polygon(1.0); wh = R.water_halfwidth()
corr = R.A[:, 0] + R.A[:, 1]
pl = []
old = [(-12.6, -99), (-94.3, -99), (-94.3, 94.7), (16, 94.7)]
old2 = [(12.6, -99.5), (94.7, -99.5), (94.7, 100)]
for o in (old, old2):
    pl.append(dict(pts=o, color=(0.95, 0.15, 0.1), w=1.6))
pl.append(dict(pts=np.vstack([poly, poly[:1]]).tolist(), color=(1, 1, 1), w=2.0))
for sgn in (1, -1):
    pl.append(dict(pts=(R.P + R.N * sgn * corr[:, None]).tolist(), color=(0.05, 0.25, 0.9), w=1.2))
    pl.append(dict(pts=(R.P + R.N * sgn * wh[:, None]).tolist(), color=(0.2, 0.9, 0.9), w=0.8))
d = json.load(open(os.path.join(root, 'data', 'river_v12.json')))
for f in d['fords']:
    c = np.array([f['centre'][0], f['centre'][2]]); a = np.array(f['across'])
    pl.append(dict(pts=[(c - a * 12).tolist(), (c + a * 12).tolist()], color=(0.1, 1.0, 0.2), w=3.0))
for b in d['bridges']:
    pts = [(s['p'][0], s['p'][2]) for s in b['deck']]
    pl.append(dict(pts=pts, color=(1.0, 0.5, 0.0), w=3.5))
for m in d['moved_spawns']:
    pl.append(dict(pts=[m['blender_from'], m['blender_to']], color=(1.0, 0.1, 0.9), w=1.2))
json.dump(dict(polylines=pl), open(os.path.join(root, 'data', 'changes_overlay.json'), 'w'))
print('OVL ok')
