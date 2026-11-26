"""Step: ground. Finer vertex-colour grid for calm large-scale variation, packed sand along road
shoulders, rock-dust tint near cliff bases; tyre-rut decals (Ground material, seamless) at dirt kickers.
The ground surface itself stays flat at z = 0 (Unity Ground is analytical); only colour changes."""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L


def _hash_noise(x, y, scale, seed):
    """Smooth value noise for arrays of world coords (not tileable; used per vertex)."""
    xs = x / scale + seed * 17.3; ys = y / scale - seed * 9.1
    x0 = np.floor(xs); y0 = np.floor(ys); fx = xs - x0; fy = ys - y0
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    def h(i, j):
        return np.mod(np.sin(i * 127.1 + j * 311.7 + seed * 74.7) * 43758.5453, 1.0)
    a = h(x0, y0); b = h(x0 + 1, y0); c = h(x0, y0 + 1); d = h(x0 + 1, y0 + 1)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm_xy(x, y, scale, seed, oct=3):
    s = 0; amp = 1; tot = 0
    for o in range(oct):
        s = s + amp * _hash_noise(x, y, scale / (2 ** o), seed + o); tot += amp; amp *= 0.5
    return s / tot


class GroundSampler:
    """Bilinear lookup of Ground vertex colours (world XY) on its regular grid."""
    def __init__(self, ob):
        me = ob.data
        n = len(me.vertices)
        co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world); co = co @ M[:3, :3].T + M[:3, 3]
        lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
        col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
        vc = np.zeros((n, 4)); cnt = np.zeros(n)
        np.add.at(vc, lv, col); np.add.at(cnt, lv, 1)
        vc /= np.maximum(cnt, 1)[:, None]
        xs = np.unique(np.round(co[:, 0], 3)); ys = np.unique(np.round(co[:, 1], 3))
        self.step = float(np.median(np.diff(xs)))
        self.x0 = xs.min(); self.y0 = ys.min()
        nx = int(round((xs.max() - xs.min()) / self.step)) + 1; ny = int(round((ys.max() - ys.min()) / self.step)) + 1
        grid = np.full((ny, nx, 3), np.nan)
        ix = np.round((co[:, 0] - self.x0) / self.step).astype(int); iy = np.round((co[:, 1] - self.y0) / self.step).astype(int)
        ok = (np.abs(co[:, 0] - (self.x0 + ix * self.step)) < 0.05) & (np.abs(co[:, 1] - (self.y0 + iy * self.step)) < 0.05)
        grid[iy[ok], ix[ok]] = vc[ok, :3]
        mean = np.nanmean(grid.reshape(-1, 3), 0)
        grid = np.where(np.isnan(grid), mean, grid)
        self.grid = grid; self.nx = nx; self.ny = ny

    def __call__(self, x, y):
        fx = (x - self.x0) / self.step; fy = (y - self.y0) / self.step
        i = int(math.floor(fx)); j = int(math.floor(fy)); tx = fx - i; ty = fy - j
        i = max(0, min(self.nx - 2, i)); j = max(0, min(self.ny - 2, j))
        g = self.grid
        c = (g[j, i] * (1 - tx) + g[j, i + 1] * tx) * (1 - ty) + (g[j + 1, i] * (1 - tx) + g[j + 1, i + 1] * tx) * ty
        return (float(c[0]), float(c[1]), float(c[2]))


def recolor_ground(ob, level, rock_fp):
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me)
    # 5 m grid -> 2.5 m grid (colour resolution for shoulders / contact); interpolates loop colours
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
    bm.to_mesh(me); bm.free()
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world); w = co @ M[:3, :3].T + M[:3, 3]
    x, y = w[:, 0], w[:, 1]
    big = fbm_xy(x, y, 70.0, 3)        # calm large patches
    mid = fbm_xy(x, y, 24.0, 11)
    warm = fbm_xy(x, y, 55.0, 23)
    lum = 0.93 + 0.12 * big + 0.06 * (mid - 0.5)
    # packed / compacted sand patches live in vertex colour (non-repeating), not in the tiling map
    packed_v = np.clip((fbm_xy(x, y, 30.0, 41) - 0.56) / 0.08, 0, 1)
    lum = lum * (1 - 0.07 * packed_v)
    # road shoulders: packed, slightly darker and less saturated sand 0.5..4 m from the asphalt edge
    rc = np.array([level.road_clearance(a, b) if -2 < a < 1e9 else 9 for a, b in zip(x, y)])
    pack = np.clip(1 - np.abs(rc - 1.8) / 2.6, 0, 1) * (rc > -0.5)
    # rock dust near cliff / boulder bases
    dust = np.zeros(n)
    if rock_fp is not None and len(rock_fp):
        from mathutils.kdtree import KDTree
        kd = KDTree(len(rock_fp))
        for i, (px, py, rad) in enumerate(rock_fp):
            kd.insert((px, py, 0), i)
        kd.balance()
        for i in range(n):
            for (_, idx, d) in kd.find_n((x[i], y[i], 0), 2):
                rad = rock_fp[idx][2]
                dust[i] = max(dust[i], float(np.clip(1 - (d - rad) / 4.0, 0, 1)))
    lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
    k = lum[lv]
    hue_r = 1 + 0.035 * (warm[lv] - 0.5) * 2 + 0.03 * packed_v[lv]
    hue_b = 1 - 0.05 * (warm[lv] - 0.5) * 2
    col[:, 0] *= k * hue_r; col[:, 1] *= k; col[:, 2] *= k * hue_b
    p = pack[lv][:, None]
    grey = col[:, :3].mean(1, keepdims=True)
    col[:, :3] = col[:, :3] * (1 - 0.10 * p) * (1 - 0.12 * p) + grey * 0.12 * p * (1 - 0.10 * p)
    d = dust[lv][:, None]
    rockdust = np.array([0.56, 0.27, 0.16])
    col[:, :3] = col[:, :3] * (1 - 0.18 * d) + rockdust * 0.18 * d
    col[:, :3] *= (1 - 0.05 * d)
    me.color_attributes['Color'].data.foreach_set('color', col.ravel())
    me['artpass_v11'] = 'ground grid 5 m -> 2.5 m (colour only, still flat); macro colour variation, packed shoulders, rock dust'
    me.update()


