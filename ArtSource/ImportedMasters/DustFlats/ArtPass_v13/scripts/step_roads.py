"""Step: ramps (jumps) and road details. The driving surface of every ramp keeps its exact v10 polygons;
new structure is added under/around it: side trusses (posts + braces + stringer following the deck profile),
deck edge angles, transverse plate seams (1 cm), lip plate, back-face bracing, footing blocks.
Deck wear is painted into vertex colours (lighter tyre lanes, darker edges)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays
from step_structures import with_mat

RAMPS = ['Ramp', 'Ramp.001', 'Ramp.002', 'Ramp.006', 'Ramp.007']


def S(kind, k=1.0):
    return L.surf(kind, k)


def ramp_frame(arr):
    """Find the main wedge (largest polygon set) and its run/side axes from deck heights."""
    co = arr['co']
    # deck heights: highest z per (x,y) cell via BVH of all original polys
    polys = []; li = 0
    for n in arr['flen']:
        polys.append(list(arr['lv'][li:li + n])); li += n
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], polys)
    mn = co.min(0); mx = co.max(0)
    def deck(x, y):
        hit = bvh.ray_cast(Vector((x, y, mx[2] + 5)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] is not None else None
    xs = np.linspace(mn[0], mx[0], 9)[1:-1]; ys = np.linspace(mn[1], mx[1], 9)[1:-1]
    P = []
    for x in xs:
        for y in ys:
            z = deck(x, y)
            if z is not None:
                P.append((x, y, z))
    P = np.array(P)
    A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]
    (a, b, c), *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
    run = Vector((a, b, 0)).normalized()
    side = Vector((-run.y, run.x, 0))
    ctr = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, 0))
    d = co[:, :2] - np.array(ctr[:2])
    pr = d @ np.array(run[:2]); ps = d @ np.array(side[:2])
    return bvh, deck, ctr, run, side, pr.min(), pr.max(), ps.min(), ps.max(), mx[2]


def ramp_details(ob, ctx, seed):
    me = ob.data
    keep = np.ones(len(me.vertices), bool)
    arr = original_arrays(me, keep)
    bvh, deck, C, run, side, r0, r1, s0, s1, ztop = ramp_frame(arr)
    r = random.Random(seed)
    # --- deck wear in vertex colours (only dark, up-facing deck faces of the wedge) ---
    co = arr['co']; col = arr['col'].copy(); li = 0
    for fi, n in enumerate(arr['flen']):
        idx = arr['lv'][li:li + n]
        pts = co[idx]
        nrm = np.cross(pts[1] - pts[0], pts[2] - pts[0]); nl = np.linalg.norm(nrm)
        if nl > 1e-9 and nrm[2] / nl > 0.6:
            c = col[li:li + n]
            lumi = c[:, :3].mean(1)
            if (lumi < 0.32).all() and (np.abs(c[:, 0] - c[:, 2]) < 0.12).all():   # deck plate, not chevrons
                for k, vi in enumerate(idx):
                    q = co[vi]
                    sp = (q[0] - C.x) * side.x + (q[1] - C.y) * side.y
                    w = s1 - s0
                    u = (sp - s0) / max(w, 1e-3)
                    lanes = math.exp(-((u - 0.3) / 0.09) ** 2) + math.exp(-((u - 0.7) / 0.09) ** 2)
                    edge = max(0.0, 1 - min(u, 1 - u) / 0.08)
                    f = (1 + 0.28 * lanes) * (1 - 0.25 * edge)
                    col[li + k, :3] = col[li + k, :3] * f + np.array([0.06, 0.05, 0.04]) * lanes * 0.6
        li += n
    arr = dict(arr); arr['col'] = col
    p = L.Part()
    steel = S('steel_dark', 1.25); steel_l = S('galvanized', 0.75); beam_s = (0.36, 0.13, 0.05, 1.0, 0.3, 0.3)
    run_len = r1 - r0
    def P(t, s, z=0.0):
        return C + run * t + side * s + Vector((0, 0, z))
    def dz(t, s):
        q = P(t, s)
        z = deck(q.x, q.y)
        return z if z is not None else 0.0
    yaw = math.atan2(run.y, run.x)
    nposts = max(3, int(run_len / 1.6))
    for sgn, s in ((-1, s0), (1, s1)):
        so = s + sgn * 0.09
        ts = np.linspace(r0 + 0.5, r1 - 0.25, nposts)
        tops = []
        for t in ts:
            ztp = dz(t, s - sgn * 0.3)
            if ztp < 0.35:
                tops.append(None); continue
            K.beam(p, P(t, so, -0.05), P(t, so, ztp - 0.06), 0.12, 0.12, beam_s, 'panel', 0.012, up=(run.x, run.y, 0))
            tops.append((t, ztp))
        valid = [x for x in tops if x is not None]
        for (ta, za), (tb, zb) in zip(valid[:-1], valid[1:]):
            K.beam(p, P(ta, so + sgn * 0.04, 0.2), P(tb, so + sgn * 0.04, zb - 0.2), 0.05, 0.1, steel, 'plain', 0.01, up=(side.x, side.y, 0))
        # stringer following the deck edge profile
        prof = [(t, dz(t, s - sgn * 0.3)) for t in np.linspace(r0, r1, 14)]
        for (ta, za), (tb, zb) in zip(prof[:-1], prof[1:]):
            if max(za, zb) < 0.08:
                continue
            K.beam(p, P(ta, so, za - 0.12), P(tb, so, zb - 0.12), 0.1, 0.2, beam_s, 'panel', 0.012, up=(side.x * 0, side.y * 0, 1))
            # deck edge angle hugging the outside of the deck edge (top flush with the driving surface)
            K.beam(p, P(ta, s + sgn * 0.05, za - 0.05), P(tb, s + sgn * 0.05, zb - 0.05), 0.1, 0.1, steel_l, 'diamond', 0.006)
        # footing blocks under posts
        for t in ts[::2]:
            K.box(p, (0.5, 0.4, 0.2), Matrix.Translation(P(t, so, 0.05)) @ Matrix.Rotation(yaw, 4, 'Z'), S('concrete', 0.85), 'concrete', 0.03)
    # transverse plate seams on the deck (1.2 cm), skipping the first metre (toe) and the lip
    for t in np.arange(r0 + 1.4, r1 - 0.6, 1.25):
        za = dz(t, s0 + 0.4); zb = dz(t, s1 - 0.4)
        if za < 0.05:
            continue
        K.beam(p, P(t, s0 + 0.25, za + 0.003), P(t, s1 - 0.25, zb + 0.003), 0.07, 0.008, S('steel_dark', 1.6), 'diamond', 0.0)
    # lip plate at the top edge + back bracing
    zt = dz(r1 - 0.15, (s0 + s1) / 2)
    K.beam(p, P(r1 + 0.04, s0 + 0.1, zt - 0.1), P(r1 + 0.04, s1 - 0.1, zt - 0.1), 0.08, 0.2, S('galvanized', 0.9), 'diamond', 0.008)
    if zt > 0.6:
        for (sa, sb) in ((s0 + 0.3, s1 - 0.3), (s1 - 0.3, s0 + 0.3)):
            K.beam(p, P(r1 + 0.12, sa, 0.15), P(r1 + 0.12, sb, zt - 0.2), 0.06, 0.12, steel, 'plain', 0.01, up=(run.x, run.y, 0))
        for sv in np.linspace(s0 + 0.3, s1 - 0.3, max(2, int((s1 - s0) / 2.5))):
            K.beam(p, P(r1 + 0.1, sv, -0.05), P(r1 + 0.1, sv, zt - 0.08), 0.14, 0.14, beam_s, 'panel', 0.012, up=(run.x, run.y, 0))
    acc = L.MeshAccumulator()
    acc.add(with_mat(arr, 0))
    acc.add(with_mat(p.arrays(), 1)); p.free()
    mats = [ob.material_slots[0].material, ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me, new, note='v11: driving surface unchanged; + side trusses, stringers, deck angles, plate seams, lip, bracing, deck wear')
    for o in users:
        L.set_object_materials(o, mats)


def rebuild_funnel(ctx):
    ob = bpy.data.objects.get('Funnel')
    if ob is None:
        return
    me = ob.data
    acc = L.MeshAccumulator(); p = L.Part()
    for pts, vc in L.mesh_components(me, weld=0.002):
        base, yaw, half, zmin = L.pca_frame(pts)
        col = vc[:, :3].mean(0)
        if half.z < 0.3 or max(half.x, half.y) < 0.2:
            continue
        hx = max(half.x, half.y); M = Matrix.Translation((base.x, base.y, 0)) @ Matrix.Rotation(yaw if half.x >= half.y else yaw + math.pi / 2, 4, 'Z')
        paint = (col[0], col[1], col[2], 1.0, 0.45, 0.12)
        # jersey-style barrier block (v10 thickness & colour kept): wide foot, sloped waist, rounded top,
        # scuffed dark base, steel connector pins between blocks
        t = max(0.35, 2 * min(half.x, half.y))
        hz = max(0.6, half.z)
        prof = [(-t / 2, 0.0), (t / 2, 0.0), (t / 2, 0.08), (t * 0.24, hz * 0.35), (t * 0.17, hz), (-t * 0.17, hz), (-t * 0.24, hz * 0.35), (-t / 2, 0.08)]
        Mb = M @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # prism extruded along local X
        K.prism(p, prof, -hx + 0.03, hx - 0.03, Mb, paint, 'plain', bevel=0.025)
        K.box(p, (2 * hx - 0.04, t + 0.01, 0.1), M @ Matrix.Translation((0, 0, 0.05)), (col[0] * 0.45, col[1] * 0.45, col[2] * 0.45, 1, 0.2, 0.05), 'plain', 0.01)
        for dx in (-hx + 0.02, hx - 0.02):
            K.cyl_between(p, M @ Vector((dx, 0, hz * 0.55)), M @ Vector((dx, 0, hz + 0.06)), 0.035, S('steel_dark', 1.2), 6)
    acc.add_part(p); p.free()
    mats = [ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me, new, note='v11: funnel barrier panels with thickness, posts and feet (positions kept)')
    for o in users:
        L.set_object_materials(o, mats)


def rebuild_barricade(ctx):
    from step_props import tyre
    ob = bpy.data.objects.get('Barricade')
    if ob is None:
        return
    me = ob.data
    acc = L.MeshAccumulator(); p = L.Part(); r = random.Random(4711)
    for pts, vc in L.mesh_components(me, weld=0.002):
        ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2; col = vc[:, :3].mean(0)
        base, yaw, half, zmin = L.pca_frame(pts)
        if ext[2] > 1.0 and max(ext[0], ext[1]) > 1.5:          # scrap block -> rusty container-like block
            M = Matrix.Translation((c[0], c[1], zmin)) @ Matrix.Rotation(yaw, 4, 'Z')
            hx, hy, hz = half.x, half.y, half.z
            paint = (col[0] * 1.05, col[1] * 1.05, col[2] * 1.05, 1.0, 0.4, 0.2)
            K.box(p, (2 * hx - 0.12, 2 * hy - 0.12, hz - 0.06), M @ Matrix.Translation((0, 0, hz / 2)), paint, 'plain', 0.03)
            for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                K.box(p, (0.14, 0.14, hz), M @ Matrix.Translation((sx * (hx - 0.07), sy * (hy - 0.07), hz / 2)), S('steel_dark', 1.25), 'plain', 0.02)
            for sy in (-1, 1):
                K.sheet(p, M @ Vector((-hx + 0.12, sy * (hy - 0.03), 0.12)), M.to_3x3() @ Vector((2 * hx - 0.24, 0, 0)), Vector((0, 0, hz - 0.3)),
                        0.03, L.mix(paint, S('rust_light'), r.uniform(0.1, 0.45)), 'corrugated', 0.9)
            K.box(p, (2 * hx, 2 * hy, 0.1), M @ Matrix.Translation((0, 0, 0.06)), S('steel_dark', 1.1), 'plain', 0.02)
            for (a, b) in (((-hx, -hy), (hx, -hy)), ((hx, -hy), (hx, hy)), ((hx, hy), (-hx, hy)), ((-hx, hy), (-hx, -hy))):
                K.beam(p, M @ Vector((a[0] * 0.97, a[1] * 0.97, hz - 0.04)), M @ Vector((b[0] * 0.97, b[1] * 0.97, hz - 0.04)), 0.12, 0.1,
                       S('steel_dark', 1.1), 'plain', 0.015)
            K.box(p, (r.uniform(0.6, 1.2), 0.04, r.uniform(0.3, 0.5)), M @ Matrix.Translation((r.uniform(-0.6, 0.6), -hy - 0.01, r.uniform(0.4, 0.8))),
                  S('rust_light'), 'rustplate', 0.0)
        elif len(pts) >= 26 and ext[2] < 0.4 and max(ext[0], ext[1]) > 0.6:   # tyre on top
            tyre(p, Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z'), max(ext[0], ext[1]) / 2, ext[2], r)
        elif max(ext[0], ext[1]) < 0.3 and ext[2] > 0.3:                    # spike
            zb = pts[:, 2].min()
            K.cyl_between(p, (c[0], c[1], zb), (c[0], c[1], zb + ext[2] + 0.05), 0.1, S('galvanized', 0.85), 6, r2=0.005)
            K.cyl_between(p, (c[0], c[1], zb - 0.02), (c[0], c[1], zb + 0.04), 0.16, S('steel_dark', 1.2), 6)
        elif max(ext) > 1.0:                                                # plank
            i = int(np.argmax(ext)); a = c.copy(); b = c.copy(); a[i] -= ext[i] / 2; b[i] += ext[i] / 2
            K.board(p, Vector(a), Vector(b), max(0.1, sorted(ext)[1]), max(0.04, min(ext)), S('wood', 0.85), 'board_b', up=(0, 0, 1) if i != 2 else (1, 0, 0))
    acc.add_part(p); p.free()
    mats = [ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me, new, note='v11: barricade scrap blocks (frames, corrugated sides, rust), tyres, spikes, planks (same footprint)')
    for o in users:
        L.set_object_materials(o, mats)


def run(ctx):
    rebuild_funnel(ctx)
    rebuild_barricade(ctx)
    n = 0
    for i, nm in enumerate(RAMPS):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        ramp_details(ob, ctx, 800 + i); n += 1
    ctx['stats']['ramps'] = n
    print('STEP roads done ramps', n, flush=True)
