"""v12 step: shallow river carved into the Ground mesh (real channel: bed, gentle banks, point bars),
wet / dry ground transition in vertex colour (+ wet gloss in UV1), separate water surface, fords
(wide, shallow, gravel, striped marker posts, tyre ruts), reed & shrub groups on the banks, boulders
on outer bends (never on crossings). Depth is checked against the reference car (0.30 m clearance)."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
import rg_rocks as R
import rg_layout12 as LY

WATER = LY.WATER_Z


def S(kind, k=1.0):
    return L.surf(kind, k)


def carve_ground(ctx, river):
    ob = bpy.data.objects['Ground']; me = ob.data
    Mw = np.array(ob.matrix_world)
    bm = bmesh.new(); bm.from_mesh(me)
    for rad in (6.0, 2.5):
        bm.faces.ensure_lookup_table()
        cen = np.array([f.calc_center_median()[:] for f in bm.faces])
        w = cen @ Mw[:3, :3].T + Mw[:3, 3]
        i, d, ww, bb, D, k = river.query(w[:, 0], w[:, 1])
        sel = np.abs(d) < (ww + bb + rad)
        edges = list({e for f, s in zip(bm.faces, sel) if s for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    co = np.array([v.co[:] for v in bm.verts])
    w = co @ Mw[:3, :3].T + Mw[:3, 3]
    z, d, ww, bb, D, idx = river.height(w[:, 0], w[:, 1])
    for v, zz in zip(bm.verts, z):
        v.co.z = zz
    # colours: bed / exposed bars / wet band / dry, gloss on wet ground
    lc = bm.loops.layers.float_color['Color']; lp = bm.loops.layers.uv['Unity_MaterialParams']
    bm.verts.index_update()
    ad = np.abs(d); kinds = river.kind
    ford = np.array([kinds[j] == 'ford' for j in idx])
    wh = np.interp(idx, np.arange(len(river.P)), river.water_halfwidth())
    under = z < WATER - 0.005
    exposed_bar = (ad < ww) & ~under & (z < -0.02)
    wet = np.clip(1 - (ad - wh) / 1.8, 0, 1) * (ad < ww + bb + 1.8) * (~under)
    fs = np.array([river.s[f] for f in ford_list(river)]) if ford_list(river) else np.zeros(0)
    sv = river.s[idx]
    lane = np.zeros(len(sv))
    for f_s in fs:
        wl = np.clip((5.0 - np.abs(sv - f_s)) / 1.4, 0, 1) * np.clip((ww + bb + 0.5 - ad) / 1.5, 0, 1)
        lane = np.maximum(lane, wl * wl * (3 - 2 * wl))
    for f in bm.faces:
        for l in f.loops:
            vi = l.vert.index
            c = l[lc]; r, g, b, a = c
            if lane[vi] > 0.02:
                gc = (0.60, 0.54, 0.44) if under[vi] else (0.66, 0.58, 0.46)
                kk = 0.78 * lane[vi]
                if under[vi]:   # keep a little of the wet-bed darkening under the lane
                    r, g, b = r * 0.8, g * 0.8, b * 0.82
                r, g, b = r * (1 - kk) + gc[0] * kk, g * (1 - kk) + gc[1] * kk, b * (1 - kk) + gc[2] * kk
                l[lp].uv = (0.15 if under[vi] else 0.05, 0.0)
            elif under[vi]:
                depth = WATER - z[vi]
                t = min(1.0, depth / 0.22)
                bed = (0.42, 0.33, 0.21) if not ford[vi] else (0.50, 0.44, 0.34)
                r, g, b = (r * 0.45 + bed[0] * 0.55) * (1 - 0.18 * t), (g * 0.45 + bed[1] * 0.55) * (1 - 0.12 * t), (b * 0.45 + bed[2] * 0.55) * (1 - 0.05 * t)
                l[lp].uv = (0.12, 0.0)
            elif exposed_bar[vi]:
                r, g, b = r * 1.08, g * 1.08, b * 1.04
                l[lp].uv = (0.05, 0.0)
            elif wet[vi] > 0:
                k = wet[vi]
                r, g, b = r * (1 - 0.30 * k), g * (1 - 0.32 * k), b * (1 - 0.30 * k)
                l[lp].uv = (0.28 * k, 0.0)
            l[lc] = (r, g, b, a)
    bm.to_mesh(me); bm.free()
    if 'custom_normal' in me.attributes:
        me.attributes.remove(me.attributes['custom_normal'])
    me.shade_smooth()
    me['artpass_v12'] = 'river channel carved: bed, banks, point bars (Ground stays one mesh); see ArtPass_v12/data/river_v12.json'
    me.update()
    return len(me.vertices)


def water_surface(ctx, river):
    p = L.Part(); bm = p.bm
    wh = river.water_halfwidth()
    us = [-1.0, -0.82, -0.5, 0.0, 0.5, 0.82, 1.0]
    rows = []; idxs = list(range(0, len(river.P), 2))
    if idxs[-1] != len(river.P) - 1:
        idxs.append(len(river.P) - 1)
    for i in idxs:
        P = river.P[i]; N = river.N[i]; hw = wh[i] + 0.25
        rows.append([bm.verts.new((P[0] + N[0] * u * hw, P[1] + N[1] * u * hw, WATER)) for u in us])
    for a in range(len(rows) - 1):
        for j in range(len(us) - 1):
            f = bm.faces.new([rows[a][j], rows[a][j + 1], rows[a + 1][j + 1], rows[a + 1][j]])
    bm.verts.index_update()
    for f in bm.faces:
        for l in f.loops:
            j = l.vert.index % len(us)
            u = abs(us[j])
            deep = (0.085, 0.27, 0.25); shallow = (0.24, 0.43, 0.36); rim = (0.50, 0.58, 0.48)
            c = L.mix(deep, shallow, min(1, u / 0.82))
            if u > 0.99:
                c = rim
            l[p.lc] = (c[0], c[1], c[2], 1.0); l[p.lp].uv = (0.85, 0.0)
            x, y, _ = l.vert.co
            l[p.luv].uv = (x / 12.0, y / 12.0)
    acc = L.MeshAccumulator(); acc.add_part(p); p.free()
    me = acc.build('AP_River_Water', materials=[ctx['mats']['River_Water']], sharp_angle=80, weighted=False)
    coll = ctx['coll_river']
    L.new_object('AP_River_Water', me, coll, parent=bpy.data.objects.get('World'), mats=[ctx['mats']['River_Water']],
                 note=f'new: river water surface at z = {WATER} (needs a transparent water shader in Unity)')


def ford_list(river):
    out = []
    run = []
    for i, k in enumerate(river.kind):
        if k == 'ford':
            run.append(i)
        elif run:
            out.append(run[len(run) // 2]); run = []
    return out


def fords(ctx, river, poly):
    """Marker posts, gravel and ruts across each ford."""
    p = L.Part(); r = random.Random(808)
    rut_paths = []
    info = []
    for fi in ford_list(river):
        P = river.P[fi]; N = river.N[fi]; T = river.T[fi]
        w, b = river.A[fi, 0], river.A[fi, 1]
        half = w + b
        zc, *_ = river.height(np.array([P[0]]), np.array([P[1]]))
        info.append(dict(station=int(fi), centre=(float(P[0]), float(P[1])), across=(float(N[0]), float(N[1])),
                         lane_width=9.2, crossing_length=round(float(2 * half), 2), water_depth=round(float(WATER - zc[0]), 3)))
        # striped marker posts at the lane edges on both banks (readable from the game camera)
        for sgn in (-1, 1):
            for lat in (-4.9, 4.9):
                q = P + N * sgn * (half + 0.9) + T * lat
                base = Vector((q[0], q[1], -0.05))
                for k in range(4):
                    col = (0.88, 0.10, 0.04, 1, 0.45, 0.1) if k % 2 == 0 else (0.92, 0.90, 0.84, 1, 0.45, 0.1)
                    K.cyl_between(p, base + Vector((0, 0, k * 0.4)), base + Vector((0, 0, (k + 1) * 0.4)), 0.11, col, 12)
                K.cyl_between(p, base + Vector((0, 0, 1.6)), base + Vector((0, 0, 1.72)), 0.12, (0.05, 0.05, 0.05, 1, 0.4, 0.1), 12)
            # yellow diamond ford sign (wave icon) facing the approach
            q = P + N * sgn * (half + 2.2) + T * 6.0
            Ms = Matrix.Translation((q[0], q[1], 0.0)) @ Matrix.Rotation(math.atan2(N[1] * sgn, N[0] * sgn) + math.pi / 2, 4, 'Z')
            K.cyl_between(p, Ms @ Vector((0, 0, -0.05)), Ms @ Vector((0, 0, 2.0)), 0.06, S('galvanized', 0.85), 8)
            K.box(p, (0.9, 0.04, 0.9), Ms @ Matrix.Translation((0, -0.07, 1.75)) @ Matrix.Rotation(math.pi / 4, 4, 'Y'), (0.95, 0.62, 0.04, 1, 0.45, 0.1), 'plain', 0.03)
            for wv in (-0.12, 0.08):
                K.box(p, (0.5, 0.02, 0.07), Ms @ Matrix.Translation((0, -0.1, 1.75 + wv)) @ Matrix.Rotation(0.18, 4, 'Y'), (0.04, 0.04, 0.04, 1, 0.4, 0.1), 'plain', 0.0)
        # flat paving slabs across the drive lane (protrude <= 5 cm) + a few loose stones at the lane edges
        for k in range(110):
            a = r.uniform(-half * 0.98, half * 0.98); lat = r.uniform(-4.4, 4.4)
            q = P + N * a + T * lat
            z, *_ = river.height(np.array([q[0]]), np.array([q[1]]))
            sz = r.uniform(0.22, 0.42)
            part = R.scree_piece(5000 + fi * 200 + k, sz)
            arr = part.arrays(); part.free()
            tone = r.uniform(0.9, 1.15)
            arr['col'][:, :3] = np.array([0.62, 0.57, 0.48]) * tone
            arr['prm'][:, 0] = 0.12
            M = Matrix.Translation((q[0], q[1], float(z[0]) - sz * 0.12)) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z') @ Matrix.Diagonal((1.15, 1.0, 0.16, 1))
            R._append_arrays(p, dict(arr, co=(arr['co'] @ np.array(M)[:3, :3].T + np.array(M)[:3, 3])))
        # tyre ruts crossing the ford (drive line perpendicular to the river)
        pts = [P + N * t for t in np.linspace(-(half + 9), half + 9, 26)]
        rut_paths.append([(float(q[0]), float(q[1])) for q in pts])
    acc = L.MeshAccumulator(); acc.add_part(p); p.free()
    me = acc.build('AP_River_Fords', materials=[ctx['mats']['Trim_Structures']], sharp_angle=40)
    L.new_object('AP_River_Fords', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Trim_Structures']],
                 note='new: ford markers (striped posts) and gravel; the drive lanes stay clear')
    return rut_paths, info


def ruts(ctx, river, extra_paths):
    import step_ground as SG
    old = bpy.data.objects.get('AP_Ground_TyreRuts')
    if old:
        bpy.data.objects.remove(old)
    sampler = ctx['ground_sampler']
    paths = []
    for path in SG.kicker_ruts(ctx['level'], sampler):
        pts = np.array(path)
        keep = ~river.corridor(pts[:, 0], pts[:, 1], 1.0)
        # split into dry runs
        run = []
        for q, k in zip(path, keep):
            if k:
                run.append(q)
            elif len(run) > 2:
                paths.append(run); run = []
            else:
                run = []
        if len(run) > 2:
            paths.append(run)
    paths += extra_paths
    acc = L.MeshAccumulator()
    nford = len(extra_paths)
    for pi_, path in enumerate(paths):
        part = SG.rut_ribbon(path, sampler, depth=0.22 if pi_ >= len(paths) - nford else 0.13)
        # follow the carved terrain
        for v in part.bm.verts:
            z, *_ = river.height(np.array([v.co.x]), np.array([v.co.y]))
            v.co.z = float(z[0]) + 0.012
        # darker, wetter ruts under / near water
        acc.add_part(part); part.free()
    me = acc.build('AP_Ground_TyreRuts', materials=[ctx['mats']['Ground']], sharp_angle=80, weighted=False)
    L.new_object('AP_Ground_TyreRuts', me, ctx['coll_ground'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Ground']],
                 note='new: tyre ruts at kickers and across the fords (Ground material, follows the channel)')


def reed_cluster(p, c, r, scale=1.0):
    n = r.randint(9, 18)
    for k in range(n):
        a = r.uniform(0, 2 * math.pi); rad = r.uniform(0, 0.55) * scale
        base = Vector((c[0] + math.cos(a) * rad, c[1] + math.sin(a) * rad, c[2] - 0.05))
        h = r.uniform(0.55, 1.25) * scale
        lean = Vector((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), 0)) * h
        col = L.mix((0.20, 0.30, 0.09), (0.55, 0.50, 0.22), r.uniform(0, 0.6))
        s = (col[0], col[1], col[2], 1.0, 0.08, 0.0)
        K.cyl_between(p, base, base + Vector((0, 0, h)) + lean, r.uniform(0.018, 0.03) * scale, s, 4, r2=0.003)
        if r.random() < 0.25:   # cattail head
            top = base + Vector((0, 0, h)) + lean
            K.cyl_between(p, top - Vector((0, 0, 0.16)) - lean * 0.12, top - lean * 0.02, 0.035 * scale, (0.30, 0.17, 0.07, 1, 0.05, 0), 6)


def shrub(p, c, r, size):
    pts = []
    for k in range(12):
        a = r.uniform(0, 2 * math.pi); e = r.uniform(-0.2, 1.0)
        rr = size * r.uniform(0.7, 1.0)
        pts.append((c[0] + math.cos(a) * rr * math.cos(e * 0.8), c[1] + math.sin(a) * rr * math.cos(e * 0.8), c[2] + max(0.0, math.sin(e)) * size * 0.9))
    f = p.hull([Vector(q) for q in pts])
    col = L.mix((0.16, 0.26, 0.08), (0.36, 0.38, 0.14), r.uniform(0, 1))
    p.paint_fn(f, lambda co, no, fa: (col[0] * (0.8 + 0.35 * max(0, no.z)), col[1] * (0.8 + 0.35 * max(0, no.z)), col[2], 1.0, 0.06, 0.0))
    p.uv_const(f, (0.5, 0.03))


def vegetation_and_rocks(ctx, river, poly, crossings):
    r = random.Random(919)
    p = L.Part(); rocks = L.Part()
    wh = river.water_halfwidth()
    nveg = nrock = 0
    level = ctx['level']
    def clear(i, q):
        s = river.s[i]
        for cs in crossings:
            if abs(s - cs) < 11.0:
                return False
        if not LY.point_in_poly(poly, q[0], q[1]):
            return river.kind[i] == 'out' or river.kind[i] == 'gap'
        if level.road_clearance(q[0], q[1]) < 2.0 or level.on_floor(q[0], q[1], 1.5):
            return False
        return True
    i = 30
    while i < len(river.P) - 30:
        k = river.curv[i]
        side = r.choice([-1, 1])
        if abs(k) > 0.012:
            side = -int(np.sign(k)) if r.random() < 0.6 else int(np.sign(k))   # mostly outer bank
        off = wh[i] + r.uniform(-0.3, 0.9)
        q = river.P[i] + river.N[i] * side * off
        if clear(i, q):
            z, *_ = river.height(np.array([q[0]]), np.array([q[1]]))
            c = (q[0], q[1], float(z[0]))
            if r.random() < 0.7:
                for m in range(r.randint(1, 3)):
                    dq = river.T[i] * r.uniform(-1.8, 1.8) + river.N[i] * side * r.uniform(0, 0.8)
                    zz, *_ = river.height(np.array([q[0] + dq[0]]), np.array([q[1] + dq[1]]))
                    reed_cluster(p, (q[0] + dq[0], q[1] + dq[1], float(zz[0])), r, r.uniform(0.8, 1.2)); nveg += 1
            else:
                q2 = river.P[i] + river.N[i] * side * (wh[i] + river.A[i, 1] * 0.8 + 0.8)
                shrub(p, (q2[0], q2[1], -0.05), r, r.uniform(0.45, 0.9)); nveg += 1
            # boulders on outer bends, partly in the water
            if abs(k) > 0.012 and side == -int(np.sign(k)) and r.random() < 0.6:
                q3 = river.P[i] + river.N[i] * side * (wh[i] + r.uniform(-0.4, 0.4))
                z3, *_ = river.height(np.array([q3[0]]), np.array([q3[1]]))
                part = R.make_rock(6200 + nrock, r.uniform(0.5, 1.1), r.uniform(0.45, 0.9), r.uniform(0.4, 0.8), r.choice(['round', 'slab']),
                                   strata=1, crack=False, bevel=0.05, uv_tile=3.0)
                arr = part.arrays(); part.free()
                M = Matrix.Translation((q3[0], q3[1], float(z3[0]) - 0.12)) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z')
                R._append_arrays(rocks, dict(arr, co=(arr['co'] @ np.array(M)[:3, :3].T + np.array(M)[:3, 3]))); nrock += 1
        i += r.randint(14, 34)
    acc = L.MeshAccumulator(); acc.add_part(p); p.free()
    me = acc.build('AP_River_Vegetation', materials=[ctx['mats']['Toon']], sharp_angle=60)
    L.new_object('AP_River_Vegetation', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Toon']],
                 note='new: reed and shrub groups on the river banks (no collision intended)')
    if len(rocks.bm.faces):
        acc = L.MeshAccumulator(); acc.add_part(rocks)
        me = acc.build('AP_River_Boulders', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50)
        L.new_object('AP_River_Boulders', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Rock_Strata']],
                     note='new: boulders on outer bends (kept off fords, bridges and drive lines)')
    rocks.free()
    return nveg, nrock


def gap_blockers(ctx, river, poly):
    """Boulder dams in the inlet / outlet gaps, just outside the outline: the car cannot leave along the river."""
    r = random.Random(77)
    acc = L.MeshAccumulator(); n = 0
    gaps = [i for i, k in enumerate(river.kind) if k == 'gap']
    runs = []
    for a in gaps:
        if runs and a == runs[-1][-1] + 1: runs[-1].append(a)
        else: runs.append([a])
    for run in runs:
        # first station of the run that is outside the playable polygon
        cand = [i for i in run if not LY.point_in_poly(poly, river.P[i][0], river.P[i][1])]
        i = cand[len(cand) // 3] if cand else run[-1]
        P = river.P[i]; N = river.N[i]; T = river.T[i]
        half = river.A[i, 0] + river.A[i, 1]
        for t in np.linspace(-half - 1.0, half + 1.0, 6):
            q = P + N * t + T * r.uniform(-1.0, 1.0)
            z, *_ = river.height(np.array([q[0]]), np.array([q[1]]))
            part = R.make_rock(6600 + n, r.uniform(1.1, 1.7), r.uniform(1.0, 1.4), r.uniform(1.3, 2.2), r.choice(['round', 'block']),
                               strata=None, tilt=(0.05, 0.3))
            acc.add(part.arrays(), Matrix.Translation((q[0], q[1], float(z[0]) - 0.2)) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z')); part.free(); n += 1
    me = acc.build('AP_River_GapBoulders', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50)
    L.new_object('AP_River_GapBoulders', me, ctx['coll_river'], parent=bpy.data.objects.get('World'), mats=[ctx['mats']['Rock_Strata']],
                 note='new: boulder dams in the river inlet/outlet gaps (need colliders in Unity: they close the outline)')
    return n


def run(ctx):
    river = ctx['river']; poly = ctx['outline']
    nv = carve_ground(ctx, river)
    import step_ground as SG
    ctx['ground_sampler'] = SG.GroundSampler(bpy.data.objects['Ground'])
    water_surface(ctx, river)
    ford_paths, finfo = fords(ctx, river, poly)
    ruts(ctx, river, ford_paths)
    crossings = [river.s[i] for i in ford_list(river)] + ctx.get('bridge_s', [])
    nveg, nrock = vegetation_and_rocks(ctx, river, poly, crossings)
    nb = gap_blockers(ctx, river, poly)
    ctx['fords'] = finfo
    ctx['stats']['river'] = dict(length_m=round(float(river.length), 1), ground_vertices=nv, fords=len(finfo),
                                 vegetation_groups=nveg, bend_boulders=nrock, gap_boulders=nb)
    print('STEP12 river done', ctx['stats']['river'], flush=True)
