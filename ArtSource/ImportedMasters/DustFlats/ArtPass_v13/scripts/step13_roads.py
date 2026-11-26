"""v13 step: roads rebuilt as smooth ribbons.

Centre line = the Unity road polyline, resampled every 0.5 m and smoothed along its length (gaussian, deviation
from the original line clamped to 0.3 m) -> no straight chords or kinks on bends. Cross-section: 6 asphalt quads
with a 2 cm crown, constant width, then a 0.95 m shoulder on each side (Ground material) that feathers the asphalt
edge 4 cm under the ground with ground-sampled, packed-dust colours (no more hard edge line). Heights follow the
terrain (exact Unity mound heights) + the original road offset. Original UV layout kept: U across 0..1,
V = a * s + b fitted on the old mesh (lane markings continue onto the bridge deck); the river bridge span and
any other gap of the old mesh are left open; free ends get a feathered ground apron."""
import bpy, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
import rg_lib as L
import rg_sculpt as S
import step13_terrain as T

ROADS = {0: 'Road', 1: 'Road.001', 2: 'Road.002', 3: 'Road.003', 4: 'Road.017'}
SHOULDER = 0.95


def resample(P, step):
    d = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(d)])
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    ss = np.linspace(0, s[-1], n)
    return np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], 1), ss


def smooth_line(P, step=0.5, sigma=2.2, max_dev=0.3):
    Q, ss = resample(P, step)
    n = len(Q); r = int(3 * sigma / step)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sigma) ** 2); k /= k.sum()
    pad = np.concatenate([np.repeat(Q[:1], r, 0) * 2 - Q[r:0:-1], Q, np.repeat(Q[-1:], r, 0) * 2 - Q[-2:-r - 2:-1]])
    Sm = np.stack([np.convolve(pad[:, i], k, mode='valid') for i in range(2)], 1)
    dev = Sm - Q; dl = np.linalg.norm(dev, axis=1)
    f = np.minimum(1.0, max_dev / np.maximum(dl, 1e-9))
    Sm = Q + dev * f[:, None]
    Sm[0] = Q[0]; Sm[-1] = Q[-1]
    return resample(Sm, step)


def old_road_info(ob):
    me = ob.data; M = ob.matrix_world
    co = np.array([(M @ v.co)[:] for v in me.vertices])
    polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], polys)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    uv = np.zeros(len(me.loops) * 2); me.uv_layers['UVMap'].data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
    prm = np.zeros(len(me.loops) * 2); me.uv_layers['Unity_MaterialParams'].data.foreach_get('uv', prm); prm = prm.reshape(-1, 2)
    kd = KDTree(len(lv))
    for i, v in enumerate(lv):
        kd.insert(co[v], i)
    kd.balance()
    zoff = []
    return dict(co=co, bvh=bvh, lv=lv, uv=uv, col=col, prm=prm, kd=kd)


