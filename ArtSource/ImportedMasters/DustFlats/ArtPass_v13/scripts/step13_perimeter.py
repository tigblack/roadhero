"""v13 step: perimeter & intro-canyon cliffs sculpted as continuous layered sandstone walls.

The v12 band of faceted boulders (4 rows) becomes a swept cliff along the winding boundary (inner edge of the
playable area unchanged): talus apron from the boundary line, a first cliff tier (rounded shoulder, 70-80 deg
face, soft strata benches), a bench, a second taller tier on ~70 % of the length, rolling top and a rounded back.
Along the length: buttresses / alcoves, gullies with debris cones, height and tone variation; rounded noses at
the gate and river gaps. Each column's profile is resampled by arc length, so faces get as many rows as flat
parts. The mesh is assigned to the existing objects by region (Cliff.003/.004/.011/.012/.014,
AP_Cliff_NorthEast; canyon walls Cliff/Cliff.001/Cliff.002) and quadric-decimated; scree is rescattered on
the new talus (rounded pebbles)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_sculpt as S
import rg_massif as MS
import rg_layout12 as LY
from step13_massif import to_object_space, with_mat, replace_mesh

DS = 0.6
N_ROWS = 84


def region_of(x, y):
    if y < -106 and abs(x) < 22:
        if y < -250.3:
            return 'Cliff.002'
        return 'Cliff' if x < 0 else 'Cliff.001'
    if y > 88:
        return 'Cliff.014' if x < 15 else 'AP_Cliff_NorthEast'
    if y < -94:
        return 'Cliff.011' if x < 0 else 'Cliff.012'
    return 'Cliff.003' if x < 0 else 'Cliff.004'


def gap_of(x, y, river):
    if 14.0 <= x <= 32.0 and y > 94:
        return True
    if river.corridor(np.array([x]), np.array([y]), 2.2)[0]:
        return True
    return False


def noise1(s, f, seed):
    return S.fbm2(np.asarray(s) * f, np.full(np.shape(s), 0.37 + seed * 0.013), seed, 3)


def gauss_smooth_closed(V, sigma_pts):
    if sigma_pts < 0.3:
        return V.copy()
    r = int(3 * sigma_pts) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_pts) ** 2); k /= k.sum()
    n = len(V)
    out = np.zeros_like(V)
    for j, w in zip(range(-r, r + 1), k):
        out += w * np.roll(V, -j, axis=0)
    return out


def build(ctx):
    river = ctx['river']; sampler = ctx['ground_sampler']; mats = ctx['mats']
    P = LY.boundary_polygon(DS)
    n = len(P)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    left = np.c_[-T[:, 1], T[:, 0]]
    NOUT = -left if area > 0 else left
    s = np.arange(n) * DS
    reg = [region_of(x, y) for x, y in P]
    gap = np.array([gap_of(x, y, river) for x, y in P])
    canyon = np.array([1.0 if r_ in ('Cliff', 'Cliff.001', 'Cliff.002') else 0.0 for r_ in reg])
    canyon = gauss_smooth_closed(canyon[:, None], 12 / DS)[:, 0]
    # distance (along the boundary) to the nearest gap -> taper the cliff into rounded noses
    eg = np.full(n, 99.0)
    idx_gap = np.where(gap)[0]
    if len(idx_gap):
        for i in range(n):
            dd = np.abs(idx_gap - i); dd = np.minimum(dd, n - dd)
            eg[i] = dd.min() * DS
    taper = S.smoothstep(0.0, 9.0, eg)
    # ---------------- per-station profile parameters
    n1 = noise1(s, 1 / 45, 11); n2 = noise1(s, 1 / 70, 12); n3 = noise1(s, 1 / 38, 13); n4 = noise1(s, 1 / 21, 14)
    n5 = noise1(s, 1 / 27, 15); nb = noise1(s, 1 / 13, 16)
    gul = np.clip((S.ridged2(s / 8.5, np.full(n, 3.3), 17, 2) - 0.78) / 0.22, 0, 1) ** 1.3
    H1 = (5.2 + 2.6 * n1) * (1 - canyon) + (4.6 + 1.6 * n1) * canyon
    t2 = S.smoothstep(-0.35, 0.25, n2) * (1 - 0.4 * canyon)
    H2 = H1 + t2 * ((5.0 + 4.0 * n3) * (1 - canyon) + (3.2 + 1.6 * n3) * canyon)
    H1 *= 0.28 + 0.72 * taper; H2 = H1 + (H2 - H1) * taper
    butt = np.clip(nb, -1, 1) * 1.2
    d_t = np.clip(2.5 + 0.9 * n4 - butt * 0.6 + gul * 1.1 + (1 - taper) * 3.0, 1.2, 5.5)
    z_t = 0.17 * H1 + 0.3 + gul * 0.7
    k1 = np.tan(np.radians(78 + 5 * n5)); k2 = np.tan(np.radians(76 - 5 * n5))
    r1 = (0.42 + 0.16 * n3) * (1 - 0.35 * canyon); r2 = (0.5 + 0.18 * n4) * (1 - 0.35 * canyon)
    b1 = np.clip(2.4 + 2.2 * n5 + (1 - t2) * 2.0, 1.2, 6.0)
    d_e1 = d_t + np.maximum(H1 - z_t, 0) / k1 + r1 * 0.4 + gul * 1.6 - butt * 0.5
    d_e2 = d_e1 + b1 + np.maximum(H2 - H1, 0) / k2
    d_max = (26.0 + 4.0 * n2) * (1 - canyon) + 13.5 * canyon
    d_max = np.maximum(d_max, d_e2 + 4.0)
    d_back = d_max + (18.0 * (1 - canyon) + 8.0 * canyon)          # long gentle outer slope (basin read)
    # ---------------- dense profile per column, resampled by arc length
    dgrid = np.arange(-0.5, d_back.max() + 0.05, 0.05)
    D = dgrid[None, :]
    def col(a):
        return a[:, None]
    zt = np.where(D <= col(d_t), -0.05 + (col(z_t) + 0.05) * np.clip(D / col(d_t), 0, 1) ** 1.7,
                  col(z_t) + (D - col(d_t)) * 0.72)
    f1 = np.where(D < col(d_e1), col(H1) - MS.fall(col(d_e1) - D, col(r1), col(k1)), col(H1) + 0.06 * (D - col(d_e1)))
    f2 = np.where(D < col(d_e2), col(H2) - MS.fall(col(d_e2) - D, col(r2), col(k2)), col(H2))
    Z = np.maximum(np.maximum(zt, f1), f2)
    Z = np.minimum(Z, np.maximum(f2, f1) + 0.0)
    # outer side: rolling highland sloping gently down to the plain
    back = S.smootherstep(col(d_max) - 2.0, col(d_back), D)
    Z = Z * (1 - 0.82 * back) + 0.4 * back * S.fbm2(D * 0.12, col(s) * 0.05, 23, 2)
    # strata benches on the steep parts
    dz = np.gradient(Z, 0.05, axis=1)
    steep = S.smoothstep(1.3, 3.2, np.abs(dz))
    Z = Z + (S.soft_terrace(Z, 1.12, 0.55, 0.21) - Z) * steep * 0.7
    Z = np.where(D > col(d_back), np.nan, Z)
    # arc-length resampling
    seg = np.sqrt(0.05 ** 2 + np.diff(np.nan_to_num(Z, nan=0.0), axis=1) ** 2)
    seg = np.where(np.isnan(Z[:, 1:]), 0.0, seg)
    cum = np.concatenate([np.zeros((n, 1)), np.cumsum(seg, axis=1)], 1)
    tot = cum[:, -1:]
    u = np.linspace(0, 1, N_ROWS)[None, :] * tot
    DR = np.zeros((n, N_ROWS)); ZR = np.zeros((n, N_ROWS))
    Zf = np.nan_to_num(Z, nan=0.0)
    for i in range(n):
        DR[i] = np.interp(u[i], cum[i], dgrid); ZR[i] = np.interp(u[i], cum[i], Zf[i])
    # curvature along the profile (concave -> cavity) for colours
    d2 = np.gradient(np.gradient(Zf, 0.05, axis=1), 0.05, axis=1)
    CAV = np.zeros((n, N_ROWS))
    for i in range(n):
        CAV[i] = np.interp(DR[i], dgrid, d2[i])
    CAV = np.clip(CAV * 0.08, -1, 1)
    # surface detail (rough faces) along the local normal, strongest on steep rows
    sl = np.abs(np.gradient(ZR, axis=1)) / np.maximum(np.abs(np.gradient(DR, axis=1)), 1e-3)
    st_ = S.smoothstep(0.8, 2.6, sl)
    SS = np.repeat(s[:, None], N_ROWS, 1)
    qz = (ZR - 0.21) / 0.88; tq = qz - np.floor(qz)
    groove = 0.22 * np.exp(-((tq - 0.5) / 0.075) ** 2)
    qz2 = (ZR - 0.6) / 2.6; tq2 = qz2 - np.floor(qz2)
    groove = groove + 0.18 * np.exp(-((tq2 - 0.5) / 0.05) ** 2)          # deeper bedding plane every ~2.6 m
    runnel = 0.26 * np.clip((S.ridged2(SS / 3.4, ZR * 0.03, 24, 2) - 0.88) / 0.12, 0, 1) ** 1.8
    DR = DR + (groove + runnel) * st_ * (ZR > 0.4)
    # ---------------- positions: smoothed normals grow with the offset (no folds behind spurs)
    levels = np.array([0, 1, 2, 4, 8, 14, 22, 34.0, 52.0])
    NL = []
    for lv in levels:
        Nn = gauss_smooth_closed(NOUT, max(0.6, 0.75 * lv) / DS)
        NL.append(Nn / np.linalg.norm(Nn, axis=1, keepdims=True))
    NL = np.array(NL)                                  # (levels, n, 2)
    X = np.zeros((n, N_ROWS)); Y = np.zeros((n, N_ROWS))
    for k in range(N_ROWS):
        dk = DR[:, k]
        li = np.clip(np.searchsorted(levels, dk) - 1, 0, len(levels) - 2)
        t = np.clip((dk - levels[li]) / (levels[li + 1] - levels[li]), 0, 1)[:, None]
        Nk = NL[li, np.arange(n)] * (1 - t) + NL[li + 1, np.arange(n)] * t
        Nk /= np.linalg.norm(Nk, axis=1, keepdims=True)
        X[:, k] = P[:, 0] + Nk[:, 0] * dk; Y[:, k] = P[:, 1] + Nk[:, 1] * dk
    # relax folds along s (rows far from the line)
    for k in range(N_ROWS):
        if DR[:, k].mean() < 3.0:
            continue
        for it in range(6):
            Q = np.c_[X[:, k], Y[:, k]]
            fwd = np.roll(Q, -1, 0) - Q
            bad = (fwd * T).sum(1) < 0.15 * DS
            if not bad.any():
                break
            bad = bad | np.roll(bad, 1) | np.roll(bad, -1)
            avg = 0.5 * (np.roll(Q, 1, 0) + np.roll(Q, -1, 0))
            Q[bad] = 0.4 * Q[bad] + 0.6 * avg[bad]
            X[:, k] = Q[:, 0]; Y[:, k] = Q[:, 1]
    det = 0.13 * S.fbm2(SS / 1.4, ZR / 0.95, 21, 3) + 0.06 * S.fbm2(SS / 0.55, ZR / 0.4, 22, 2)
    disp = det * (0.25 + 0.75 * st_) * (ZR > 0.05)
    # push along the horizontal outward normal (faces) and up (flats)
    NX = (X - P[:, :1]); NY = (Y - P[:, 1:2])
    nl = np.maximum(np.hypot(NX, NY), 1e-6)
    NX = np.where(nl > 1e-3, NX / nl, NOUT[:, :1]); NY = np.where(nl > 1e-3, NY / nl, NOUT[:, 1:2])
    X = X + NX * disp * st_; Y = Y + NY * disp * st_
    ZR = ZR + disp * (1 - st_) * 0.4
    ZR = np.where(DR < 0.02, np.minimum(ZR, -0.04), ZR)
    # ---------------- runs per object (skip gaps); adjacent runs share their seam column
    keep = ~gap
    runs = []
    i0 = None
    order = list(range(n))
    start = int(np.argmax(gap)) if gap.any() else 0
    order = order[start:] + order[:start]
    cur = None; cols = []
    for i in order + [order[0]]:
        r_ = reg[i] if keep[i] else None
        if r_ != cur:
            if cur is not None and cols:
                if r_ is not None:
                    cols.append(i)                    # share the seam column with the next run
                runs.append((cur, cols))
            cur = r_; cols = [i] if r_ is not None else []
        elif r_ is not None:
            cols.append(i)
    if cur is not None and cols:
        runs.append((cur, cols))
    by_obj = {}
    stats = {}
    for name, cl in runs:
        if len(cl) < 3:
            continue
        cl = np.array(cl)
        Xr, Yr, Zr = X[cl], Y[cl], ZR[cl]
        co, tris, used = S.grid_tris(Xr, Yr, Zr)
        fn, _ = S.face_normals(co, tris)
        if (fn[:, 2] < 0).mean() > 0.5:
            tris = tris[:, ::-1]
        cav = CAV[cl].ravel()[used]
        by_obj.setdefault(name, []).append((co, tris, cav))
    out_arrays = {}
    total_dense = 0; total = 0
    for name, items in by_obj.items():
        arrs = []
        for co, tris, cav in items:
            total_dense += len(tris)
            co2, t2, at = S.decimate(co, tris, 0.42, {'cav': cav})
            fn, _ = S.face_normals(co2, t2); vn = S.vertex_normals(co2, t2)
            zf = co2[t2][:, :, 2]
            role = np.where(zf.max(1) < 0.3, 2, 1)
            tone = (0.52, 0.22, 0.12) if 'Cliff.0' in name or name.startswith('AP_') else (0.55, 0.24, 0.13)
            rock = S.rock_colours(co2, vn, tone, hash(name) % 1000, band=1.2, cavity=at['cav'], top_z=14.0)
            g = sampler.many(co2[:, 0], co2[:, 1])
            tal = 0.5 * rock[:, :3] + 0.5 * g * 0.92
            lv = t2.ravel(); rl = np.repeat(role, 3)
            cc = np.ones((len(lv), 4))
            cc[:, :3] = np.where((rl == 2)[:, None], tal[lv], rock[lv, :3])
            for r_ in (1, 2):
                m = role == r_
                if not m.any():
                    continue
                c3, t3, _ = S.sub_tris(co2, t2, m)
                a = S.arrays_from_tris(c3, t3, None, uv_tile=6.0 if r_ == 1 else 40.0, corner_col=cc.reshape(-1, 3, 4)[m].reshape(-1, 4))
                arrs.append(with_mat(a, 0 if r_ == 1 else 1))
            total += len(t2)
        out_arrays[name] = arrs
    for name, arrs in out_arrays.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        stats[name] = replace_mesh(ob, arrs, [mats['Rock_Strata'], mats['Ground']],
                                   'v13: continuous sculpted layered cliff along the boundary (talus, 2 tiers, buttresses, gullies, rounded gap noses)')
    ctx['perimeter'] = dict(P=P, NOUT=NOUT, d_t=d_t, gap=gap, X=X, Y=Y, Z=ZR, DR=DR)
    return stats, total_dense, total


def scree(ctx):
    """Rounded pebbles on the new talus aprons (AP_Scree_* objects keep their names, one per cliff object)."""
    per = ctx['perimeter']; P = per['P']; NOUT = per['NOUT']; d_t = per['d_t']; gap = per['gap']
    mats = ctx['mats']
    targets = {}
    for ob in bpy.data.objects:
        if ob.name.startswith('AP_Scree_') and ob.type == 'MESH':
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            c = sum(pts, Vector()) / 8
            targets[ob.name] = (region_of(c.x, c.y), ob)
    by_region = {}
    for nm, (rg, ob) in targets.items():
        by_region.setdefault(rg, []).append(ob)
    r = random.Random(1313)
    acc = {ob.name: L.MeshAccumulator() for _, ob in targets.values()}
    X, Y, Z, DR = per['X'], per['Y'], per['Z'], per['DR']
    count = 0
    for i in range(0, len(P), 2):
        if gap[i]:
            continue
        rg = region_of(P[i, 0], P[i, 1])
        obs = by_region.get(rg)
        if not obs:
            continue
        for k in range(r.choice([0, 0, 1, 1])):
            dd = r.uniform(0.25, max(0.4, d_t[i] * 0.95))
            zz = float(np.interp(dd, DR[i], Z[i]))
            q = P[i] + NOUT[i] * dd
            size = r.uniform(0.1, 0.32) * (1.6 if r.random() < 0.12 else 1.0)
            a = S.pebble_arrays(9000 + count, size, subdiv=0 if size < 0.2 else 1)
            ang = r.uniform(0, math.tau)
            Rm = np.array([[math.cos(ang), -math.sin(ang), 0], [math.sin(ang), math.cos(ang), 0], [0, 0, 1]])
            a['co'] = a['co'] @ Rm.T + np.array((q[0], q[1], zz - 0.02))
            ob = obs[count % len(obs)]
            acc[ob.name].add(to_object_space(with_mat(a, 0), ob))
            count += 1
    st = {}
    for nm, (rg, ob) in targets.items():
        A = acc[nm]
        if A.empty():
            continue
        mats_ = [mats['Rock_Strata']]
        old = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        new = A.build(ob.data.name + '__v13', materials=mats_, sharp_angle=80.0, weighted=False)
        users, _ = L.swap_mesh(ob.data, new, note='v13: rounded scree pebbles rescattered on the new talus aprons')
        for o in users:
            L.set_object_materials(o, mats_)
        st[nm] = (old, sum(len(p.vertices) - 2 for p in new.polygons))
    return st


def run(ctx):
    stats, dense, total = build(ctx)
    sc = scree(ctx)
    ctx['stats']['perimeter'] = dict(objects=stats, dense_tris=dense, tris=total, scree=sc)
    print('STEP13 perimeter', ctx['stats']['perimeter'], flush=True)
