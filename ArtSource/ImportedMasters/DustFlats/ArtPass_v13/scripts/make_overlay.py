import json, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rg_layout12 as LY
poly = LY.boundary_polygon(1.0)
R = LY.River(0.5)
wh = R.water_halfwidth()
corr = R.A[:, 0] + R.A[:, 1]
left = R.P + R.N * corr[:, None]; right = R.P - R.N * corr[:, None]
wl = R.P + R.N * wh[:, None]; wr = R.P - R.N * wh[:, None]
pl = [dict(pts=np.vstack([poly, poly[:1]]).tolist(), color=(1, 1, 1), w=2.0),
      dict(pts=left.tolist(), color=(0.05, 0.25, 0.9), w=1.2), dict(pts=right.tolist(), color=(0.05, 0.25, 0.9), w=1.2),
      dict(pts=wl.tolist(), color=(0.2, 0.9, 0.9), w=0.8), dict(pts=wr.tolist(), color=(0.2, 0.9, 0.9), w=0.8)]
for k, col in (('ford', (0.1, 1.0, 0.2)), ('bridge', (1.0, 0.5, 0.0)), ('bridge2', (1.0, 0.5, 0.0))):
    idx = [i for i, kk in enumerate(R.kind) if kk == k]
    runs = []
    for a in idx:
        if runs and a == runs[-1][-1] + 1: runs[-1].append(a)
        else: runs.append([a])
    for r in runs: pl.append(dict(pts=R.P[r].tolist(), color=col, w=3.0))
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json.dump(dict(polylines=pl), open(os.path.join(root, 'data', 'plan_overlay.json'), 'w'))
print('OVL river length', round(R.length, 1), 'stations', len(R.P), 'boundary pts', len(poly))