def build_road(ctx, idx, rd, ob):
    level = ctx['level']; sampler = ctx['ground_sampler']
    P = rd[0]; w = rd[1]
    info = old_road_info(ob)
    C, ss = smooth_line(P, 0.5, 2.2 if w < 12 else 4.0, 0.3)
    n = len(C)
    T_ = np.gradient(C, axis=0); T_ /= np.linalg.norm(T_, axis=1, keepdims=True)
    N_ = np.c_[-T_[:, 1], T_[:, 0]]
    # coverage + V mapping + height offset from the old mesh
    cover = np.zeros(n, bool); vs = []; zo = []
    for i in range(n):
        hit = info['bvh'].ray_cast(Vector((C[i, 0], C[i, 1], 30)), Vector((0, 0, -1)))
        if hit[0] is None:
            # also accept a hit within 1.2 m across (tight bends of the old polyline)
            for o in (-1.2, 1.2):
                q = C[i] + N_[i] * o
                hit = info['bvh'].ray_cast(Vector((q[0], q[1], 30)), Vector((0, 0, -1)))
                if hit[0] is not None:
                    break
        if hit[0] is not None:
            cover[i] = True
            zo.append(hit[0].z - float(T.terrain_height(level, np.array([hit[0].x]), np.array([hit[0].y]))[0]))
            _, li, _ = info['kd'].find(hit[0])
            vs.append((ss[i], info['uv'][li, 1]))
    zoff = float(np.median(zo)) if zo else 0.03
    vs = np.array(vs)
    a, b = np.polyfit(vs[:, 0], vs[:, 1], 1) if len(vs) > 4 else (1 / (1.6 * w), 0.0)
    # close small coverage holes (< 2 m), keep real gaps (bridge)
    cv = cover.copy()
    i = 0
    while i < n:
        if not cv[i]:
            j = i
            while j < n and not cv[j]:
                j += 1
            if (j - i) * 0.5 < 2.0 and i > 0 and j < n:
                cv[i:j] = True
            i = j
        else:
            i += 1
    # extend each covered run 0.4 m under the neighbouring deck / gap edge
    runs = []; i = 0
    while i < n:
        if cv[i]:
            j = i
            while j < n and cv[j]:
                j += 1
            runs.append((max(0, i - 1), min(n - 1, j)))
            i = j
        else:
            i += 1
    lat_a = np.array([-0.5, -0.36, -0.2, 0.0, 0.2, 0.36, 0.5]) * w
    crown = 0.02 * (1 - (lat_a / (w / 2)) ** 2)
    sh = np.array([0.42, 1.0]) * SHOULDER
    arrays = []
    tri_count = 0
    for (i0, i1) in runs:
        idxs = np.arange(i0, i1 + 1)
        m = len(idxs)
        if m < 2:
            continue
        Cr = C[idxs]; Nr = N_[idxs]; sr = ss[idxs]
        lat = np.concatenate([-w / 2 - sh[::-1], lat_a, w / 2 + sh])          # 11 columns
        ncol = len(lat)
        X = Cr[:, 0:1] + Nr[:, 0:1] * lat[None, :]; Y = Cr[:, 1:2] + Nr[:, 1:2] * lat[None, :]
        G = T.terrain_height(level, X, Y)
        Z = G + zoff
        Z[:, 2:9] += crown[None, :]
        # shoulders: feather from the asphalt edge down under the ground
        Z[:, 1] = G[:, 1] + zoff * 0.35; Z[:, 9] = G[:, 9] + zoff * 0.35
        Z[:, 0] = G[:, 0] - 0.04; Z[:, 10] = G[:, 10] - 0.04
        co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        gi = np.arange(m * ncol).reshape(m, ncol)
        quads = []; qmat = []
        for c in range(ncol - 1):
            a0 = gi[:-1, c]; b0 = gi[:-1, c + 1]; c0 = gi[1:, c + 1]; d0 = gi[1:, c]
            quads.append(np.stack([a0, d0, c0, b0], 1))      # CCW seen from above (lat = left normal)
            qmat.append(np.full(m - 1, 0 if 2 <= c < 8 else 1))
        quads = np.concatenate(quads); qmat = np.concatenate(qmat)
        # orientation check
        p0 = co[quads[:, 0]]; p1 = co[quads[:, 1]]; p2 = co[quads[:, 2]]
        if (np.cross(p1 - p0, p2 - p0)[:, 2] < 0).mean() > 0.5:
            quads = quads[:, ::-1]
        lv = quads.ravel()
        # UVs: asphalt U across 0..1, V along; shoulders: ground (world) mapping
        colidx = np.tile(np.arange(ncol), m)[lv]; rowidx = np.repeat(np.arange(m), ncol)[lv]
        u_asph = (lat[colidx] + w / 2) / w
        v_asph = a * sr[rowidx] + b
        P_ = co[lv]
        uv = np.where(np.repeat(qmat, 4)[:, None] == 0, np.stack([np.clip(u_asph, 0, 1), v_asph], 1), P_[:, :2] / 40.0)
        # colours: old asphalt colour (nearest), shoulders = ground colour, packed & dusted
        col = np.ones((len(lv), 4)); prm = np.zeros((len(lv), 2))
        qm4 = np.repeat(qmat, 4)
        for k, vi in enumerate(lv):
            q = co[vi]
            if qm4[k] == 0:
                _, li, _ = info['kd'].find(Vector((q[0], q[1], q[2])))
                col[k] = info['col'][li]; prm[k] = info['prm'][li]
            else:
                g = sampler(q[0], q[1])
                e = abs(lat[colidx[k]]) - w / 2              # 0 at the asphalt edge
                t = min(1.0, max(0.0, e / SHOULDER))
                kk = 0.86 + 0.14 * t                          # darker packed dust next to the asphalt
                col[k, :3] = (g[0] * kk, g[1] * kk * 0.98, g[2] * kk * 0.96)
        arrays.append(dict(co=co, flen=np.full(len(quads), 4, np.int32), lv=lv.astype(np.int32), col=col.astype(np.float32),
                           uv=uv.astype(np.float32), prm=prm.astype(np.float32), mat=qmat.astype(np.int32)))
        tri_count += 2 * len(quads)
        # feathered ground aprons at free ends (not at gaps where a deck continues)
        for end, sgn in ((i0, -1), (i1, 1)):
            if (end == 0 or end == n - 1) and idx != 4:
                arrays.append(end_apron(C[end], T_[end] * sgn, N_[end], w, zoff, level, sampler))
    return arrays, tri_count, dict(zoff=zoff, v_a=a, v_b=b, runs=len(runs), cover=float(cv.mean()))


