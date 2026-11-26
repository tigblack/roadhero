"""Ashen Winter (third zone, index 2): gameplay layout shared by Blender and Unity.

    python3 awl_layout.py <scene.json> <out_dir>      (numpy only; any Python 3)

Reads the world metadata of the 2026-11-17 snapshot (the zone's roads and spawns are identical in the current
generator: checked by export) and writes:
  AshenWinter_layout.json   structures (arena deck and ramps, bunker tunnel, jump ramp and landing pad, landmarks),
                            keep-out rectangles for the generator, minimap marks, dev spawn points
  AshenWinter_surfaces.bytes  0.5 m base height grid of the zone (the ravine under the jump), header 'AWSF'
  AshenWinter_layout_plan.png a plan for checking (needs matplotlib; skipped without it)
Unity reads the JSON (Resources/Levels/AshenWinter_layout) in AshenSurfaces.Plan, before the zones generate: the
keep-out rectangles go to Structures.Exclusions, so World.KeepClearOfStructures moves the few spawns that stood in a
new structure's footprint (their IDs, specs and rewards stay). The Blender build places the art from the same file.
Unity axes: x right, z north (Blender y), y up.
"""
import json
import math
import os
import struct
import sys

import numpy as np

ZONE = 2
ZMIN, ZMAX = 300.0, 500.0

# ---------------------------------------------------------------------------------------------- design
ARENA = dict(x=8.4, z=464.0, radius=20.0, height=1.2, rampLength=11.0, rampHalfWidth=5.8)
BUNKER = dict(innerHalfWidth=6.6, halfLength=8.0, height=5.6, wall=1.4, moundHalfX=19.0, moundHalfZ=11.5, z0=361.0, z1=377.0)
JUMP = dict(x=28.0, z=330.0, yaw=0.0, halfWidth=3.8, length=10.0, height=2.2, boost=13.5)   # x, z = the lip
PAD = dict(x=28.0, z=349.0, radius=10.0)
RAVINE = dict(z0=331.5, z1=339.5, x0=19.0, x1=37.0, depth=0.85)
TOWER = dict(x=-38.0, z=488.0, rBase=10.0, rWaist=7.4, rTop=8.4, height=26.0)
WORKSHOP = dict(x=-8.0, z=493.0, halfX=10.0, halfZ=5.5, height=13.0)
CHIMNEY = dict(x=34.0, z=492.0, rBase=2.0, rTop=1.35, height=34.0)
PIPE_SUPPORTS = [(21.0, 492.0), (29.0, 492.5)]        # the pipe leaves the workshop's east wall (x 2) over the road
PYLONS = [(62.0, 345.0), (-52.0, 398.0), (76.0, 474.0), (-54.0, 334.0)]   # the last one clear of the repair pad (-41, 322)
VIADUCT_X = -88.5
VIADUCT_PIERS = [338.0, 356.0, 374.0, 412.0, 430.0]
VIADUCT_SPANS = [(338.0, 356.0), (356.0, 374.0), (412.0, 430.0)]
VIADUCT_STUBS = [(374.0, 383.0), (430.0, 437.0)]                 # broken span ends hanging from a pier


def polyline(points):
    return np.array(points, float).reshape(-1, 3)[:, [0, 2]]


def heading_deg(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def circle_hits(pts, cx, cz, r):
    """Points where a polyline crosses a circle: list of (x, z, segment direction)."""
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        da = math.hypot(a[0] - cx, a[1] - cz) - r
        db = math.hypot(b[0] - cx, b[1] - cz) - r
        if da * db <= 0 and da != db:
            t = da / (da - db)
            p = a + (b - a) * t
            d = (b - a) / max(np.linalg.norm(b - a), 1e-9)
            out.append((p, d))
    return out


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, float(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-9))))
    return float(np.linalg.norm(p - (a + ab * t)))


def road_dist(p, roads):
    best = 1e9
    for pts, w in roads:
        for a, b in zip(pts[:-1], pts[1:]):
            best = min(best, seg_dist(p, a, b) - w / 2)
    return best


def rect(name, x, z, hx, hz, yaw=0.0):
    return dict(name=name, x=round(x, 3), z=round(z, 3), halfX=round(hx, 3), halfZ=round(hz, 3), yaw=round(yaw, 3))


