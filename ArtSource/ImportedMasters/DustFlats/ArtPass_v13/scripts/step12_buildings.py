"""v12 step: building silhouettes. Shack family gets three distinct designs (same footprint & door side):
  0 'porch'   gable roof with deep eaves, front porch canopy on posts, side lean-to shed, stove pipe, steps
  1 'quonset' barrel-vault corrugated roof, round end gables, door hood, AC box, vent turbine
  2 'tall'    taller two-storey shack, mono-pitch roof with overhanging front eave, water tank on stilts, sign
Watch towers: flared two-pitch hip roof with brackets and finial, rounded posts. Garage roof object: barrel
vault (open drive-through ends, arch ribs, gutters), emblem kept on the crown. Gate towers: hip-roofed lookouts.
Mammoth Works: entrance truss arch over the ramp mouth and three round stair towers at the hangar corners."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays
from step_structures import with_mat, finish_mesh, crate
from step12_ramps import split_arrays, face_comp_ids, sweep, rounded_rect


def S(kind, k=1.0):
    return L.surf(kind, k)


def vault(p, origin, axis, across, L_, span, rise, thick, col, segs=16, step=1.2, strip='corrugated', m_per_u=1.0):
    """Barrel vault surface (slab of thickness 'thick'); axis = length direction, across = span direction."""
    o = Vector(origin); ax = Vector(axis).normalized(); ac = Vector(across).normalized(); up = Vector((0, 0, 1))
    R_ = (span * span / 4 + rise * rise) / (2 * rise); a0 = math.asin((span / 2) / R_)
    nl = max(2, int(L_ / step))
    bm = p.bm; top = []; bot = []
    for i in range(nl + 1):
        t = -L_ / 2 + L_ * i / nl
        rt = []; rb = []
        for j in range(segs + 1):
            a = -a0 + 2 * a0 * j / segs
            for (lst, rr) in ((rt, R_), (rb, R_ - thick)):
                q = o + ax * t + ac * (math.sin(a) * rr) + up * (math.cos(a) * rr - (R_ - rise))
                lst.append(bm.verts.new(q))
        top.append(rt); bot.append(rb)
    faces = []
    for i in range(nl):
        for j in range(segs):
            faces.append(bm.faces.new([top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]]))
            faces.append(bm.faces.new([bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]]))
    for i in range(nl):
        for j in (0, segs):
            try: faces.append(bm.faces.new([top[i][j], top[i + 1][j], bot[i + 1][j], bot[i][j]]))
            except ValueError: pass
    for i in (0, nl):
        for j in range(segs):
            try: faces.append(bm.faces.new([top[i][j], bot[i][j], bot[i][j + 1], top[i][j + 1]]))
            except ValueError: pass
    bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=faces)
    p.paint(faces, col)
    v0, v1 = K._strip(strip); p.uv_trim(faces, v0, v1, m_per_u, auto=strip not in K.ANISO)
    return R_, a0


def arch_rib(p, origin, ac, span, rise, r_off, col, w=0.14, h=0.16, segs=12):
    o = Vector(origin); ac = Vector(ac).normalized(); up = Vector((0, 0, 1))
    R_ = (span * span / 4 + rise * rise) / (2 * rise); a0 = math.asin((span / 2) / R_)
    pts = [o + ac * (math.sin(a) * (R_ - r_off)) + up * (math.cos(a) * (R_ - r_off) - (R_ - rise)) for a in np.linspace(-a0, a0, segs + 1)]
    for a, b in zip(pts[:-1], pts[1:]):
        K.beam(p, a, b, w, h, col, 'plain', 0.01, up=tuple(ac.cross(Vector((0, 0, 1)))), ext=0.04)


# ------------------------------------------------------------------------------------------------
# Shacks (footprint 3.2 x 2.8, door on -Y, crate at (-1.9, -0.6))
# ------------------------------------------------------------------------------------------------
def shack_common(p, r, W, D, H, wall_s, metal=False, door=(-0.2, 0.7), plinth_h=0.2):
    # rounded plinth
    K.box(p, (W + 0.3, D + 0.3, plinth_h), Matrix.Translation((0, 0, plinth_h / 2 - 0.04)), S('concrete', 0.9), 'concrete', 0.06, wear=S('concrete', 1.12))
    K.box(p, (W - 0.06, D - 0.06, H), Matrix.Translation((0, 0, plinth_h + H / 2)), wall_s, 'corrugated' if metal else 'board_a', 0.05)
    # corner posts with chamfers
    for (x, y) in ((-W / 2, -D / 2), (W / 2, -D / 2), (-W / 2, D / 2), (W / 2, D / 2)):
        K.beam(p, (x, y, 0.1), (x, y, plinth_h + H + 0.1), 0.18, 0.18, S('wood_dark', 1.05), 'board_b', 0.04, up=(1, 0, 0))
    # door frame, leaf, step
    x0, x1 = door; yf = -D / 2 - 0.06; z0 = plinth_h; z1 = plinth_h + 1.85
    for xx in (x0 - 0.06, x1 + 0.06):
        K.beam(p, (xx, yf, z0), (xx, yf, z1 + 0.12), 0.12, 0.12, S('wood_dark', 1.1), 'board_b', 0.025, up=(1, 0, 0))
    K.beam(p, (x0 - 0.18, yf, z1 + 0.08), (x1 + 0.18, yf, z1 + 0.08), 0.16, 0.14, S('wood_dark', 1.1), 'board_b', 0.03)
    for i in range(4):
        xa = x0 + (x1 - x0) * (i + 0.5) / 4
        K.board(p, (xa, yf + 0.03, z0 + 0.02), (xa, yf + 0.03, z1 - 0.02), (x1 - x0) / 4 - 0.015, 0.04, S('wood', 0.7 * r.uniform(0.9, 1.1)), 'board_b', up=(1, 0, 0))
    K.box(p, (0.05, 0.06, 0.22), Matrix.Translation((x1 - 0.12, yf - 0.05, z0 + 0.95)), S('steel', 0.8), 'plain', 0.012)
    # entry steps (wood) with rounded nosing
    for k, (dy, h) in enumerate(((0.35, plinth_h * 0.55), (0.7, plinth_h * 0.1))):
        K.box(p, (x1 - x0 + 0.5, 0.36, h + 0.06), Matrix.Translation(((x0 + x1) / 2, -D / 2 - dy, (h + 0.06) / 2 - 0.04)), S('wood_grey', 0.95), 'board_a', 0.03)


def shack_porch(r):
    p = L.Part(); W, D, H = 3.2, 2.8, 2.35
    wall = S('wood_grey', 0.95)
    shack_common(p, r, W, D, H, wall)
    zt = 0.2 + H
    # gable roof (ridge along X) with deep eaves, thick fascia, ridge cap
    pitch = math.radians(27); ov = 0.45; RX = W / 2 + 0.4; ry = D / 2 + ov
    zr = zt + (D / 2) * math.tan(pitch) + 0.05; ze = zr - ry * math.tan(pitch)
    roof = (0.46, 0.12, 0.045, 1.0, 0.42, 0.2)
    for sgn in (-1, 1):
        K.sheet(p, (-RX, 0, zr + 0.04), (2 * RX, 0, 0), (0, sgn * ry, ze - zr), 0.07, roof, 'corrugated', m_per_u=1.0)
        K.beam(p, (-RX, sgn * ry, ze - 0.02), (RX, sgn * ry, ze - 0.02), 0.08, 0.2, S('wood_dark', 1.1), 'board_b', 0.03, ext=0.1)
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.03)
        K.prism(p, [(-D / 2, zt), (D / 2, zt), (0, zr - 0.02)], -0.04, 0.04, Matrix.Translation((x, 0, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))), wall, 'board_a')
        for sgn in (-1, 1):
            K.beam(p, (sx * (RX + 0.03), 0, zr + 0.08), (sx * (RX + 0.03), sgn * (ry + 0.03), ze + 0.08), 0.07, 0.2, S('wood_dark', 1.1), 'board_b', 0.025, up=(0, -sgn * math.sin(pitch), math.cos(pitch)), ext=0.12)
    K.cyl_between(p, (-RX - 0.05, 0, zr + 0.1), (RX + 0.05, 0, zr + 0.1), 0.09, S('galvanized', 0.85), 10)
    # front porch canopy on two rounded posts
    cy0 = -D / 2 - 0.05; cy1 = -D / 2 - 1.45; zc0 = zt - 0.05; zc1 = zt - 0.38
    K.sheet(p, (-1.25, cy0, zc0), (2.5, 0, 0), (0, cy1 - cy0, zc1 - zc0), 0.06, (0.58, 0.20, 0.06, 1, 0.45, 0.2), 'corrugated', 1.0)
    for x in (-1.1, 1.1):
        K.cyl_between(p, (x, cy1 + 0.15, 0.0), (x, cy1 + 0.15, zc1 - 0.02), 0.07, S('wood_dark', 1.05), 10)
        K.beam(p, (x, cy1 + 0.15, zc1 - 0.35), (x, cy0, zc0 - 0.45), 0.07, 0.07, S('wood_dark', 1.05), 'board_b', 0.01)
    K.beam(p, (-1.25, cy1 + 0.12, zc1 - 0.06), (1.25, cy1 + 0.12, zc1 - 0.06), 0.12, 0.14, S('wood_dark', 1.05), 'board_b', 0.025)
    # side lean-to shed on +X
    sx0 = W / 2; sx1 = W / 2 + 1.3
    K.box(p, (1.2, 1.9, 1.5), Matrix.Translation(((sx0 + sx1) / 2, 0.2, 0.75)), S('wood', 0.8), 'board_b', 0.04)
    K.sheet(p, (sx0, -0.85, 1.85), (1.5, 0, -0.45), (0, 2.1, 0), 0.05, S('rust_light', 1.0), 'corrugated', 1.0)
    # window with shutter, stove pipe with hat
    K.box(p, (0.65, 0.05, 0.55), Matrix.Translation((-0.85, -D / 2 - 0.02, 1.55)), S('glass', 0.6), 'plain')
    K.box(p, (0.36, 0.035, 0.6), Matrix.Translation((-1.35, -D / 2 - 0.12, 1.55)) @ Matrix.Rotation(-0.6, 4, 'Z'), (0.08, 0.30, 0.31, 1, 0.5, 0.15), 'panel', 0.01)
    K.cyl_between(p, (1.0, 0.85, zr - 0.6), (1.0, 0.85, zr + 0.9), 0.1, S('steel_dark', 1.4), 12)
    K.cyl_between(p, (1.0, 0.85, zr + 0.85), (1.0, 0.85, zr + 1.05), 0.2, S('steel_dark', 1.2), 12, r2=0.03)
    crate(p, Vector((-1.95, -0.65, 0)), (0.7, 0.7, 0.82), r, yaw=0.15)
    return p


def shack_quonset(r):
    p = L.Part(); W, D, H = 3.2, 2.8, 1.25
    wall = (0.20, 0.25, 0.28, 1.0, 0.42, 0.18)
    K.box(p, (W + 0.3, D + 0.3, 0.22), Matrix.Translation((0, 0, 0.07)), S('concrete', 0.9), 'concrete', 0.06)
    # low side walls + barrel roof spanning the depth (axis along X)
    K.box(p, (W, D - 0.04, H), Matrix.Translation((0, 0, 0.18 + H / 2)), wall, 'corrugated', 0.04)
    vault(p, (0, 0, 0.18 + H), (1, 0, 0), (0, 1, 0), W + 0.5, D + 0.25, 1.35, 0.06, (0.32, 0.34, 0.36, 1.0, 0.45, 0.55), 18, 0.6, 'corrugated', 1.0)
    for x in (-W / 2 - 0.2, -W / 4, W / 4, W / 2 + 0.2):
        arch_rib(p, (x, 0, 0.18 + H + 0.02), (0, 1, 0), D + 0.25, 1.35, -0.03, S('steel_dark', 1.2), 0.09, 0.07, 12)
    # end gables (closed half-discs) with the door on the -Y wall below the vault
    for sx in (-1, 1):
        R_ = ((D + 0.25) ** 2 / 4 + 1.35 ** 2) / (2 * 1.35); a0 = math.asin(((D + 0.25) / 2) / R_)
        pts = [((math.sin(a) * (R_ - 0.08)), (math.cos(a) * (R_ - 0.08) - (R_ - 1.35))) for a in np.linspace(-a0, a0, 14)]
        K.prism(p, [(y, 0.0) for y, _ in pts[:1]] + pts + [(pts[-1][0], 0.0)], -0.03, 0.03,
                Matrix.Translation((sx * (W / 2 + 0.05), 0, 0.18 + H)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))), wall, 'corrugated')
    # door with a curved hood on the front (-Y) wall
    x0, x1 = -0.2, 0.7; yf = -D / 2 - 0.04
    K.box(p, (x1 - x0, 0.05, 1.25), Matrix.Translation(((x0 + x1) / 2, yf, 0.18 + 0.625)), (0.55, 0.10, 0.04, 1, 0.5, 0.15), 'panel', 0.02, wear=S('steel'))
    vault(p, ((x0 + x1) / 2, yf - 0.3, 0.18 + H + 0.05), (1, 0, 0), (0, 1, 0), 1.4, 0.7, 0.25, 0.04, S('galvanized', 0.9), 8, 0.7, 'plain')
    # AC box, vent turbine, gas bottles
    K.box(p, (0.8, 0.5, 0.6), Matrix.Translation((W / 2 + 0.35, 0.6, 0.55)), S('paint_cream', 0.85), 'panel', 0.05, wear=S('rust_light'))
    K.cyl_between(p, (W / 2 + 0.35, 0.6 - 0.26, 0.6), (W / 2 + 0.35, 0.6 - 0.27, 0.6), 0.2, S('steel_dark', 1.3), 14)
    K.cyl_between(p, (0.9, 0.0, 0.18 + H + 1.3), (0.9, 0.0, 0.18 + H + 1.75), 0.12, S('galvanized', 0.85), 12)
    K.cyl_between(p, (0.9, 0.0, 0.18 + H + 1.75), (0.9, 0.0, 0.18 + H + 2.0), 0.22, S('galvanized', 0.8), 14, r2=0.1)
    for k in range(2):
        K.cyl_between(p, (-W / 2 - 0.3, -0.5 + k * 0.4, 0.0), (-W / 2 - 0.3, -0.5 + k * 0.4, 0.9), 0.14, (0.75, 0.15, 0.08, 1, 0.5, 0.15), 14, bevel=0.04)
    crate(p, Vector((-1.95, 0.6, 0)), (0.7, 0.7, 0.82), r, yaw=-0.2)
    return p


def shack_tall(r):
    p = L.Part(); W, D, H = 3.0, 2.6, 3.3
    wall = S('wood', 0.75)
    shack_common(p, r, W, D, H, wall)
    zt = 0.2 + H
    # mono-pitch roof falling to the back, overhanging front eave with brackets
    zf = zt + 0.75; zb = zt + 0.05; ov_f = 0.8; ov_b = 0.35
    K.sheet(p, (-W / 2 - 0.35, -D / 2 - ov_f, zf + 0.06), (W + 0.7, 0, 0), (0, D + ov_f + ov_b, zb - zf), 0.08, (0.44, 0.12, 0.045, 1, 0.42, 0.2), 'corrugated', 1.0)
    K.beam(p, (-W / 2 - 0.35, -D / 2 - ov_f, zf - 0.03), (W / 2 + 0.35, -D / 2 - ov_f, zf - 0.03), 0.1, 0.24, S('wood_dark', 1.1), 'board_b', 0.03)
    for sx in (-1, 1):
        K.prism(p, [(-D / 2, zt), (D / 2, zt), (D / 2, zb), (-D / 2, zf)], -0.04, 0.04,
                Matrix.Translation((sx * (W / 2 + 0.03), 0, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))), wall, 'board_a')
    for x in (-1.0, 0.0, 1.0):
        K.beam(p, (x, -D / 2, zf - 0.6), (x, -D / 2 - ov_f + 0.1, zf - 0.08), 0.08, 0.1, S('wood_dark', 1.1), 'board_b', 0.012)
    # first-floor band and windows
    K.beam(p, (-W / 2 - 0.02, -D / 2 - 0.05, 2.15), (W / 2 + 0.02, -D / 2 - 0.05, 2.15), 0.18, 0.1, S('wood_dark', 1.2), 'board_b', 0.02)
    for x in (-0.85, 0.85):
        K.box(p, (0.6, 0.05, 0.6), Matrix.Translation((x, -D / 2 - 0.02, 2.85)), S('glass', 0.6), 'plain')
        K.box(p, (0.72, 0.06, 0.08), Matrix.Translation((x, -D / 2 - 0.06, 2.52)), S('wood_dark', 1.2), 'board_b', 0.01)
    # sign board above the door
    K.box(p, (1.6, 0.06, 0.4), Matrix.Translation((0.25, -D / 2 - 0.1, 2.45 - 0.35)), S('paint_cream', 0.95), 'board_b', 0.015, wear=S('wood'))
    # water tank on stilts at the back-left
    tx, ty = -W / 2 - 0.55, D / 2 - 0.2
    for (dx, dy) in ((-0.35, -0.35), (0.35, -0.35), (-0.35, 0.35), (0.35, 0.35)):
        K.beam(p, (tx + dx, ty + dy, 0.0), (tx + dx * 0.8, ty + dy * 0.8, 2.2), 0.09, 0.09, S('wood_dark', 1.1), 'board_b', 0.012)
    K.cyl_between(p, (tx, ty, 2.2), (tx, ty, 3.1), 0.55, S('paint_teal', 0.85), 18, bevel=0.05)
    for z in (2.35, 2.95):
        K.cyl_between(p, (tx, ty, z - 0.02), (tx, ty, z + 0.02), 0.57, S('steel_dark', 1.2), 18)
    K.cyl_between(p, (tx, ty, 3.1), (tx, ty, 3.4), 0.56, S('paint_teal', 0.8), 18, r2=0.1)
    # chimney pipe
    K.cyl_between(p, (1.0, 0.7, zt), (1.0, 0.7, zf + 0.9), 0.11, S('steel_dark', 1.4), 12)
    K.cyl_between(p, (1.0, 0.7, zf + 0.85), (1.0, 0.7, zf + 1.05), 0.22, S('steel_dark', 1.2), 12, r2=0.03)
    crate(p, Vector((-1.9, -0.7, 0)), (0.7, 0.7, 0.82), r, yaw=0.05)
    return p


# ------------------------------------------------------------------------------------------------
def tower_roof(p, zr0, R0, rise, col):
    """Flared two-pitch hip roof (bell-cast) over a square of half size R0 at height zr0."""
    bm = p.bm
    levels = [(R0 * 1.18, zr0 - 0.12), (R0 * 0.92, zr0 + rise * 0.25), (R0 * 0.32, zr0 + rise * 0.82), (0.0, zr0 + rise)]
    rings = []
    for (rr, z) in levels:
        if rr == 0:
            rings.append([bm.verts.new((0, 0, z))]); continue
        rings.append([bm.verts.new((sx * rr, sy * rr, z)) for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            k = (j + 1) % 4
            if len(b) == 1:
                faces.append(bm.faces.new([a[j], a[k], b[0]]))
            else:
                faces.append(bm.faces.new([a[j], a[k], b[k], b[j]]))
    faces.append(bm.faces.new(rings[0][::-1]))
    bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=faces)
    p.paint(faces, col); v0, v1 = K._strip('corrugated'); p.uv_trim(faces, v0, v1, 0.8)
    # hip cappings
    for j in range(4):
        pts = [rings[i][j].co.copy() if len(rings[i]) > 1 else rings[i][0].co.copy() for i in range(len(rings))]
        for a, b in zip(pts[:-1], pts[1:]):
            K.beam(p, a + Vector((0, 0, 0.05)), b + Vector((0, 0, 0.05)), 0.09, 0.07, S('galvanized', 0.8), 'plain', 0.0, ext=0.05)
    K.cyl_between(p, (0, 0, zr0 + rise), (0, 0, zr0 + rise + 0.45), 0.05, S('steel_dark', 1.2), 8)
    K.cyl_between(p, (0, 0, zr0 + rise + 0.4), (0, 0, zr0 + rise + 0.55), 0.11, (0.85, 0.15, 0.06, 1, 0.5, 0.15), 10, r2=0.02)


def rebuild_towers(ctx):
    from step_structures import build_tower
    for k in range(3):
        me = bpy.data.meshes.get(f'Tower_{k}_0')
        if me is None:
            continue
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        # v11 tower is in the scaled frame already: rebuild from the v11 builder, swapping the roof
        ext = co.max(0) - co.min(0)
        p = build_tower(500 + k)
        # drop the old pyramid roof (faces above the roof posts' top) and add the flared roof
        bm = p.bm; zp = 4.1
        old = [f for f in bm.faces if min(v.co.z for v in f.verts) > zp + 1.55 and max(abs(v.co.x) for v in f.verts) > 0.05]
        bmesh.ops.delete(bm, geom=old, context='FACES')
        tower_roof(p, zp + 1.62, 1.18, 1.25, (0.44, 0.12, 0.045, 1.0, 0.42, 0.2))
        # corner brackets under the eaves
        for sx in (-1, 1):
            for sy in (-1, 1):
                K.beam(p, (sx * 1.05, sy * 1.05, zp + 1.25), (sx * 1.3, sy * 1.3, zp + 1.55), 0.07, 0.07, S('wood_dark', 1.1), 'board_b', 0.01)
        sxy = ext[0] / 2.76 if ext[0] > 1 else 1.0; sz = ext[2] / 7.5 if ext[2] > 1 else 1.0
        acc = L.MeshAccumulator(); acc.add(p.arrays(), Matrix.Diagonal((sxy, sxy, sz, 1.0))); p.free()
        finish_mesh(acc, me, ctx, f'v12: watch tower variant {k}: flared hip roof with brackets and finial')


def rebuild_garage_roof(ctx):
    ob = bpy.data.objects.get('GarageRoof')
    if ob is None:
        return
    me = ob.data
    arr = original_arrays(me, np.ones(len(me.vertices), bool))
    mi = np.zeros(len(me.polygons), int); me.polygons.foreach_get('material_index', mi)
    arr['mat'] = mi.astype(np.int32)
    v10 = split_arrays(arr, mi == 0)
    comp = face_comp_ids(v10)
    starts = np.concatenate([[0], np.cumsum(v10['flen'])[:-1]])
    keep = np.zeros(len(v10['flen']), bool)
    allco = v10['co']
    c = allco.mean(0); d = allco[:, :2] - c[:2]; w, v = np.linalg.eigh(d.T @ d)
    ax = Vector((v[0, 1], v[1, 1], 0)).normalized(); side = Vector((-ax.y, ax.x, 0))
    pa = d @ np.array(ax[:2]); ps = d @ np.array(side[:2])
    Lx = pa.max() - pa.min(); Ly = ps.max() - ps.min()
    zbase = allco[:, 2].min()
    rise = 1.7
    # keep only the emblem pieces (small, light/red, top) and lift them onto the vault crown
    emb = []
    for cid in np.unique(comp):
        fs = np.where(comp == cid)[0]
        vi = np.unique(np.concatenate([v10['lv'][starts[f]:starts[f] + v10['flen'][f]] for f in fs]))
        pts = v10['co'][vi]; ext = pts.max(0) - pts.min(0)
        col = v10['col'][np.concatenate([np.arange(starts[f], starts[f] + v10['flen'][f]) for f in fs])][:, :3].mean(0)
        if max(ext[0], ext[1]) < 8.0 and (col[0] > 0.5) and pts[:, 2].min() > zbase + 0.2:
            keep[fs] = True
    emblem = split_arrays(v10, keep) if keep.any() else None
    p = L.Part()
    Cv = Vector((c[0], c[1], zbase + 0.15))
    vault(p, Cv, ax, side, Lx + 0.4, Ly, rise, 0.1, (0.46, 0.13, 0.05, 1.0, 0.42, 0.2), 20, 1.2, 'corrugated', 1.0)
    for t in np.linspace(-Lx / 2 - 0.1, Lx / 2 + 0.1, 5):
        arch_rib(p, Cv + ax * t + Vector((0, 0, -0.02)), side, Ly, rise, 0.1, S('steel_dark', 1.25), 0.2, 0.22, 14)
    # end gable infill (upper half of each arch), gutters and down pipes
    for sgn in (-1, 1):
        for s_ in (-1, 1):
            q = Cv + ax * sgn * (Lx / 2 + 0.15) + side * s_ * (Ly / 2 - 0.1)
        K.beam(p, Cv + side * (Ly / 2 + 0.05) + ax * sgn * 0 - ax * (Lx / 2) , Cv + side * (Ly / 2 + 0.05) + ax * (Lx / 2), 0.2, 0.16, S('galvanized', 0.8), 'plain', 0.03) if sgn > 0 else \
            K.beam(p, Cv - side * (Ly / 2 + 0.05) - ax * (Lx / 2), Cv - side * (Ly / 2 + 0.05) + ax * (Lx / 2), 0.2, 0.16, S('galvanized', 0.8), 'plain', 0.03)
    for (sa, sb) in ((1, 1), (-1, -1)):
        q = Cv + ax * sa * (Lx / 2 - 0.4) + side * sb * (Ly / 2 + 0.08)
        K.cyl_between(p, q, q - Vector((0, 0, zbase + 0.1)), 0.07, S('galvanized', 0.8), 8)
    acc = L.MeshAccumulator()
    if emblem is not None:
        e = dict(emblem); co = e['co'].copy(); z0 = co[:, 2].min()
        R_ = (Ly * Ly / 4 + rise * rise) / (2 * rise)
        for k in range(len(co)):
            so = (Vector(co[k]) - Cv).dot(side)
            zs = Cv.z + math.sqrt(max(0.0, R_ * R_ - so * so)) - (R_ - rise)
            co[k, 2] = zs + 0.06 + (co[k, 2] - z0)
        e['co'] = co
        acc.add(with_mat(e, 0))
    acc.add(with_mat(p.arrays(), 1)); p.free()
    mats = [ob.material_slots[0].material, ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v12', materials=mats, sharp_angle=40.0)
    users, _ = L.swap_mesh(me, new, note='v12: garage roof is now a corrugated barrel vault (still the separate fading roof object)')
    for o in users:
        L.set_object_materials(o, mats)


def gate_lookouts(p, arr):
    for sx in (-1, 1):
        cx = sx * 7.2
        for (dx, dy) in ((-1.9, -1.9), (1.9, -1.9), (-1.9, 1.9), (1.9, 1.9)):
            K.cyl_between(p, (cx + dx, dy, 5.8), (cx + dx, dy, 7.7), 0.11, S('wood_dark', 1.05), 10)
        sub = L.Part()
        tower_roof(sub, 7.65, 2.25, 1.35, (0.40, 0.11, 0.045, 1.0, 0.42, 0.2))
        a = sub.arrays(); sub.free()
        a['co'] = a['co'] + np.array([cx, 0.0, 0.0])
        import rg_rocks as R
        R._append_arrays(p, a)


def works_entrance_arch(p):
    """Truss arch over the ramp mouth (x ~ 21.5), pylons outside the lane, sign board on top."""
    steel = (0.42, 0.16, 0.06, 1.0, 0.42, 0.3); dark = S('steel_dark', 1.25)
    x = 21.2
    for y in (35.6, 48.4):
        K.box(p, (0.9, 0.9, 0.5), Matrix.Translation((x, y, 0.25)), S('concrete', 0.9), 'concrete', 0.06)
        K.beam(p, (x - 0.25, y, 0.5), (x - 0.25, y, 6.0), 0.22, 0.22, steel, 'panel', 0.03, up=(1, 0, 0))
        K.beam(p, (x + 0.25, y, 0.5), (x + 0.25, y, 6.0), 0.22, 0.22, steel, 'panel', 0.03, up=(1, 0, 0))
        for z in np.arange(0.9, 5.8, 0.9):
            K.beam(p, (x - 0.25, y, z), (x + 0.25, y, z + 0.6), 0.06, 0.06, dark, 'plain', 0.0)
    # arched top chord + straight bottom chord with web members
    pts_top = [(x, y, 6.0 + 1.2 * math.sin(math.pi * (y - 35.6) / 12.8)) for y in np.linspace(35.6, 48.4, 13)]
    pts_bot = [(x, y, 5.9) for y in np.linspace(35.6, 48.4, 13)]
    for a, b in zip(pts_top[:-1], pts_top[1:]):
        K.beam(p, a, b, 0.24, 0.24, steel, 'panel', 0.03, ext=0.05)
    for a, b in zip(pts_bot[:-1], pts_bot[1:]):
        K.beam(p, a, b, 0.2, 0.2, steel, 'panel', 0.02, ext=0.05)
    for j in range(12):
        a, b = (pts_bot[j], pts_top[j + 1]) if j % 2 == 0 else (pts_top[j], pts_bot[j + 1])
        K.beam(p, a, b, 0.08, 0.08, dark, 'plain', 0.0)
    # sign board (red with cream bands) and two lamps
    K.box(p, (0.18, 6.4, 1.1), Matrix.Translation((x - 0.2, 42.0, 7.45)), (0.60, 0.07, 0.035, 1, 0.5, 0.15), 'panel', 0.04)
    for z in (7.2, 7.7):
        K.box(p, (0.05, 5.4, 0.18), Matrix.Translation((x - 0.32, 42.0, z)), S('paint_cream', 1.0), 'plain', 0.0)
    for y in (39.0, 45.0):
        K.box(p, (0.5, 0.35, 0.25), Matrix.Translation((x - 0.5, y, 6.75)) @ Matrix.Rotation(0.5, 4, 'Y'), dark, 'plain', 0.03)
        K.box(p, (0.03, 0.28, 0.18), Matrix.Translation((x - 0.72, y, 6.66)) @ Matrix.Rotation(0.5, 4, 'Y'), (1.0, 0.86, 0.55, 0.25, 0.6, 0.0), 'plain', 0.0)


def stair_tower(p, cx, cy, h=6.2, r=1.7):
    wall = (0.42, 0.40, 0.37, 1.0, 0.1, 0.0)
    K.cyl_between(p, (cx, cy, -0.05), (cx, cy, 0.4), r + 0.25, S('concrete', 0.85), 24, bevel=0.06)
    K.cyl_between(p, (cx, cy, 0.4), (cx, cy, h), r, wall, 24, 'concrete', bevel=0.05)
    for z in (1.6, 3.1, 4.6):
        K.cyl_between(p, (cx, cy, z), (cx, cy, z + 0.12), r + 0.05, S('steel_dark', 1.2), 24)
    K.cyl_between(p, (cx, cy, h), (cx, cy, h + 0.25), r + 0.25, S('steel_dark', 1.2), 24, bevel=0.04)
    K.cyl_between(p, (cx, cy, h + 0.25), (cx, cy, h + 1.1), r * 0.45, S('galvanized', 0.85), 16, r2=r * 0.15)
    for k, z in enumerate((2.2, 3.7, 5.2)):
        a = k * 1.3 + 0.4
        q = (cx + math.cos(a) * (r + 0.02), cy + math.sin(a) * (r + 0.02))
        K.box(p, (0.08, 0.45, 0.7), Matrix.Translation((q[0], q[1], z)) @ Matrix.Rotation(a, 4, 'Z'), S('glass', 0.7), 'plain', 0.02)


def run(ctx):
    r = random.Random(1500)
    for k, fn in enumerate((shack_porch, shack_quonset, shack_tall)):
        me = bpy.data.meshes.get(f'Shack_{k}_0')
        if me:
            acc = L.MeshAccumulator(); p = fn(random.Random(1500 + k)); acc.add_part(p); p.free()
            finish_mesh(acc, me, ctx, f'v12: shack variant {k} ({fn.__name__[6:]}) — distinct silhouette, same footprint and door side')
    rebuild_towers(ctx)
    rebuild_garage_roof(ctx)
    from step_works import augment2
    ob = bpy.data.objects.get('GateTowers')
    if ob:
        augment2(ob, ctx, lambda p: gate_lookouts(p, None), 'v12: hip-roofed lookouts on the gate towers')
    ob = bpy.data.objects.get('WorksEntrance')
    if ob:
        augment2(ob, ctx, works_entrance_arch, 'v12: entrance truss arch with sign over the ramp mouth (pylons outside the lane)')
    ob = bpy.data.objects.get('HangarWallE')
    if ob:
        augment2(ob, ctx, lambda p: (stair_tower(p, 78.6, 51.4), stair_tower(p, 78.6, 90.6)), 'v12: round stair towers at the east hangar corners')
    ob = bpy.data.objects.get('HangarWallS')
    if ob:
        augment2(ob, ctx, lambda p: stair_tower(p, 25.4, 51.4, 5.4, 1.5), 'v12: round stair tower at the south-west hangar corner')
    ctx['stats']['buildings'] = 'shacks x3 designs, towers, garage vault, gate lookouts, works arch + 3 stair towers'
    print('STEP12 buildings done', flush=True)
