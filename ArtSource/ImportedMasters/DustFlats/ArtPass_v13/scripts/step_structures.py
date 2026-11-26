"""Step: camp structures. Shared spawn meshes (Shack/Tent/Tower families) are rebuilt in place, so every
instance updates and instancing is kept. Unique structures (garage, gate, billboard, palisades) keep their
objects; palisade stakes keep their positions (gaps/openings unchanged)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays


def S(kind, k=1.0, a=1.0):
    return L.surf(kind, k, a)


def finish_mesh(acc, me_old, ctx, note, mats=None):
    mats = mats or [ctx['mats']['Trim_Structures']]
    new = acc.build(me_old.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me_old, new, note=note)
    for o in users:
        L.set_object_materials(o, mats)
    return users


def with_mat(arr, idx):
    a = dict(arr); a['mat'] = np.full(len(arr['flen']), idx, np.int32); return a


# ------------------------------------------------------------------------------------------------
# Crate (prop family piece, also used beside shacks)
# ------------------------------------------------------------------------------------------------
def crate(p, c, size, r, kind='wood', yaw=0.0):
    sx, sy, sz = size
    M = Matrix.Translation(c) @ Matrix.Rotation(yaw, 4, 'Z')
    wood = S('wood', r.uniform(0.85, 1.1)); dark = S('wood_dark', 1.1)
    K.box(p, (sx - 0.06, sy - 0.06, sz - 0.06), M @ Matrix.Translation((0, 0, sz / 2)), wood, 'board_a', 0.02, wear=S('wood_light'))
    t = 0.07
    for zz in (t / 2 + 0.005, sz - t / 2 - 0.005):              # top/bottom frame boards
        for (a, b, w) in (((-sx / 2, -sy / 2), (sx / 2, -sy / 2), 0), ((-sx / 2, sy / 2), (sx / 2, sy / 2), 0)):
            K.beam(p, M @ Vector((a[0], a[1], zz)), M @ Vector((b[0], b[1], zz)), 0.04, t, dark, 'board_b', 0.01)
        for (a, b) in (((-sx / 2, -sy / 2), (-sx / 2, sy / 2)), ((sx / 2, -sy / 2), (sx / 2, sy / 2))):
            K.beam(p, M @ Vector((a[0], a[1], zz)), M @ Vector((b[0], b[1], zz)), 0.04, t, dark, 'board_b', 0.01)
    for (x, y) in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (-sx / 2, sy / 2), (sx / 2, sy / 2)):
        K.beam(p, M @ Vector((x, y, 0.0)), M @ Vector((x, y, sz)), 0.07, 0.07, dark, 'board_b', 0.012)
    # diagonal brace on the two long faces
    for y in (-sy / 2 - 0.012, sy / 2 + 0.012):
        K.beam(p, M @ Vector((-sx / 2 + 0.06, y, 0.08)), M @ Vector((sx / 2 - 0.06, y, sz - 0.08)), 0.02, 0.07, dark, 'board_b', 0.008,
               up=(M.to_3x3() @ Vector((0, 1, 0))))


# ------------------------------------------------------------------------------------------------
# Shack family (3 variants, footprint 3.2 x 2.8, front = -Y)
# ------------------------------------------------------------------------------------------------
def build_shack(variant, seed):
    r = random.Random(seed)
    p = L.Part()
    W, D, H = 3.2, 2.8, 2.42
    metal_walls = (variant == 1)
    wall_s = S('paint_grey', 0.85) if metal_walls else S('wood_grey', 0.95)
    if metal_walls:
        wall_s = (0.20, 0.25, 0.28, 1.0, 0.42, 0.18)
    core = S('wood_dark', 0.8)
    # plinth
    K.box(p, (W + 0.22, D + 0.22, 0.16), Matrix.Translation((0, 0, 0.06)), S('concrete', 0.9), 'concrete', 0.03, wear=S('concrete', 1.1))
    # core walls (hidden mostly by cladding)
    K.box(p, (W - 0.06, D - 0.06, H), Matrix.Translation((0, 0, 0.14 + H / 2)), core, 'plain', 0.0)
    # openings on the front (-Y) wall: (x0, x1, z0, z1)
    door = (-0.2, 0.7, 0.14, 1.82); window = (-1.2, -0.5, 1.3, 1.9)
    openings_front = [door, window]
    def clad_wall(origin, along, normal, length, openings, rot=0):
        """Horizontal boards (wood) or vertical corrugated sheets (metal) on one wall."""
        along = Vector(along); normal = Vector(normal); origin = Vector(origin)
        if metal_walls:
            x = 0.0; i = 0
            while x < length - 0.05:
                w = min(0.9, length - x)
                x0, x1 = x, x + w
                segs = [(0.16, H + 0.12)]
                for (ox0, ox1, oz0, oz1) in openings:
                    if ox1 + length / 2 > x0 and ox0 + length / 2 < x1:
                        # sheet column overlapping an opening: split above/below
                        segs = [(0.16, oz0), (oz1, H + 0.12)] if oz0 > 0.3 else [(oz1, H + 0.12)]
                for (z0, z1) in segs:
                    if z1 - z0 < 0.1:
                        continue
                    k = r.uniform(0.9, 1.08)
                    c = (wall_s[0] * k, wall_s[1] * k, wall_s[2] * k, 1.0, wall_s[4], wall_s[5])
                    o = origin + along * x0 + normal * (0.02 + 0.01 * (i % 2)) + Vector((0, 0, z0))
                    K.sheet(p, o, along * w, Vector((0, 0, z1 - z0)), 0.025, c, 'corrugated', m_per_u=1.2)
                x += w - 0.04; i += 1
        else:
            z = 0.16; row = 0
            while z < H + 0.1:
                bh = r.uniform(0.2, 0.25)
                z1 = min(H + 0.12, z + bh)
                segs = [(0.0, length)]
                for (ox0, ox1, oz0, oz1) in openings:
                    if z1 > oz0 and z < oz1:
                        a0, a1 = ox0 + length / 2, ox1 + length / 2
                        segs = [s for seg in segs for s in ((seg[0], min(seg[1], a0)), (max(seg[0], a1), seg[1])) if s[1] - s[0] > 0.08]
                for (x0, x1) in segs:
                    k = r.uniform(0.82, 1.12)
                    c = (wall_s[0] * k, wall_s[1] * k, wall_s[2] * k, 1.0, 0.08, 0.0)
                    off = normal * (0.025 + r.uniform(0, 0.012))
                    a = origin + along * x0 + off + Vector((0, 0, (z + z1) / 2))
                    b = origin + along * x1 + off + Vector((0, 0, (z + z1) / 2))
                    K.board(p, a, b, z1 - z - 0.018, 0.03, c, r.choice(['board_a', 'board_b']), up=(0, 0, 1))
                z = z1; row += 1
    clad_wall((-W / 2, -D / 2, 0), (1, 0, 0), (0, -1, 0), W, openings_front)
    clad_wall((W / 2, D / 2, 0), (-1, 0, 0), (0, 1, 0), W, [])
    clad_wall((W / 2, -D / 2, 0), (0, 1, 0), (1, 0, 0), D, [(-0.6, 0.6, 0.6, 1.5)] if variant == 2 else [])
    clad_wall((-W / 2, D / 2, 0), (0, -1, 0), (-1, 0, 0), D, [])
    post = S('wood_dark', 1.05)
    for (x, y) in ((-W / 2, -D / 2), (W / 2, -D / 2), (-W / 2, D / 2), (W / 2, D / 2)):
        K.beam(p, (x, y, 0.1), (x, y, H + 0.2), 0.16, 0.16, post, 'board_b', 0.025, up=(1, 0, 0))
        # steel corner angle at the base
        K.box(p, (0.2, 0.2, 0.32), Matrix.Translation((x, y, 0.3)), S('steel_dark', 1.2), 'plain', 0.01)
    # top plates
    for (a, b) in (((-W / 2, -D / 2), (W / 2, -D / 2)), ((-W / 2, D / 2), (W / 2, D / 2))):
        K.beam(p, (a[0], a[1], H + 0.12), (b[0], b[1], H + 0.12), 0.14, 0.14, post, 'board_b', 0.02)
    # door: frame + leaf of planks + Z brace + handle
    x0, x1, z0, z1 = door
    yf = -D / 2 - 0.05
    for xx in (x0 - 0.05, x1 + 0.05):
        K.beam(p, (xx, yf, z0), (xx, yf, z1 + 0.1), 0.1, 0.1, post, 'board_b', 0.015, up=(1, 0, 0))
    K.beam(p, (x0 - 0.12, yf, z1 + 0.06), (x1 + 0.12, yf, z1 + 0.06), 0.12, 0.12, post, 'board_b', 0.015)
    nplank = 4
    for i in range(nplank):
        xa = x0 + (x1 - x0) * (i + 0.5) / nplank
        k = r.uniform(0.85, 1.1)
        K.board(p, (xa, yf + 0.04, z0 + 0.02), (xa, yf + 0.04, z1 - 0.02), (x1 - x0) / nplank - 0.015, 0.035,
                S('wood', 0.75 * k), 'board_b', up=(1, 0, 0))
    for zz in (z0 + 0.3, z1 - 0.3):
        K.board(p, (x0 + 0.04, yf - 0.0, zz), (x1 - 0.04, yf - 0.0, zz), 0.1, 0.03, S('wood_dark', 1.2), 'board_b')
    K.board(p, (x0 + 0.08, yf - 0.005, z0 + 0.32), (x1 - 0.08, yf - 0.005, z1 - 0.32), 0.09, 0.025, S('wood_dark', 1.2), 'board_b',
            up=(0, -1, 0))
    K.box(p, (0.05, 0.06, 0.2), Matrix.Translation((x1 - 0.12, yf - 0.05, 1.0)), S('steel', 0.8), 'plain', 0.01)
    for zz in (z0 + 0.3, z1 - 0.3):
        K.box(p, (0.22, 0.02, 0.05), Matrix.Translation((x0 + 0.08, yf - 0.03, zz)), S('steel_dark', 1.3), 'plain', 0.0)
    # window: frame, dark pane, open teal shutter
    wx0, wx1, wz0, wz1 = window
    K.box(p, (wx1 - wx0, 0.05, wz1 - wz0), Matrix.Translation(((wx0 + wx1) / 2, yf + 0.04, (wz0 + wz1) / 2)), S('glass', 0.6), 'plain')
    for (a, b) in (((wx0, wz0), (wx1, wz0)), ((wx0, wz1), (wx1, wz1)), ((wx0, wz0), (wx0, wz1)), ((wx1, wz0), (wx1, wz1))):
        K.beam(p, (a[0], yf - 0.01, a[1]), (b[0], yf - 0.01, b[1]), 0.07, 0.07, S('wood_light', 0.9), 'board_b', 0.01,
               up=(0, -1, 0), ext=0.07)
    K.beam(p, ((wx0 + wx1) / 2, yf - 0.02, wz0), ((wx0 + wx1) / 2, yf - 0.02, wz1), 0.04, 0.04, S('wood_light', 0.9), 'board_b', 0.0)
    shut = (0.08, 0.30, 0.31, 1.0, 0.5, 0.15) if variant != 1 else (0.55, 0.10, 0.04, 1.0, 0.5, 0.15)
    sw = (wx1 - wx0) * 0.5
    hinge = Vector((wx0 - 0.04, yf - 0.02, 0))
    Ms = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(-115), 4, 'Z') @ Matrix.Translation((sw / 2, 0, (wz0 + wz1) / 2))
    K.box(p, (sw, 0.03, wz1 - wz0 - 0.02), Ms, shut, 'panel', 0.008, wear=S('steel', 0.9))
    # repair patches: rusty corrugated (front left, low) and painted plate (front right)
    K.sheet(p, (-1.48, yf - 0.035, 0.25), (0.95, 0, 0.06), (0.03, 0, 0.85), 0.02, S('rust_light', 1.0), 'corrugated', 1.0)
    pc = (0.08, 0.28, 0.29, 1.0, 0.5, 0.15) if variant == 0 else ((0.62, 0.22, 0.06, 1.0, 0.48, 0.15) if variant == 1 else (0.80, 0.69, 0.50, 1.0, 0.45, 0.1))
    K.sheet(p, (0.92, yf - 0.035, 0.55), (0.6, 0, 0.0), (0.0, 0, 1.45), 0.025, pc, 'panel', 1.0)
    for (bx, bz) in ((0.97, 0.62), (1.47, 0.62), (0.97, 1.93), (1.47, 1.93), (-1.43, 0.32), (-0.58, 0.36), (-1.4, 1.0), (-0.56, 1.05)):
        K.bolt(p, (bx, yf - 0.05, bz), (0, -1, 0), 0.025, S('steel', 0.9), 0.025)
    # side patch (+X), slightly tilted rust plate with bolts
    Mp = Matrix.Translation((W / 2 + 0.06, 0.3, 1.0)) @ Matrix.Rotation(math.radians(6), 4, 'X')
    K.box(p, (0.03, 1.35, 1.25), Mp, (0.60, 0.17, 0.05, 1, 0.45, 0.15), 'rustplate', 0.01)
    for (dy, dz) in ((-0.58, -0.52), (0.58, -0.52), (-0.58, 0.52), (0.58, 0.52)):
        K.bolt(p, Mp @ Vector((0.02, dy, dz)), (1, 0, 0), 0.03, S('steel', 0.9), 0.03)
    # gable roof (ridge along X) — corrugated sheets with thickness, ridge cap, barge boards, rafter tails
    pitch = math.radians(24)
    ov = 0.3; RX = W / 2 + 0.3; ry = D / 2 + ov
    zr = H + 0.2 + (D / 2) * math.tan(pitch)
    ze = zr - ry * math.tan(pitch)
    roof_s = (0.42, 0.11, 0.045, 1.0, 0.42, 0.2) if variant != 1 else (0.30, 0.31, 0.32, 1.0, 0.45, 0.55)
    for sgn in (-1, 1):
        o = Vector((-RX, 0, zr + 0.03)); u = Vector((2 * RX, 0, 0)); v = Vector((0, sgn * ry, ze - zr))
        K.sheet(p, o, u, v, 0.05, roof_s, 'corrugated', m_per_u=1.0)
        # rafter tails
        for x in np.linspace(-W / 2 + 0.2, W / 2 - 0.2, 4):
            K.beam(p, (x, sgn * (D / 2 - 0.1), H + 0.17), (x, sgn * (ry - 0.05), ze + 0.0), 0.07, 0.12, post, 'board_b', 0.01,
                   up=(0, -sgn * math.sin(pitch), math.cos(pitch)))
    # gable triangles (boards) and barge boards
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.02)
        K.prism(p, [(-D / 2, H + 0.14), (D / 2, H + 0.14), (0, zr - 0.02)], -0.03, 0.03,
                Matrix.Translation((x, 0, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
                wall_s if not metal_walls else S('wood_grey'), 'board_a')
        for sgn in (-1, 1):
            K.beam(p, (sx * (RX + 0.02), 0, zr + 0.06), (sx * (RX + 0.02), sgn * (ry + 0.02), ze + 0.06), 0.06, 0.16, post, 'board_b', 0.012,
                   up=(0, -sgn * math.sin(pitch), math.cos(pitch)), ext=0.1)
    # ridge cap
    for sgn in (-1, 1):
        K.sheet(p, (-RX - 0.03, 0, zr + 0.09), (2 * RX + 0.06, 0, 0), (0, sgn * 0.2, -0.2 * math.tan(pitch)), 0.025,
                S('galvanized', 0.85), 'panel', 1.0)
    # chimney pipe with cap and flashing
    cx, cy = 1.0, 0.9
    zroof = zr - abs(cy) * math.tan(pitch)
    K.cyl_between(p, (cx, cy, zroof - 0.2), (cx, cy, 3.55), 0.11, S('steel_dark', 1.4), 12)
    K.cyl_between(p, (cx, cy, 3.5), (cx, cy, 3.72), 0.2, S('steel_dark', 1.2), 12, r2=0.04)
    K.box(p, (0.36, 0.36, 0.08), Matrix.Translation((cx, cy, zroof + 0.06)) @ Matrix.Rotation(-pitch, 4, 'X'), S('rust', 1.2), 'plain', 0.01)
    # side crate (variant-dependent) + sign
    crate(p, Vector((-1.9, -0.6, 0)), (0.72, 0.72, 0.86), r, yaw=r.uniform(-0.2, 0.2))
    if variant == 2:
        K.box(p, (1.45, 0.05, 0.36), Matrix.Translation((0.25, yf - 0.06, 2.06)), S('paint_cream', 0.95), 'board_b', 0.01, wear=S('wood'))
        for xx in (-0.35, 0.85):
            K.bolt(p, (xx, yf - 0.09, 2.06), (0, -1, 0), 0.025, S('steel', 0.8), 0.02)
    return p


# ------------------------------------------------------------------------------------------------
# Tent family: canvas A-frame (width X 2.5, depth Y 2.6, height 1.9), door at -Y
# ------------------------------------------------------------------------------------------------
def build_tent(variant, seed, w=2.5, d=2.6, h=1.9):
    r = random.Random(seed)
    p = L.Part()
    canvas = [S('canvas', 0.86), S('canvas', 0.78), (0.56, 0.38, 0.24, 1.0, 0.02, 0.0)][variant % 3]
    hw = w / 2; hd = d / 2
    for sgn in (-1, 1):
        K.sag_sheet(p, (sgn * hw, -hd, 0.02), (sgn * hw, hd, 0.02), (0.0, -hd, h), (0.0, hd, h), 5, 3, 0.09, 0.03, canvas, 'plain', seed + sgn) if False else K.sag_sheet(p, (sgn * hw, -hd, 0.02), (sgn * hw, hd, 0.02), (0.0, -hd, h), (0.0, hd, h), 6, 4, 0.16, 0.03, canvas, 'plain', seed + sgn)
    # back end closed
    K.prism(p, [(-hw + 0.05, 0.02), (hw - 0.05, 0.02), (0, h - 0.05)], -0.015, 0.015,
            Matrix.Translation((0, hd - 0.02, 0)) @ Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
            (canvas[0] * 0.92, canvas[1] * 0.92, canvas[2] * 0.92, 1, 0.02, 0), 'plain')
    # dark interior + rolled-back door flaps
    K.prism(p, [(-hw * 0.55, 0.02), (hw * 0.55, 0.02), (0, h * 0.82)], -0.01, 0.01,
            Matrix.Translation((0, -hd + 0.25, 0)) @ Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
            S('black', 1.2), 'plain')
    for sgn in (-1, 1):
        K.prism(p, [(sgn * hw * 0.5, 0.02), (sgn * (hw - 0.05), 0.02), (0, h - 0.05)], -0.012, 0.012,
                Matrix.Translation((0, -hd + 0.02, 0)) @ Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
                (canvas[0] * 0.95, canvas[1] * 0.95, canvas[2] * 0.95, 1, 0.02, 0), 'plain')
        K.cyl_between(p, (sgn * hw * 0.3, -hd - 0.02, 0.15), (sgn * 0.1, -hd - 0.02, h - 0.25), 0.07, canvas, 8)
    pole = S('wood_dark', 1.1)
    K.cyl_between(p, (0, -hd - 0.05, 0), (0, -hd - 0.05, h + 0.25), 0.05, pole, 8)
    K.cyl_between(p, (0, hd + 0.05, 0), (0, hd + 0.05, h + 0.25), 0.05, pole, 8)
    K.cyl_between(p, (0, -hd - 0.12, h + 0.05), (0, hd + 0.12, h + 0.05), 0.045, pole, 8)
    rope = S('canvas_dark', 0.8)
    for sy in (-1, 1):
        top = Vector((0, sy * (hd + 0.05), h + 0.18)); stake = Vector((0, sy * (hd + 0.85), 0.0))
        K.cyl_between(p, top, stake, 0.015, rope, 5)
        K.cyl_between(p, stake + Vector((0, 0, -0.1)), stake + Vector((0, 0, 0.2)), 0.04, pole, 6)
    for sx in (-1, 1):
        for sy in (-0.6, 0.6):
            top = Vector((sx * hw * 0.55, sy * hd, h * 0.45)); stake = Vector((sx * (hw + 0.55), sy * hd, 0.0))
            K.cyl_between(p, top, stake, 0.013, rope, 5)
            K.cyl_between(p, stake + Vector((0, 0, -0.08)), stake + Vector((0, 0, 0.16)), 0.035, pole, 6)
    # patches on the canvas
    for i in range(2 + variant % 2):
        sgn = r.choice([-1, 1]); u = r.uniform(0.25, 0.7); v = r.uniform(-0.6, 0.5)
        x = sgn * hw * (1 - u); z = h * u
        M = Matrix.Translation((x * 1.02, v, z)) @ Matrix.Rotation(-sgn * math.atan2(h, hw), 4, 'Y')
        pcs = r.choice([S('canvas_dark'), (0.10, 0.27, 0.28, 1, 0.05, 0), S('paint_olive')])
        K.box(p, (0.03, 0.45, 0.4), M @ Matrix.Translation((sgn * 0.035, 0, 0)), pcs, 'plain', 0.0)
    # sandbags holding the canvas edge
    for (x, y) in ((-hw + 0.1, -hd + 0.3), (hw - 0.1, hd - 0.4), (-hw + 0.1, hd - 0.5)):
        K.box(p, (0.45, 0.28, 0.18), Matrix.Translation((x, y, 0.09)) @ Matrix.Rotation(r.uniform(-0.5, 0.5), 4, 'Z'),
              S('canvas_dark', 1.1), 'plain', 0.07)
    return p


# ------------------------------------------------------------------------------------------------
# Watch tower family (built at Tower_0 proportions, scaled per variant)
# ------------------------------------------------------------------------------------------------
def build_tower(seed):
    r = random.Random(seed)
    p = L.Part()
    post = S('wood_dark', 1.0); plank = S('wood', 0.95); brace = S('wood_dark', 1.25)
    zp = 4.1; half_b = 0.95; half_t = 0.85
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = Vector((sx * half_b, sy * half_b, -0.05)); b = Vector((sx * half_t, sy * half_t, zp + 1.15))
            K.beam(p, a, b, 0.2, 0.2, post, 'board_b', 0.025, up=(sx, 0, 0)); legs.append((a, b))
            K.box(p, (0.42, 0.42, 0.22), Matrix.Translation((sx * half_b, sy * half_b, 0.08)), S('concrete', 0.85), 'concrete', 0.04)
    def at(sx, sy, z):
        t = (z + 0.05) / (zp + 1.2)
        k = half_b + (half_t - half_b) * t
        return Vector((sx * k, sy * k, z))
    for (z0, z1) in ((0.3, 2.1), (2.1, 3.9)):
        for (s1, s2) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            K.beam(p, at(*s1, z0), at(*s2, z1), 0.06, 0.13, brace, 'board_b', 0.01)
            K.beam(p, at(*s2, z0), at(*s1, z1), 0.06, 0.13, brace, 'board_b', 0.01)
            K.beam(p, at(*s1, z1), at(*s2, z1), 0.1, 0.14, post, 'board_b', 0.012)
    # platform deck (planks) + joists
    for i in range(9):
        y = -1.1 + i * 0.275
        K.board(p, (-1.17, y, zp + 0.1), (1.17, y, zp + 0.1), 0.25, 0.06, (plank[0] * r.uniform(0.85, 1.1), plank[1] * r.uniform(0.85, 1.1), plank[2], 1, 0.1, 0), r.choice(['board_a', 'board_b']), up=(0, 1, 0))
    for x in (-1.05, 0, 1.05):
        K.beam(p, (x, -1.2, zp - 0.04), (x, 1.2, zp - 0.04), 0.1, 0.16, post, 'board_b', 0.01)
    # railing: posts + top rail + half-wall planks (red-painted patch on one side like v10)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.beam(p, (sx * 1.12, sy * 1.12, zp + 0.1), (sx * 1.12, sy * 1.12, zp + 1.25), 0.1, 0.1, post, 'board_b', 0.01)
    sides = [((-1.12, -1.12), (1.12, -1.12)), ((1.12, -1.12), (1.12, 1.12)), ((1.12, 1.12), (-1.12, 1.12)), ((-1.12, 1.12), (-1.12, -1.12))]
    for k, (a, b) in enumerate(sides):
        K.beam(p, (a[0], a[1], zp + 1.22), (b[0], b[1], zp + 1.22), 0.09, 0.08, post, 'board_b', 0.01, ext=0.1)
        for j, zz in enumerate((zp + 0.32, zp + 0.58)):
            col = (0.50, 0.12, 0.04, 1, 0.4, 0.12) if (k == 3) else (plank[0] * r.uniform(0.8, 1.05), plank[1] * 0.95, plank[2], 1, 0.1, 0)
            K.board(p, (a[0], a[1], zz), (b[0], b[1], zz), 0.24, 0.04, col, 'board_b' if k != 3 else 'panel', up=(0, 0, 1))
    # hip roof: four corrugated triangles approximated by sheets + cap, on four thin posts
    zr0 = zp + 1.6; zr1 = zp + 2.45; R = 1.38
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.beam(p, (sx * 1.05, sy * 1.05, zp + 1.2), (sx * 1.05, sy * 1.05, zr0 + 0.02), 0.08, 0.08, post, 'board_b', 0.008)
    roof = (0.40, 0.10, 0.04, 1.0, 0.42, 0.2)
    corners = [Vector((-R, -R, zr0)), Vector((R, -R, zr0)), Vector((R, R, zr0)), Vector((-R, R, zr0))]
    apex = Vector((0, 0, zr1))
    bm = p.bm
    faces = []
    for i in range(4):
        a = corners[i]; b = corners[(i + 1) % 4]
        n = (b - a).cross(apex - a).normalized()
        va = [bm.verts.new(q + n * 0.03) for q in (a, b, apex)]
        vb = [bm.verts.new(q - n * 0.03) for q in (a, b, apex)]
        faces.append(bm.faces.new(va)); faces.append(bm.faces.new(list(reversed(vb))))
        for j in range(3):
            k = (j + 1) % 3
            faces.append(bm.faces.new([va[j], vb[j], vb[k], va[k]]))
    bm.normal_update()
    p.paint(faces, roof)
    v0, v1 = K._strip('corrugated'); p.uv_trim(faces, v0, v1, 0.8)
    for i in range(4):
        K.beam(p, corners[i] + Vector((0, 0, 0.05)), apex + Vector((0, 0, 0.06)), 0.07, 0.07, S('galvanized', 0.8), 'plain', 0.0)
    K.cyl_between(p, apex, apex + Vector((0, 0, 0.12)), 0.09, S('steel_dark', 1.2), 8)
    # ladder on the front (-Y)
    for xx in (0.2, 0.7):
        K.beam(p, (xx, -1.32, 0.0), (xx, -1.14, zp + 0.15), 0.06, 0.08, plank, 'board_b', 0.008, up=(1, 0, 0))
    for i in range(8):
        z = 0.35 + i * 0.5
        t = z / (zp + 0.15)
        y = -1.32 + 0.18 * t
        K.beam(p, (0.15, y - 0.02, z), (0.75, y - 0.02, z), 0.06, 0.06, S('wood_light', 0.85), 'board_b', 0.008)
    # flag pole + flag
    K.cyl_between(p, (-0.95, -0.95, zp + 0.1), (-0.95, -0.95, zr1 + 0.9), 0.035, post, 6)
    K.sag_sheet(p, (-0.93, -0.95, zr1 + 0.88), (-0.35, -0.95, zr1 + 0.84), (-0.93, -0.95, zr1 + 0.5), (-0.35, -0.95, zr1 + 0.52), 3, 2, 0.04, 0.015,
                S('paint_red', 0.9), 'plain', seed)
    return p


def build_billboard(seed):
    r = random.Random(seed)
    p = L.Part()
    post = S('wood_dark', 1.0)
    for x in (-2.2, 2.2):
        K.beam(p, (x, 0.05, -0.1), (x, 0.05, 5.65), 0.26, 0.26, post, 'board_b', 0.03, up=(1, 0, 0))
        K.beam(p, (x, 0.05, 2.0), (x, 0.9, -0.05), 0.12, 0.14, post, 'board_b', 0.015)
        K.box(p, (0.5, 0.5, 0.25), Matrix.Translation((x, 0.05, 0.08)), S('concrete', 0.85), 'concrete', 0.04)
    K.beam(p, (-2.2, 0.15, 3.0), (2.2, 0.15, 3.0), 0.1, 0.12, post, 'board_b', 0.012)
    K.beam(p, (-2.2, 0.17, 3.15), (2.2, 0.17, 5.5), 0.06, 0.1, post, 'board_b', 0.01)
    # sign: steel frame + board face (keeps the v10 colour layout)
    K.box(p, (6.0, 0.16, 2.6), Matrix.Translation((0, 0, 4.4)), S('paint_cream', 0.85), 'board_b', 0.03, wear=S('wood'))
    K.box(p, (5.4, 0.04, 2.0), Matrix.Translation((0, -0.09, 4.4)), (0.36, 0.12, 0.07, 1, 0.3, 0.1), 'panel', 0.0)
    K.box(p, (2.2, 0.03, 0.3), Matrix.Translation((1.2, -0.12, 4.0)), S('paint_cream', 1.05), 'panel', 0.0)
    K.box(p, (1.6, 0.03, 0.4), Matrix.Translation((-1.2, -0.12, 4.6)), S('paint_cream', 1.05), 'panel', 0.0)
    for (a, b) in (((-3.0, 3.1), (3.0, 3.1)), ((-3.0, 5.7), (3.0, 5.7)), ((-3.0, 3.1), (-3.0, 5.7)), ((3.0, 3.1), (3.0, 5.7))):
        K.beam(p, (a[0], -0.02, a[1]), (b[0], -0.02, b[1]), 0.1, 0.22, S('steel_dark', 1.3), 'plain', 0.012, up=(0, -1, 0), ext=0.1)
    # torn corner + rust drip, two lamps on arms
    K.box(p, (0.7, 0.05, 0.5), Matrix.Translation((2.55, -0.08, 5.25)) @ Matrix.Rotation(0.3, 4, 'Y'), S('rust_light'), 'rustplate', 0.0)
    for x in (-1.6, 1.6):
        K.beam(p, (x, -0.05, 5.75), (x, -0.75, 6.0), 0.05, 0.05, S('steel_dark', 1.2), 'plain', 0.0)
        K.box(p, (0.4, 0.2, 0.1), Matrix.Translation((x, -0.8, 5.97)) @ Matrix.Rotation(-0.35, 4, 'X'), S('steel_dark', 1.3), 'plain', 0.02)
    return p


# ------------------------------------------------------------------------------------------------
# Palisades: stakes keep positions; varied height/thickness/lean; rails kept
# ------------------------------------------------------------------------------------------------
def rebuild_palisade(ob, ctx, seed):
    me = ob.data
    comps = L.mesh_components(me, weld=0.002)
    r = random.Random(seed)
    acc = L.MeshAccumulator()
    nst = 0
    for pts, vc in comps:
        ext = pts.max(0) - pts.min(0)
        p = L.Part()
        c = (pts.max(0) + pts.min(0)) / 2
        if ext[2] > 1.4 and max(ext[0], ext[1]) < 1.0:     # stake
            zb = pts[:, 2].min(); zt = pts[:, 2].max()
            # stake axis from base centroid to tip
            base = pts[pts[:, 2] < zb + 0.3].mean(0); tip = pts[pts[:, 2] > zt - 0.05].mean(0)
            h = (zt - zb) * r.uniform(0.9, 1.1)
            rad = max(0.11, min(ext[0], ext[1]) * 0.42) * r.uniform(0.85, 1.18)
            lean = Vector((tip[0] - base[0], tip[1] - base[1], 0)) + Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), 0))
            top = Vector((base[0], base[1], zb)) + Vector((0, 0, h)) + lean * 0.8
            b0 = Vector((base[0], base[1], zb - 0.15))
            segs = 6
            col = (0.37 * r.uniform(0.75, 1.15), 0.15 * r.uniform(0.8, 1.15), 0.05 * r.uniform(0.8, 1.2), 1.0, 0.06, 0.0)
            shaft_top = b0.lerp(top, 0.86)
            K.cyl_between(p, b0, shaft_top, rad, col, segs, 'board_a', m_per_u=1.5)
            # sharpened point: lighter fresh-cut wood
            K.cyl_between(p, shaft_top, top, rad, (0.55, 0.36, 0.2, 1, 0.08, 0), segs, 'board_a', r2=0.015, m_per_u=1.0)
            if r.random() < 0.35:   # rope lashing
                zl = b0.lerp(top, 0.7)
                K.cyl_between(p, zl - Vector((0, 0, 0.06)), zl + Vector((0, 0, 0.06)), rad * 1.08, S('canvas_dark', 0.7), segs)
            nst += 1
        elif ext[2] < 0.4 and max(ext[0], ext[1]) > 1.0:  # rail
            d = pts[:, :2] - c[:2]
            w, v = np.linalg.eigh(d.T @ d)
            ax = v[:, 1]
            proj = d @ ax
            a = Vector((c[0] + ax[0] * proj.min(), c[1] + ax[1] * proj.min(), c[2])); b = Vector((c[0] + ax[0] * proj.max(), c[1] + ax[1] * proj.max(), c[2]))
            K.beam(p, a, b, 0.11, 0.12, S('wood_dark', 1.0), 'board_b', 0.02, ext=0.05)
        else:
            p.free(); continue
        acc.add_part(p); p.free()
    users = finish_mesh(acc, me, ctx, f'v11: {nst} stakes rebuilt (6-sided, varied height/thickness/lean, positions & gaps kept)')
    return nst


# ------------------------------------------------------------------------------------------------
# Unique structures augmented in place (garage, gate, repair pad)
# ------------------------------------------------------------------------------------------------
def augment(ob, ctx, build_fn, note, recolor=None, roof=False):
    me = ob.data
    keep = np.ones(len(me.vertices), bool)
    arr = original_arrays(me, keep)
    if recolor:
        arr = recolor(arr)
    acc = L.MeshAccumulator()
    acc.add(with_mat(arr, 0))
    p = L.Part(); build_fn(p, arr)
    acc.add(with_mat(p.arrays(), 1)); p.free()
    mats = [ob.material_slots[0].material, ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me, new, note=note)
    for o in users:
        L.set_object_materials(o, mats)


def wall_frame(arr):
    """Long axis of the main wall box in an augmented mesh (world-space garage walls)."""
    co = arr['co']
    c = co.mean(0)
    d = co[:, :2] - c[:2]
    w, v = np.linalg.eigh(d.T @ d)
    ax = Vector((v[0, 1], v[1, 1], 0)).normalized()
    proj = d @ np.array(ax[:2])
    side = Vector((-ax.y, ax.x, 0))
    sp = d @ np.array(side[:2])
    return Vector((c[0], c[1], 0)), ax, side, proj.min(), proj.max(), sp.min(), sp.max(), co[:, 2].max()


def garage_wall_details(p, arr):
    """Garage is a drive-through: details only on the OUTER face and on top; the lane side stays flush."""
    c, ax, side, a0, a1, s0, s1, ztop = wall_frame(arr)
    gc = Vector((-47.5, -38.9, 0))                       # garage floor centre (lane)
    out = side if (c - gc).dot(side) > 0 else -side       # outward normal of this wall
    L0 = c + ax * (a0 + 0.6); L1 = c + ax * (a1 - 0.6)
    yaw = math.atan2(ax.y, ax.x)
    K.beam(p, L0 + Vector((0, 0, 3.62)), L1 + Vector((0, 0, 3.62)), 0.75, 0.16, S('steel_dark', 1.2), 'panel', 0.02, ext=0.4)
    K.beam(p, L0 + out * 0.3 + Vector((0, 0, 0.18)), L1 + out * 0.3 + Vector((0, 0, 0.18)), 0.3, 0.36, S('concrete', 0.8), 'concrete', 0.03)
    n = int((a1 - a0) / 2.6)
    for i in range(n + 1):
        q = c + ax * (a0 + 0.9 + i * (a1 - a0 - 1.8) / max(n, 1))
        o = q + out * 0.29
        K.box(p, (0.2, 0.08, 3.2), Matrix.Translation(o + Vector((0, 0, 1.9))) @ Matrix.Rotation(yaw, 4, 'Z'), S('steel', 0.7), 'panel', 0.01)
        for z in (0.9, 2.9):
            K.bolt(p, o + out * 0.04 + Vector((0, 0, z)), out, 0.035, S('steel', 0.9), 0.03)


def garage_roof_details(p, arr):
    co = arr['co']
    c = co.mean(0)
    d = co[:, :2] - c[:2]
    w, v = np.linalg.eigh(d.T @ d)
    ax = Vector((v[0, 1], v[1, 1], 0)).normalized(); side = Vector((-ax.y, ax.x, 0))
    pa = d @ np.array(ax[:2]); ps = d @ np.array(side[:2])
    a0, a1, s0, s1 = pa.min(), pa.max(), ps.min(), ps.max()
    z = co[:, 2].max()
    C = Vector((c[0], c[1], 0))
    yaw = math.atan2(ax.y, ax.x)
    # perimeter C-channel fascia (gives the slab a visible thickness and edge)
    for (u0, v0_, u1, v1_) in ((a0, s0, a1, s0), (a0, s1, a1, s1), (a0, s0, a0, s1), (a1, s0, a1, s1)):
        A = C + ax * u0 + side * v0_; B = C + ax * u1 + side * v1_
        K.beam(p, A + Vector((0, 0, z - 0.16)), B + Vector((0, 0, z - 0.16)), 0.14, 0.42, S('steel_dark', 1.25), 'panel', 0.02, ext=0.14)
    # gutter + downpipes on one long side
    A = C + ax * a0 + side * (s0 - 0.12); B = C + ax * a1 + side * (s0 - 0.12)
    K.beam(p, A + Vector((0, 0, z - 0.3)), B + Vector((0, 0, z - 0.3)), 0.16, 0.14, S('galvanized', 0.8), 'plain', 0.03)
    for t in (0.08, 0.92):
        q = A.lerp(B, t)
        K.cyl_between(p, q + Vector((0, 0, 0.1)), q + Vector((0, 0, z - 0.3)), 0.06, S('galvanized', 0.8), 8)
    # roof vents and a water tank on the roof (part of the roof object -> fades with it in Unity)
    for (u, v) in ((0.3, 0.25), (0.72, 0.7)):
        q = C + ax * (a0 + (a1 - a0) * u) + side * (s0 + (s1 - s0) * v)
        K.box(p, (0.9, 0.9, 0.35), Matrix.Translation(q + Vector((0, 0, z + 0.2))) @ Matrix.Rotation(yaw, 4, 'Z'), S('galvanized', 0.85), 'panel', 0.03)
        K.cyl_between(p, q + Vector((0, 0, z + 0.37)), q + Vector((0, 0, z + 0.55)), 0.32, S('steel_dark', 1.2), 12)
    q = C + ax * (a0 + (a1 - a0) * 0.86) + side * (s0 + (s1 - s0) * 0.22)
    for (dx, dy) in ((-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)):
        o = q + ax * dx + side * dy
        K.beam(p, o + Vector((0, 0, z)), o + Vector((0, 0, z + 0.55)), 0.08, 0.08, S('steel_dark', 1.2), 'plain', 0.0)
    K.cyl_between(p, q + Vector((0, 0, z + 0.55)), q + Vector((0, 0, z + 1.55)), 0.62, S('paint_teal', 0.9), 16, bevel=0.04)


def recolor_roof_sheets(arr):
    """GarageRoof: give the flat stripe sheets the corrugated trim (UV) — slot stays Toon (v10 material);
    corrugation therefore lives in geometry of the new fascia only. Colours slightly weathered."""
    col = arr['col'].copy()
    col[:, :3] *= 0.97
    arr = dict(arr); arr['col'] = col
    return arr


def gate_details(p, arr):
    # local mesh coords: towers at x = +-7.2 (3.6 box, top cap 4.4 at z 5.2-5.8), front = -Y
    for sx in (-1, 1):
        cx = sx * 7.2
        # corner posts and horizontal scrap-board bands on the tower faces
        for (dx, dy) in ((-1.85, -1.85), (1.85, -1.85), (-1.85, 1.85), (1.85, 1.85)):
            K.beam(p, (cx + dx, dy, -0.05), (cx + dx, dy, 5.25), 0.24, 0.24, S('wood_dark', 1.0), 'board_b', 0.03, up=(1, 0, 0))
        for z in (0.9, 2.1, 4.4):
            for (a, b) in (((-1.86, -1.86), (1.86, -1.86)), ((1.86, -1.86), (1.86, 1.86)), ((1.86, 1.86), (-1.86, 1.86)), ((-1.86, 1.86), (-1.86, -1.86))):
                K.beam(p, (cx + a[0], a[1], z), (cx + b[0], b[1], z), 0.06, 0.26, S('wood', 0.9), 'board_a', 0.01, ext=0.1)
        # bolted scrap plates
        K.box(p, (1.4, 0.05, 1.0), Matrix.Translation((cx + 0.6 * sx, -1.88, 1.4)) @ Matrix.Rotation(0.06 * sx, 4, 'Y'), S('rust_light', 1.0), 'rustplate', 0.01)
        for (dx, dz) in ((-0.6, -0.42), (0.6, -0.42), (-0.6, 0.42), (0.6, 0.42)):
            K.bolt(p, (cx + 0.6 * sx + dx, -1.92, 1.4 + dz), (0, -1, 0), 0.04, S('steel', 0.9), 0.04)
        # parapet planks on top cap
        for (a, b) in (((-2.15, -2.15), (2.15, -2.15)), ((2.15, -2.15), (2.15, 2.15)), ((2.15, 2.15), (-2.15, 2.15)), ((-2.15, 2.15), (-2.15, -2.15))):
            K.board(p, (cx + a[0], a[1], 6.0), (cx + b[0], b[1], 6.0), 0.4, 0.06, S('wood_dark', 1.1), 'board_b', up=(0, 0, 1))
        # sandbags at the base (outside the road opening x in [-5.4, 5.4])
        for i in range(4):
            K.box(p, (0.55, 0.32, 0.22), Matrix.Translation((cx + sx * (2.1 + 0.05 * i), -1.0 + i * 0.6, 0.11 + (i % 2) * 0.0)), S('canvas_dark', 1.05), 'plain', 0.08)


def run(ctx):
    st = {}
    # families (shared meshes; keep instancing)
    for k in range(3):
        me = bpy.data.meshes.get(f'Shack_{k}_0')
        if me:
            acc = L.MeshAccumulator(); p = build_shack(k, 300 + k); acc.add_part(p); p.free()
            finish_mesh(acc, me, ctx, f'v11: shack variant {k} rebuilt (board/metal cladding, gable corrugated roof, frames, patches)')
    for k in range(3):
        me = bpy.data.meshes.get(f'Tent_{k}_0')
        if me:
            comps = L.mesh_components(me, weld=0.002)
            pts = max(comps, key=lambda c: float(np.prod(np.maximum(c[0].max(0) - c[0].min(0), 0.05))))[0]
            ext = pts.max(0) - pts.min(0)
            acc = L.MeshAccumulator(); p = build_tent(k, 400 + k, ext[0], ext[1], ext[2]); acc.add_part(p); p.free()
            finish_mesh(acc, me, ctx, f'v11: tent variant {k} rebuilt (sagging canvas, poles, guy ropes, patches)')
    for k in range(3):
        me = bpy.data.meshes.get(f'Tower_{k}_0')
        if me:
            co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
            ext = co.max(0) - co.min(0)
            sxy = ext[0] / 2.9; sz = ext[2] / 7.6
            acc = L.MeshAccumulator(); p = build_tower(500 + k)
            acc.add(p.arrays(), Matrix.Diagonal((sxy, sxy, sz, 1.0))); p.free()
            finish_mesh(acc, me, ctx, f'v11: watch tower variant {k} rebuilt (braced legs, plank deck, railing, hip roof, ladder)')
    me = bpy.data.meshes.get('billboard_0')
    if me:
        acc = L.MeshAccumulator(); p = build_billboard(600); acc.add_part(p); p.free()
        finish_mesh(acc, me, ctx, 'v11: billboard rebuilt (posts, braces, frame, lamps)')
    st['stakes'] = 0
    for i, nm in enumerate(('Palisade', 'Palisade.001', 'Palisade.002')):
        ob = bpy.data.objects.get(nm)
        if ob:
            st['stakes'] += rebuild_palisade(ob, ctx, 700 + i)
    for nm in ('GarageWallN', 'GarageWallS'):
        ob = bpy.data.objects.get(nm)
        if ob:
            augment(ob, ctx, garage_wall_details, 'v11: garage wall + steel cap, concrete footing, ribs, bolts')
    ob = bpy.data.objects.get('GarageRoof')
    if ob:
        augment(ob, ctx, garage_roof_details, 'v11: garage roof + fascia channel, gutter, vents, water tank (still the fading roof object)',
                recolor=recolor_roof_sheets)
    ob = bpy.data.objects.get('GateTowers')
    if ob:
        augment(ob, ctx, gate_details, 'v11: gate towers + posts, board bands, scrap plates, parapet, sandbags')
    ctx['stats']['structures'] = st
    print('STEP structures done', st, flush=True)
