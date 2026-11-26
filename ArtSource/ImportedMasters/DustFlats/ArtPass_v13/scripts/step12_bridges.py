"""v12 step: bridges.
Bridge 1 carries main road 0 over the river: the deck follows the road's curved centre line, asphalt top re-uses
the road UVs (markings continue), smooth eased approach ramps (no thresholds), concrete deck slab with chamfers,
4 riveted steel girders, piers with rounded cutwaters on the river bed, abutments + wing / retaining walls,
low railings, repair patches. The road mesh is cut only where the bridge replaces it.
Bridge 2 is a track bridge (timber deck on steel stringers, low pony trusses, steel trestle piers, earth ramps)
leading from the centre to the ridge pass. Both keep the fords as the other way across."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import rg_lib as L
import rg_kit as K
import rg_layout12 as LY
from step_rocks import original_arrays
from step_structures import with_mat


def S(kind, k=1.0):
    return L.surf(kind, k)


def ease(t):
    t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)


class Path:
    def __init__(self, pts, step=0.5):
        P = np.array(pts, float)
        d = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(d)])
        n = max(2, int(s[-1] / step)); t = np.linspace(0, s[-1], n)
        self.P = np.c_[np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])]; self.s = t
        T = np.gradient(self.P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
        self.T = T; self.N = np.c_[-T[:, 1], T[:, 0]]

    def at(self, s):
        i = int(np.clip(np.searchsorted(self.s, s), 1, len(self.s) - 1)); a = (s - self.s[i - 1]) / max(1e-6, self.s[i] - self.s[i - 1])
        p = self.P[i - 1] * (1 - a) + self.P[i] * a; t = self.T[i - 1] * (1 - a) + self.T[i] * a; t /= np.linalg.norm(t)
        return p, t, np.array([-t[1], t[0]])


class RoadUV:
    """UV / height lookup on the original road mesh (barycentric on the nearest triangle)."""
    def __init__(self, ob):
        me = ob.data; Mw = ob.matrix_world
        me.calc_loop_triangles()
        self.V = [Mw @ v.co for v in me.vertices]
        self.tris = [tuple(t.vertices) for t in me.loop_triangles]; self.tl = [tuple(t.loops) for t in me.loop_triangles]
        uv = np.zeros(len(me.loops) * 2); me.uv_layers['UVMap'].data.foreach_get('uv', uv); self.uv = uv.reshape(-1, 2)
        flat = [Vector((v.x, v.y, 0)) for v in self.V]
        self.bvh = BVHTree.FromPolygons(flat, self.tris)

    def lookup(self, x, y):
        loc, nrm, idx, dist = self.bvh.find_nearest(Vector((x, y, 0)))
        a, b, c = (self.V[i] for i in self.tris[idx]); la, lb, lc = self.tl[idx]
        v0 = Vector((b.x - a.x, b.y - a.y)); v1 = Vector((c.x - a.x, c.y - a.y)); v2 = Vector((x - a.x, y - a.y))
        d00 = v0.dot(v0); d01 = v0.dot(v1); d11 = v1.dot(v1); d20 = v2.dot(v0); d21 = v2.dot(v1)
        den = d00 * d11 - d01 * d01 or 1e-9
        v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den; u = 1 - v - w
        uv = self.uv[la] * u + self.uv[lb] * v + self.uv[lc] * w
        z = a.z * u + b.z * v + c.z * w
        return (float(uv[0]), float(uv[1])), float(z)


def road_crossing(level, river, road_index=0):
    pts, width = level.roads[road_index]
    path = Path(pts, 0.5)
    i, d, w, b, D, k = river.query(path.P[:, 0], path.P[:, 1])
    inside = np.abs(d) < (w + b + 0.6)
    idx = np.where(inside)[0]
    runs = []
    for a in idx:
        if runs and a == runs[-1][-1] + 1: runs[-1].append(a)
        else: runs.append([a])
    return path, width, [(path.s[r[0]], path.s[r[-1]]) for r in runs]


def deck_strip(p, path, s0, s1, half_w, zfun, s_col, uvfun=None, step=0.5, nlat=6):
    """Top surface strip along a path between s0..s1 (z = zfun(s)); optional uvfun(x, y) -> (uv, z_road)."""
    bm = p.bm; rows = []
    ss = np.arange(s0, s1 + 1e-6, step)
    if ss[-1] < s1: ss = np.append(ss, s1)
    for s in ss:
        P, T, N = path.at(s)
        row = []
        for j in range(nlat + 1):
            u = -1 + 2 * j / nlat
            q = P + N * u * half_w
            row.append(bm.verts.new((q[0], q[1], zfun(s, u))))
        rows.append(row)
    faces = []
    for a in range(len(rows) - 1):
        for j in range(nlat):
            faces.append(bm.faces.new([rows[a][j], rows[a][j + 1], rows[a + 1][j + 1], rows[a + 1][j]]))
    bm.normal_update()
    p.paint(faces, s_col, mat=0)
    if uvfun:
        for f in faces:
            for l in f.loops:
                uv, _ = uvfun(l.vert.co.x, l.vert.co.y)
                l[p.luv].uv = uv
    return rows


def side_wall(p, path, s0, s1, off, zbot, ztop_fun, thick, s_col, strip='concrete', step=1.0):
    """Wall following the path at lateral offset 'off', from zbot(s) to ztop_fun(s)."""
    bm = p.bm
    ss = np.arange(s0, s1 + 1e-6, step)
    if ss[-1] < s1: ss = np.append(ss, s1)
    outer = []; inner = []
    for s in ss:
        P, T, N = path.at(s)
        qo = P + N * (off + np.sign(off) * thick / 2); qi = P + N * (off - np.sign(off) * thick / 2)
        zt = ztop_fun(s); zb = zbot(s)
        outer.append((bm.verts.new((qo[0], qo[1], zb)), bm.verts.new((qo[0], qo[1], zt + 0.0))))
        inner.append((bm.verts.new((qi[0], qi[1], zb)), bm.verts.new((qi[0], qi[1], zt))))
    faces = []
    for a in range(len(ss) - 1):
        o0, o1 = outer[a], outer[a + 1]; i0, i1 = inner[a], inner[a + 1]
        for quad in ([o0[0], o1[0], o1[1], o0[1]], [i0[1], i1[1], i1[0], i0[0]], [o0[1], o1[1], i1[1], i0[1]]):
            try:
                faces.append(bm.faces.new(quad if off > 0 else quad[::-1]))
            except ValueError:
                pass
    for (o, i) in ((outer[0], inner[0]), (outer[-1], inner[-1])):
        try:
            faces.append(bm.faces.new([o[0], o[1], i[1], i[0]]))
        except ValueError:
            pass
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    p.paint(faces, s_col, mat=1)
    v0, v1 = K._strip(strip); p.uv_trim(faces, v0, v1, 2.0, auto=True)
    return faces


def build_road_bridge(ctx, river):
    level = ctx['level']
    path, width, runs = road_crossing(level, river, 0)
    if not runs:
        return None
    cs0, cs1 = max(runs, key=lambda r: r[1] - r[0])
    H = 1.05; Lr = 9.5
    sa_deck = cs0 - 1.2; sb_deck = cs1 + 1.2
    sa = sa_deck - Lr; sb = sb_deck + Lr
    road_ob = bpy.data.objects['Road']
    ruv = RoadUV(road_ob)
    def zroad(x, y):
        return ruv.lookup(x, y)[1]
    P0, _, _ = path.at(sa); P1, _, _ = path.at(sb)
    z0 = zroad(*P0); z1 = zroad(*P1)
    def ztop(s, u=0.0):
        base = z0 + (z1 - z0) * (s - sa) / (sb - sa)
        if s < sa_deck:
            h = H * ease((s - sa) / Lr)
        elif s > sb_deck:
            h = H * ease((sb - s) / Lr)
        else:
            h = H
        return base + h + 0.006
    half = width / 2 + 0.25
    p = L.Part(); pdeck = L.Part(); r = random.Random(1001)
    asphalt = (1.0, 1.0, 1.0, 1.0, 0.0, 0.0)
    deck_strip(pdeck, path, sa, sb, half, lambda s, u: ztop(s, u), asphalt, uvfun=ruv.lookup, step=0.5, nlat=6)
    conc = S('concrete', 0.95); conc_d = S('concrete', 0.75); steel = S('steel_dark', 1.25)
    girder_col = (0.40, 0.15, 0.06, 1.0, 0.35, 0.3)
    # deck slab edge (fascia) and soffit under the span, chamfered look via two steps
    for sgn in (-1, 1):
        side_wall(p, path, sa_deck - 0.6, sb_deck + 0.6, sgn * (half + 0.3), lambda s: ztop(s) - 0.42, lambda s: ztop(s) + 0.22, 0.6, conc, 'concrete')
        # curbs' steel edge angle
        side_wall(p, path, sa_deck - 0.6, sb_deck + 0.6, sgn * (half + 0.62), lambda s: ztop(s) - 0.45, lambda s: ztop(s) + 0.18, 0.06, steel, 'plain')
        # retaining walls along the approach ramps (ground -> ramp top)
        side_wall(p, path, sa, sa_deck - 0.6, sgn * (half + 0.2), lambda s: -0.15, lambda s: ztop(s) + 0.12, 0.4, conc_d, 'concrete')
        side_wall(p, path, sb_deck + 0.6, sb, sgn * (half + 0.2), lambda s: -0.15, lambda s: ztop(s) + 0.12, 0.4, conc_d, 'concrete')
    # soffit slab
    side_wall(p, path, sa_deck - 0.6, sb_deck + 0.6, 0.0, lambda s: ztop(s) - 0.42, lambda s: ztop(s) - 0.05, 2 * half + 0.2, conc_d, 'concrete')
    # girders (I-sections) between abutments
    for lat in np.linspace(-half + 0.9, half - 0.9, 4):
        side_wall(p, path, sa_deck - 0.3, sb_deck + 0.3, lat, lambda s: ztop(s) - 0.95, lambda s: ztop(s) - 0.42, 0.08, girder_col, 'rustplate')
        side_wall(p, path, sa_deck - 0.3, sb_deck + 0.3, lat, lambda s: ztop(s) - 1.0, lambda s: ztop(s) - 0.93, 0.34, girder_col, 'panel')
        # rivet rows on the webs
        for s in np.arange(sa_deck, sb_deck, 0.6):
            P, T, N = path.at(s)
            for sg in (-1, 1):
                q = P + N * (lat + sg * 0.05)
                K.bolt(p, (q[0], q[1], ztop(s) - 0.55), (N[0] * sg, N[1] * sg, 0), 0.022, S('steel', 0.8), 0.015, segs=6)
    # piers on the river bed with rounded cutwaters, steel cap beams
    span = sb_deck - sa_deck
    npier = max(1, int(span / 7.5))
    for k in range(npier):
        s = sa_deck + span * (k + 1) / (npier + 1)
        P, T, N = path.at(s)
        zb, *_ = river.height(np.array([P[0]]), np.array([P[1]]))
        zb = float(zb[0]) - 0.25; zt = ztop(s) - 1.0
        Mp = Matrix.Translation((P[0], P[1], (zb + zt) / 2)) @ Matrix.Rotation(math.atan2(N[1], N[0]), 4, 'Z')
        K.box(p, (2 * half - 0.6, 0.8, zt - zb), Mp, conc, 'concrete', 0.06, wear=S('concrete', 1.1))
        for sg in (-1, 1):
            q = P + N * sg * (half - 0.3)
            K.cyl_between(p, (q[0], q[1], zb), (q[0], q[1], zt), 0.4, conc, 16, 'concrete', bevel=0.04)
        K.box(p, (2 * half + 0.4, 1.0, 0.22), Matrix.Translation((P[0], P[1], zt + 0.0)) @ Matrix.Rotation(math.atan2(N[1], N[0]), 4, 'Z'), steel, 'panel', 0.02)
        # water-line stain band
        K.box(p, (2 * half - 0.55, 0.82, 0.18), Matrix.Translation((P[0], P[1], LY.WATER_Z + 0.05)) @ Matrix.Rotation(math.atan2(N[1], N[0]), 4, 'Z'),
              (0.22, 0.24, 0.20, 1, 0.1, 0), 'plain', 0.03)
        if k == 0:   # repair: timber shoring + sandbags at this pier
            for sg in (-1, 1):
                q = P + N * sg * 1.2 + T * 0.9
                K.beam(p, (q[0], q[1], zb + 0.1), (q[0], q[1], zt - 0.02), 0.22, 0.22, S('wood', 0.8), 'board_b', 0.02)
            for m in range(5):
                q = P + T * (0.9 + 0.25 * (m % 2)) + N * (m - 2) * 0.55
                K.box(p, (0.5, 0.32, 0.2), Matrix.Translation((q[0], q[1], zb + 0.35 + 0.18 * (m % 2))) @ Matrix.Rotation(r.uniform(-0.3, 0.3), 4, 'Z'),
                      S('canvas_dark', 1.0), 'plain', 0.07)
    # abutments
    for s in (sa_deck, sb_deck):
        P, T, N = path.at(s)
        Mp = Matrix.Translation((P[0], P[1], (ztop(s) - 0.4) / 2 - 0.2)) @ Matrix.Rotation(math.atan2(N[1], N[0]), 4, 'Z')
        K.box(p, (2 * half + 1.4, 1.2, ztop(s) - 0.4 + 0.6), Mp, conc_d, 'concrete', 0.08, wear=conc)
    # railings on the span: posts every 2 m, two round rails, hazard end posts; one bent section + timber repair
    for sgn in (-1, 1):
        ss = np.arange(sa_deck - 0.4, sb_deck + 0.41, 2.0)
        for j, s in enumerate(ss):
            P, T, N = path.at(s); q = P + N * sgn * (half + 0.45)
            col = (0.95, 0.62, 0.05, 1, 0.45, 0.1) if j in (0, len(ss) - 1) else S('galvanized', 0.85)
            K.cyl_between(p, (q[0], q[1], ztop(s) + 0.2), (q[0], q[1], ztop(s) + 1.05), 0.055, col, 8)
        for zz in (0.6, 0.98):
            for a, b in zip(ss[:-1], ss[1:]):
                Pa, _, Na = path.at(a); Pb, _, Nb = path.at(b)
                qa = Pa + Na * sgn * (half + 0.45); qb = Pb + Nb * sgn * (half + 0.45)
                bend = 0.12 if (sgn > 0 and abs((a + b) / 2 - (sa_deck + sb_deck) / 2) < 1.5 and zz > 0.9) else 0.0
                if sgn < 0 and abs((a + b) / 2 - sa_deck - 3.0) < 1.1 and zz < 0.9:
                    K.board(p, (qa[0], qa[1], ztop(a) + zz + 0.2), (qb[0], qb[1], ztop(b) + zz + 0.2), 0.22, 0.05, S('wood', 0.9), 'board_b')
                    continue
                K.cyl_between(p, (qa[0], qa[1], ztop(a) + zz + 0.2 - bend), (qb[0], qb[1], ztop(b) + zz + 0.2 - bend), 0.04, S('galvanized', 0.8), 10)
    # deck repair plate (1 cm) and asphalt patch rim
    P, T, N = path.at((sa_deck + sb_deck) / 2 + 2.0)
    K.box(p, (1.6, 1.2, 0.012), Matrix.Translation((P[0] + N[0] * 1.8, P[1] + N[1] * 1.8, ztop((sa_deck + sb_deck) / 2) + 0.006)) @ Matrix.Rotation(math.atan2(T[1], T[0]) + 0.08, 4, 'Z'),
          S('steel_dark', 1.5), 'diamond', 0.0)
    for (cx, cy) in ((0.7, 0.5), (-0.7, 0.5), (0.7, -0.5), (-0.7, -0.5)):
        q = np.array([P[0] + N[0] * 1.8, P[1] + N[1] * 1.8]) + T * cx + N * cy
        K.bolt(p, (q[0], q[1], ztop(0) * 0 + ztop((sa_deck + sb_deck) / 2) + 0.012), (0, 0, 1), 0.03, S('steel', 0.8), 0.015)
    acc = L.MeshAccumulator(); acc.add(with_mat(pdeck.arrays(), 0)); acc.add(with_mat(p.arrays(), 1)); p.free(); pdeck.free()
    mats = [ctx['mats']['Road0'], ctx['mats']['Trim_Structures']]
    me = acc.build('AP_Bridge_Road0', materials=mats, sharp_angle=40)
    L.new_object('AP_Bridge_Road0', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=mats,
                 note='new: road-0 bridge over the river (deck follows the road; asphalt top keeps the road UVs)')
    # cut the road where the bridge replaces it (keep 0.8 m overlap at both ramp feet)
    cut_road(road_ob, path, sa + 0.8, sb - 0.8, width / 2 + 1.5)
    deck_samples = []
    for s in np.arange(sa, sb + 0.01, 1.0):
        P, T, N = path.at(s)
        deck_samples.append(dict(s=round(float(s - sa), 2), x=round(float(P[0]), 3), y=round(float(P[1]), 3), z_top=round(float(ztop(s)), 3),
                                 half_width=round(float(half), 2)))
    return dict(name='AP_Bridge_Road0', road='road 0', deck_height=H, ramp_length=Lr, span=round(float(sb_deck - sa_deck), 2),
                total_length=round(float(sb - sa), 2), width=round(float(2 * half), 2), samples=deck_samples,
                river_s=float(river.s[int(river.query(np.array([path.at((cs0 + cs1) / 2)[0][0]]), np.array([path.at((cs0 + cs1) / 2)[0][1]]))[0][0])]))


def cut_road(ob, path, s0, s1, half):
    me = ob.data
    n = len(me.polygons)
    cen = np.zeros(n * 3); me.polygons.foreach_get('center', cen); cen = cen.reshape(-1, 3)
    Mw = np.array(ob.matrix_world); w = cen @ Mw[:3, :3].T + Mw[:3, 3]
    # nearest path station per face
    keep_faces = np.ones(n, bool)
    for fi in range(n):
        dd = np.hypot(path.P[:, 0] - w[fi, 0], path.P[:, 1] - w[fi, 1]); j = int(np.argmin(dd))
        if dd[j] < half and s0 <= path.s[j] <= s1:
            keep_faces[fi] = False
    lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    ls = np.zeros(n, np.int32); me.polygons.foreach_get('loop_start', ls); lt = np.zeros(n, np.int32); me.polygons.foreach_get('loop_total', lt)
    vmask = np.zeros(len(me.vertices), bool)
    for fi in np.where(keep_faces)[0]:
        vmask[lv[ls[fi]:ls[fi] + lt[fi]]] = True
    arr = original_arrays(me, vmask)
    # original_arrays keeps polys whose verts are all kept: drop the cut faces explicitly
    acc = L.MeshAccumulator(); acc.add(arr)
    mats = [s.material for s in ob.material_slots]
    new = acc.build(me.name + '__v12', materials=mats, sharp_angle=60.0, weighted=False)
    users, _ = L.swap_mesh(me, new, note=f'v12: {int((~keep_faces).sum())} faces removed under the river bridge (replaced by the bridge deck)')
    for o in users:
        L.set_object_materials(o, mats)


def build_track_bridge(ctx, river, sampler):
    idx = [i for i, k in enumerate(river.kind) if k == 'bridge2']
    i = idx[len(idx) // 2]
    C = river.P[i]; A = river.N[i]                       # across the river
    half_corr = river.A[i, 0] + river.A[i, 1]
    Hs = half_corr + 1.0; H = 0.9; Lr = 7.5; half = 3.3
    pts = [C - A * (Hs + Lr + 6), C + A * (Hs + Lr + 6)]
    path = Path(pts, 0.5)
    mid = path.s[-1] / 2
    sa = mid - Hs - Lr; sb = mid + Hs + Lr; sa_deck = mid - Hs; sb_deck = mid + Hs
    def ztop(s, u=0.0):
        if s < sa_deck: return H * ease((s - sa) / Lr) + 0.004
        if s > sb_deck: return H * ease((sb - s) / Lr) + 0.004
        return H
    p = L.Part(); pg = L.Part(); r = random.Random(2002)
    # earth ramps (Ground material, compacted track colour) up to the abutments
    def gcol(x, y):
        g = sampler(x, y); return (g[0] * 0.88, g[1] * 0.86, g[2] * 0.84)
    for (s0, s1) in ((sa, sa_deck), (sb_deck, sb)):
        rows = deck_strip(pg, path, s0, s1, half + 0.6, lambda s, u: ztop(s) - (0.18 * max(0.0, abs(u) - 0.8) / 0.2 if abs(u) > 0.8 else 0.0),
                          (1, 1, 1, 1, 0, 0), step=0.5, nlat=8)
        for row in rows:
            for v in row:
                for l in v.link_loops:
                    c = gcol(v.co.x, v.co.y); l[pg.lc] = (c[0], c[1], c[2], 1.0)
        # stone-faced ramp flanks
        for sgn in (-1, 1):
            side_wall(p, path, s0, s1, sgn * (half + 0.75), lambda s: -0.2, lambda s: ztop(s) - 0.05, 0.35, S('rock', 1.0), 'concrete')
    # deck: steel stringers + cross planks
    for lat in (-2.2, -0.75, 0.75, 2.2):
        side_wall(p, path, sa_deck - 0.4, sb_deck + 0.4, lat, lambda s: H - 0.62, lambda s: H - 0.12, 0.26, (0.36, 0.14, 0.06, 1, 0.35, 0.3), 'rustplate')
    for s in np.arange(sa_deck - 0.3, sb_deck + 0.3, 0.32):
        P, T, N = path.at(s)
        a = P + N * (half + 0.15); b = P - N * (half + 0.15)
        k = r.uniform(0.8, 1.1)
        K.board(p, (a[0], a[1], H - 0.04 + r.uniform(-0.01, 0.01)), (b[0], b[1], H - 0.04), 0.29, 0.08,
                (0.40 * k, 0.26 * k, 0.14 * k, 1, 0.1, 0), r.choice(['board_a', 'board_b']), up=(T[0], T[1], 0))
    # wheel runner planks (lighter, worn) along the deck
    for lat in (-1.0, 1.0):
        side_wall(p, path, sa_deck - 0.3, sb_deck + 0.3, lat, lambda s: H, lambda s: H + 0.05, 0.6, S('wood_light', 0.9), 'board_a')
    # pony trusses (low) on both sides
    for sgn in (-1, 1):
        ss = np.linspace(sa_deck - 0.3, sb_deck + 0.3, 7)
        top = []; bot = []
        for s in ss:
            P, T, N = path.at(s); q = P + N * sgn * (half + 0.3)
            top.append((q[0], q[1], H + 1.0)); bot.append((q[0], q[1], H + 0.05))
            K.beam(p, (q[0], q[1], H - 0.1), (q[0], q[1], H + 1.0), 0.14, 0.14, (0.42, 0.16, 0.06, 1, 0.4, 0.3), 'panel', 0.015)
        for a, b in zip(top[:-1], top[1:]):
            K.beam(p, a, b, 0.16, 0.12, (0.42, 0.16, 0.06, 1, 0.4, 0.3), 'panel', 0.015)
        for j in range(len(ss) - 1):
            a, b = (bot[j], top[j + 1]) if j % 2 == 0 else (top[j], bot[j + 1])
            K.beam(p, a, b, 0.08, 0.08, S('steel_dark', 1.3), 'plain', 0.0)
    # steel trestle piers in the water
    span = sb_deck - sa_deck
    for k in range(2):
        s = sa_deck + span * (k + 1) / 3
        P, T, N = path.at(s)
        zb, *_ = river.height(np.array([P[0]]), np.array([P[1]])); zb = float(zb[0]) - 0.2
        legs = [P + N * l for l in (-2.6, -0.9, 0.9, 2.6)]
        for q in legs:
            K.beam(p, (q[0], q[1], zb), (q[0], q[1], H - 0.6), 0.22, 0.22, S('steel_dark', 1.2), 'panel', 0.02, up=(T[0], T[1], 0))
        K.beam(p, (legs[0][0], legs[0][1], H - 0.62), (legs[-1][0], legs[-1][1], H - 0.62), 0.3, 0.2, S('steel_dark', 1.2), 'panel', 0.015, ext=0.3)
        K.beam(p, (legs[0][0], legs[0][1], zb + 0.15), (legs[-1][0], legs[-1][1], H - 0.7), 0.06, 0.1, S('steel', 0.7), 'plain', 0.0)
        K.beam(p, (legs[-1][0], legs[-1][1], zb + 0.15), (legs[0][0], legs[0][1], H - 0.7), 0.06, 0.1, S('steel', 0.7), 'plain', 0.0)
    # abutments: timber cribs filled with stones
    for s in (sa_deck, sb_deck):
        P, T, N = path.at(s)
        Mp = Matrix.Translation((P[0], P[1], H / 2 - 0.25)) @ Matrix.Rotation(math.atan2(N[1], N[0]), 4, 'Z')
        K.box(p, (2 * half + 1.6, 1.0, H + 0.3), Mp, S('concrete', 0.85), 'concrete', 0.06)
    acc = L.MeshAccumulator(); acc.add(with_mat(p.arrays(), 1)); acc.add(with_mat(pg.arrays(), 2)); p.free(); pg.free()
    mats = [ctx['mats']['Road0'], ctx['mats']['Trim_Structures'], ctx['mats']['Ground']]
    me = acc.build('AP_Bridge_Track', materials=mats, sharp_angle=40)
    L.new_object('AP_Bridge_Track', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=mats,
                 note='new: track bridge (timber deck, steel stringers, pony trusses, trestle piers, earth ramps) towards the ridge pass')
    samples = []
    for s in np.arange(sa, sb + 0.01, 1.0):
        P, T, N = path.at(s)
        samples.append(dict(s=round(float(s - sa), 2), x=round(float(P[0]), 3), y=round(float(P[1]), 3), z_top=round(float(ztop(s)), 3), half_width=half))
    # approach ruts (centre side and ridge-pass side)
    ruts = []
    for (s0, s1) in ((sa - 14, sa + 1.0), (sb - 1.0, sb + 14)):
        ruts.append([tuple(path.at(min(max(s, 0.0), path.s[-1]))[0]) for s in np.linspace(s0, s1, 10)])
    return dict(name='AP_Bridge_Track', road='track (centre <-> ridge pass)', deck_height=H, ramp_length=Lr, span=round(float(span), 2),
                total_length=round(float(sb - sa), 2), width=2 * half, samples=samples, river_s=float(river.s[i])), ruts


def run(ctx):
    river = ctx['river']
    b1 = build_road_bridge(ctx, river)
    b2, ruts = build_track_bridge(ctx, river, ctx['ground_sampler'])
    ctx['bridges'] = [b for b in (b1, b2) if b]
    ctx['bridge_ruts'] = ruts
    # dirt-track ruts leading to the track bridge (Ground material, seamless)
    import step_ground as SG
    acc = L.MeshAccumulator()
    for path in ruts:
        part = SG.rut_ribbon(path, ctx['ground_sampler'], half_w=1.5, gauge=0.9)
        acc.add_part(part); part.free()
    me = acc.build('AP_Ground_BridgeTrackRuts', materials=[ctx['mats']['Ground']], sharp_angle=80, weighted=False)
    L.new_object('AP_Ground_BridgeTrackRuts', me, ctx['coll_ground'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Ground']],
                 note='new: track ruts leading to the track bridge from the centre and from the ridge pass')
    ctx['stats']['bridges'] = [dict(name=b['name'], span=b['span'], total=b['total_length'], width=b['width'], deck=b['deck_height']) for b in ctx['bridges']]
    print('STEP12 bridges done', ctx['stats']['bridges'], flush=True)
