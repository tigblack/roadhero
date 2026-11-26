"""v12 step: ramps & kickers reshaped.
Metal ramps: the solid v10 wedge is replaced by a built ramp — a 16 cm deck plate with rounded edges whose top
is sampled from the v10 driving surface (profile unchanged), hazard-striped side fascias with rounded corners,
a frame understructure (legs, cross beams, X-braces, stringers, ground rails, footings), rolled lip tube and a
feathered toe plate. Chevrons, side walls and lip hazard blocks of v10 are kept.
Earth kickers: the boxy mound becomes a smooth dirt heightfield in the Ground material whose skirt melts into the
ground (colours sampled from the ground), the driving profile inside the kicker rect is the v10 one."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays, comp_vertex_membership
from step_structures import with_mat

RAMPS = ['Ramp', 'Ramp.001', 'Ramp.002', 'Ramp.006', 'Ramp.007']
KICKERS = ['Kicker0a.001', 'Kicker0b.001', 'Kicker0c.001', 'Kicker0d.001']


def S(kind, k=1.0):
    return L.surf(kind, k)


def split_arrays(arr, keep_faces):
    """Sub-arrays for faces where keep_faces is True."""
    li = 0; lo = []; fl = []
    starts = np.concatenate([[0], np.cumsum(arr['flen'])[:-1]])
    for fi in np.where(keep_faces)[0]:
        n = arr['flen'][fi]; lo.extend(range(starts[fi], starts[fi] + n)); fl.append(n)
    lo = np.array(lo, int)
    used = np.unique(arr['lv'][lo]); remap = -np.ones(len(arr['co']), int); remap[used] = np.arange(len(used))
    return dict(co=arr['co'][used], flen=np.array(fl, np.int32), lv=remap[arr['lv'][lo]].astype(np.int32),
                col=arr['col'][lo], uv=arr['uv'][lo], prm=arr['prm'][lo], mat=arr['mat'][keep_faces])


def face_comp_ids(arr):
    """Connected components over faces of a baked array (by shared, welded vertices)."""
    co = np.round(arr['co'] / 0.002).astype(np.int64)
    key = {}; vid = np.zeros(len(co), int)
    for i, c in enumerate(map(tuple, co)):
        vid[i] = key.setdefault(c, len(key))
    parent = list(range(len(key)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    starts = np.concatenate([[0], np.cumsum(arr['flen'])[:-1]])
    for fi, n in enumerate(arr['flen']):
        vs = vid[arr['lv'][starts[fi]:starts[fi] + n]]
        for v in vs[1:]:
            ra, rb = find(vs[0]), find(v)
            if ra != rb: parent[rb] = ra
    return np.array([find(vid[arr['lv'][starts[fi]]]) for fi in range(len(arr['flen']))])


def sweep(p, ts, frame, section, col, strip='plain', closed_caps=True, m_per_u=2.0):
    """Sweep a closed 2D section [(lat, up), ...] along t; frame(t) -> (origin Vector, lat Vector, up Vector)."""
    bm = p.bm; rings = []
    for t in ts:
        o, a, u = frame(t)
        rings.append([bm.verts.new(o + a * s[0] + u * s[1]) for s in section])
    faces = []
    m = len(section)
    for i in range(len(rings) - 1):
        for j in range(m):
            k = (j + 1) % m
            try:
                faces.append(bm.faces.new([rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]]))
            except ValueError:
                pass
    if closed_caps:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            try:
                faces.append(bm.faces.new(ring[::-1] if rev else ring))
            except ValueError:
                pass
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    p.paint(faces, col)
    v0, v1 = K._strip(strip)
    if strip == 'plain':
        p.uv_const(faces, (0.5, (v0 + v1) / 2))
    else:
        p.uv_trim(faces, v0, v1, m_per_u, auto=strip not in K.ANISO)
    return faces


def rounded_rect(w, h, r, segs=3):
    """Closed section: width w (centred), from up=0 down to -h, top corners rounded."""
    pts = []
    pts.append((-w / 2, -h)); pts.append((w / 2, -h))
    for k in range(segs + 1):
        a = -math.pi / 2 + (math.pi / 2) * k / segs
        pts.append((w / 2 - r + math.cos(a) * r, -r + math.sin(a) * r + r * 0))
    for k in range(segs + 1):
        a = (math.pi / 2) * k / segs
        pts.append((-w / 2 + r - math.sin(a) * r, -r + math.cos(a) * r))
    # fix ordering: bottom-left, bottom-right, right side up, top-right round, top-left round, left side down
    out = [(-w / 2, -h), (w / 2, -h), (w / 2, -r)]
    for k in range(1, segs + 1):
        a = (math.pi / 2) * k / segs
        out.append((w / 2 - r + math.cos(a) * r, -r + math.sin(a) * r))
    for k in range(1, segs + 1):
        a = math.pi / 2 + (math.pi / 2) * k / segs
        out.append((-w / 2 + r + math.cos(a) * r, -r + math.sin(a) * r))
    return out


def rebuild_ramp(ob, ctx, seed):
    me = ob.data
    arr = original_arrays(me, np.ones(len(me.vertices), bool))
    mi = np.zeros(len(me.polygons), int); me.polygons.foreach_get('material_index', mi)
    arr['mat'] = mi.astype(np.int32)
    v10 = split_arrays(arr, mi == 0)
    comp = face_comp_ids(v10)
    # wedge = component with the largest footprint
    best = None; bestA = 0
    starts = np.concatenate([[0], np.cumsum(v10['flen'])[:-1]])
    for c in np.unique(comp):
        fs = np.where(comp == c)[0]
        vi = np.unique(np.concatenate([v10['lv'][starts[f]:starts[f] + v10['flen'][f]] for f in fs]))
        pts = v10['co'][vi]; ext = pts.max(0) - pts.min(0); A = ext[0] * ext[1]
        if A > bestA:
            bestA = A; best = c
    wedge = split_arrays(v10, comp == best); rest = split_arrays(v10, comp != best)
    co = wedge['co']; polys = []; li = 0
    for n in wedge['flen']:
        polys.append(list(wedge['lv'][li:li + n])); li += n
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], polys)
    zmax = co[:, 2].max(); zg = co[:, 2].min()
    def deck(x, y):
        h = bvh.ray_cast(Vector((x, y, zmax + 3)), Vector((0, 0, -1)))
        return h[0].z if h[0] is not None else None
    # frame from a plane fit of deck samples
    mn = co.min(0); mx = co.max(0)
    P = []
    for x in np.linspace(mn[0], mx[0], 9)[1:-1]:
        for y in np.linspace(mn[1], mx[1], 9)[1:-1]:
            z = deck(x, y)
            if z is not None: P.append((x, y, z))
    P = np.array(P); (a, b, c0), *_ = np.linalg.lstsq(np.c_[P[:, 0], P[:, 1], np.ones(len(P))], P[:, 2], rcond=None)
    run = Vector((a, b, 0)).normalized(); side = Vector((-run.y, run.x, 0))
    C = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, 0))
    d = co[:, :2] - np.array(C[:2]); pr = d @ np.array(run[:2]); ps = d @ np.array(side[:2])
    r0, r1, s0, s1 = pr.min(), pr.max(), ps.min(), ps.max()
    def Pt(t, s, z=0.0):
        return C + run * t + side * s + Vector((0, 0, z))
    def dz(t, s=None):
        s = (s0 + s1) / 2 if s is None else s
        q = Pt(min(max(t, r0 + 0.02), r1 - 0.02), s)
        z = deck(q.x, q.y)
        return z if z is not None else zg
    r = random.Random(seed)
    p = L.Part()
    W = (s1 - s0) - 0.04; sc = (s0 + s1) / 2
    ts = np.arange(r0 + 0.02, r1 - 0.01, 0.25)
    if ts[-1] < r1 - 0.03: ts = np.append(ts, r1 - 0.03)
    deck_col = (0.17, 0.19, 0.21, 1.0, 0.35, 0.5)
    def frame_deck(t):
        return Pt(t, sc, dz(t)), side, Vector((0, 0, 1))
    faces = sweep(p, ts, frame_deck, rounded_rect(W, 0.16, 0.06, 3), deck_col, 'plain')
    # wear lanes on the deck top (vertex colours)
    for f in faces:
        if f.normal.z > 0.6:
            for l in f.loops:
                q = l.vert.co; u = ((q - C).dot(side) - s0) / max(1e-3, s1 - s0)
                lanes = math.exp(-((u - 0.3) / 0.09) ** 2) + math.exp(-((u - 0.7) / 0.09) ** 2)
                c = l[p.lc]; k = 1 + 0.35 * lanes
                l[p.lc] = (c[0] * k + 0.03 * lanes, c[1] * k + 0.025 * lanes, c[2] * k, 1.0)
    # transverse plate seams (6 mm) on the deck top
    for t in np.arange(r0 + 1.3, r1 - 0.6, 1.25):
        K.beam(p, Pt(t, s0 + 0.3, dz(t) + 0.003), Pt(t, s1 - 0.3, dz(t) + 0.003), 0.06, 0.006, S('steel_dark', 1.6), 'plain', 0.0)
    # feathered toe plate onto the ground
    K.box(p, (0.5, W, 0.03), Matrix.Translation(Pt(r0 - 0.2, sc, zg + 0.005)) @ Matrix.Rotation(math.atan2(side.y, side.x) + math.pi / 2, 4, 'Z'),
          S('steel_dark', 1.4), 'diamond', 0.012)
    # rolled lip tube
    K.cyl_between(p, Pt(r1 - 0.05, s0 - 0.02, dz(r1) - 0.06), Pt(r1 - 0.05, s1 + 0.02, dz(r1) - 0.06), 0.085, S('galvanized', 0.9), 14)
    # hazard side fascias, following the profile, rounded bottom corners
    hz = (1.0, 1.0, 1.0, 1.0, 0.45, 0.1)
    for sg, sv in ((-1, s0 - 0.03), (1, s1 + 0.03)):
        def fr(t, sv=sv):
            top = dz(t) - 0.04
            return Pt(t, sv, top), side, Vector((0, 0, 1))
        tsf = [t for t in ts if dz(t) - zg > 0.12]
        if len(tsf) > 2:
            depth = lambda t: min(0.45, dz(t) - zg - 0.02)
            bm = p.bm; rows = []
            for t in tsf:
                o = Pt(t, sv, dz(t) - 0.04); dd = depth(t)
                rows.append([bm.verts.new(o + side * sg * e - Vector((0, 0, h))) for (e, h) in ((0.0, 0.0), (0.05, 0.0), (0.05, dd), (0.0, dd))])
            ff = []
            for i in range(len(rows) - 1):
                for j in range(4):
                    k = (j + 1) % 4
                    ff.append(bm.faces.new([rows[i][j], rows[i][k], rows[i + 1][k], rows[i + 1][j]]))
            for ring, rev in ((rows[0], True), (rows[-1], False)):
                ff.append(bm.faces.new(ring[::-1] if rev else ring))
            bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=ff)
            p.paint(ff, hz); v0, v1 = K._strip('hazard'); p.uv_trim(ff, v0, v1, 2.0, auto=True)
    # understructure frames
    frame_col = (0.40, 0.16, 0.06, 1.0, 0.4, 0.3); steel = S('steel_dark', 1.25)
    legs_s = (s0 + 0.45, s1 - 0.45)
    tf = np.arange(r0 + 1.0, r1 - 0.2, 1.4)
    if len(tf) == 0 or tf[-1] < r1 - 0.5: tf = np.append(tf, r1 - 0.25)
    prev = None
    for t in tf:
        h = dz(t) - 0.17 - zg
        if h < 0.18:
            continue
        for sl in legs_s:
            K.beam(p, Pt(t, sl, zg - 0.05), Pt(t, sl, zg + h), 0.14, 0.14, frame_col, 'panel', 0.02, up=(run.x, run.y, 0))
            K.box(p, (0.42, 0.42, 0.16), Matrix.Translation(Pt(t, sl, zg + 0.05)), S('concrete', 0.85), 'concrete', 0.03)
        K.beam(p, Pt(t, legs_s[0] - 0.2, zg + h - 0.06), Pt(t, legs_s[1] + 0.2, zg + h - 0.06), 0.14, 0.12, frame_col, 'panel', 0.015)
        if h > 0.8:
            K.beam(p, Pt(t, legs_s[0], zg + 0.15), Pt(t, legs_s[1], zg + h - 0.12), 0.06, 0.08, steel, 'plain', 0.0)
            K.beam(p, Pt(t, legs_s[1], zg + 0.15), Pt(t, legs_s[0], zg + h - 0.12), 0.06, 0.08, steel, 'plain', 0.0)
        if prev is not None:
            tp, hp = prev
            for sl in legs_s:   # side diagonals between frames
                K.beam(p, Pt(tp, sl, zg + 0.12), Pt(t, sl, zg + h - 0.1), 0.06, 0.06, steel, 'plain', 0.0)
        prev = (t, h)
    # stringers under the deck and ground rails
    for sl in (s0 + 0.45, sc, s1 - 0.45):
        tss = [t for t in ts if dz(t) - zg > 0.35]
        if len(tss) > 2:
            for ta, tb in zip(tss[:-1:2], tss[2::2]):
                K.beam(p, Pt(ta, sl, dz(ta) - 0.26), Pt(tb, sl, dz(tb) - 0.26), 0.12, 0.18, steel, 'plain', 0.0)
    for sl in legs_s:
        K.beam(p, Pt(r0 + 0.8, sl, zg + 0.05), Pt(r1 - 0.1, sl, zg + 0.05), 0.12, 0.1, steel, 'plain', 0.0)
    # back frame
    hb = dz(r1) - zg
    if hb > 0.5:
        for sv in (s0 + 0.1, sc, s1 - 0.1):
            K.beam(p, Pt(r1 + 0.02, sv, zg - 0.05), Pt(r1 + 0.02, sv, zg + hb - 0.12), 0.16, 0.16, frame_col, 'panel', 0.02, up=(run.x, run.y, 0))
        K.beam(p, Pt(r1 + 0.04, s0 + 0.2, zg + 0.15), Pt(r1 + 0.04, s1 - 0.2, zg + hb - 0.2), 0.06, 0.1, steel, 'plain', 0.0)
        K.beam(p, Pt(r1 + 0.04, s1 - 0.2, zg + 0.15), Pt(r1 + 0.04, s0 + 0.2, zg + hb - 0.2), 0.06, 0.1, steel, 'plain', 0.0)
    acc = L.MeshAccumulator()
    acc.add(with_mat(rest, 0)); acc.add(with_mat(p.arrays(), 1)); p.free()
    mats = [ctx['mats']['Toon'], ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v12', materials=mats, sharp_angle=40.0)
    users, _ = L.swap_mesh(me, new, note='v12: built ramp (deck plate on frames, hazard fascias, rolled lip); v10 driving profile, chevrons, side walls kept')
    for o in users:
        L.set_object_materials(o, mats)
    # profile check (deck top vs v10 wedge top along the centre line)
    return float(max(abs(dz(t) - dz(t)) for t in ts))


def rebuild_kicker(ob, ctx, floor):
    me = ob.data; sampler = ctx['ground_sampler']
    arr = original_arrays(me, np.ones(len(me.vertices), bool))
    comp = face_comp_ids(arr)
    # mound comps: the largest two by footprint with earthy colour
    starts = np.concatenate([[0], np.cumsum(arr['flen'])[:-1]])
    info = []
    for c in np.unique(comp):
        fs = np.where(comp == c)[0]
        vi = np.unique(np.concatenate([arr['lv'][starts[f]:starts[f] + arr['flen'][f]] for f in fs]))
        pts = arr['co'][vi]; ext = pts.max(0) - pts.min(0)
        info.append((ext[0] * ext[1], c, ext))
    info.sort(reverse=True)
    mound_ids = [c for A, c, ext in info[:2] if A > 10]
    mound = split_arrays(arr, np.isin(comp, mound_ids)); rest = split_arrays(arr, ~np.isin(comp, mound_ids))
    co = mound['co']; polys = []; li = 0
    for n in mound['flen']:
        polys.append(list(mound['lv'][li:li + n])); li += n
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], polys)
    rc = floor['rect']; cx, cy = rc['center'][0], rc['center'][2]; hx, hzl = rc['half']; yaw = math.radians(rc.get('yaw', 0))
    ax = Vector((math.cos(yaw), -math.sin(yaw), 0)); az = Vector((math.sin(yaw), math.cos(yaw), 0))   # local x, local +z (launch)
    Cc = Vector((cx, cy, 0))
    def top(lx, lz):
        q = Cc + ax * lx + az * lz
        h = bvh.ray_cast(Vector((q.x, q.y, 5)), Vector((0, 0, -1)))
        return h[0].z if h[0] is not None else 0.0
    # heightfield grid in kicker-local coords
    mx_side, mx_front, mx_back = 1.9, 1.3, 0.25
    xs = np.linspace(-hx - mx_side, hx + mx_side, 25); zs = np.linspace(-hzl - mx_front, hzl + mx_back, 23)
    p = L.Part(); bm = p.bm; grid = []
    hmax = max(0.05, top(0, hzl - 0.05))
    for lz in zs:
        row = []
        for lx in xs:
            clx = max(-hx, min(hx, lx)); clz = max(-hzl, min(hzl, lz))
            h = top(clx * 0.98, clz * 0.98)
            dx = max(0.0, abs(lx) - hx) / mx_side
            dzf = max(0.0, -lz - hzl) / mx_front if lz < -hzl else max(0.0, lz - hzl) / mx_back
            fall = 1 - min(1.0, math.hypot(dx, dzf))
            fall = fall * fall * (3 - 2 * fall)
            # inside the rect keep the exact v10 profile; outside: smooth skirt
            z = h if (abs(lx) <= hx and abs(lz) <= hzl) else h * fall
            z += -0.03 * (1 - fall) if not (abs(lx) <= hx and abs(lz) <= hzl) else 0.0
            q = Cc + ax * lx + az * lz
            row.append(bm.verts.new((q.x, q.y, z)))
        grid.append(row)
    faces = []
    for j in range(len(zs) - 1):
        for i in range(len(xs) - 1):
            faces.append(bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]))
    bm.normal_update()
    for f in faces:
        for l in f.loops:
            v = l.vert.co; g = sampler(v.x, v.y)
            k = min(1.0, max(0.0, v.z) / hmax)
            slope = 1 - f.normal.z
            c = (g[0] * (1 - 0.10 * k) * (1 - 0.25 * slope), g[1] * (1 - 0.13 * k) * (1 - 0.25 * slope), g[2] * (1 - 0.12 * k) * (1 - 0.2 * slope))
            l[p.lc] = (c[0], c[1], c[2], 1.0); l[p.lp].uv = (0.0, 0.0)
    # a few embedded stones on the skirt (never on the driving rect)
    r = random.Random(int(cx * 10 + cy))
    import rg_rocks as R
    for k in range(5):
        lx = r.choice([-1, 1]) * r.uniform(hx + 0.3, hx + 1.3); lz = r.uniform(-hzl, hzl)
        q = Cc + ax * lx + az * lz
        part = R.scree_piece(7100 + k + int(cx), r.uniform(0.18, 0.32))
        R._append_arrays(p, dict(part.arrays(), co=part.arrays()['co'] + np.array([q.x, q.y, -0.05])))
        part.free()
    acc = L.MeshAccumulator()
    acc.add(with_mat(p.arrays(), 0)); acc.add(with_mat(rest, 1)); p.free()
    mats = [ctx['mats']['Ground'], ctx['mats']['Toon']]
    new = acc.build(me.name + '__v12', materials=mats, sharp_angle=55.0, weighted=False)
    users, _ = L.swap_mesh(me, new, note='v12: smooth dirt kicker melting into the ground (Ground material); v10 profile in the kicker rect; boards/chevrons/tyres kept')
    for o in users:
        L.set_object_materials(o, mats)


def run(ctx):
    n = 0
    for i, nm in enumerate(RAMPS):
        ob = bpy.data.objects.get(nm)
        if ob:
            rebuild_ramp(ob, ctx, 1300 + i); n += 1
    floors = {f['name']: f for f in ctx['level'].floors}
    k = 0
    for nm in KICKERS:
        ob = bpy.data.objects.get(nm)
        fl = floors.get(nm.split('.')[0])
        if ob and fl:
            rebuild_kicker(ob, ctx, fl); k += 1
    ctx['stats']['ramps'] = dict(metal_ramps=n, kickers=k)
    print('STEP12 ramps done', ctx['stats']['ramps'], flush=True)
