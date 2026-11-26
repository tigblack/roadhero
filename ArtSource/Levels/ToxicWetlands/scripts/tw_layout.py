"""Toxic Wetlands layout: shallow pools, channels and the arena moat of the second zone, as one heightfield.

    python3 tw_layout.py <scene.json> <out_dir>      (numpy; matplotlib optional for the plan image)

The water is a signed-distance field: hand-placed pool / channel / moat shapes (smooth union, organic edge noise),
intersected with a clearance field that keeps every gameplay object of the zone dry and flat: roads (+ shoulders),
spawn points (with their radii), structures and keep-outs (underpass, rock tunnel, hills, kickers, jumps), camps,
the repair pad, billboard, both gates, the arena island and the zone edges. Heights:
  dry bank  : 0 -> water level over BANK m outside the shoreline,
  water bed : water level -> BED over INNER m inside it  (max depth BED - LEVEL).
The same grid drives Blender (ground / water meshes) and Unity (Ground base height, wheel water contacts).
"""
import json
import math
import os
import struct
import sys

import numpy as np

X0, X1, Z0, Z1, STEP = -100.0, 100.0, 100.0, 300.0, 0.5
LEVEL, BED, BANK, INNER = -0.08, -0.32, 1.6, 2.4       # metres: water surface, deepest bed, bank / inner widths
ARENA = (-15.6, 264.0)
ISLAND_R = 24.0

# hand-placed water shapes (Unity x, z). Ellipses: (cx, cz, rx, rz, yaw_deg). Channels: polyline + half width.
POOLS = [
    (-62, 124, 17, 9, 15), (-36, 116, 9, 6, -10), (-24, 129, 6, 5, 0), (-84, 150, 8, 13, 0), (-26, 150, 8, 6, 30),
    (-72, 140, 6, 8, 0), (-50, 196, 11, 8, 0), (-84, 214, 8, 17, 5), (-35, 202, 7, 11, 0), (-74, 255, 13, 8, -25),
    (-48, 280, 12, 7, 10), (-84, 292, 9, 5, 0), (6, 124, 9, 6, 30),
    (62, 120, 14, 7, -8), (86, 150, 7, 14, 0), (34, 152, 9, 7, 20), (20, 162, 8, 6, 0), (70, 180, 13, 6, -10),
    (86, 196, 6, 15, 0), (78, 236, 10, 8, 30), (35, 229, 8, 5, 0), (14, 232, 9, 7, -10), (40, 284, 14, 8, 0),
    (10, 278, 8, 7, 0), (30, 262, 7, 5, 0), (76, 262, 6, 5, 0), (-6, 182, 5, 9, 0), (52, 260, 6, 5, 0),
]
CHANNELS = [
    ([(-62, 124), (-48, 120), (-36, 116), (-24, 129)], 2.6),
    ([(-84, 150), (-80, 175), (-84, 214)], 2.4),
    ([(-74, 255), (-60, 268), (-48, 280)], 2.6),
    ([(62, 120), (78, 132), (86, 150)], 2.4),
    ([(86, 196), (84, 218), (78, 236)], 2.4),
    ([(14, 232), (8, 250), (10, 278)], 2.6),
    ([(40, 284), (24, 282), (10, 278)], 2.6),
    ([(-35, 202), (-32, 186), (-26, 150)], 2.0),
    ([(-50, 196), (-35, 202)], 2.2),
    ([(70, 180), (86, 196)], 2.2),
    ([(34, 152), (20, 162)], 2.0),
    ([(-86, 132), (-86.5, 150), (-86.5, 200), (-86, 245), (-84, 292)], 1.8),
    ([(86, 128), (86.5, 170), (86.5, 230), (86, 280)], 1.8),
]
MOAT = (ARENA, 30.0, 4.6)          # ring centre, mean radius, half width (causeways come from the road clearance)
TOXIC = [(-44.0, 266.0, 3.0), (12.0, 252.0, 3.2), (-62, 124, 3.0), (40, 284, 3.0), (78, 236, 2.6),
         (-84, 214, 2.6), (86, 150, 2.6)]   # (x, z, radius): leaking drums / outfall pipes tint the water locally


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def seg_dist(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    L2 = max(vx * vx + vz * vz, 1e-9)
    t = np.clip(((px - ax) * vx + (pz - az) * vz) / L2, 0.0, 1.0)
    dx, dz = px - ax - t * vx, pz - az - t * vz
    return np.sqrt(dx * dx + dz * dz)


def poly_dist(px, pz, pts):
    d = np.full(px.shape, 1e9)
    for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
        d = np.minimum(d, seg_dist(px, pz, ax, az, bx, bz))
    return d


def rect_dist(px, pz, c, half, yaw):
    a = math.radians(yaw)
    ca, sa = math.cos(a), math.sin(a)
    dx, dz = px - c[0], pz - c[2]
    # Unity ORect: local x along right = (cos, -sin)? use rotation of the rect by yaw about Y (clockwise in x/z)
    lx = dx * ca - dz * sa
    lz = dx * sa + dz * ca
    qx = np.abs(lx) - half[0]
    qz = np.abs(lz) - half[1]
    out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2)
    inside = np.minimum(np.maximum(qx, qz), 0.0)
    return out + inside


