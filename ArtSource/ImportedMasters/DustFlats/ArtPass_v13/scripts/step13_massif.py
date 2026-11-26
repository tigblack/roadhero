"""v13 step: rock massifs sculpted (Lookout Mesa, Plateau 0, Ridge 0; the perimeter in step13_perimeter).

* Lookout Mesa: the box with wedge walls becomes one sculpted sandstone massif (rg_massif): exact Unity floors
  (S1/H1/S2/H2/S3/L3/Top) on top, 0.2 m rounded shoulders + near-vertical layered faces between the lanes
  (inside the lane margins), eroded / buttressed outer cliffs with rounded corners, soft benches and talus aprons
  where there is room (none towards the river, the S1 approach and the jump landing). Decks -> MesaDecks
  (Ground material, small v10 marks kept), rock -> MesaRock (Rock_Strata + Ground on the low talus) with the
  v11 parapet rocks rebuilt as rounded boulders on the same spots; MesaEdgeStones -> rounded stones.
* Plateau 0: same builder; exact 2 m sand top (rounded corners, eroded rim), layered cliff, talus, boulders.
* Ridge 0: continuous sculpted rock walls (crest, steep layered flanks, talus, rounded ends) on the footprint
  of the v11 rock clusters, gaps / pass markers kept clear; markers rebuilt round."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_sculpt as S
import rg_massif as MS
import rg_kit as K
from step_rocks import original_arrays
from step12_ramps import split_arrays, face_comp_ids


def full_arrays(me):
    arr = original_arrays(me, np.ones(len(me.vertices), bool))
    mi = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', mi)
    arr['mat'] = mi
    return arr


def comp_list(arr):
    comp = face_comp_ids(arr)
    starts = np.concatenate([[0], np.cumsum(arr['flen'])[:-1]])
    out = []
    for c in np.unique(comp):
        fs = np.where(comp == c)[0]
        vi = np.unique(np.concatenate([arr['lv'][starts[f]:starts[f] + arr['flen'][f]] for f in fs]))
        pts = arr['co'][vi]
        li = np.concatenate([np.arange(starts[f], starts[f] + arr['flen'][f]) for f in fs])
        out.append(dict(id=c, faces=fs, pts=pts, mn=pts.min(0), mx=pts.max(0), col=arr['col'][li, :3].mean(0)))
    return comp, out


def cluster_stacks(comps, tol=0.7):
    """Group stacked strata pieces (same XY footprint) into one rock."""
    groups = []
    for c in sorted(comps, key=lambda c: c['mn'][2]):
        cx = (c['mn'][:2] + c['mx'][:2]) / 2
        for g in groups:
            gx = (g['mn'][:2] + g['mx'][:2]) / 2
            if np.linalg.norm(cx - gx) < tol + 0.25 * np.linalg.norm(g['mx'][:2] - g['mn'][:2]):
                g['pts'] = np.vstack([g['pts'], c['pts']]); g['mn'] = np.minimum(g['mn'], c['mn']); g['mx'] = np.maximum(g['mx'], c['mx'])
                g['cols'].append(c['col']); break
        else:
            groups.append(dict(pts=c['pts'].copy(), mn=c['mn'].copy(), mx=c['mx'].copy(), cols=[c['col']]))
    return groups


def boulder_from_group(g, seed, flat=0.38, lumpy=0.15, strata=0.6, bury=0.15):
    base, yaw, half, zmin = L.pca_frame(g['pts'])
    hx = max(0.18, half.x * 1.04); hy = max(0.18, half.y * 1.04); hz = max(0.15, half.z / 1.78)
    sz = max(hx, hy, hz)
    sub = 4 if sz > 2.0 else (3 if sz > 0.45 else 2)
    tone = tuple(np.clip(np.mean(g['cols'], 0), 0, 1))
    p = S.boulder_part(seed, hx, hy, hz, subdiv=sub, lumpy=lumpy, flat_top=flat, strata=strata, bury=bury, tone=tone,
                       tilt=random.Random(seed).uniform(-0.05, 0.05))
    a = p.arrays(); p.free()
    W = np.array(Matrix.Translation((base.x, base.y, zmin)) @ Matrix.Rotation(yaw, 4, 'Z'))
    a['co'] = a['co'] @ W[:3, :3].T + W[:3, 3]
    return a


def to_object_space(arr, ob):
    Mi = np.array(ob.matrix_world.inverted())
    a = dict(arr); a['co'] = arr['co'] @ Mi[:3, :3].T + Mi[:3, 3]
    return a


def with_mat(arr, m):
    a = dict(arr); a['mat'] = np.full(len(arr['flen']), m, np.int32)
    return a


def massif_colours(M, co, tris, at, sampler, tone, seed, top_z, deck_tint=(1.0, 1.0, 1.0), sand_top=None):
    """Per-corner colours + roles. role 0 = deck (exact floor), 1 = rock, 2 = low talus (ground material)."""
    fn, _ = S.face_normals(co, tris); vn = S.vertex_normals(co, tris)
    deck_v = at['deck'] > 0.5
    zf = co[tris][:, :, 2]
    role = np.where(deck_v[tris].all(1) & (fn[:, 2] > 0.965), 0, np.where(zf.max(1) < 0.34, 2, 1))
    rock = S.rock_colours(co, vn, tone, seed, band=1.15, cavity=at['cav'], top_z=top_z)
    g = sampler.many(co[:, 0], co[:, 1])
    n1 = S.fbm2(co[:, 0] * 0.21, co[:, 1] * 0.21, seed + 41, 3)
    packed = np.array((0.54, 0.335, 0.18))
    deck = (0.55 * g + 0.45 * packed[None, :]) * (0.97 + 0.07 * n1)[:, None] * np.array(deck_tint)[None, :]
    if sand_top is not None:
        st = (co[:, 2] > sand_top - 0.2)[:, None]
        sand = S.SAND[None, :] * (0.98 + 0.08 * n1)[:, None]
        deck = np.where(st, 0.35 * deck + 0.65 * sand, deck)
    deck *= (1.0 - 0.22 * np.clip(at['cav'], 0, 1))[:, None]        # contact darkening at wall toes
    tal = 0.5 * rock[:, :3] + 0.5 * g * 0.92
    vc = {0: deck, 1: rock[:, :3], 2: tal}
    lv = tris.ravel(); rl = np.repeat(role, 3)
    cc = np.ones((len(lv), 4))
    for r_, arr in vc.items():
        m = rl == r_
        cc[m, :3] = np.clip(arr[lv[m]], 0, 1)
    return role, cc


def split_roles(co, tris, role, cc, uv_tile=6.0):
    out = {}
    for r_ in (0, 1, 2):
        m = role == r_
        if not m.any():
            continue
        c2, t2, used = S.sub_tris(co, tris, m)
        corner = cc.reshape(-1, 3, 4)[m].reshape(-1, 4)
        out[r_] = S.arrays_from_tris(c2, t2, None, uv_tile=uv_tile if r_ == 1 else 40.0, corner_col=corner)
    return out


def replace_mesh(ob, arrays, mats, note, sharp=70.0):
    acc = L.MeshAccumulator()
    for a in arrays:
        acc.add(to_object_space(a, ob))
    old = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    new = acc.build(ob.data.name + '__v13', materials=mats, sharp_angle=sharp, weighted=False)
    nt = sum(len(p.vertices) - 2 for p in new.polygons)
    users, _ = L.swap_mesh(ob.data, new, note=note)
    for o in users:
        L.set_object_materials(o, mats)
    return old, nt


# ================================================================================================ Lookout Mesa
def build_mesa(ctx):
    level = ctx['level']; river = ctx['river']; sampler = ctx['ground_sampler']; mats = ctx['mats']
    fl = {f['name']: f for f in level.floors}
    names = ['MesaS1', 'MesaH1', 'MesaS2', 'MesaH2', 'MesaS3', 'MesaL3', 'MesaTop']
    floors = [MS.Floor(fl[n]) for n in names]

    def space(x, y):
        sp = np.ones(np.shape(x))
        sp = np.where(river.corridor(np.ravel(x), np.ravel(y), 1.4).reshape(np.shape(x)), 0.0, sp)
        sp = np.where((x > -50.6) & (x < -42.4) & (y < 52.6), 0.0, sp)                 # S1 approach road
        sp = np.where((x > -93) & (x < -79) & (y < 61.8) & (y > 30), np.minimum(sp, 0.45), sp)   # jump landing
        return sp

    def cap(x, y):
        c = np.full(np.shape(x), 1e9)
        c = np.where(river.corridor(np.ravel(x), np.ravel(y), 0.15).reshape(np.shape(x)), -0.06, c)
        c = np.where((x > -49.55) & (x < -43.45) & (y < 52.0) & (y > 36), -0.06, c)
        return c
    space = MS.Raster(space, -106, -34, 35, 103, 0.3)
    xs = np.unique(np.concatenate([MS.dense_axis(-103.5, -36.5, 0.42, [-96, -68, -59, -50, -43], 2.3, 0.06),
                                   MS.dense_axis(-103.5, -36.5, 9.0, [-68, -59, -50], 0.85, 0.025)]))
    ys = np.unique(np.concatenate([MS.dense_axis(37.5, 100.5, 0.42, [44, 52, 54, 62, 84, 94], 2.3, 0.06),
                                   MS.dense_axis(37.5, 100.5, 9.0, [54, 62, 84], 0.85, 0.025)]))
    rims = [('MesaTop', 'n', 1.05, 1.6), ('MesaTop', 'w', 1.0, 1.5), ('MesaL3', 'n', 1.0, 1.5), ('MesaH1', 'n', 0.95, 1.5)]
    M = MS.Massif(floors, xs, ys, seed=4401, inner=(0.2, 9.5, 0.26), outer=(0.75, 3.4, 0.6), corner_r=2.0,
                  erode=0.75, bulge=2.0, talus=(0.22, 0.35, 1.7, 0.35), space_fn=space, cap_fn=cap,
                  strata=(0.95, 0.72), blur_sigma=1.4, bench=(0.5, 1.7, 2.8),
                  inner_shrink={'MesaS2': 0.62, 'MesaS3': 0.62, 'MesaH1': 0.5, 'MesaH2': 0.5, 'MesaL3': 0.5, 'MesaTop': 0.6},
                  inner_rho={'MesaS2': 0.42, 'MesaS3': 0.42, 'MesaH1': 0.35, 'MesaH2': 0.35, 'MesaL3': 0.35, 'MesaTop': 0.42},
                  rims=rims)
    import time; t0 = time.time()
    M.build(); t1 = time.time()
    co, tris, at, dense = MS.massif_mesh(M, 62000); t2 = time.time()
    print('MESA timing build', round(t1 - t0, 1), 'mesh+decimate', round(t2 - t1, 1), 'grid', M.X.shape, flush=True)
    tone = (0.52, 0.22, 0.12)
    role, cc = massif_colours(M, co, tris, at, sampler, tone, 4401, 8.6, sand_top=8.0)
    parts = split_roles(co, tris, role, cc)
    # --- MesaDecks: deck faces + the small v10 marks (arrows, summit tufts) kept as they were
    obd = bpy.data.objects['MesaDecks']
    arr = full_arrays(obd.data)
    Mw = np.array(obd.matrix_world)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    small = [c['id'] for c in comps if np.max(c['mx'][:2] - c['mn'][:2]) < 3.5]
    kept = split_arrays(arr_w, np.isin(comp, small)) if small else None
    deck_arrays = [with_mat(parts[0], 0)] + ([with_mat(kept, 0)] if kept is not None else [])
    st = {}
    st['MesaDecks'] = replace_mesh(obd, deck_arrays, [mats['Ground']],
                                   'v13: exact mesa floors cut from the sculpted massif (irregular eroded rims); v10 marks kept')
    # --- MesaRock: sculpted faces + parapet rocks rebuilt as rounded boulders
    obr = bpy.data.objects['MesaRock']
    arr = full_arrays(obr.data); Mw = np.array(obr.matrix_world)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    rocks = [c for c in comps if np.max(c['mx'][:2] - c['mn'][:2]) < 6.0 and len(c['faces']) < 160 and c['mn'][2] < 0.5]
    groups = cluster_stacks(rocks, 0.6)
    boulders = [boulder_from_group(g, 4500 + i) for i, g in enumerate(groups)]
    rock_arrays = [with_mat(parts[1], 0)] + ([with_mat(parts[2], 1)] if 2 in parts else []) + [with_mat(b, 0) for b in boulders]
    st['MesaRock'] = replace_mesh(obr, rock_arrays, [mats['Rock_Strata'], mats['Ground']],
                                  f'v13: sculpted sandstone massif (rounded shoulders, layered faces, eroded buttressed cliffs, talus) + {len(boulders)} rounded parapet boulders')
    # --- edge stones
    obe = bpy.data.objects.get('MesaEdgeStones')
    if obe:
        arr = full_arrays(obe.data); Mw = np.array(obe.matrix_world)
        arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
        comp, comps = comp_list(arr_w)
        groups = cluster_stacks(comps, 0.4)
        bl = []
        rr = random.Random(4699)
        for i, g in enumerate(groups):
            # wider, lower, irregular stones (no more 'pegs'); a smaller companion stone on some
            ext = g['mx'] - g['mn']; c = (g['mn'] + g['mx']) / 2
            k = rr.uniform(1.15, 1.5)
            g2 = dict(g); g2['pts'] = np.vstack([g['pts'], (g['pts'] - c) * np.array([k, k, 0.75]) + c])
            g2['mn'] = g2['pts'].min(0); g2['mx'] = g2['pts'].max(0)
            g2['mn'][2] = g['mn'][2]
            bl.append(with_mat(boulder_from_group(g2, 4700 + i, flat=0.45, lumpy=0.2, strata=0.5, bury=0.25), 0))
            if rr.random() < 0.45:
                g3 = dict(g); off = np.array([rr.uniform(-0.6, 0.6), rr.uniform(-0.6, 0.6), 0])
                g3['pts'] = (g['pts'] - c) * np.array([0.55, 0.55, 0.5]) + c + off
                g3['mn'] = g3['pts'].min(0); g3['mx'] = g3['pts'].max(0); g3['mn'][2] = g['mn'][2]
                bl.append(with_mat(boulder_from_group(g3, 4800 + i, flat=0.35, lumpy=0.22, strata=0.3, bury=0.3), 0))
        st['MesaEdgeStones'] = replace_mesh(obe, bl, [mats['Rock_Strata']], f'v13: {len(bl)} rounded edge stones on the v11 spots')
    st['dense_tris'] = dense
    return st


# ================================================================================================ Plateau 0
def build_plateau(ctx):
    level = ctx['level']; sampler = ctx['ground_sampler']; mats = ctx['mats']
    fl = {f['name']: f for f in level.floors}
    f = MS.Floor(fl['Plateau0'])
    x0, x1 = f.c[0] - f.hx, f.c[0] + f.hx; y0, y1 = f.c[1] - f.hz, f.c[1] + f.hz

    def space(x, y):
        return np.ones(np.shape(x))
    xs = MS.dense_axis(x0 - 6.5, x1 + 6.5, 0.35, [x0, x1], 3.2, 0.05)
    ys = MS.dense_axis(y0 - 6.5, y1 + 6.5, 0.35, [y0, y1], 3.2, 0.05)
    M = MS.Massif([f], xs, ys, seed=5101, outer=(0.42, 5.0, 0.42), corner_r=1.2, erode=0.45, bulge=0.65,
                  talus=(0.22, 0.22, 1.1, 0.25), space_fn=space, strata=(0.55, 0.75), blur_sigma=1.1, bench=(0.5, 1.2, 2.6))
    M.build()
    co, tris, at, dense = MS.massif_mesh(M, 16000)
    role, cc = massif_colours(M, co, tris, at, sampler, (0.53, 0.23, 0.13), 5101, 2.4, sand_top=2.0)
    parts = split_roles(co, tris, role, cc)
    ob = bpy.data.objects['Plateau']
    arr = full_arrays(ob.data); Mw = np.array(ob.matrix_world)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    # v11 rocks around the old box: keep the ones clear of the new cliff body as rounded boulders
    rocks = [c for c in comps if np.max(c['mx'][:2] - c['mn'][:2]) < 6.0]
    groups = cluster_stacks(rocks, 0.6)
    bl = []
    groups.sort(key=lambda g: -np.prod(g['mx'][:2] - g['mn'][:2]))
    for i, g in enumerate(groups):
        # every 2nd v12 rock becomes an accent boulder pushed off the drivable top onto the talus;
        # the approach / flight path from PlateauRamp0 (west side) stays clear
        if i % 2:
            continue
        c = (g['mn'][:2] + g['mx'][:2]) / 2; half = (g['mx'][:2] - g['mn'][:2]) / 2 * 0.85
        if c[0] < x0 + 1.5 and abs(c[1] - f.c[1]) < 6.5:
            continue
        d = [c[0] - x0, x1 - c[0], c[1] - y0, y1 - c[1]]
        k = int(np.argmin(d))
        n = [np.array((-1, 0)), np.array((1, 0)), np.array((0, -1)), np.array((0, 1))][k]
        edge = c.copy()
        if k == 0: edge[0] = x0
        if k == 1: edge[0] = x1
        if k == 2: edge[1] = y0
        if k == 3: edge[1] = y1
        newc = edge + n * (abs(n @ half) + 0.9)
        shift = np.r_[newc - c, 0.0]
        g2 = dict(g); g2['pts'] = (g['pts'] - np.r_[c, 0]) * np.array([0.85, 0.85, 0.8]) + np.r_[c, 0] + shift
        g2['pts'][:, 2] = g2['pts'][:, 2] - g2['pts'][:, 2].min()
        g2['mn'] = g2['pts'].min(0); g2['mx'] = g2['pts'].max(0)
        bl.append(with_mat(boulder_from_group(g2, 5300 + i, bury=0.25), 0))
    arrays = [with_mat(parts[1], 0), with_mat(parts[0], 1)] + ([with_mat(parts[2], 1)] if 2 in parts else []) + bl
    st = {'Plateau': replace_mesh(ob, arrays, [mats['Rock_Strata'], mats['Ground']],
                                  f'v13: sculpted plateau (exact 2 m sand top, rounded corners, eroded rim, layered cliff, talus) + {len(bl)} accent boulders on the talus (v12 rock spots pushed off the drivable top)'),
          'dense_tris': dense}
    return st


# ================================================================================================ Ridge 0
def build_ridge(ctx):
    sampler = ctx['ground_sampler']; mats = ctx['mats']
    ob = bpy.data.objects['Ridge0.001']
    arr = full_arrays(ob.data); Mw = np.array(ob.matrix_world)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    a = np.array((20.0, -53.0)); b = np.array((78.0, -55.0))
    d = b - a; Ln = np.linalg.norm(d); t_ = d / Ln; n_ = np.array((-t_[1], t_[0]))
    rocks = []; markers = []
    for c in comps:
        ext = c['mx'] - c['mn']
        if max(ext[0], ext[1]) < 0.45:
            markers.append(c)
        else:
            rocks.append(c)
    # footprint of the v11 rock clusters in ridge coordinates (t along, s across)
    P = np.concatenate([c['pts'] for c in rocks])
    T = (P[:, :2] - a) @ t_; Sx = (P[:, :2] - a) @ n_
    segs = []
    order = np.argsort(T); Ts = T[order]
    start = Ts[0]; prev = Ts[0]
    for v in Ts[1:]:
        if v - prev > 3.0:
            segs.append((start, prev)); start = v
        prev = v
    segs.append((start, prev))
    ts = np.arange(min(T) - 3, max(T) + 3, 0.12)
    ss = np.arange(-7.5, 7.5, 0.12)
    TT, SS = np.meshgrid(ts, ss)
    WX = a[0] + t_[0] * TT + n_[0] * SS; WY = a[1] + t_[1] * TT + n_[1] * SS
    # envelope of the old rocks: height & half-width per t (smoothed)
    nb = len(ts); H = np.zeros(nb); s_lo = np.full(nb, 9.0); s_hi = np.full(nb, -9.0)
    for i, tv in enumerate(ts):
        m = np.abs(T - tv) < 1.2
        if m.any():
            H[i] = P[m, 2].max(); s_lo[i] = Sx[m].min(); s_hi[i] = Sx[m].max()
    occ = H > 0.3
    k = np.exp(-0.5 * (np.arange(-25, 26) * 0.12 / 1.2) ** 2); k /= k.sum()
    Hs = np.convolve(np.where(occ, H, 0.0), k, mode='same')
    sc = np.convolve(np.where(occ, (s_lo + s_hi) / 2, 0.0), k, mode='same') / np.maximum(np.convolve(occ.astype(float), k, mode='same'), 1e-6)
    wd = np.convolve(np.where(occ, (s_hi - s_lo) / 2, 0.0), k, mode='same') / np.maximum(np.convolve(occ.astype(float), k, mode='same'), 1e-6)
    endf = np.convolve(occ.astype(float), np.ones(21) / 21, mode='same')                 # rounded ends
    Hc = np.maximum(Hs, 0) * S.smoothstep(0.05, 0.85, endf)
    n1 = S.fbm2(TT * 0.18, SS * 0.18, 811, 3); n2 = S.ridged2(TT * 0.4, SS * 0.4 + 2.0, 812, 3)
    hc = np.interp(TT, ts, Hc) * (1.0 + 0.12 * S.fbm2(TT * 0.09, 0 * TT, 813, 2))
    cen = np.interp(TT, ts, sc); hw = np.interp(TT, ts, wd) * 0.86 + 0.35
    e = np.abs(SS - cen) - (hw * (0.62 + 0.12 * n1))            # distance outside the crest band
    crest = hc * (1.0 - 0.10 * np.clip(1 - np.abs(SS - cen) / np.maximum(hw * 0.7, 0.3), 0, 1) * (0.5 + 0.5 * n1))
    face = crest - MS.fall(e + 0.25 * n2, 0.55, 3.4)
    tal = (0.22 * hc + 0.25) * (1 - np.clip((e - 0.6) / (1.3 + 0.25 * hc), 0, 1)) ** 1.8 * (hc > 0.2)
    Z = np.maximum(np.maximum(face, tal), 0)
    gy_, gx_ = np.gradient(Z, ss, ts); slope = np.hypot(gx_, gy_)
    steep = S.smoothstep(1.1, 2.8, slope)
    Z = Z + (0.05 * S.fbm2(WX * 0.9, WY * 0.9, 814, 3) + 0.03 * S.fbm2(WX * 2.6, WY * 2.6, 815, 2)) * (Z > 0.03)
    Z = Z + (S.soft_terrace(Z, 0.95, 0.5, 0.3) - Z) * steep * 0.75
    Z = S.blur2(Z, 1.2)
    gy_, gx_ = np.gradient(Z, ss, ts)
    lap = np.gradient(gx_, ts, axis=1) + np.gradient(gy_, ss, axis=0)
    cav = np.clip(S.blur2(lap, 2.0) * 0.3, -1, 1)
    low = Z < 0.004
    keepv = ~low
    cells = keepv[:-1, :-1] | keepv[:-1, 1:] | keepv[1:, :-1] | keepv[1:, 1:]
    Zm = np.where(low, -0.045, Z)
    co, tris, used = S.grid_tris(WX, WY, Zm, cells)
    fn, _ = S.face_normals(co, tris)
    if (fn[:, 2] < 0).mean() > 0.5:
        tris = tris[:, ::-1]
    dense = len(tris)
    co, tris, at = S.decimate(co, tris, min(1.0, 11000 / max(1, len(tris))), {'deck': np.zeros(len(co)), 'cav': cav.ravel()[used]})

    class _M:
        pass
    role, cc = massif_colours(_M, co, tris, at, sampler, (0.53, 0.23, 0.13), 811, 5.0)
    parts = split_roles(co, tris, role, cc)
    # pass markers rebuilt: 12-sided posts with a rounded painted cap (cairn stones at the foot)
    p = L.Part(); mk = 0
    for c in markers:
        ext = c['mx'] - c['mn']
        if ext[2] < 1.0:
            continue
        cx, cy = (c['mn'][:2] + c['mx'][:2]) / 2
        K.cyl_between(p, (cx, cy, -0.1), (cx, cy, 1.62), 0.1, L.surf('wood_dark', 1.1), 12, bevel=0.0)
        f_, bf = p.box((0.3, 0.3, 0.34), Matrix.Translation((cx, cy, 1.72)), bevel=0.07, segs=3)
        p.paint(f_, (0.82, 0.55, 0.12, 1.0, 0.45, 0.1)); p.uv_const(f_, (0.5, 0.03)); mk += 1
    marker_arr = p.arrays(); p.free()
    cairns = []
    r = random.Random(816)
    for c in markers:
        ext = c['mx'] - c['mn']
        if ext[2] < 1.0:
            continue
        cx, cy = (c['mn'][:2] + c['mx'][:2]) / 2
        for k_ in range(3):
            ang = r.uniform(0, math.tau); rr = r.uniform(0.25, 0.45)
            q = S.boulder_part(817 + len(cairns), r.uniform(0.22, 0.34), r.uniform(0.18, 0.28), r.uniform(0.12, 0.2), subdiv=2,
                               lumpy=0.2, flat_top=0.3, strata=0.0, bury=0.2)
            aa = q.arrays(); q.free(); aa['co'] = aa['co'] + np.array((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr, 0.0))
            cairns.append(with_mat(aa, 0))
    arrays = [with_mat(parts[1], 0)] + ([with_mat(parts[2], 1)] if 2 in parts else []) + [with_mat(marker_arr, 0)] + cairns
    st = {'Ridge0.001': replace_mesh(ob, arrays, [mats['Rock_Strata'], mats['Ground']],
                                     f'v13: sculpted ridge walls on the v11 footprint ({len(segs)} segments: crest, layered flanks, talus, rounded ends); {mk} pass markers rebuilt'),
          'segments': [(round(float(s0), 1), round(float(s1), 1)) for s0, s1 in segs], 'dense_tris': dense}
    return st


def run(ctx):
    st = {}
    st['mesa'] = build_mesa(ctx)
    st['plateau'] = build_plateau(ctx)
    st['ridge'] = build_ridge(ctx)
    ctx['stats']['massif'] = st
    print('STEP13 massif', st, flush=True)