def end_apron(c, t, nrm, w, zoff, level, sampler):
    """Half-disc of packed ground around a free road end (feathers under the ground)."""
    na = 9; rr = np.array([0.0, 0.5, 1.0])
    pts = []
    ang = np.linspace(-np.pi / 2, np.pi / 2, na)
    for r in rr:
        for a in ang:
            d = nrm * math.sin(a) * (w / 2 + r * SHOULDER) + t * math.cos(a) * (r * SHOULDER * 1.4)
            pts.append(c + d)
    pts = np.array(pts)
    g = T.terrain_height(level, pts[:, 0], pts[:, 1])
    z = g + np.repeat(np.array([zoff * 0.6, zoff * 0.25, -0.04]), na)
    co = np.c_[pts, z]
    gi = np.arange(3 * na).reshape(3, na)
    quads = []
    for rI in range(2):
        for k in range(na - 1):
            quads.append([gi[rI, k], gi[rI, k + 1], gi[rI + 1, k + 1], gi[rI + 1, k]])
    quads = np.array(quads)
    p0 = co[quads[:, 0]]; p1 = co[quads[:, 1]]; p2 = co[quads[:, 2]]
    if (np.cross(p1 - p0, p2 - p0)[:, 2] < 0).mean() > 0.5:
        quads = quads[:, ::-1]
    lv = quads.ravel()
    col = np.ones((len(lv), 4))
    for k, vi in enumerate(lv):
        gq = sampler(co[vi, 0], co[vi, 1]); col[k, :3] = (gq[0] * 0.9, gq[1] * 0.88, gq[2] * 0.86)
    return dict(co=co, flen=np.full(len(quads), 4, np.int32), lv=lv.astype(np.int32), col=col.astype(np.float32),
                uv=(co[lv, :2] / 40.0).astype(np.float32), prm=np.zeros((len(lv), 2), np.float32), mat=np.ones(len(quads), np.int32))


def run(ctx):
    level = ctx['level']
    md_roads = [r for r in level.md['roads'] if r.get('zone', 0) == 0]
    stats = {}
    for r in md_roads:
        idx = r['index']; nm = ROADS.get(idx)
        ob = bpy.data.objects.get(nm) if nm else None
        if ob is None:
            continue
        p = r['points']
        P = np.array([(p[i], p[i + 2]) for i in range(0, len(p), 3)], np.float64)
        old_tris = sum(len(q.vertices) - 2 for q in ob.data.polygons)
        arrays, nt, info = build_road(ctx, idx, (P, float(r['width'])), ob)
        Mi = np.array(ob.matrix_world.inverted())
        for a in arrays:
            a['co'] = a['co'] @ Mi[:3, :3].T + Mi[:3, 3]
        mats = [ctx['mats']['Road0'], ctx['mats']['Ground']]
        acc = L.MeshAccumulator()
        for a in arrays:
            acc.add(a)
        new = acc.build(ob.data.name + '__v13', materials=mats, sharp_angle=60.0, weighted=False)
        users, _ = L.swap_mesh(ob.data, new, note='v13: smooth road ribbon (smoothed centre line, constant width, crown, feathered ground shoulders; old UV layout, bridge gap kept)')
        for o in users:
            L.set_object_materials(o, mats)
        stats[nm] = dict(old_tris=old_tris, new_tris=nt, **info)
    ctx['stats']['roads'] = stats
    print('STEP13 roads', {k: (v['old_tris'], v['new_tris'], round(v['cover'], 2)) for k, v in stats.items()}, flush=True)


LANES = {'Road.022': 'MesaS1', 'Road.023': 'MesaS2', 'Road.024': 'MesaS3'}