def in_rect(px, pz, r, pad=0.0):
    a = math.radians(r['yaw'])
    dx, dz = px - r['x'], pz - r['z']
    lx = dx * math.cos(a) - dz * math.sin(a)
    lz = dx * math.sin(a) + dz * math.cos(a)
    return abs(lx) <= r['halfX'] + pad and abs(lz) <= r['halfZ'] + pad


def build(scene_path):
    md = json.load(open(scene_path))['metadata']
    roads = [(polyline(r['points']), r['width']) for r in md['roads'] if r['zone'] == ZONE]
    main = roads[0][0]
    spawns = [s for s in md['spawns'] if s.get('zone') == ZONE]
    L = {'version': 1, 'zone': ZONE, 'source': os.path.basename(scene_path)}

    # ---- arena: a raised round deck on the main road, a ramp where the road meets it on either side
    cx, cz, R = ARENA['x'], ARENA['z'], ARENA['radius']
    ramps = []
    for p, d in circle_hits(main, cx, cz, R):
        out = np.array([p[0] - cx, p[1] - cz]) / R          # outward at the crossing
        along = out                                          # the ramp runs radially out of the deck
        Lr = ARENA['rampLength']
        c = p + along * (Lr / 2 - 0.6)
        yaw = heading_deg(-along[0], -along[1])              # local +z points into the deck (uphill)
        ramps.append(dict(x=round(float(c[0]), 3), z=round(float(c[1]), 3), yaw=round(yaw, 3),
                          halfX=ARENA['rampHalfWidth'], halfZ=round(Lr / 2, 3),
                          angle=round(math.degrees(math.atan2(out[1], out[0])), 2),
                          roadHeading=round(heading_deg(d[0], d[1]), 2)))
    L['arena'] = dict(ARENA, ramps=ramps)

    # ---- bunker: straight tunnel on the main road through the old canopy site
    sel = np.array([p for p in main if BUNKER['z0'] - 6 <= p[1] <= BUNKER['z1'] + 6])
    A = np.vstack([sel[:, 1], np.ones(len(sel))]).T
    kx, bx = np.linalg.lstsq(A, sel[:, 0], rcond=None)[0]      # x = kx * z + bx
    zc = 0.5 * (BUNKER['z0'] + BUNKER['z1'])
    xc = kx * zc + bx
    yaw = math.degrees(math.atan2(kx, 1.0))
    L['bunker'] = dict(BUNKER, x=round(float(xc), 3), z=round(zc, 3), yaw=round(yaw, 3))

    # ---- jump ramp on the side track, the ravine under the jump, the landing pad
    L['jump'] = dict(JUMP)
    L['pad'] = dict(PAD)
    L['ravine'] = dict(RAVINE)
    L['landmarks'] = dict(tower=TOWER, workshop=WORKSHOP, chimney=CHIMNEY,
                          pipeSupports=[dict(x=x, z=z) for x, z in PIPE_SUPPORTS],
                          pylons=[dict(x=x, z=z) for x, z in PYLONS],
                          viaduct=dict(x=VIADUCT_X, piers=VIADUCT_PIERS, spans=[list(s) for s in VIADUCT_SPANS],
                                       stubs=[list(s) for s in VIADUCT_STUBS]))

    # ---- keep-out rectangles (World.KeepClearOfStructures moves the spawns standing in them)
    ex = []
    b = L['bunker']
    ex.append(rect('AshenBunker', b['x'], b['z'], BUNKER['moundHalfX'] + 1.5, BUNKER['moundHalfZ'] + 1.5, b['yaw']))
    ex.append(rect('AshenArenaDeck', cx, cz, R + 3.0, R + 3.0, 0.0))
    for k, rp in enumerate(ramps):
        ex.append(rect('AshenArenaRamp%d' % k, rp['x'], rp['z'], rp['halfX'] + 1.5, rp['halfZ'] + 2.0, rp['yaw']))
    lipz = JUMP['z']
    ex.append(rect('AshenJump', JUMP['x'], (lipz - JUMP['length'] - 16.0 + PAD['z'] + PAD['radius']) / 2, 9.0,
                   (PAD['z'] + PAD['radius'] - (lipz - JUMP['length'] - 16.0)) / 2, 0.0))
    ex.append(rect('AshenTower', TOWER['x'], TOWER['z'], TOWER['rBase'] + 1.5, TOWER['rBase'] + 1.5))
    ex.append(rect('AshenWorkshop', WORKSHOP['x'], WORKSHOP['z'], WORKSHOP['halfX'] + 1.5, WORKSHOP['halfZ'] + 1.5))
    ex.append(rect('AshenChimney', CHIMNEY['x'], CHIMNEY['z'], CHIMNEY['rBase'] + 2.0, CHIMNEY['rBase'] + 2.0))
    for k, (x, z) in enumerate(PIPE_SUPPORTS):
        ex.append(rect('AshenPipeSupport%d' % k, x, z, 2.0, 2.0))
    for k, (x, z) in enumerate(PYLONS):
        ex.append(rect('AshenPylon%d' % k, x, z, 3.5, 3.5))
    for k, z in enumerate(VIADUCT_PIERS):
        ex.append(rect('AshenViaductPier%d' % k, VIADUCT_X, z, 3.0, 2.6))
    L['exclusions'] = ex

    # ---- conflicts: spawns inside new footprints (moved by the generator), roads under new solids (must be none)
    moved, road_hits = [], []
    for r in ex:
        for s in spawns:
            if s['kind'] == 'Boss':
                continue
            x, _, z = s['position']
            if in_rect(x, z, r, s.get('radius', 1.0) * s.get('scale', 1.0) + 0.8):
                moved.append((r['name'], s['id'], s['model']))
    solids = [r for r in ex if r['name'].startswith(('AshenTower', 'AshenWorkshop', 'AshenChimney', 'AshenPipe', 'AshenPylon', 'AshenViaduct'))]
    for r in solids:
        p = np.array([r['x'], r['z']])
        d = road_dist(p, roads) - max(r['halfX'], r['halfZ'])
        if d < 1.0:
            road_hits.append((r['name'], round(d, 2)))

    # ---- minimap marks (rects; colour 0..1)
    marks = [dict(rect('AshenArena', cx, cz, R, R), r=0.70, g=0.70, b=0.68)]
    for k, rp in enumerate(ramps):
        marks.append(dict(rect('AshenArenaRamp%d' % k, rp['x'], rp['z'], rp['halfX'], rp['halfZ'], rp['yaw']), r=0.62, g=0.62, b=0.60))
    marks.append(dict(rect('AshenBunker', b['x'], b['z'], BUNKER['moundHalfX'], BUNKER['moundHalfZ'], b['yaw']), r=0.82, g=0.83, b=0.86))
    marks.append(dict(rect('AshenJump', JUMP['x'], JUMP['z'] - JUMP['length'] / 2, JUMP['halfWidth'], JUMP['length'] / 2), r=0.95, g=0.75, b=0.25))
    marks.append(dict(rect('AshenPad', PAD['x'], PAD['z'], PAD['radius'] * 0.8, PAD['radius'] * 0.8), r=0.66, g=0.66, b=0.64))
    marks.append(dict(rect('AshenTower', TOWER['x'], TOWER['z'], TOWER['rBase'] * 0.8, TOWER['rBase'] * 0.8), r=0.55, g=0.55, b=0.56))
    marks.append(dict(rect('AshenWorkshop', WORKSHOP['x'], WORKSHOP['z'], WORKSHOP['halfX'], WORKSHOP['halfZ']), r=0.45, g=0.40, b=0.38))
    L['marks'] = marks
    L['spawnY'] = [dict(id=ZONE * 10000 + 9500, y=ARENA['height'])]
    L['report'] = dict(moved=[list(m) for m in moved], roadHits=[list(h) for h in road_hits])
    return L, roads, spawns