def rut_ribbon(points, sampler, half_w=1.35, gauge=0.82, track_hw=0.22, depth=0.13, z=0.012):
    """Two tyre ruts along a polyline (world XY). Colour = ground colour x rut profile (1.0 at ribbon edges)."""
    p = L.Part(); bm = p.bm
    us = [-1.0, -0.8, -0.62, -0.5, -0.38, -0.2, 0.0, 0.2, 0.38, 0.5, 0.62, 0.8, 1.0]
    rows = []
    pts = [Vector((a, b, 0)) for a, b in points]
    for i, P in enumerate(pts):
        T = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        N = Vector((-T.y, T.x, 0))
        rows.append([bm.verts.new(P + N * (u * half_w) + Vector((0, 0, z))) for u in us])
    for i in range(len(rows) - 1):
        for j in range(len(us) - 1):
            bm.faces.new([rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]])
    bm.verts.index_update()
    lc = p.lc
    nrows = len(rows)
    for f in bm.faces:
        for l in f.loops:
            v = l.vert
            ri = v.index // len(us); uj = v.index % len(us)
            u = us[uj]
            dist = abs(abs(u * half_w) - gauge)
            prof = math.exp(-(dist / track_hw) ** 2)
            fade = min(1.0, ri / 3.0, (nrows - 1 - ri) / 3.0)
            g = sampler(v.co.x, v.co.y)
            k = 1 - depth * prof * fade * (1.0 if abs(u) < 0.99 else 0.0)
            l[lc] = (g[0] * k, g[1] * k * 0.995, g[2] * k * 0.985, 1.0)
            l[p.lp].uv = (0.0, 0.0)
    return p


def kicker_ruts(level, sampler):
    """Tyre tracks leading onto each dirt kicker and away from its landing."""
    paths = []
    for f in level.floors:
        if not f['name'].startswith(('Kicker', 'BigJump0')):
            continue
        r = f['rect']
        if not (-262 < r['center'][2] < 100 and -100 < r['center'][0] < 100):
            continue   # zone 0 only
        c = Vector((r['center'][0], r['center'][2], 0)); yaw = math.radians(r.get('yaw', 0))
        d = Vector((math.sin(yaw), math.cos(yaw), 0)); side = Vector((d.y, -d.x, 0))
        half = r['half'][1]
        run_len = 16.0 if f['name'].startswith('Kicker') else 0.0
        land = 7.0 if f['name'].startswith('Kicker') else 0.0
        if run_len:
            a = c - d * (half + run_len); b = c - d * (half + 0.3)
            bend = side * 1.6
            pts = [a + bend * (1 - t) ** 2 + (b - a) * t for t in np.linspace(0, 1, 12)]
            paths.append([(q.x, q.y) for q in pts])
            a2 = c + d * (half + land); b2 = a2 + d * 12.0 - side * 1.2
            pts2 = [a2 + (b2 - a2) * t - side * 1.2 * t * t for t in np.linspace(0, 1, 10)]
            paths.append([(q.x, q.y) for q in pts2])
    return paths


def run(ctx):
    level = ctx['level']
    ground = bpy.data.objects['Ground']
    # rock footprints (from v10 rock meshes) for the dust tint
    fp = []
    for nm in ctx['rock_objects']:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        for pts, _ in L.mesh_components(ob.data):
            if len(pts) < 8:
                continue
            Mw = np.array(ob.matrix_world); wp = pts @ Mw[:3, :3].T + Mw[:3, 3]
            c = wp[:, :2].mean(0); rad = float(np.percentile(np.linalg.norm(wp[:, :2] - c, axis=1), 80))
            fp.append((float(c[0]), float(c[1]), rad))
    ctx['rock_footprints'] = fp
    recolor_ground(ground, level, fp)
    sampler = GroundSampler(ground)
    ctx['ground_sampler'] = sampler
    # tyre ruts at the dirt kickers / big jump approach
    acc = L.MeshAccumulator()
    for path in kicker_ruts(level, sampler):
        part = rut_ribbon(path, sampler)
        acc.add_part(part); part.free()
    if not acc.empty():
        coll = ctx['coll_ground']
        me = acc.build('AP_Ground_TyreRuts', materials=[ctx['mats']['Ground']], sharp_angle=80, weighted=False)
        L.new_object('AP_Ground_TyreRuts', me, coll, parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Ground']],
                     note='new: tyre-rut ground decals (Ground material, world UV; seamless via vertex colour)')
    print('STEP ground done', flush=True)


def _sample_many(self, x, y):
    """Vectorised bilinear lookup (arrays) -> (N,3)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    fx = (x - self.x0) / self.step; fy = (y - self.y0) / self.step
    i = np.clip(np.floor(fx).astype(int), 0, self.nx - 2); j = np.clip(np.floor(fy).astype(int), 0, self.ny - 2)
    tx = np.clip(fx - i, 0, 1)[:, None]; ty = np.clip(fy - j, 0, 1)[:, None]
    g = self.grid
    return (g[j, i] * (1 - tx) + g[j, i + 1] * tx) * (1 - ty) + (g[j + 1, i] * (1 - tx) + g[j + 1, i + 1] * tx) * ty


GroundSampler.many = _sample_many