def build_lane(ctx, ob, fl):
    """Mesa lane road: straight ribbon on the exact lane slope (floor + old offset), 6 asphalt quads with a small
    crown, rounded 0.45 m shoulders feathering under the deck (deck = floor + 1.2 cm)."""
    import rg_massif as MS
    F = MS.Floor(fl)
    info = old_road_info(ob)
    co_old = info['co']
    x0, y0 = co_old[:, 0].min(), co_old[:, 1].min(); x1, y1 = co_old[:, 0].max(), co_old[:, 1].max()
    w = float(x1 - x0); cx = float((x0 + x1) / 2)
    ys = np.arange(y0, y1 + 1e-6, 0.5)
    if ys[-1] < y1 - 1e-3:
        ys = np.append(ys, y1)
    zoff = float(np.median(co_old[:, 2] - F.h(co_old[:, 0], co_old[:, 1])))
    # V mapping from the old mesh
    vv = info['uv'][:, 1]; yy = co_old[info['lv'], 1]
    a, b = np.polyfit(yy, vv, 1)
    lat = np.array([-w / 2 - 0.45, -w / 2 - 0.2, -0.5 * w, -0.33 * w, -0.17 * w, 0, 0.17 * w, 0.33 * w, 0.5 * w, w / 2 + 0.2, w / 2 + 0.45])
    X = cx + lat[None, :] + 0 * ys[:, None]; Y = ys[:, None] + 0 * lat[None, :]
    H = F.h(X, Y)
    Z = H + zoff
    Z[:, 2:9] += 0.015 * (1 - (lat[2:9] / (w / 2)) ** 2)[None, :]
    Z[:, 1] = H[:, 1] + zoff * 0.45; Z[:, 9] = H[:, 9] + zoff * 0.45
    Z[:, 0] = H[:, 0] + 0.0; Z[:, 10] = H[:, 10] + 0.0
    m, ncol = Z.shape
    co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    gi = np.arange(m * ncol).reshape(m, ncol)
    quads = []; qmat = []
    for c in range(ncol - 1):
        quads.append(np.stack([gi[:-1, c], gi[:-1, c + 1], gi[1:, c + 1], gi[1:, c]], 1))
        qmat.append(np.full(m - 1, 0 if 2 <= c < 8 else 1))
    quads = np.concatenate(quads); qmat = np.concatenate(qmat)
    p0 = co[quads[:, 0]]; p1 = co[quads[:, 1]]; p2 = co[quads[:, 2]]
    if (np.cross(p1 - p0, p2 - p0)[:, 2] < 0).mean() > 0.5:
        quads = quads[:, ::-1]
    lv = quads.ravel(); qm4 = np.repeat(qmat, 4)
    colidx = np.tile(np.arange(ncol), m)[lv]
    P_ = co[lv]
    uv = np.where(qm4[:, None] == 0, np.stack([np.clip((lat[colidx] + w / 2) / w, 0, 1), a * P_[:, 1] + b], 1), P_[:, :2] / 40.0)
    col = np.ones((len(lv), 4)); prm = np.zeros((len(lv), 2))
    sampler = ctx['ground_sampler']
    for k, vi in enumerate(lv):
        q = co[vi]
        if qm4[k] == 0:
            _, li, _ = info['kd'].find(Vector((q[0], q[1], q[2])))
            col[k] = info['col'][li]; prm[k] = info['prm'][li]
        else:
            g = sampler(q[0], q[1]); kk = 0.8
            col[k, :3] = (0.55 * g[0] * kk + 0.45 * 0.54 * kk, 0.55 * g[1] * kk + 0.45 * 0.335 * kk, 0.55 * g[2] * kk + 0.45 * 0.18 * kk)
    arr = dict(co=co, flen=np.full(len(quads), 4, np.int32), lv=lv.astype(np.int32), col=col.astype(np.float32),
               uv=uv.astype(np.float32), prm=prm.astype(np.float32), mat=qmat.astype(np.int32))
    Mi = np.array(ob.matrix_world.inverted())
    arr['co'] = arr['co'] @ Mi[:3, :3].T + Mi[:3, 3]
    mats = [ctx['mats']['Road0'], ctx['mats']['Ground']]
    acc = L.MeshAccumulator(); acc.add(arr)
    old = sum(len(q.vertices) - 2 for q in ob.data.polygons)
    new = acc.build(ob.data.name + '__v13', materials=mats, sharp_angle=60.0, weighted=False)
    users, _ = L.swap_mesh(ob.data, new, note='v13: mesa lane road on the exact lane slope (crown, rounded shoulders feathering under the deck; old UVs)')
    for o in users:
        L.set_object_materials(o, mats)
    return dict(old=old, new=sum(len(q.vertices) - 2 for q in new.polygons), zoff=round(zoff, 3))


_run_roads = run


def run(ctx):
    _run_roads(ctx)
    fl = {f['name']: f for f in ctx['level'].floors}
    st = {}
    for nm, fn in LANES.items():
        ob = bpy.data.objects.get(nm)
        if ob is not None and fn in fl:
            st[nm] = build_lane(ctx, ob, fl[fn])
    ctx['stats']['roads'].update(st)
    print('STEP13 mesa lanes', st, flush=True)
