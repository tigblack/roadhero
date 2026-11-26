"""Quasimodo limbs, DetailedCar pass. Each part is built in its own object's local frame (rigid parts, game IK pivots kept):
  UpperArm*: bone along local +Y from the shoulder (0) to the elbow (0.28)
  ForeArm*:  bone along local +Y from the elbow (0) to the wrist / grip (0.27)
  Hand*:     origin = grip centre, +Y = forearm direction, +Z ~ launcher up; fist wraps the real handle axis
  LegMesh*:  hip pivot space (identity), knee / ankle / sole from ModelsActors.QuasiLeg"""
import math

from mathutils import Matrix, Vector

import organic
from mb import MB, C, TAU, circle, fillet, hash01, mixc, rrect, shade
from parts_quasi import (QBoots, QBrass, QCloak, QCloakDark, QHole, QLeather, QLeatherDark, QSkin, QSkinShade, QSole,
                         QTrousers, QWrap, folds, smooth_step)

UPPER_LEN, FORE_LEN = 0.28, 0.27


def lerp_prof(prof, y):
    for (y0, r0), (y1, r1) in zip(prof, prof[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0) if y1 > y0 else 0
            return r0 + (r1 - r0) * t
    return prof[0][1] if y < prof[0][0] else prof[-1][1]


def sleeve(b, y0, y1, prof, seed, n_rings=26, n_seg=28, ell=(1.0, 0.92), bunch=None, col=QCloak, thick=0.006,
           close_start=True, lining=0.05):
    """Cloth tube along local +Y with twisted folds, elbow bunching, an open (thick) distal edge."""
    rows = []
    for i in range(n_rings):
        y = y0 + (y1 - y0) * i / (n_rings - 1)
        r = lerp_prof(prof, y)
        row = []
        for k in range(n_seg):
            a = TAU * k / n_seg
            rr = r * (1 + 0.07 * folds(a + y * 7.0, seed, 7, 0.45) * smooth_step(y0, y0 + 0.06, y))
            if bunch:
                yb0, yb1, amp = bunch
                w = smooth_step(yb0, yb0 + 0.03, y) * (1 - smooth_step(yb1 - 0.03, yb1, y))
                rr += amp * w * (0.5 + 0.5 * math.sin((y - yb0) * 140 + a * 2 + seed))
            row.append((math.cos(a) * rr * ell[0], y, math.sin(a) * rr * ell[1]))
        rows.append(row)
    # winding check: outward from the local Y axis
    p = [Vector(rows[2][0]), Vector(rows[2][1]), Vector(rows[3][1]), Vector(rows[3][0])]
    nrm = (p[1] - p[0]).cross(p[3] - p[0])
    flip = nrm.dot(Vector((p[0].x, 0, p[0].z))) < 0
    oi = b.grid(rows, col, cv=True, flip=flip, colfn=lambda i, j: QCloakDark if hash01(j * 5 + seed) < 0.12 else shade(col, 0.95 + 0.1 * hash01(j * 3 + seed)))
    # lining near the open end + thick rim
    inner = []
    nl = max(2, int(n_rings * lining / (y1 - y0)))
    for i in range(n_rings - nl, n_rings):
        inner.append([(x * (1 - thick / max(1e-6, math.hypot(x, z))), y, z * (1 - thick / max(1e-6, math.hypot(x, z)))) for (x, y, z) in rows[i]])
    ii = b.grid(inner, QHole, cv=True, flip=not flip)
    b.stitch([oi[-1], ii[-1]], QCloakDark, cv=True, flip=flip)
    # caps: the hidden inner end of the lining and the closed start
    def cap(ring_idx, ring_pts, direction):
        c = sum((Vector(q) for q in ring_pts), Vector()) / len(ring_pts)
        ci = b.vs([tuple(c)])[0]
        for k in range(len(ring_idx)):
            b.face_out([ci, ring_idx[k], ring_idx[(k + 1) % len(ring_idx)]], ("d", direction), col=QHole)
    cap(ii[0], inner[0], (0, 1, 0))
    if close_start:
        cap(oi[0], rows[0], (0, -1, 0))
    return rows


def upper_arm(seed):
    b = MB("MAT_Cloth", 0.08, 0.0)
    prof = [(-0.05, 0.068), (0.0, 0.077), (0.05, 0.076), (0.12, 0.068), (0.19, 0.063), (0.24, 0.066), (0.285, 0.072), (0.305, 0.075)]
    sleeve(b, -0.05, 0.305, prof, seed, bunch=(0.19, 0.3, 0.005))
    # elbow patch (darker, stitched on)
    b.m("MAT_Leather", 0.25, 0.0)
    with b.at((0, 0.255, 0.0), (0, 0, 0)):
        pass
    return b


def fore_arm(seed, side):
    b = MB("MAT_Cloth", 0.08, 0.0)
    prof = [(-0.035, 0.06), (0.04, 0.059), (0.12, 0.056), (0.18, 0.057), (0.2, 0.061)]
    rows = sleeve(b, -0.035, 0.2, prof, seed, n_rings=20, bunch=(0.0, 0.06, 0.004))
    # ragged cuff flaps (thin cloth shells) hanging off the sleeve end
    end = rows[-1]
    n = len(end)
    for k in range(0, n, 4):
        p, q = Vector(end[k]), Vector(end[(k + 2) % n])
        out = Vector((p.x + q.x, 0, p.z + q.z)).normalized()
        L = 0.025 + 0.03 * hash01(k + seed)
        m = (p + q) / 2
        tip = m + Vector((0, L, 0)) + out * 0.004
        rws = [[p, q], [m + Vector((0, L * 0.5, 0)) - (q - p) * 0.3, m + Vector((0, L * 0.5, 0)) + (q - p) * 0.3], [tip - (q - p) * 0.05, tip + (q - p) * 0.05]]
        o = [[tuple(v) for v in r] for r in rws]
        i_ = [[tuple(v - out * 0.003) for v in r] for r in rws]
        from parts_quasi import solid_shell
        solid_shell(b, o, i_, QCloakDark, QHole, QCloakDark, flip=True)
    # leather bracer with two straps and brass buckles
    b.m("MAT_Leather", 0.3, 0.0)
    br = [(0.0, 0.1), (0.066, 0.1), (0.068, 0.11), (0.066, 0.175), (0.064, 0.185), (0.0, 0.185)]
    with b.at((0, 0, 0), (-90, 0, 0)):
        pass
    rows_b = []
    for i in range(12):
        y = 0.1 + 0.085 * i / 11
        r = 0.0635 + 0.003 * math.sin(i / 11 * math.pi)
        rows_b.append([(math.cos(TAU * k / 28) * r, y, math.sin(TAU * k / 28) * r * 0.94) for k in range(28)])
    p = [Vector(rows_b[2][0]), Vector(rows_b[2][1]), Vector(rows_b[3][1]), Vector(rows_b[3][0])]
    flip = ((p[1] - p[0]).cross(p[3] - p[0])).dot(Vector((p[0].x, 0, p[0].z))) < 0
    oi = b.grid(rows_b, QLeather, cv=True, flip=flip)
    inner = [[(x * 0.93, y, z * 0.93) for (x, y, z) in r] for r in rows_b]
    ii = b.grid(inner, QLeatherDark, cv=True, flip=not flip)
    b.stitch([oi[-1], ii[-1]], QLeatherDark, cv=True, flip=flip)
    b.stitch([ii[0], oi[0]], QLeatherDark, cv=True, flip=flip)
    for y in (0.118, 0.165):
        ring = [(math.cos(TAU * k / 28) * 0.0685, y, math.sin(TAU * k / 28) * 0.0645) for k in range(28)]
        b.tube(ring, 0.0045, 6, QLeatherDark, closed=True, up=(0, 1, 0))
        b.m("MAT_Metal", 0.75, 0.9)
        b.rbox((0.0, y, -0.07), (0.011, 0.008, 0.004), 0.002, 1, QBrass)
        b.m("MAT_Leather", 0.3, 0.0)
    # bare wrist (skin) into the hand
    b.m("MAT_Skin", 0.22, 0.0)
    b.cyl((0, 0.16, 0), (0, 0.262, 0), 0.037, 20, QSkin, r2=0.031, fillet_r=0.012)
    return b


# ---------------------------------------------------------------- hands (fist round the launcher handle)
def hand(side_index, axis_local, z_local=Vector((0, 0, 1))):
    """side_index: 0 = right hand, 1 = left hand. axis_local: handle axis (crew +X) in hand space."""
    a = Vector(axis_local).normalized()
    ylocal = Vector((0, 1, 0))
    w = (-ylocal) - a * ((-ylocal).dot(a))
    e1 = w.normalized()                                  # toward the wrist / forearm
    e2 = a.cross(e1).normalized()
    if e2.dot(z_local) < 0:
        e2 = -e2
    index_dir = -1.0 if side_index == 0 else 1.0         # index finger toward the launcher's centre line
    R_BAR = 0.027
    fingers = [(index_dir * 0.034, 0.0108, 1.0), (index_dir * 0.012, 0.0113, 1.04), (-index_dir * 0.01, 0.0105, 0.98),
               (-index_dir * 0.031, 0.0092, 0.88)]

    def P(apos, phi_deg, r):
        ph = math.radians(phi_deg)
        return a * apos + (e1 * math.cos(ph) + e2 * math.sin(ph)) * r

    b = MB("MAT_Skin", 0.25, 0.0)
    # palm + back of the hand: a thick wrap round the bar from the heel (wrist side) over the top to the knuckles
    rows = []
    for i in range(9):
        t = i / 8
        apos = index_dir * 0.046 + (-index_dir * 0.044 - index_dir * 0.046) * t
        row = []
        for k in range(15):
            ph = -35 + 165 * k / 14
            thick = 0.016 + 0.018 * math.sin(math.radians((ph + 35) / 165 * 180)) ** 0.7
            row.append(tuple(P(apos * (0.92 + 0.08 * math.sin(math.radians((ph + 35) / 165 * 180))), ph, R_BAR + 0.004 + thick)))
        rows.append(row)
    inner = [[tuple(P(index_dir * 0.046 + (-index_dir * 0.044 - index_dir * 0.046) * (i / 8), -35 + 165 * k / 14, R_BAR + 0.001)) for k in range(15)] for i in range(9)]
    from parts_quasi import solid_shell
    solid_shell(b, rows, inner, QSkin, QSkin, QSkin, mat=("MAT_Skin", (0.25, 0.0)))
    # fingers: three phalanges each, knuckle bulges, wrapping over the front and under the bar
    for (apos, fr, ln) in fingers:
        path, rads = [], []
        for k in range(15):
            t = k / 14
            ph = 120 + (300 - 120) * t * ln
            rr = R_BAR + fr + 0.0015 + 0.004 * math.exp(-((t - 0.0) / 0.12) ** 2)
            path.append(tuple(P(apos, ph, rr)))
        b.tube(path, fr, 12, QSkin, scale=lambda t: (1.0 + 0.12 * math.exp(-((t - 0.36) / 0.06) ** 2) + 0.1 * math.exp(-((t - 0.7) / 0.06) ** 2)) * (1 - 0.18 * t))
        b.ellipsoid(path[-1], (fr * 0.85, fr * 0.85, fr * 0.85), QSkin, 12, 6)
        b.ellipsoid(tuple(P(apos, 122, R_BAR + 0.03)), (0.0125, 0.0125, 0.0125), QSkin, 12, 6)    # knuckle
    # thumb: from the heel of the palm under the bar, lying over the fingers' middle joints
    tp = []
    for k in range(11):
        t = k / 10
        ph = -25 - 105 * t
        apos = index_dir * (0.05 - 0.04 * t)
        rr = R_BAR + 0.03 - 0.008 * t + 0.012 * math.sin(t * math.pi)
        tp.append(tuple(P(apos, ph, rr)))
    b.tube(tp, 0.0135, 12, QSkin, scale=lambda t: 1.15 - 0.3 * t)
    b.ellipsoid(tp[-1], (0.011, 0.011, 0.011), QSkin, 12, 6)
    # wrist stub joining the forearm end (forearm skin ends ~1.5 cm behind the grip centre on -Y)
    wrist_end = Vector((0, -0.02, 0))
    heel = P(-index_dir * 0.03, -10, R_BAR + 0.022)
    for k in range(6):
        p = wrist_end.lerp(heel, k / 5)
        b.ellipsoid(tuple(p), (0.034 - 0.004 * k / 5,) * 3, QSkin, 16, 8)
    me = b.build("_hand_union", sharp_deg=None)
    hand_me = organic.remesh_union(me, voxel=0.0022, smooth=4, smooth_factor=0.5, target_tris=3200, name="_hand")

    def hcol(p):
        q = p - a * p.dot(a)
        ph = math.degrees(math.atan2(q.dot(e2), q.dot(e1)))
        r = q.length
        along = p.dot(a) * index_dir
        near_wrist = (p - wrist_end).length < 0.05 or (p - heel).length < 0.03
        on_back = -40 <= ph <= 128 and r > R_BAR + 0.012
        if near_wrist or (on_back and abs(along) < 0.05):
            if r > R_BAR + 0.03 and 20 < ph < 110:
                return (QLeather, (0.3, 0.0), "MAT_Leather")
            return (QLeatherDark if near_wrist else QLeather, (0.3, 0.0), "MAT_Leather")
        if 128 < ph or ph < -60:
            return (mixc(QSkin, QSkinShade, 0.25 if ph > 250 or ph < -60 else 0.0), (0.25, 0.0), "MAT_Skin")
        return (QSkin, (0.25, 0.0), "MAT_Skin")
    organic.paint(hand_me, hcol, ["MAT_Skin", "MAT_Leather"])
    # glove strap with a brass buckle round the wrist
    b2 = MB("MAT_Leather", 0.3, 0.0)
    ring = []
    cw = wrist_end.lerp(heel, 0.35)
    ax = (heel - wrist_end).normalized()
    u_ = ax.orthogonal().normalized()
    v_ = ax.cross(u_)
    for k in range(24):
        ang = TAU * k / 24
        ring.append(tuple(cw + (u_ * math.cos(ang) + v_ * math.sin(ang)) * 0.0345))
    b2.tube(ring, 0.0045, 6, QLeatherDark, closed=True)
    b2.m("MAT_Metal", 0.75, 0.9)
    bp = Vector(ring[6])
    b2.rbox(tuple(bp + (bp - cw).normalized() * 0.003), (0.008, 0.008, 0.008), 0.002, 1, QBrass)
    extra = b2.build("_hand_strap", sharp_deg=45)
    return organic.join_meshes([hand_me, extra], "_hand_joined")


# ---------------------------------------------------------------- legs
def leg(s):
    hip = Vector((0, 0, 0.03))
    knee = Vector((s * 0.03, 0.12, -0.245))
    ankle = Vector((s * 0.02, 0.05, -0.49))
    b = MB("MAT_Cloth", 0.12, 0.0)
    # trousers: one continuous tube through the knee (dense loops at the bend)
    from parts_details import catmull
    path = catmull([tuple(hip), tuple(hip.lerp(knee, 0.55) + Vector((0, 0.01, 0))), tuple(knee),
                    tuple(knee.lerp(ankle, 0.5) + Vector((0, -0.005, 0))), tuple(ankle + Vector((0, 0, 0.08)))], 7)
    prof = [(0.0, 0.08), (0.2, 0.074), (0.42, 0.068), (0.5, 0.066), (0.58, 0.067), (0.75, 0.064), (1.0, 0.06)]

    def rad(t):
        r = lerp_prof(prof, t)
        r *= 1 + 0.035 * math.sin(t * 60 + s) * smooth_step(0.4, 0.5, t) * (1 - smooth_step(0.6, 0.7, t))
        return r / 0.07

    def tcol(i, j):
        return shade(QTrousers, 0.92 + 0.12 * hash01(j * 3 + i // 4))
    b.sweep(path, [(math.cos(TAU * k / 24) * 0.07, math.sin(TAU * k / 24) * 0.07 * 0.95) for k in range(24)], QTrousers,
            up=(1, 0, 0), scale=rad, colfn=tcol)
    # puttee wrap spiralling round the shin above the boot
    b.m("MAT_Cloth", 0.05, 0.0)
    helix = []
    turns, z0, z1 = 2.6, -0.29, -0.405
    for k in range(60):
        t = k / 59
        c = knee.lerp(ankle, (0.245 - (z0 + (z1 - z0) * t) * -1) / 0.245 if False else 0.0)
        z = z0 + (z1 - z0) * t
        f = (z - knee.z) / (ankle.z - knee.z)
        cen = knee.lerp(ankle, f)
        ang = TAU * turns * t
        helix.append((cen.x + math.cos(ang) * 0.069, cen.y + math.sin(ang) * 0.069, z))
    b.sweep(helix, rrect(0.034, 0.004, 0.0015, 1), QWrap, up=(0, 0, 1), caps=True)
    # boot: sculpted union (shaft, foot, toe, heel), remeshed
    bb = MB("MAT_Leather", 0.35, 0.0)
    bb.cyl((s * 0.02, 0.05, -0.53), (s * 0.024, 0.07, -0.36), 0.069, 24, QBoots, r2=0.072, fillet_r=0.01)
    bb.ellipsoid((s * 0.02, 0.105, -0.535), (0.068, 0.12, 0.05), QBoots, 24, 12)
    bb.ellipsoid((s * 0.02, 0.19, -0.545), (0.058, 0.06, 0.04), QBoots, 20, 10)
    bb.ellipsoid((s * 0.02, 0.022, -0.54), (0.06, 0.05, 0.05), QBoots, 18, 10)
    bme = bb.build("_boot_union", sharp_deg=None)
    boot = organic.remesh_union(bme, voxel=0.004, smooth=6, smooth_factor=0.6, target_tris=2600, name="_boot")

    def bcol(p):
        if p.z > -0.39:
            return (shade(QBoots, 0.82), (0.3, 0.0), "MAT_Leather")
        if p.y > 0.17 and p.z < -0.52:
            return (shade(QBoots, 1.12), (0.45, 0.0), "MAT_Leather")       # scuffed toe cap
        return (QBoots, (0.35, 0.0), "MAT_Leather")
    organic.paint(boot, bcol, ["MAT_Leather"])
    # sole + heel, laces, two buckled straps
    b.m("MAT_Rubber", 0.2, 0.0)
    b.rbox((s * 0.02, 0.11, -0.5825), (0.066, 0.125, 0.0125), 0.01, 2, QSole, flat=(1, 3, 1))
    b.rbox((s * 0.02, 0.02, -0.57), (0.055, 0.04, 0.012), 0.008, 2, shade(QSole, 1.1))
    b.m("MAT_Leather", 0.2, 0.0)
    for k in range(4):
        z = -0.49 + k * 0.025
        yc = 0.05 + 0.02 * (z + 0.53) / 0.17
        y = yc + 0.075 + (0.012 if z < -0.48 else 0.0)
        for sgn in (-1, 1):
            b.tube([(s * 0.02 - sgn * 0.022, y, z), (s * 0.02 + sgn * 0.022, y + 0.002, z + 0.016)], 0.0028, 6, QWrap)
    for z in (-0.4, -0.455):
        ring = []
        for k in range(28):
            ang = TAU * k / 28
            ring.append((s * 0.021 + math.cos(ang) * 0.0735, 0.06 + math.sin(ang) * 0.0735, z))
        b.m("MAT_Leather", 0.3, 0.0)
        b.tube(ring, 0.0055, 6, QLeatherDark, closed=True, up=(0, 0, 1))
        b.m("MAT_Metal", 0.75, 0.9)
        b.rbox((s * 0.021 + s * 0.077, 0.06, z), (0.003, 0.012, 0.01), 0.002, 1, QBrass)
    rest = b.build("_leg_rest", sharp_deg=50)
    return organic.join_meshes([rest, boot], "_leg")
