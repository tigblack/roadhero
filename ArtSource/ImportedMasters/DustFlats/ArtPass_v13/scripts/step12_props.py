"""v12 step: props to one quality bar. Car wrecks rebuilt from rounded swept sections (body, cabin, fenders,
bumpers) instead of boxes; junk piles become composed scrap heaps (barrel, tyres, bent sheets, pipes, engine block,
crate, planks) on a sand mound; crates get softer double chamfers. Barrels / tyres from v11 already have 20-28
segments. Instancing kept (shared spawn meshes rebuilt in place)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
from step_structures import finish_mesh, crate
from step_props import barrel, tyre
from step12_ramps import sweep, rounded_rect


def S(kind, k=1.0):
    return L.surf(kind, k)


def section_body(w, h, r, segs=3):
    """Closed rounded section centred on lateral 0, from up=0 (bottom) to up=h, all four corners rounded."""
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, r, -90), (w / 2 - r, h - r, 0), (-w / 2 + r, h - r, 90), (-w / 2 + r, r, 180)):
        for k in range(segs + 1):
            a = math.radians(a0 + 90 * k / segs)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def car_wreck_round(p, rr, paint, L_, W, missing):
    hw, hl = W / 2, L_ / 2
    rust = S('rust_light', 1.0)
    def fr_y(t, z0=0.0, x0=0.0):
        return Vector((x0, t, z0)), Vector((1, 0, 0)), Vector((0, 0, 1))
    # lower body with rounded section, rounded nose & tail via tapered end segments
    ts = np.linspace(-hl + 0.15, hl - 0.15, 14)
    sweep(p, ts, lambda t: fr_y(t, 0.28), section_body(W, 0.56, 0.2, 4), paint, 'plain')
    for sgn in (-1, 1):
        sweep(p, np.linspace(sgn * (hl - 0.15), sgn * (hl - 0.02), 2), lambda t: fr_y(t, 0.33), section_body(W - 0.12, 0.46, 0.18, 4), paint, 'plain')
    for sgn in (-1, 1):
        # bumper
        K.cyl_between(p, (-hw - 0.02, sgn * (hl + 0.06), 0.42), (hw + 0.02, sgn * (hl + 0.06), 0.42), 0.09,
                      S('steel', 0.75) if sgn > 0 else rust, 12)
    # fenders over the wheel positions (bulges on the flanks)
    for sy in (-1, 1):
        wy = sy * (hl - 0.8)
        for sx in (-1, 1):
            K.cyl_between(p, (sx * (hw - 0.32), wy, 0.44), (sx * (hw + 0.05), wy, 0.44), 0.47, paint, 20, bevel=0.04)
            K.cyl_between(p, (sx * (hw - 0.3), wy, 0.44), (sx * (hw + 0.06), wy, 0.44), 0.39, S('black', 1.4), 20)
    # cabin: rounded trapezoid sweep, window bands, sagging roof
    cab = [(-hw + 0.08, 0.0), (hw - 0.08, 0.0), (hw - 0.22, 0.5), (hw - 0.34, 0.56), (-hw + 0.34, 0.56), (-hw + 0.22, 0.5)]
    sweep(p, np.linspace(-1.25, 0.45, 6), lambda t: fr_y(t, 0.82), cab, L.mix(paint, rust, 0.15), 'plain')
    for sx in (-1, 1):
        K.box(p, (0.02, 1.5, 0.3), Matrix.Translation((sx * (hw - 0.14), -0.4, 1.08)) @ Matrix.Rotation(sx * 0.22, 4, 'Y'), S('black', 1.6), 'plain', 0.0)
    K.box(p, (W - 0.5, 0.02, 0.32), Matrix.Translation((0, 0.52, 1.07)) @ Matrix.Rotation(0.5, 4, 'X'), S('glass', 0.55), 'plain', 0.0)
    # open hood, engine
    K.box(p, (W - 0.24, 1.05, 0.05), Matrix.Translation((0, hl - 1.05, 0.88)) @ Matrix.Rotation(-0.85, 4, 'X') @ Matrix.Translation((0, 0.5, 0)),
          L.mix(paint, rust, 0.25), 'plain', 0.03, wear=rust)
    K.box(p, (0.75, 0.62, 0.32), Matrix.Translation((0, hl - 0.75, 0.78)), S('steel_dark', 1.6), 'plain', 0.06)
    K.cyl_between(p, (-0.25, hl - 0.75, 0.94), (0.25, hl - 0.75, 0.94), 0.08, S('steel', 0.6), 10)
    # headlights (one broken), rust patches
    for sx in (-1, 1):
        K.cyl_between(p, (sx * (hw - 0.3), hl + 0.02, 0.62), (sx * (hw - 0.3), hl + 0.08, 0.62), 0.1,
                      S('paint_cream', 0.6) if sx > 0 else S('black', 1.4), 12)
    for i in range(3):
        sx = rr.choice([-1, 1]); y = rr.uniform(-hl + 0.6, hl - 0.8)
        K.box(p, (0.02, rr.uniform(0.4, 0.8), rr.uniform(0.16, 0.28)), Matrix.Translation((sx * (hw + 0.004), y, rr.uniform(0.38, 0.62))), rust, 'rustplate', 0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            wy = sy * (hl - 0.8)
            if (sx, sy) == missing:
                K.cyl_between(p, (sx * (hw - 0.05), wy, 0.18), (sx * (hw + 0.05), wy, 0.18), 0.17, S('rust', 1.0), 12)
                continue
            tyre(p, Matrix.Translation((sx * (hw - 0.1), wy, 0.33)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'), 0.34, 0.24, rr, rim=True)


def rebuild_wrecks(ctx):
    for k in range(3):
        me = bpy.data.meshes.get(f'CarWreck_{k}_0')
        if me is None:
            continue
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
        # body colour: most saturated common colour of the v11 wreck
        ratio = col[:, 1] / np.maximum(col[:, 0], 1e-3)
        cand = col[(ratio < 0.45) & (col[:, 0] > 0.15), :3]
        body = cand.mean(0) if len(cand) else np.array([0.42, 0.10, 0.03])
        paint = (body[0], body[1], body[2], 1.0, 0.45, 0.15)
        lo = np.percentile(co[:, :2], 3, axis=0); hi = np.percentile(co[:, :2], 97, axis=0); ext = hi - lo; c = (lo + hi) / 2
        rr = random.Random(2400 + k)
        p = L.Part()
        L_ = max(3.6, min(4.3, max(ext))); W = max(1.7, min(2.0, min(ext)))
        car_wreck_round(p, rr, paint, L_, W, [(1, -1), (-1, 1), (1, 1)][k])
        acc = L.MeshAccumulator()
        M = Matrix.Translation((c[0], c[1], 0.0)) @ (Matrix() if ext[1] >= ext[0] else Matrix.Rotation(math.pi / 2, 4, 'Z'))
        acc.add(p.arrays(), M); p.free()
        sp = L.Part()
        K.lathe(sp, [(0.0, 0.0, 's'), (1.0, 0.0, 's'), (0.8, 0.3, 's'), (0.4, 0.55, 's'), (0.0, 0.62, 's')], 14,
                Matrix.Translation((c[0] - 1.3, c[1] - 1.5, -0.03)) @ Matrix.Diagonal((0.9, 0.7, 0.5, 1.0)),
                lambda t, i, j: (0.62, 0.40, 0.21, 1.0, 0.0, 0.0), 'plain', cap_bottom=False, cap_top=False)
        acc.add_part(sp); sp.free()
        finish_mesh(acc, me, ctx, f'v12: car wreck variant {k} rebuilt from rounded sections (body, cabin, fenders, bumpers)')


def junk_heap(p, rr, variant):
    # sand mound base
    K.lathe(p, [(0.0, 0.0, 's'), (1.0, 0.0, 's'), (0.85, 0.22, 's'), (0.45, 0.42, 's'), (0.0, 0.48, 's')], 16,
            Matrix.Translation((0, 0, -0.05)) @ Matrix.Diagonal((1.45, 1.2, 0.7, 1.0)),
            lambda t, i, j: (0.60, 0.39, 0.21, 1.0, 0.0, 0.0), 'plain', cap_bottom=False, cap_top=False)
    paints = [(0.55, 0.10, 0.04, 1, 0.5, 0.15), (0.06, 0.18, 0.40, 1, 0.5, 0.15), (0.70, 0.45, 0.05, 1, 0.5, 0.15)]
    # lying barrel
    M = Matrix.Translation((rr.uniform(-0.4, 0.3), rr.uniform(-0.5, -0.2), 0.48)) @ Matrix.Rotation(rr.uniform(0, 3.14), 4, 'Z') @ \
        Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Translation((0, 0, -0.475))
    barrel(p, M, 0.34, 0.9, paints[variant % 3], rr)
    # tyres
    tyre(p, Matrix.Translation((0.7, 0.45, 0.32)) @ Matrix.Rotation(0.25, 4, 'X'), 0.45, 0.26, rr)
    tyre(p, Matrix.Translation((-0.9, 0.5, 0.55)) @ Matrix.Rotation(1.2, 4, 'Y') @ Matrix.Rotation(0.4, 4, 'X'), 0.42, 0.24, rr, rim=variant == 1)
    # bent corrugated sheets leaning on the heap
    for k in range(2 + variant % 2):
        a = rr.uniform(0, 2 * math.pi); d = rr.uniform(0.5, 0.9)
        base = Vector((math.cos(a) * d, math.sin(a) * d, 0.05)); n = Vector((-math.sin(a), math.cos(a), 0)) * rr.uniform(1.0, 1.5)
        up = Vector((-math.cos(a) * 0.4, -math.sin(a) * 0.4, rr.uniform(0.8, 1.15)))
        col = rr.choice([S('rust_light', 1.0), (0.10, 0.28, 0.29, 1, 0.45, 0.15), S('galvanized', 0.75)])
        K.sag_sheet(p, base - n / 2, base + n / 2, base - n / 2 + up, base + n / 2 + up, 4, 3, -0.08, 0.025, col, 'corrugated', rr.randint(0, 99), 0.8)
    # pipe bundle
    for k in range(3):
        y = -0.15 + k * 0.17
        K.cyl_between(p, (-1.25, 0.9 + y, 0.12 + 0.05 * k), (0.95, 0.75 + y, 0.25 + 0.08 * k), 0.07 + 0.015 * k, rr.choice([S('rust', 1.1), S('steel', 0.7)]), 12)
    # engine block
    K.box(p, (0.62, 0.45, 0.4), Matrix.Translation((0.25, -0.05, 0.62)) @ Matrix.Rotation(0.3, 4, 'Z') @ Matrix.Rotation(0.2, 4, 'X'), S('steel_dark', 1.5), 'plain', 0.07)
    K.cyl_between(p, (0.05, -0.1, 0.84), (0.48, 0.05, 0.9), 0.1, S('steel', 0.6), 10)
    # crate & planks
    crate(p, Vector((-0.75, -0.75, 0.0)), (0.6, 0.55, 0.55), rr, yaw=rr.uniform(-0.6, 0.6))
    for k in range(3):
        a = rr.uniform(0, 3.14)
        K.board(p, (math.cos(a) * -0.9, math.sin(a) * -0.9, 0.08 + 0.05 * k), (math.cos(a) * 0.8, math.sin(a) * 0.8, 0.35 + 0.08 * k), 0.16, 0.04, S('wood', 0.8), 'board_b')


def rebuild_junk(ctx):
    for k in range(3):
        me = bpy.data.meshes.get(f'JunkPile_{k}_0')
        if me is None:
            continue
        p = L.Part(); junk_heap(p, random.Random(2600 + k), k)
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        finish_mesh(acc, me, ctx, f'v12: junk pile variant {k} rebuilt as a composed scrap heap (barrel, tyres, bent sheets, pipes, engine, crate)')


def run(ctx):
    rebuild_wrecks(ctx)
    rebuild_junk(ctx)
    ctx['stats']['props'] = 'car wrecks x3 (rounded sections), junk piles x3 (composed heaps)'
    print('STEP12 props done', flush=True)
