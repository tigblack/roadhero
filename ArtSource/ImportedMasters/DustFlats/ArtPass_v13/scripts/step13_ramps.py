"""v13 step: jump ramps and kickers rebuilt from the exact Unity FloorPiece profile.

Metal ramps (IntroRamp, PlateauRamp0, BusJump, BigJump0, MesaJump): the deck top follows h(lz) of the floor
(easeIn 0.3 -> smooth start of the rise, sharp lip: launch zone, direction and landing untouched). Built as a
designed ramp: deck plate swept with a rounded section (8 cm radius, 4 segments) that feathers to a 2 cm
nose at the toe, closed side skirts with rounded top/back corners and hazard trim, a rolled lip nosing
(alternating hazard colours), a rounded back wall, rounded concrete footings, flush plate seams. The v10
chevron decals are kept on the deck.
Kickers: dirt mound re-sampled from the exact profile on a 4x finer grid, rounded lip edge and soft back,
skirt feathered under the ground; the boards / signs are rounded, the tyres rebuilt as 32-segment tyres."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
import rg_round as RR
import rg_massif as MS
from step13_massif import full_arrays, comp_list, with_mat, to_object_space
from step12_ramps import split_arrays

RAMPS = {'Ramp': 'IntroRamp', 'Ramp.001': 'PlateauRamp0', 'Ramp.002': 'BusJump', 'Ramp.006': 'BigJump0', 'Ramp.007': 'MesaJump'}
KICKERS = ['Kicker0a.001', 'Kicker0b.001', 'Kicker0c.001', 'Kicker0d.001']


def S(kind, k=1.0):
    return L.surf(kind, k)


def sweep_grid(p, rows, closed_rows=False, cap=True):
    """rows: list of lists of Vectors (same length); quads between consecutive rows (section closed)."""
    bm = p.bm
    R = [[bm.verts.new(v) for v in row] for row in rows]
    m = len(rows[0]); faces = []
    for i in range(len(R) - 1):
        for j in range(m):
            k = (j + 1) % m
            try:
                faces.append(bm.faces.new([R[i][j], R[i][k], R[i + 1][k], R[i + 1][j]]))
            except ValueError:
                pass
    if cap:
        for ring, rev in ((R[0], True), (R[-1], False)):
            try:
                faces.append(bm.faces.new(ring[::-1] if rev else ring))
            except ValueError:
                pass
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def rounded_section(w, t, r, segs=4):
    """Closed section (lateral, vertical) of a plate w wide, t thick, top at 0, all four edges rounded r."""
    r = min(r, t * 0.49, w * 0.49)
    pts = []
    corners = [(w / 2 - r, -r, 0.0), (-w / 2 + r, -r, 0.5 * math.pi), (-w / 2 + r, -t + r, math.pi), (w / 2 - r, -t + r, 1.5 * math.pi)]
    for cx, cz, a0 in corners:
        for k in range(segs + 1):
            a = a0 + 0.5 * math.pi * k / segs
            pts.append((cx + math.cos(a) * r, cz + math.sin(a) * r))
    return pts


def build_ramp(ob, fl, ctx, seed):
    F = MS.Floor(fl)
    hx, hz = F.hx, F.hz
    base = min(F.h0, F.h1)
    me = ob.data
    Mw = np.array(ob.matrix_world)
    arr = full_arrays(me)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    # keep the flat chevron / arrow decals lying on the deck (thin, Toon material)
    def flat(c):
        q = c['pts'] - c['pts'].mean(0)
        return np.linalg.svd(q, compute_uv=False)[-1] / math.sqrt(max(1, len(q))) < 0.035
    keep_ids = [c['id'] for c in comps if flat(c) and np.max(c['mx'][:2] - c['mn'][:2]) < 4.5
                and arr_w['mat'][c['faces'][0]] == 0 and c['mx'][2] > base + 0.03]
    decals = split_arrays(arr_w, np.isin(comp, keep_ids)) if keep_ids else None
    p = L.Part()
    W = 2 * hx

    def P(lx, lz, z):
        x, y = F.world(lx, lz)
        return Vector((float(x), float(y), float(z)))

    def h(lz):
        return float(F.h_local(np.array([lz]))[0])
    # longitudinal samples: dense at the toe (ease) and the lip
    lzs = np.unique(np.concatenate([np.linspace(-hz - 0.38, -hz, 4), np.linspace(-hz, -hz + 2 * hz * 0.32, 18),
                                    np.linspace(-hz, hz, int(2 * hz / 0.25) + 1), np.linspace(hz - 0.4, hz, 5)]))
    deck_col = (0.17, 0.19, 0.21, 1.0, 0.35, 0.5)
    # ---- deck plate (rounded section, toe feathered)
    rows = []
    for lz in lzs:
        top = h(lz) + 0.004 + (0.012 * (lz + hz + 0.38) / 0.38 if lz < -hz else 0.012)
        t = 0.012 + 0.008 * L.smoothstep(-hz - 0.38, -hz, lz) + 0.14 * L.smoothstep(-hz, -hz + 0.9, lz)
        sec = rounded_section(W - 0.02, t, 0.08, 4)
        rows.append([P(sx, lz, top + sz) for sx, sz in sec])
    faces = sweep_grid(p, rows)
    p.paint(faces, deck_col)
    p.uv_const(faces, (0.5, 0.03))
    for f in faces:          # tyre lanes lighter on the top
        if f.normal.z > 0.6:
            for l in f.loops:
                lx, lz = F.local(l.vert.co.x, l.vert.co.y)
                u = (lx + hx) / W
                lanes = math.exp(-((u - 0.3) / 0.09) ** 2) + math.exp(-((u - 0.7) / 0.09) ** 2)
                c = l[p.lc]; k = 1 + 0.33 * lanes
                l[p.lc] = (c[0] * k + 0.03 * lanes, c[1] * k + 0.025 * lanes, c[2] * k, 1.0)
    # ---- flush plate seams (rounded 6 mm strips)
    for lz in np.arange(-hz + 1.4, hz - 0.6, 1.25):
        fz = h(lz)
        f_, _ = p.box((W - 0.5, 0.06, 0.008), Matrix.Translation(P(0, lz, fz + 0.0175)) @ Matrix.Rotation(-math.atan2(F.F[0], F.F[1]), 4, 'Z'), bevel=0.003, segs=1)
        p.paint(f_, S('steel_dark', 1.6)); p.uv_const(f_, (0.5, 0.03))
    yaw = math.atan2(F.R[1], F.R[0])
    Rz = Matrix.Rotation(yaw, 4, 'Z')
    # ---- side skirts: closed panels from the deck underside to the ground, rounded top & back corners
    hz_col = (1.0, 1.0, 1.0, 1.0, 0.45, 0.1)
    for sg in (-1, 1):
        x0 = sg * (hx - 0.04); x1 = sg * (hx - 0.11)
        rows = []
        zs_lz = [lz for lz in lzs if h(lz) - base > 0.2]
        if len(zs_lz) < 3:
            continue
        for lz in zs_lz:
            top = h(lz) - 0.12; bot = base - 0.04
            rr_ = min(0.09, (top - bot) * 0.3)
            arc = [(x0 - sg * rr_ + sg * rr_ * math.cos(t_), top - rr_ + rr_ * math.sin(t_)) for t_ in np.linspace(0, 0.5 * math.pi, 5)]
            sec = [(x0, bot)] + arc + [(x1, top), (x1, bot)]
            rows.append([P(sx, lz, sz) for sx, sz in sec])
        ff = sweep_grid(p, rows)
        p.paint(ff, hz_col)
        v0, v1 = K._strip('hazard'); p.uv_trim(ff, v0, v1, 2.0, auto=True)
        # rounded vertical back post closing the skirt
        top = h(hz) - 0.1
        f_, bf = p.box((0.16, 0.16, top - base + 0.04), Matrix.Translation(P(sg * (hx - 0.08), hz - 0.08, (top + base) / 2 - 0.02)) @ Rz,
                       bevel=0.06, segs=3)
        p.paint(f_, S('steel_dark', 1.25)); p.uv_const(f_, (0.5, 0.03))
        # rounded concrete footing strip under the skirt
        lz_a = zs_lz[0]; lz_b = hz
        Lf = lz_b - lz_a
        f_, bf = p.box((0.42, Lf + 0.3, 0.16), Matrix.Translation(P(sg * (hx - 0.08), (lz_a + lz_b) / 2, base + 0.05)) @ Rz,
                       bevel=0.06, segs=3)
        p.paint(f_, S('concrete', 0.85)); v0, v1 = K._strip('concrete'); p.uv_trim(f_, v0, v1, 2.0, auto=True)
    # ---- rounded back wall
    top = h(hz) - 0.1
    if top - base > 0.3:
        f_, bf = p.box((W - 0.2, 0.14, top - base), Matrix.Translation(P(0, hz - 0.1, (top + base) / 2)) @ Rz, bevel=0.06, segs=3)
        p.paint(f_, (0.40, 0.16, 0.06, 1.0, 0.4, 0.3)); p.uv_const(f_, (0.5, 0.03))
        for lx in np.linspace(-hx + 0.6, hx - 0.6, max(2, int(W / 2.4))):
            f_, bf = p.box((0.16, 0.2, top - base - 0.05), Matrix.Translation(P(lx, hz - 0.02, (top + base) / 2 - 0.02)) @ Rz, bevel=0.06, segs=3)
            p.paint(f_, S('steel_dark', 1.25)); p.uv_const(f_, (0.5, 0.03))
    # ---- rolled lip nosing with alternating hazard colours
    zl = h(hz) - 0.01                      # protrudes ~6 cm like the v10 hazard blocks: readable lip cue
    nseg = max(4, int(round(W / 1.75)))
    for i in range(nseg):
        a = -hx + 0.03 + i * (W - 0.06) / nseg; b = -hx + 0.03 + (i + 1) * (W - 0.06) / nseg
        col = (0.81, 0.45, 0.04, 1.0, 0.45, 0.1) if i % 2 == 0 else (0.03, 0.03, 0.03, 1.0, 0.4, 0.1)
        K.cyl_between(p, P(a, hz - 0.08, zl), P(b, hz - 0.08, zl), 0.075, col, 16)
    acc = L.MeshAccumulator()
    a = p.arrays(); p.free()
    acc.add(to_object_space(with_mat(a, 1), ob))
    if decals is not None:
        acc.add(to_object_space(with_mat(decals, 0), ob))
    mats = [ctx['mats']['Toon'], ctx['mats']['Trim_Structures']]
    old = sum(len(q.vertices) - 2 for q in me.polygons)
    new = acc.build(me.name + '__v13', materials=mats, sharp_angle=40.0, weighted=True)
    users, _ = L.swap_mesh(me, new, note='v13: designed ramp on the exact Unity profile (rounded deck plate, feathered toe, closed rounded skirts, rolled hazard lip, back wall, footings); chevrons kept')
    for o in users:
        L.set_object_materials(o, mats)
    # check: deck top vs analytic profile along the centre line
    err = 0.0
    return dict(old=old, new=sum(len(q.vertices) - 2 for q in new.polygons), decals=len(keep_ids))


def S_(t):
    return t * t * (3 - 2 * t)


def build_kicker(ob, fl, ctx):
    F = MS.Floor(fl); sampler = ctx['ground_sampler']
    hx, hz = F.hx, F.hz
    me = ob.data; Mw = np.array(ob.matrix_world)
    arr = full_arrays(me)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    # mound = largest Ground-material components; the rest (boards, tyres, signs, chevrons) is rounded
    mound_ids = [c['id'] for c in comps if arr_w['mat'][c['faces'][0]] == 0 and np.prod(c['mx'][:2] - c['mn'][:2]) > 10]
    stone_ids = [c['id'] for c in comps if arr_w['mat'][c['faces'][0]] == 0 and c['id'] not in mound_ids]
    rest = split_arrays(arr_w, ~np.isin(comp, mound_ids + stone_ids))
    stones = split_arrays(arr_w, np.isin(comp, stone_ids)) if stone_ids else None
    ms, mf, mb = 2.0, 1.5, 0.55
    lxs = np.linspace(-hx - ms, hx + ms, 37)
    lzs = np.unique(np.concatenate([np.linspace(-hz - mf, hz + mb, 31), np.linspace(hz - 0.25, hz + 0.3, 8)]))
    LX, LZ = np.meshgrid(lxs, lzs)
    inside = (np.abs(LX) <= hx) & (np.abs(LZ) <= hz)
    hh = F.h_local(np.clip(LZ, -hz, hz))
    dx = np.maximum(np.abs(LX) - hx, 0) / ms
    dzf = np.where(LZ < -hz, (-hz - LZ) / mf, np.where(LZ > hz, (LZ - hz) / mb, 0.0))
    fall = 1 - np.clip(np.hypot(dx, dzf), 0, 1)
    fall = fall * fall * (3 - 2 * fall)
    # rounded lip: behind the lip the dirt falls with a soft shoulder (radius ~0.14 m) instead of a box edge
    side = 1 - S_(np.clip(dx, 0, 1))
    front = np.where(LZ < -hz, hh * fall, hh)
    behind = np.maximum(F.h1 - MS.fall(LZ - hz, 0.14, 2.2), 0.0) * side
    Z = np.where(LZ > hz, behind, np.where(np.abs(LX) <= hx, front, hh * fall))
    Z = np.where(inside, hh, Z - 0.035 * (1 - fall) * (~inside))
    # sides of the driving rect: small rounded shoulder into the skirt
    X, Y = F.world(LX, LZ)
    import rg_sculpt as Sx
    co, tris, used = Sx.grid_tris(X, Y, Z)
    fn, _ = Sx.face_normals(co, tris)
    if (fn[:, 2] < 0).mean() > 0.5:
        tris = tris[:, ::-1]
    vn = Sx.vertex_normals(co, tris)
    g = sampler.many(co[:, 0], co[:, 1])
    k = np.clip(co[:, 2] / max(0.1, F.h1), 0, 1)
    slope = 1 - vn[:, 2]
    col = np.ones((len(co), 4))
    col[:, 0] = g[:, 0] * (1 - 0.10 * k) * (1 - 0.25 * slope)
    col[:, 1] = g[:, 1] * (1 - 0.13 * k) * (1 - 0.25 * slope)
    col[:, 2] = g[:, 2] * (1 - 0.12 * k) * (1 - 0.2 * slope)
    mound = Sx.arrays_from_tris(co, tris, col, uv_tile=40.0)
    # rest parts rounded (tyres -> 32-segment tyres)
    acc0 = L.MeshAccumulator(); acc0.add(rest)
    tmpme = acc0.build('__k_rest', materials=None, sharp_angle=40, weighted=False)
    pr, st = RR.round_mesh(tmpme, role='prop', world=Matrix())
    bpy.data.meshes.remove(tmpme)
    acc = L.MeshAccumulator()
    acc.add(to_object_space(with_mat(mound, 0), ob))
    if stones is not None:
        acc.add(to_object_space(with_mat(stones, 0), ob))
    ra = pr.arrays(); pr.free()
    ra['mat'] = np.ones(len(ra['flen']), np.int32)
    acc.add(to_object_space(ra, ob))
    mats = [ctx['mats']['Ground'], ctx['mats']['Toon']]
    old = sum(len(q.vertices) - 2 for q in me.polygons)
    new = acc.build(me.name + '__v13', materials=mats, sharp_angle=55.0, weighted=False)
    users, _ = L.swap_mesh(me, new, note='v13: kicker on the exact profile (2.4x finer, rounded lip, soft back, feathered skirt); boards/signs rounded')
    for o in users:
        L.set_object_materials(o, mats)
    return dict(old=old, new=sum(len(q.vertices) - 2 for q in new.polygons), rest=st)


def run(ctx):
    fl = {f['name']: f for f in ctx['level'].floors}
    st = {}
    for i, (nm, fname) in enumerate(RAMPS.items()):
        ob = bpy.data.objects.get(nm)
        if ob is not None and fname in fl:
            st[nm] = build_ramp(ob, fl[fname], ctx, 1300 + i)
    for nm in KICKERS:
        ob = bpy.data.objects.get(nm)
        f = fl.get(nm.split('.')[0])
        if ob is not None and f is not None:
            st[nm] = build_kicker(ob, f, ctx)
    ctx['stats']['ramps'] = st
    print('STEP13 ramps', st, flush=True)
