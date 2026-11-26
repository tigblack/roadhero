"""Step: props as consistent families. Shared spawn meshes are rebuilt in place (instancing kept):
barrels (round 20-seg bodies, rolled rims, hoops, lids, worn edges, rust at the foot), tyres (tread blocks,
sidewall, rims), crates (framed plank crates), car wrecks (bevelled body, cabin pillars, open hood, wheels,
rust), junk piles (+ sheets/pipes), the bus wreck (+ windows frames, bumpers, wheels, roof rack)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays
from step_structures import with_mat, crate, finish_mesh
from step_works import augment2

def S(kind, k=1.0):
    return L.surf(kind, k)


def _paint_variant(col):
    """Map a v10 barrel colour to a paint surface (keep the hue, Toon-friendly paint params)."""
    return (col[0] * 1.08, col[1] * 1.08, col[2] * 1.08, 1.0, 0.5, 0.15)


def barrel(p, M, r, h, paint, rr):
    rim = S('steel', 0.85); rust = S('rust', 1.0)
    def pf(tag, i, j):
        if tag == 'rim':
            return rim
        if tag == 'hoop':
            return (paint[0] * 0.8, paint[1] * 0.8, paint[2] * 0.8, 1, 0.5, 0.2)
        if tag == 'foot':
            return L.mix(paint, rust, 0.65) if len(paint) == 6 else rust
        if tag == 'lid':
            return (paint[0] * 0.9, paint[1] * 0.9, paint[2] * 0.9, 1, 0.45, 0.15)
        # body: occasional vertical rust streaks / scuffs
        if rr.random() < 0.06:
            return L.mix(paint, rust, 0.45)
        return paint
    hz = h
    prof = [(r * 0.96, 0.0, 'foot'), (r * 1.0, 0.012, 'foot'), (r * 1.025, 0.03, 'rim'), (r * 1.025, 0.055, 'rim'),
            (r * 0.99, 0.07, 'foot'), (r * 0.995, 0.16, 'body'),
            (r * 1.0, hz * 0.30, 'hoop'), (r * 1.03, hz * 0.32, 'hoop'), (r * 1.03, hz * 0.35, 'hoop'), (r * 1.0, hz * 0.37, 'body'),
            (r * 1.0, hz * 0.63, 'hoop'), (r * 1.03, hz * 0.65, 'hoop'), (r * 1.03, hz * 0.68, 'hoop'), (r * 1.0, hz * 0.70, 'body'),
            (r * 0.99, hz - 0.07, 'rim'), (r * 1.025, hz - 0.055, 'rim'), (r * 1.025, hz - 0.02, 'rim'), (r * 0.94, hz - 0.012, 'lid'),
            (r * 0.94, hz - 0.03, 'lid')]
    # the last ring is a slight recess (lid below the rim)
    K.lathe(p, prof, 20, M, pf, 'plain')
    # bungs on the lid
    for (dx, dy, rb) in ((r * 0.5, 0.0, 0.06), (-r * 0.55, r * 0.2, 0.035)):
        q = M @ Vector((dx, dy, hz - 0.03)); n = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
        K.cyl_between(p, q, q + n * 0.025, rb, rim, 8)


def rebuild_barrels(ctx):
    for k in range(3):
        me = bpy.data.meshes.get(f'Barrels_{k}_0')
        if me is None:
            continue
        rr = random.Random(900 + k)
        p = L.Part()
        for pts, vc in L.mesh_components(me, weld=0.002):
            if len(pts) < 41:
                continue          # hoops: rebuilt inside each barrel
            ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2
            col = vc[:, :3].mean(0)
            paint = _paint_variant(col)
            if ext[2] > 0.85:      # upright
                M = Matrix.Translation((c[0], c[1], 0.0)) @ Matrix.Rotation(rr.uniform(0, 6.28), 4, 'Z')
                barrel(p, M, 0.36, 0.95, paint, rr)
            else:                  # lying: axis = horizontal PCA axis
                d = pts[:, :2] - c[:2]; w, v = np.linalg.eigh(d.T @ d); ax = v[:, 1]
                yaw = math.atan2(ax[1], ax[0])
                M = (Matrix.Translation((c[0], c[1], 0.36)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'Y')
                     @ Matrix.Translation((0, 0, -0.475)))
                barrel(p, M, 0.36, 0.95, paint, rr)
        # a little spilled oil stain under the lying barrel (flat, dark)
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        finish_mesh(acc, me, ctx, f'v11: barrel family variant {k} rebuilt (20-seg lathe, rims, hoops, lids, bungs, rust foot)')


def tyre(p, M, R, w, rr, rim=False):
    """Tyre lying in local XY (axle = local Z), outer radius R, width w."""
    rub = S('rubber', 1.0); side = S('rubber', 1.35); hub = S('steel', 0.7) if rim else S('rubber', 0.6)
    ri = R * 0.48
    prof = [(ri, -w * 0.32, 'in'), (ri * 1.12, -w * 0.48, 'side'), (R * 0.82, -w * 0.5, 'side'), (R * 0.96, -w * 0.42, 'tread'),
            (R, -w * 0.3, 'tread'), (R, w * 0.3, 'tread'), (R * 0.96, w * 0.42, 'tread'), (R * 0.82, w * 0.5, 'side'),
            (ri * 1.12, w * 0.48, 'side'), (ri, w * 0.32, 'in')]
    def pf(tag, i, j):
        return side if tag == 'side' else rub
    full = prof + [prof[0]]
    def disp(i, j):
        tag = full[i][2]
        if tag == 'tread' and i in (4, 5):
            return 0.018 if (j // 2) % 2 == 0 else -0.004
        return 0.0
    K.lathe(p, full, 28, M, pf, 'plain', cap_bottom=False, cap_top=False, disp=disp)
    if rim:
        K.cyl_between(p, M @ Vector((0, 0, -w * 0.3)), M @ Vector((0, 0, w * 0.3)), ri * 1.02, hub, 16)
        for k in range(5):
            a = k * 2 * math.pi / 5
            q = M @ Vector((math.cos(a) * ri * 0.5, math.sin(a) * ri * 0.5, w * 0.3))
            K.bolt(p, q, M.to_3x3() @ Vector((0, 0, 1)), 0.025, S('steel', 0.9), 0.02)


def rebuild_tyres(ctx):
    for k in range(3):
        me = bpy.data.meshes.get(f'Tires_{k}_0')
        if me is None:
            continue
        rr = random.Random(950 + k)
        p = L.Part()
        for pts, vc in L.mesh_components(me, weld=0.002):
            if len(pts) < 41:
                continue          # inner discs
            ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2
            if ext[2] < 0.4:      # lying in a stack
                R = max(ext[0], ext[1]) / 2; w = ext[2]
                M = Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(rr.uniform(0, 6.28), 4, 'Z')
                tyre(p, M, R, w, rr, rim=False)
            else:                 # standing / leaning tyre: axle horizontal along the thin horizontal axis
                R = ext[2] / 2
                d = pts[:, :2] - c[:2]; w_, v = np.linalg.eigh(d.T @ d); ax = v[:, 0]
                yaw = math.atan2(ax[1], ax[0])
                M = Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'Y')
                tyre(p, M, R, min(ext[0], ext[1]) * 0.9 if min(ext[0], ext[1]) < 0.45 else 0.3, rr, rim=(k == 1))
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        finish_mesh(acc, me, ctx, f'v11: tyre family variant {k} rebuilt (tread blocks, sidewalls, rim on one variant)')


def rebuild_crates(ctx):
    for k in range(3):
        me = bpy.data.meshes.get(f'Crates_{k}_0')
        if me is None:
            continue
        rr = random.Random(970 + k)
        p = L.Part()
        comps = L.mesh_components(me, weld=0.002)
        for pts, vc in comps:
            ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2
            col = vc[:, :3].mean(0)
            if min(ext) > 0.45 and len(pts) <= 26 and col[0] > 0.3:                  # crate body
                d = pts[:, :2] - c[:2]; w, v = np.linalg.eigh(d.T @ d); ax = v[:, 1]
                yaw = math.atan2(ax[1], ax[0]) if w[1] > w[0] * 1.2 else rr.uniform(-0.05, 0.05)
                # pca on a square box is unreliable: use the bbox (crates are axis aligned in v10)
                crate(p, Vector((c[0], c[1], pts[:, 2].min())), (ext[0], ext[1], ext[2]), rr, yaw=0.0)
            elif min(ext) < 0.15 and max(ext) > 0.5 and ext[2] < 0.15 and max(ext[0], ext[1]) > 1.0:
                continue                                                            # straps: crate frames replace them
            elif min(ext) < 0.16 and max(ext) > 0.5:                                # loose plank
                i = int(np.argmax(ext)); a = c.copy(); b = c.copy(); a[i] -= ext[i] / 2; b[i] += ext[i] / 2
                K.board(p, Vector(a), Vector(b), max(0.08, sorted(ext)[1]), max(0.03, min(ext)), S('wood', 0.9), 'board_b',
                        up=(0, 0, 1) if i != 2 else (1, 0, 0))
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        finish_mesh(acc, me, ctx, f'v11: crate family variant {k} rebuilt (framed plank crates, braces)')


def car_wreck(p, rr, body_col, L_=4.1, W=1.93, missing_wheel=(1, -1)):
    """Stylized rusted sedan wreck, nose = +Y, footprint ~W x L_."""
    hw = W / 2; hl = L_ / 2
    paint = body_col; rust = S('rust_light', 1.0); dark = S('steel_dark', 1.3)
    # lower body
    K.box(p, (W, L_ - 0.1, 0.5), Matrix.Translation((0, 0, 0.5)), paint, 'plain', 0.08, wear=S('rust_light', 1.1))
    K.box(p, (W - 0.06, L_ * 0.28, 0.16), Matrix.Translation((0, hl - L_ * 0.18, 0.83)) @ Matrix.Rotation(-0.06, 4, 'X'), paint, 'plain', 0.04, wear=S('paint_cream', 0.8))
    K.box(p, (W - 0.06, L_ * 0.2, 0.14), Matrix.Translation((0, -hl + L_ * 0.12, 0.82)), paint, 'plain', 0.04, wear=S('paint_cream', 0.8))
    # cabin: pillars + roof (sagging, rusty), dark interior
    K.box(p, (W - 0.3, 1.85, 0.5), Matrix.Translation((0, -0.3, 0.98)), S('black', 1.8), 'plain', 0.02)
    K.box(p, (W - 0.24, 1.55, 0.07), Matrix.Translation((0, -0.35, 1.42)) @ Matrix.Rotation(0.04, 4, 'Y'), L.mix(paint, rust, 0.35), 'plain', 0.025, wear=paint)
    for sx in (-1, 1):
        for (y0, y1) in ((0.62, 0.36), (-1.25, -1.05)):
            K.beam(p, (sx * (hw - 0.14), y0, 0.74), (sx * (hw - 0.16), y1, 1.4), 0.08, 0.08, paint, 'plain', 0.01)
        K.beam(p, (sx * (hw - 0.14), -0.35, 0.74), (sx * (hw - 0.14), -0.35, 1.4), 0.07, 0.07, paint, 'plain', 0.01)
    # open hood (tilted up), engine block glimpse
    K.box(p, (W - 0.2, 1.0, 0.05), Matrix.Translation((0, hl - 0.95, 1.03)) @ Matrix.Rotation(-0.75, 4, 'X') @ Matrix.Translation((0, 0.45, 0)),
          L.mix(paint, rust, 0.3), 'plain', 0.02, wear=rust)
    K.box(p, (0.8, 0.7, 0.35), Matrix.Translation((0, hl - 0.75, 0.82)), S('steel_dark', 1.6), 'plain', 0.04)
    # bumpers, grille, broken lights
    K.box(p, (W + 0.06, 0.14, 0.18), Matrix.Translation((0, hl + 0.02, 0.42)), S('steel', 0.7), 'plain', 0.04, wear=rust)
    K.box(p, (W + 0.02, 0.14, 0.16), Matrix.Translation((0, -hl - 0.0, 0.42)) @ Matrix.Rotation(0.12, 4, 'Y'), rust, 'rustplate', 0.04)
    K.box(p, (W * 0.6, 0.05, 0.22), Matrix.Translation((0, hl + 0.0, 0.66)), dark, 'diamond', 0.01)
    for sx in (-1, 1):
        K.cyl_between(p, (sx * (hw - 0.22), hl - 0.02, 0.66), (sx * (hw - 0.22), hl + 0.03, 0.66), 0.09, S('paint_cream', 0.6), 10)
    # rust patches on the flanks
    for i in range(3):
        sx = rr.choice([-1, 1]); y = rr.uniform(-hl + 0.4, hl - 0.6)
        K.box(p, (0.02, rr.uniform(0.4, 0.9), rr.uniform(0.18, 0.32)), Matrix.Translation((sx * (hw + 0.002), y, rr.uniform(0.38, 0.6))), rust, 'rustplate', 0.0)
    # wheels (one missing -> brake drum on the ground)
    for sx in (-1, 1):
        for sy in (-1, 1):
            wy = sy * (hl - 0.78)
            if (sx, sy) == missing_wheel:
                K.cyl_between(p, (sx * (hw - 0.05), wy, 0.18), (sx * (hw + 0.05), wy, 0.18), 0.17, S('rust', 1.0), 10)
                continue
            M = Matrix.Translation((sx * (hw - 0.12), wy, 0.3)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
            tyre(p, M, 0.33, 0.24, rr, rim=True)
    # wheel arches (dark) suggestion
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box(p, (0.03, 0.82, 0.12), Matrix.Translation((sx * (hw + 0.003), sy * (hl - 0.78), 0.72)), S('black', 1.5), 'plain', 0.0)


def rebuild_carwrecks(ctx):
    cols = {}
    for k in range(3):
        me = bpy.data.meshes.get(f'CarWreck_{k}_0')
        if me is None:
            continue
        comps = L.mesh_components(me, weld=0.002)
        body = max(comps, key=lambda c: float(np.prod(np.maximum(c[0].max(0) - c[0].min(0), 0.05))))
        ext = body[0].max(0) - body[0].min(0); c = (body[0].max(0) + body[0].min(0)) / 2
        col = body[1][:, :3].mean(0)
        paint = (col[0] * 1.05, col[1] * 1.05, col[2] * 1.05, 1.0, 0.45, 0.15)
        rr = random.Random(990 + k)
        p = L.Part()
        long_y = ext[1] >= ext[0]
        car_wreck(p, rr, paint, L_=max(ext[0], ext[1]), W=min(ext[0], ext[1]), missing_wheel=[(1, -1), (-1, 1), (1, 1)][k])
        acc = L.MeshAccumulator()
        M = Matrix.Translation((c[0], c[1], 0.0)) @ (Matrix() if long_y else Matrix.Rotation(math.pi / 2, 4, 'Z'))
        acc.add(p.arrays(), M); p.free()
        # keep the v10 sand heap piece (drift against the wreck)
        for pts, vc in comps:
            if len(pts) >= 160:
                sp = L.Part()
                hx = (pts.max(0) - pts.min(0)) / 2
                sc_ = (pts.max(0) + pts.min(0)) / 2
                sp_bm = sp.bm
                K.lathe(sp, [(0.0, 0.0, 's'), (1.0, 0.0, 's'), (0.85, 0.35, 's'), (0.5, 0.7, 's'), (0.0, 0.85, 's')], 12,
                        Matrix.Translation((sc_[0], sc_[1], -0.02)) @ Matrix.Diagonal((hx[0], hx[1], max(0.2, hx[2] * 2), 1.0)),
                        lambda t, i, j: (0.62, 0.40, 0.21, 1.0, 0.0, 0.0), 'plain', cap_bottom=False, cap_top=False)
                acc.add_part(sp); sp.free()
        finish_mesh(acc, me, ctx, f'v11: car wreck variant {k} rebuilt (bevelled body, cabin pillars, open hood, wheels, rust)')


def bus_details(p, arr):
    co = arr['co']
    c = co.mean(0); d = co[:, :2] - c[:2]
    w, v = np.linalg.eigh(d.T @ d); ax = Vector((v[0, 1], v[1, 1], 0)).normalized(); side = Vector((-ax.y, ax.x, 0))
    pa = d @ np.array(ax[:2]); ps = d @ np.array(side[:2])
    # body is the largest box: use central extents
    a0, a1 = np.percentile(pa, 2), np.percentile(pa, 98); s0, s1 = np.percentile(ps, 2), np.percentile(ps, 98)
    C = Vector((c[0], c[1], 0)); yaw = math.atan2(ax.y, ax.x)
    R = Matrix.Rotation(yaw, 4, 'Z')
    def P(u, s, z):
        return C + ax * u + side * s + Vector((0, 0, z))
    steel = S('steel', 0.7); dark = S('black', 1.5); rust = S('rust_light', 1.0)
    # window band frames and pillars on both flanks
    for sgn, s in ((-1, s0), (1, s1)):
        n = 8
        for i in range(n + 1):
            u = a0 + 0.6 + (a1 - a0 - 1.2) * i / n
            K.box(p, (0.12, 0.04, 0.62), Matrix.Translation(P(u, s + sgn * 0.02, 1.2)) @ R, S('paint_yellow', 0.7), 'plain', 0.01)
        K.beam(p, P(a0 + 0.4, s + sgn * 0.03, 0.88), P(a1 - 0.4, s + sgn * 0.03, 0.88), 0.04, 0.08, S('black', 1.2), 'plain', 0.0)
        K.beam(p, P(a0 + 0.2, s + sgn * 0.03, 0.35), P(a1 - 0.2, s + sgn * 0.03, 0.35), 0.04, 0.12, rust, 'rustplate', 0.0)
        for (u, wdt) in ((a0 + 1.6, 1.0), (a1 - 2.2, 0.8)):
            K.box(p, (wdt, 0.02, 0.3), Matrix.Translation(P(u, s + sgn * 0.035, 0.6)) @ R, rust, 'rustplate', 0.0)
    # bumpers
    for u in (a0 - 0.05, a1 + 0.05):
        K.box(p, (0.16, s1 - s0 + 0.1, 0.22), Matrix.Translation(P(u, (s0 + s1) / 2, 0.35)) @ R, steel, 'plain', 0.04, wear=rust)
    # roof rack with junk
    for u in np.linspace(a0 + 1.0, a1 - 1.0, 5):
        K.beam(p, P(u, s0 + 0.3, 1.72), P(u, s1 - 0.3, 1.72), 0.06, 0.06, S('steel_dark', 1.2), 'plain', 0.0)
    for s in (s0 + 0.3, s1 - 0.3):
        K.beam(p, P(a0 + 1.0, s, 1.76), P(a1 - 1.0, s, 1.76), 0.06, 0.06, S('steel_dark', 1.2), 'plain', 0.0)
    K.box(p, (1.0, 0.8, 0.5), Matrix.Translation(P(a0 + 2.0, s0 + 1.0, 2.0)) @ R, S('canvas_dark'), 'plain', 0.1)
    K.box(p, (0.7, 0.7, 0.6), Matrix.Translation(P(a1 - 2.5, s1 - 1.1, 2.05)) @ R @ Matrix.Rotation(0.3, 4, 'Z'), S('wood'), 'board_a', 0.03)
    # wheel rims on the existing tyres
    for u, s in ((a0 + 1.6, s0), (a1 - 1.6, s1)):
        pass


def junk_details(p, arr):
    co = arr['co']; mn = co.min(0); mx = co.max(0); c = (mn + mx) / 2
    rr = random.Random(int(abs(c[0] * 100)) + 7)
    top = mx[2]
    K.sheet(p, (c[0] - 0.9, c[1] - 0.5, 0.05), (1.3, 0.2, 0.0), (0.2, 0.1, top * 0.9), 0.025, S('rust_light', 1.0), 'corrugated', 1.0)
    K.sheet(p, (c[0] + 0.2, c[1] + 0.35, 0.05), (0.9, -0.3, 0.0), (-0.1, 0.25, top * 0.7), 0.025, (0.10, 0.28, 0.29, 1, 0.45, 0.15), 'corrugated', 1.0)
    K.cyl_between(p, (c[0] - 1.1, c[1] + 0.6, 0.15), (c[0] + 0.9, c[1] - 0.2, top * 0.75), 0.07, S('rust', 1.1), 10)
    K.cyl_between(p, (c[0] + 0.8, c[1] + 0.8, 0.1), (c[0] + 0.1, c[1] + 0.9, 0.5), 0.05, S('steel', 0.7), 8)


def run(ctx):
    rebuild_barrels(ctx)
    rebuild_tyres(ctx)
    rebuild_crates(ctx)
    rebuild_carwrecks(ctx)
    for k in range(3):
        me = bpy.data.meshes.get(f'JunkPile_{k}_0')
        if me:
            users = [o for o in bpy.data.objects if o.data == me]
            augment2(users[0], ctx, lambda p, _me=me: junk_details(p, original_arrays(_me, np.ones(len(_me.vertices), bool))),
                     f'v11: junk pile variant {k} + corrugated sheets and pipes')
    ob = bpy.data.objects.get('Wreck')
    if ob:
        me = ob.data
        arr = original_arrays(me, np.ones(len(me.vertices), bool))
        augment2(ob, ctx, lambda p: bus_details(p, arr), 'v11: bus wreck + window frames, pillars, rust bands, bumpers, roof rack')
    print('STEP props done', flush=True)
