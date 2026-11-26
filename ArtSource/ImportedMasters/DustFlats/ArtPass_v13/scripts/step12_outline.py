"""v12 step: winding map outline. New perimeter cliff bands along rg_layout12.BOUNDARY (inner face on the line),
2-3 rows rising outwards, gaps for the river inlet/outlet, the gate and the canyon; flared canyon mouth;
scree / sand drifts re-scattered; ground rock-dust re-tinted; spawns / decor caught in the new rocks are moved
inside; presentation backdrop (ground to the horizon + far mesas) hides the rectangular ground edge."""
import bpy, bmesh, math, random, json, os
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_rocks as R
import rg_layout12 as LY
from step_rocks import original_arrays, comp_vertex_membership

WALLS = ['Cliff.003', 'Cliff.004', 'Cliff.011', 'Cliff.012', 'Cliff.014']


def classify(x, y):
    if y > 88:
        return 'Cliff.014' if x < 15 else 'AP_Cliff_NorthEast'
    if y < -94:
        return 'Cliff.011' if x < 0 else 'Cliff.012'
    return 'Cliff.003' if x < 0 else 'Cliff.004'


def boundary_frames(poly):
    n = len(poly)
    area = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
    T = np.roll(poly, -1, 0) - np.roll(poly, 1, 0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    left = np.c_[-T[:, 1], T[:, 0]]
    out = -left if area > 0 else left           # CCW -> interior on the left -> outward = right
    return T, out


def skip_station(x, y, river):
    if y < -111.5 and abs(x) < 30:
        return 'canyon'
    if 15.0 <= x <= 31.0 and y > 95:
        return 'gate'
    if river.corridor(np.array([x]), np.array([y]), 1.5)[0]:
        return 'river'
    return None


def build_bands(ctx, poly, river):
    """Dense cliff band: 4 rows walked independently along the outline, overlapping, rising outwards."""
    T, OUT = boundary_frames(poly)
    rr = random.Random(1212)
    per_obj = {}; footprints = []
    n = len(poly)
    tilt = {nm: (math.radians(rr.uniform(2, 6)), rr.uniform(0, 6.28)) for nm in WALLS + ['AP_Cliff_NorthEast']}
    seg = np.linalg.norm(np.roll(poly, -1, 0) - poly, axis=1); S = np.concatenate([[0], np.cumsum(seg)])
    total = S[-1]
    def at(s):
        s = s % total; k = int(np.searchsorted(S, s, 'right') - 1) % n
        return k
    ROWS = [  # (hx range, hy range, base offset, height factor, spacing factor range, probability)
        ((3.2, 6.0), (2.6, 4.2), 0.0, 1.0, (0.55, 0.72), 1.0),
        ((4.0, 7.0), (3.5, 5.5), 4.5, 1.45, (0.55, 0.75), 1.0),
        ((5.0, 9.0), (4.5, 7.0), 11.0, 1.9, (0.60, 0.85), 1.0),
        ((7.0, 12.0), (6.0, 9.0), 19.0, 2.35, (0.70, 1.00), 0.7),
    ]
    seed = 0
    for ri, (hxr, hyr, off0, hf, spr, prob) in enumerate(ROWS):
        s = rr.uniform(0, 4)
        while s < total:
            k = at(s); x, y = poly[k]; t = T[k]; o = OUT[k]
            hx = rr.uniform(*hxr); hy = rr.uniform(*hyr)
            step = 2 * hx * rr.uniform(*spr)
            if rr.random() > prob:
                s += step; continue
            if y < -111.5 and abs(x) < 34:                 # existing canyon walls
                s += step; continue
            if 13.0 <= x <= 33.0 and y > 93:                # gate passage stays open through all rows
                s += step; continue
            side_ns = y > 88 or y < -94
            H1 = rr.uniform(3.4, 5.6) if side_ns else rr.uniform(4.8, 7.6)
            off = off0 + hy * (0.92 if ri == 0 else 0.85) + (rr.uniform(-0.3, 0.5) if ri == 0 else rr.uniform(-1.4, 1.4))
            c = np.array([x, y]) + o * off + (t * rr.uniform(-1.0, 1.0) if ri else 0)
            if river.corridor(np.array([c[0]]), np.array([c[1]]), max(hx, hy) + 0.6)[0]:
                s += step; continue
            if ri == 0:
                for _ in range(8):
                    inner = c - o * hy * 0.95
                    if not LY.point_in_poly(poly, inner[0], inner[1]):
                        break
                    c = c + o * 0.5
            else:
                yaw0 = math.atan2(t[1], t[0])
                ring = [(c[0] + math.cos(a) * hx * math.cos(yaw0) - math.sin(a) * hy * math.sin(yaw0),
                         c[1] + math.cos(a) * hx * math.sin(yaw0) + math.sin(a) * hy * math.cos(yaw0)) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
                ring = np.array(ring)
                if LY.point_in_poly(poly, ring[:, 0], ring[:, 1]).any():
                    s += step; continue
            nm = classify(x, y)
            yaw = math.atan2(t[1], t[0]) + rr.uniform(-0.3, 0.3)
            style = rr.choice(['block', 'slab', 'round', 'block'] if ri == 0 else ['block', 'spire', 'block', 'slab'])
            seed += 1
            part = R.make_rock(77000 + seed, hx, hy, H1 * hf * rr.uniform(0.85, 1.15), style, tilt=tilt[nm], detail=1.0 if ri < 3 else 0.8)
            M = Matrix.Translation((c[0], c[1], 0.0)) @ Matrix.Rotation(yaw, 4, 'Z')
            per_obj.setdefault(nm, L.MeshAccumulator()).add(part.arrays(), M); part.free()
            footprints.append((c[0], c[1], hx, hy, yaw, H1 * hf, False, ri + 1))
            s += step
    return per_obj, footprints


def trim_canyon(ctx, poly):
    """Remove v11 canyon-wall rocks that now stand inside the widened (flared) canyon mouth."""
    removed = 0
    for nm in ('Cliff', 'Cliff.001'):
        ob = bpy.data.objects[nm]; me = ob.data
        comps = L.mesh_components(me, weld=0.002)
        memb = comp_vertex_membership(me, comps)
        keep = np.ones(len(me.vertices), bool)
        Mw = np.array(ob.matrix_world)
        for ci, (pts, _) in enumerate(comps):
            w = pts @ Mw[:3, :3].T + Mw[:3, 3]
            low = w[w[:, 2] < 1.2] if (w[:, 2] < 1.2).any() else w
            inside = LY.point_in_poly(poly, low[:, 0], low[:, 1]).mean()
            if w[:, 1].mean() > -114 and inside > 0.25:
                keep &= (memb != ci); removed += 1
        arr = original_arrays(me, keep)
        acc = L.MeshAccumulator(); acc.add(arr)
        new = acc.build(me.name + '__v12', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50.0)
        users, _ = L.swap_mesh(me, new, note='v12: canyon mouth flared (rocks inside the new outline removed)')
        for o in users:
            L.set_object_materials(o, [ctx['mats']['Rock_Strata']])
    return removed


def old_wall_footprints():
    fp = []
    for nm in WALLS:
        ob = bpy.data.objects[nm]; Mw = np.array(ob.matrix_world)
        for pts, _ in L.mesh_components(ob.data, weld=0.01):
            w = pts @ Mw[:3, :3].T + Mw[:3, 3]
            c = w[:, :2].mean(0); rad = float(np.percentile(np.linalg.norm(w[:, :2] - c, axis=1), 80))
            fp.append((float(c[0]), float(c[1]), rad))
    return fp


def dust_field(x, y, fp):
    from mathutils.kdtree import KDTree
    d = np.zeros(len(x))
    if not fp:
        return d
    kd = KDTree(len(fp))
    for i, (px, py, r) in enumerate(fp):
        kd.insert((px, py, 0), i)
    kd.balance()
    for i in range(len(x)):
        for (_, idx, dist) in kd.find_n((x[i], y[i], 0), 2):
            d[i] = max(d[i], float(np.clip(1 - (dist - fp[idx][2]) / 4.0, 0, 1)))
    return d


def retint_ground(old_fp, new_fp):
    ob = bpy.data.objects['Ground']; me = ob.data
    n = len(me.vertices); co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world); w = co @ M[:3, :3].T + M[:3, 3]
    near = (np.abs(w[:, 0]) > 70) | (w[:, 1] > 70) | (w[:, 1] < -85)
    d_old = np.zeros(n); d_new = np.zeros(n)
    idx = np.where(near)[0]
    d_old[idx] = dust_field(w[idx, 0], w[idx, 1], old_fp)
    d_new[idx] = dust_field(w[idx, 0], w[idx, 1], new_fp)
    lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
    rockdust = np.array([0.56, 0.27, 0.16])
    do = d_old[lv][:, None]; dn = d_new[lv][:, None]
    base = (col[:, :3] / (1 - 0.05 * do) - rockdust * 0.18 * do) / (1 - 0.18 * do)
    out = base * (1 - 0.18 * dn) + rockdust * 0.18 * dn
    out *= (1 - 0.05 * dn)
    col[:, :3] = np.clip(out, 0, 2)
    me.color_attributes['Color'].data.foreach_set('color', col.ravel())
    me.update()


def scatter(ctx, fps, poly, river, seed):
    level = ctx['level']; sampler = ctx['ground_sampler']
    r = random.Random(seed)
    scree = {}; drifts = {}
    ns = nd = 0
    for (cx, cy, hx, hy, yaw, hz, small, row) in fps:
        if row != 1:
            continue
        nm = classify(cx, cy)
        if r.random() < 0.55:
            for k in range(r.randint(2, 5)):
                a = r.uniform(0, 2 * math.pi)
                rad = math.hypot(hx * math.cos(a), hy * math.sin(a)) + r.uniform(0.2, 1.4)
                wx = cx + math.cos(a + yaw) * rad; wy = cy + math.sin(a + yaw) * rad
                if not LY.point_in_poly(poly, wx, wy):
                    continue
                if river.corridor(np.array([wx]), np.array([wy]), 1.0)[0]:
                    continue
                if not level.clear_for_decor(wx, wy, road_margin=1.0, floor_margin=1.0, keepout=True, route_margin=1.0):
                    continue
                s = r.uniform(0.22, 0.65) * (1.4 if r.random() < 0.15 else 1.0)
                part = R.scree_piece(seed * 977 + ns, s)
                scree.setdefault(nm, L.MeshAccumulator()).add(part.arrays(), Matrix.Translation((wx, wy, -0.04)) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z'))
                part.free(); ns += 1
        if hz > 2.0 and r.random() < 0.38:
            # drift on the playable side of the rock
            o = np.array([math.cos(yaw + math.pi / 2), math.sin(yaw + math.pi / 2)])
            if not LY.point_in_poly(poly, cx + o[0] * (hy + 2), cy + o[1] * (hy + 2)):
                o = -o
            wx, wy = cx + o[0] * hy * 0.9, cy + o[1] * hy * 0.9
            length = min(5.5, max(2.5, 1.3 * hx)) * r.uniform(0.85, 1.1); width = r.uniform(1.4, 2.4); height = r.uniform(0.22, 0.42)
            tang = yaw
            ok = all(LY.point_in_poly(poly, wx + o[0] * width * 0.6 + math.cos(tang) * t * length * 0.5,
                                      wy + o[1] * width * 0.6 + math.sin(tang) * t * length * 0.5) for t in (-1, 0, 1))
            ok = ok and not river.corridor(np.array([wx]), np.array([wy]), 2.0)[0]
            ok = ok and level.clear_for_decor(wx, wy, road_margin=0.6, floor_margin=0.8, keepout=True, route_margin=0.8)
            if not ok:
                continue
            M = Matrix.Translation((wx, wy, 0)) @ Matrix.Rotation(tang, 4, 'Z')
            part = R.sand_drift_arrays(seed * 31 + nd, length, width, height, sampler, M)
            drifts.setdefault(nm, L.MeshAccumulator()).add(part.arrays(), M); part.free(); nd += 1
    world = bpy.data.objects.get('World')
    for nm, acc in scree.items():
        on = 'AP_Scree_' + nm
        me = acc.build(on, materials=[ctx['mats']['Rock_Strata']], sharp_angle=50)
        L.new_object(on, me, ctx['coll_rocks'], parent=world, mats=[ctx['mats']['Rock_Strata']],
                     note=f'new: scree at the base of the v12 outline ({nm})')
    for nm, acc in drifts.items():
        on = 'AP_SandDrift_' + nm
        me = acc.build(on, materials=[ctx['mats']['Ground']], sharp_angle=80, weighted=False)
        L.new_object(on, me, ctx['coll_ground'], parent=world, mats=[ctx['mats']['Ground']],
                     note=f'new: sand drifts against the v12 outline ({nm})')
    return ns, nd


def relocate(ctx, poly, river):
    """Move spawn roots / decor pieces that ended up inside the new rocks or (later) the river corridor."""
    moved = []
    for ob in bpy.context.scene.objects:
        import re
        if not re.match(r'^Spawn_\d{5}_', ob.name):
            continue
        p = ob.matrix_world.translation
        inside = LY.point_in_poly(poly, p.x, p.y)
        in_river = river.corridor(np.array([p.x]), np.array([p.y]), 1.2)[0]
        if inside and not in_river:
            continue
        # search the nearest free spot on rings around it
        best = None
        for rad in np.arange(1.0, 30.0, 1.0):
            for a in np.linspace(0, 2 * math.pi, 24, endpoint=False):
                q = (p.x + math.cos(a) * rad, p.y + math.sin(a) * rad)
                if not LY.point_in_poly(poly, q[0] - 0, q[1]):
                    continue
                if river.corridor(np.array([q[0]]), np.array([q[1]]), 2.0)[0]:
                    continue
                if not ctx['level'].clear_for_decor(q[0], q[1], road_margin=1.0, floor_margin=1.0, keepout=False, route_margin=1.0):
                    continue
                # keep >= 4 m from the outline
                bd = np.min(np.hypot(poly[:, 0] - q[0], poly[:, 1] - q[1]))
                if bd < 4.0:
                    continue
                best = q; break
            if best:
                break
        if best is None:
            continue
        old = (round(p.x, 2), round(p.y, 2))
        mw = ob.matrix_world.copy(); mw.translation = Vector((best[0], best[1], mw.translation.z))
        ob.matrix_world = mw
        moved.append(dict(object=ob.name, reason='river' if in_river else 'outline',
                          blender_from=old, blender_to=(round(best[0], 2), round(best[1], 2)),
                          unity_from=(old[0], 0.0, old[1]), unity_to=(round(best[0], 2), 0.0, round(best[1], 2)),
                          unity_id=ob.get('unity_id', '')))
    # Decor (single merged mesh of small stones / bushes): drop pieces outside the outline or in the river
    ob = bpy.data.objects.get('Decor'); dropped = 0
    if ob:
        me = ob.data
        comps = L.mesh_components(me, weld=0.002)
        memb = comp_vertex_membership(me, comps)
        keep = np.ones(len(me.vertices), bool)
        Mw = np.array(ob.matrix_world)
        for ci, (pts, _) in enumerate(comps):
            c = (pts.mean(0) @ Mw[:3, :3].T + Mw[:3, 3])
            if (not LY.point_in_poly(poly, c[0], c[1])) or river.corridor(np.array([c[0]]), np.array([c[1]]), 0.8)[0]:
                keep &= (memb != ci); dropped += 1
        if dropped:
            arr = original_arrays(me, keep)
            mats = [s.material for s in ob.material_slots]
            acc = L.MeshAccumulator(); acc.add(arr)
            new = acc.build(me.name + '__v12', materials=mats, sharp_angle=40.0)
            users, _ = L.swap_mesh(me, new, note=f'v12: {dropped} decor pieces removed (inside new rocks or river)')
            for o in users:
                L.set_object_materials(o, mats)
    return moved, dropped


def backdrop(ctx, river):
    """Presentation ground to the horizon (+ far mesas). Lies 3 cm under the Ground plane where they overlap."""
    gx0, gx1, gy0, gy1 = -175.0, 175.0, -260.0, 100.0
    step = 25.0; X0, X1, Y0, Y1 = -1350.0, 1350.0, -1450.0, 1300.0
    bm = bmesh.new()
    nx = int((X1 - X0) / step); ny = int((Y1 - Y0) / step)
    vg = {}
    def V(i, j):
        if (i, j) not in vg:
            vg[(i, j)] = bm.verts.new((X0 + i * step, Y0 + j * step, -0.03))
        return vg[(i, j)]
    for j in range(ny):
        for i in range(nx):
            x0 = X0 + i * step; y0 = Y0 + j * step
            if x0 >= gx0 + 1 and x0 + step <= gx1 - 1 and y0 >= gy0 + 1 and y0 + step <= gy1 - 1:
                continue
            bm.faces.new([V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)])
    # refine along the outside river reaches, then carve
    for depth, rad in ((3, 40.0), (1, 10.0)):
        for _ in range(depth):
            bm.faces.ensure_lookup_table()
            cen = np.array([f.calc_center_median()[:2] for f in bm.faces])
            i, d, w, b, D, k = river.query(cen[:, 0], cen[:, 1])
            sel = np.abs(d) < (w + b + rad)
            edges = list({e for f, s in zip(bm.faces, sel) if s for e in f.edges})
            if edges:
                bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    co = np.array([v.co[:] for v in bm.verts])
    z, d, w, b, D, idx = river.height(co[:, 0], co[:, 1])
    for v, zz in zip(bm.verts, z):
        v.co.z = -0.03 + zz
    lc = bm.loops.layers.float_color.new('Color'); luv = bm.loops.layers.uv.new('UVMap'); lp = bm.loops.layers.uv.new('Unity_MaterialParams')
    import step_ground as SG
    sampler = ctx['ground_sampler']
    bm.verts.index_update()
    X = co[:, 0]; Yv = co[:, 1]; Z = z
    g = np.array([sampler(max(gx0, min(gx1, a)), max(gy0, min(gy1, b_))) for a, b_ in zip(X, Yv)])
    # distance outside the Ground rectangle: no tint change at the seam, slow variation and haze far away
    ox = np.maximum(0, np.maximum(gx0 - X, X - gx1)); oy = np.maximum(0, np.maximum(gy0 - Yv, Yv - gy1))
    out = np.hypot(ox, oy)
    far = np.clip((out - 350.0) / 900.0, 0, 1) * 0.6
    k = 1.0 + (0.18 * (SG.fbm_xy(X, Yv, 160.0, 61) - 0.5)) * np.clip(out / 120.0, 0, 1)
    base = g * k[:, None]
    haze = np.array([0.74, 0.56, 0.42])
    c = base * (1 - far[:, None] * 0.55) + haze * far[:, None] * 0.55
    wet = np.clip((-0.03 - Z) / 0.25, 0, 1) * (Z < -0.06)
    c = c * (1 - wet[:, None] * 0.8) + np.array([0.34, 0.27, 0.17]) * wet[:, None] * 0.8
    for f in bm.faces:
        for l in f.loops:
            cc = c[l.vert.index]
            l[lc] = (cc[0], cc[1], cc[2], 1.0); l[lp].uv = (0.0, 0.0); l[luv].uv = (0.0, 0.0)
    me = bpy.data.meshes.new('AP_Ground_Backdrop'); bm.to_mesh(me); bm.free()
    uvl = me.uv_layers['UVMap']; me.uv_layers.active = uvl
    me.color_attributes.active_color = me.color_attributes['Color']
    me.shade_smooth()
    coll = L.ensure_collection('Zone_00 v12 — Backdrop (presentation horizon)', ctx['zone'])
    L.new_object('AP_Ground_Backdrop', me, coll, parent=None, mats=[ctx['mats']['Ground']],
                 note='new: presentation ground to the horizon around the snapshot (not part of the playable area)')
    # far mesas
    rr = random.Random(3131); acc = L.MeshAccumulator(); n = 0
    for k in range(26):
        for _ in range(30):
            a = rr.uniform(0, 2 * math.pi); dist = rr.uniform(330, 760)
            x = math.cos(a) * dist; y = -80 + math.sin(a) * dist
            if abs(x) < 190 and -280 < y < 120:
                continue
            if river.corridor(np.array([x]), np.array([y]), 40.0)[0]:
                continue
            break
        hx = rr.uniform(22, 60); hy = rr.uniform(18, 45); hz = rr.uniform(14, 34)
        part = R.make_rock(91000 + k, hx, hy, hz, rr.choice(['slab', 'block', 'block']), strata=3,
                           tilt=(math.radians(3), 0.4), bevel=0.6, uv_tile=24.0, dust=0.8)
        acc.add(part.arrays(), Matrix.Translation((x, y, -0.5)) @ Matrix.Rotation(rr.uniform(0, 6.28), 4, 'Z')); part.free(); n += 1
    me = acc.build('AP_Backdrop_Mesas', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50.0)
    L.new_object('AP_Backdrop_Mesas', me, coll, parent=None, mats=[ctx['mats']['Rock_Strata']],
                 note='new: distant mesas on the horizon (presentation)')
    return n


def run(ctx):
    river = ctx['river']; poly = LY.boundary_polygon(1.0)
    ctx['outline'] = poly
    old_fp = old_wall_footprints()
    per_obj, fps = build_bands(ctx, poly, river)
    world = bpy.data.objects.get('World')
    stats = {}
    for nm, acc in per_obj.items():
        mats = [ctx['mats']['Rock_Strata']]
        if nm in bpy.data.objects:
            ob = bpy.data.objects[nm]
            new = acc.build(ob.data.name + '__v12', materials=mats, sharp_angle=50.0)
            users, _ = L.swap_mesh(ob.data, new, note='v12: rebuilt as a winding perimeter band along the new outline')
            for o in users:
                L.set_object_materials(o, mats)
        else:
            me = acc.build(nm, materials=mats, sharp_angle=50.0)
            L.new_object(nm, me, ctx['coll_rocks'], parent=world, mats=mats,
                         note='new: perimeter rocks closing the outline east of the gate (v12)')
        stats[nm] = sum(1 for f in fps if classify(f[0], f[1]) == nm)
    # old scree / drifts along the replaced walls
    for o in list(bpy.data.objects):
        if o.name.startswith(('AP_Scree_Cliff.0', 'AP_SandDrift_Cliff.0')) and o.name.split('_')[-1] in WALLS:
            bpy.data.objects.remove(o)
    removed = trim_canyon(ctx, poly)
    new_fp = [(f[0], f[1], max(f[2], f[3])) for f in fps if f[7] == 1]
    retint_ground(old_fp, new_fp)
    import step_ground as SG
    ctx['ground_sampler'] = SG.GroundSampler(bpy.data.objects['Ground'])
    ns, nd = scatter(ctx, fps, poly, river, 4242)
    moved, dropped = relocate(ctx, poly, river)
    nm_mesas = backdrop(ctx, river)
    ctx['stats']['outline'] = dict(rocks_per_object=stats, canyon_rocks_removed=removed, scree=ns, drifts=nd,
                                   spawns_moved=len(moved), decor_pieces_removed=dropped, far_mesas=nm_mesas)
    ctx['moved_spawns'] = moved
    print('STEP12 outline done', ctx['stats']['outline'], flush=True)