def ellipse_sdf(px, pz, cx, cz, rx, rz, yaw):
    a = math.radians(yaw)
    ca, sa = math.cos(a), math.sin(a)
    dx, dz = px - cx, pz - cz
    lx = dx * ca - dz * sa
    lz = dx * sa + dz * ca
    k = np.sqrt((lx / rx) ** 2 + (lz / rz) ** 2)
    return (k - 1.0) * min(rx, rz)


def value_noise(px, pz, scale, seed):
    """Smooth periodic-free value noise from a hashed lattice (deterministic)."""
    gx, gz = px / scale, pz / scale
    ix, iz = np.floor(gx).astype(np.int64), np.floor(gz).astype(np.int64)
    fx, fz = gx - ix, gz - iz

    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 2147483647) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 65535.0 * 2 - 1
    ux, uz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b, c, d = h(ix, iz), h(ix + 1, iz), h(ix, iz + 1), h(ix + 1, iz + 1)
    return (a * (1 - ux) + b * ux) * (1 - uz) + (c * (1 - ux) + d * ux) * uz


def build(scene_path):
    sc = json.load(open(scene_path))
    md = sc['metadata']
    xs = np.arange(X0, X1 + 1e-6, STEP)
    zs = np.arange(Z0, Z1 + 1e-6, STEP)
    PX, PZ = np.meshgrid(xs, zs)              # [iz, ix]
    clear = np.full(PX.shape, 1e9)
    notes = []

    def add(d, name):
        nonlocal clear
        clear = np.minimum(clear, d)
        notes.append(name)
    # roads (+3 m shoulder margin beyond the half width)
    for r in md['roads']:
        if r['zone'] != 1:
            continue
        pts = np.array(r['points']).reshape(-1, 3)[:, [0, 2]]
        add(poly_dist(PX, PZ, [tuple(p) for p in pts]) - (r['width'] / 2 + 2.5), 'road%d' % r['index'])
    # spawns
    spawns = [s for s in md['spawns'] if s['zone'] == 1]
    for s in spawns:
        x, _, z = s['position']
        r = s['radius'] * s.get('scale', 1.0)
        extra = 1.3 if s['kind'] == 'Prop' else (2.5 if s['kind'] in ('Vehicle', 'Boss') else 1.0)
        add(np.sqrt((PX - x) ** 2 + (PZ - z) ** 2) - (r + extra), 'spawn')
    # structures: floors, holes, keepouts (+1.5)
    for f in md['floors']:
        c = f['rect']['center']
        if 95 <= c[2] <= 305:
            add(rect_dist(PX, PZ, c, f['rect']['half'], f['rect']['yaw']) - 1.5, f['name'])
    for k in md['keepouts'] + md['holes']:
        c = k['center']
        if 95 <= c[2] <= 305:
            add(rect_dist(PX, PZ, c, k['half'], k['yaw']) - 1.5, 'keepout')
    # camps (palisade radius 15.5), repair pad, billboard, gates, arena island
    for c in ((-53.3, 162.2), (57.7, 206.7), (-57.1, 228.4)):
        add(np.sqrt((PX - c[0]) ** 2 + (PZ - c[1]) ** 2) - 17.5, 'camp')
    for (cx, cz, r) in ((37, 122, 10.0), (9, 113, 4.5), (22, 100, 15.0), (-26, 300, 15.0)):
        add(np.sqrt((PX - cx) ** 2 + (PZ - cz) ** 2) - r, 'fixed')
    add(np.sqrt((PX - ARENA[0]) ** 2 + (PZ - ARENA[1]) ** 2) - ISLAND_R, 'island')
    # zone edges: berms along the walls and the south flood wall
    add(np.minimum(np.minimum(88.5 - np.abs(PX), PZ - 112.0), 291.0 - PZ), 'edges')
    # water shapes
    shape = np.full(PX.shape, 1e9)
    for (cx, cz, rx, rz, yaw) in POOLS:
        shape = smin(shape, ellipse_sdf(PX, PZ, cx, cz, rx, rz, yaw), 4.0)
    for pts, hw in CHANNELS:
        shape = smin(shape, poly_dist(PX, PZ, pts) - hw, 2.5)
    (mc, mr, mw) = MOAT
    ring = np.abs(np.sqrt((PX - mc[0]) ** 2 + (PZ - mc[1]) ** 2) - mr) - mw
    shape = smin(shape, ring, 3.0)
    shape = shape + 1.3 * value_noise(PX, PZ, 9.0, 7) + 0.5 * value_noise(PX, PZ, 3.5, 8)
    allowed = (BANK + 0.6) - clear
    sdf = np.maximum(shape, allowed)
    # heights
    h = np.zeros(PX.shape)
    bank = (sdf >= 0) & (sdf < BANK)
    h[bank] = LEVEL * sstep(BANK, 0.0, sdf[bank])
    wet = sdf < 0
    h[wet] = LEVEL + (BED - LEVEL) * sstep(0.0, -INNER, sdf[wet])
    # toxicity (0..1) for the water tint
    tox = np.zeros(PX.shape)
    for (tx, tz, tr) in TOXIC:
        tox = np.maximum(tox, 0.85 * sstep(tr, 0.0, np.sqrt((PX - tx) ** 2 + (PZ - tz) ** 2) - 0.5))
    tox *= wet
    # checks
    issues = []
    for s in spawns:
        x, _, z = s['position']
        ix, iz = int(round((x - X0) / STEP)), int(round((z - Z0) / STEP))
        if 0 <= ix < len(xs) and 0 <= iz < len(zs) and h[iz, ix] < -0.002:
            issues.append(('spawn in water', s['id'], s['model'], x, z, float(h[iz, ix])))
    for r in md['roads']:
        if r['zone'] != 1:
            continue
        for p in np.array(r['points']).reshape(-1, 3):
            ix, iz = int(round((p[0] - X0) / STEP)), int(round((p[2] - Z0) / STEP))
            if 0 <= ix < len(xs) and 0 <= iz < len(zs) and h[iz, ix] < -0.002:
                issues.append(('road in water', r['index'], p[0], p[2]))
    stats = {'waterArea_m2': float(wet.sum() * STEP * STEP), 'bankArea_m2': float(bank.sum() * STEP * STEP),
             'zoneArea_m2': float(PX.size * STEP * STEP), 'waterFraction': float(wet.mean()),
             'minHeight': float(h.min()), 'maxDepth': float(LEVEL - h.min()), 'issues': len(issues)}
    return xs, zs, h, sdf, tox, clear, stats, issues