def surfaces(L):
    """0.5 m grid over the zone: base ground height (0 = flat). Only the ravine under the jump dips (gentle banks)."""
    step = 0.5
    x0, x1 = -100.0, 100.0
    z0, z1 = ZMIN, ZMAX
    xs = np.arange(x0, x1 + 1e-6, step)
    zs = np.arange(z0, z1 + 1e-6, step)
    X, Z = np.meshgrid(xs, zs)
    h = np.zeros_like(X)
    rv = L['ravine']
    bank = 2.4
    # depth profile across z (smooth banks), fading out at the x ends
    tz = np.minimum((Z - rv['z0']) / bank, (rv['z1'] - Z) / bank)
    tx = np.minimum((X - rv['x0']) / 3.0, (rv['x1'] - X) / 3.0)
    t = np.clip(np.minimum(tz, tx), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    h = -rv['depth'] * t
    # keep only the part that dips (plus a margin of flat cells): the rest of the zone is flat ground
    nzr, nxr = np.nonzero(np.abs(h) > 1e-6)
    j0, j1 = max(0, nzr.min() - 4), min(len(zs) - 1, nzr.max() + 4)
    i0, i1 = max(0, nxr.min() - 4), min(len(xs) - 1, nxr.max() + 4)
    return xs[i0:i1 + 1], zs[j0:j1 + 1], h[j0:j1 + 1, i0:i1 + 1]


def write_surfaces(path, xs, zs, h):
    nx, nz = len(xs), len(zs)
    hh = np.clip(np.round(h * 1000.0), -32768, 32767).astype('<i2')
    with open(path, 'wb') as f:
        f.write(b'AWSF')
        f.write(struct.pack('<iifff', nx, nz, float(xs[0]), float(zs[0]), float(xs[1] - xs[0])))
        f.write(hh.tobytes())


def plot(path, L, roads, spawns):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, Polygon
    except Exception:
        return False
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_xlim(-110, 110); ax.set_ylim(292, 508); ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
    for pts, w in roads:
        ax.plot(pts[:, 0], pts[:, 1], '-', color='k', lw=w * 0.9, alpha=0.25, solid_capstyle='round')
    for s in spawns:
        x, _, z = s['position']
        ax.add_patch(Circle((x, z), max(0.6, s.get('radius', 1)), color='tab:blue' if s['kind'] == 'Prop' else 'tab:red', alpha=0.6))

    def orect(r, **kw):
        a = math.radians(r['yaw']); co, si = math.cos(a), math.sin(a)
        pts = [(r['x'] + lx * co + lz * si, r['z'] - lx * si + lz * co) for lx, lz in
               [(-r['halfX'], -r['halfZ']), (r['halfX'], -r['halfZ']), (r['halfX'], r['halfZ']), (-r['halfX'], r['halfZ'])]]
        ax.add_patch(Polygon(pts, closed=True, **kw))
    for r in L['exclusions']:
        orect(r, fill=False, ec='red', lw=0.8)
        ax.text(r['x'], r['z'], r['name'].replace('Ashen', ''), fontsize=6)
    a = L['arena']
    ax.add_patch(Circle((a['x'], a['z']), a['radius'], fill=False, ec='k', lw=1.5))
    for rp in a['ramps']:
        orect(dict(rp), fill=True, color='orange', alpha=0.5)
    ax.set_title('Ashen Winter layout (red: keep-out rectangles)')
    plt.savefig(path, dpi=80, bbox_inches='tight')
    return True


def main():
    scene, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    L, roads, spawns = build(scene)
    xs, zs, h = surfaces(L)
    write_surfaces(os.path.join(out, 'AshenWinter_surfaces.bytes'), xs, zs, h)
    with open(os.path.join(out, 'AshenWinter_layout.json'), 'w') as f:
        json.dump(L, f, indent=1, ensure_ascii=False)
    plot(os.path.join(out, 'AshenWinter_layout_plan.png'), L, roads, spawns)
    rep = L['report']
    print('AWL_LAYOUT arena ramps', [(r['x'], r['z'], r['yaw']) for r in L['arena']['ramps']])
    print('AWL_LAYOUT bunker', L['bunker']['x'], L['bunker']['z'], L['bunker']['yaw'])
    print('AWL_LAYOUT spawns to move', len(rep['moved']), rep['moved'])
    print('AWL_LAYOUT solids over roads', rep['roadHits'])
    print('AWL_LAYOUT grid', h.shape, 'min', float(h.min()))


if __name__ == '__main__':
    main()