def write(out, xs, zs, h, tox, stats, issues):
    os.makedirs(out, exist_ok=True)
    nx, nz = len(xs), len(zs)
    # Unity / Blender binary grid: header + int16 heights (mm) + uint8 toxicity, row-major by z then x
    with open(os.path.join(out, 'ToxicWetlands_surfaces.bytes'), 'wb') as f:
        f.write(b'TWSF')
        f.write(struct.pack('<iiffff', nx, nz, X0, Z0, STEP, LEVEL))
        f.write(np.round(h * 1000.0).astype('<i2').tobytes())
        f.write(np.round(tox * 255.0).astype(np.uint8).tobytes())
    meta = {'grid': {'nx': nx, 'nz': nz, 'x0': X0, 'z0': Z0, 'step': STEP}, 'waterLevel': LEVEL, 'bedDepth': BED,
            'bankWidth': BANK, 'innerWidth': INNER, 'arena': ARENA, 'islandRadius': ISLAND_R,
            'pools': POOLS, 'channels': CHANNELS, 'moat': [list(MOAT[0]), MOAT[1], MOAT[2]], 'toxic': TOXIC,
            'stats': stats, 'issues': issues}
    with open(os.path.join(out, 'ToxicWetlands_layout.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    return meta


def plot(out, xs, zs, h, clear, scene_path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        return
    sc = json.load(open(scene_path))
    md = sc['metadata']
    fig, ax = plt.subplots(figsize=(13, 13))
    ax.imshow(np.where(h < LEVEL - 0.002, h, np.nan), origin='lower', extent=[X0, X1, Z0, Z1], cmap='viridis_r', vmin=BED, vmax=LEVEL)
    ax.contour(xs, zs, h, levels=[LEVEL * 0.5], colors='saddlebrown', linewidths=0.6)
    for r in md['roads']:
        if r['zone'] != 1:
            continue
        p = np.array(r['points']).reshape(-1, 3)
        ax.plot(p[:, 0], p[:, 2], '-', color='k', lw=r['width'] * 0.6, alpha=0.25)
    for s in md['spawns']:
        if s['zone'] != 1:
            continue
        x, _, z = s['position']
        ax.plot(x, z, 'o', ms=2.5, color='r' if s['kind'] != 'Prop' else 'b')
    ax.set_xlim(X0, X1); ax.set_ylim(Z0, Z1); ax.grid(alpha=0.3)
    ax.set_xticks(range(-100, 101, 10)); ax.set_yticks(range(100, 301, 10))
    plt.xticks(fontsize=6); plt.yticks(fontsize=6)
    plt.savefig(os.path.join(out, 'ToxicWetlands_layout_plan.png'), dpi=100, bbox_inches='tight')


if __name__ == '__main__':
    scene = sys.argv[1]
    out = sys.argv[2]
    xs, zs, h, sdf, tox, clear, stats, issues = build(scene)
    meta = write(out, xs, zs, h, tox, stats, issues)
    plot(out, xs, zs, h, clear, scene)
    print('TW_LAYOUT', json.dumps(stats), 'issues:', issues[:10])
