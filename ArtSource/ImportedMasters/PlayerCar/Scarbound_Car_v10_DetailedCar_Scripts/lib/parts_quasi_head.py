"""Quasimodo head + hood (HeadMesh), built in crew space with the game's QHeadShift, values from ModelsActors.QuasiHead."""
import math

from mathutils import Vector

import organic
from mb import MB, C, TAU, fillet, hash01, mixc, shade
from parts_quasi import (QBrow, QCloak, QCloakDark, QCloakLight, QEyeWhite, QHoodIn, QMouth, QPupil, QSkin, QSkinLight,
                         QSkinShade, QSocket, QStubble, QTeeth, folds, smooth_step)

SHIFT = Vector((0.0, 0.035, 0.02))          # QHeadShift (0, 0.02, 0.035) in Blender axes


def U(x, y, z):
    return Vector((x, z, y)) + SHIFT


def UR(x, y, z):
    """Unity radii -> Blender radii."""
    return (x, z, y)


FACE_PARTS = [  # (name, centre, radii, blender rot deg)
    ("skull", U(0, 1.125, 0.215), UR(0.096, 0.112, 0.105), None),
    ("face", U(0, 1.095, 0.26), UR(0.1, 0.13, 0.09), None),
    ("forehead", U(0, 1.165, 0.27), UR(0.095, 0.065, 0.075), None),
    ("earR", U(0.104, 1.1, 0.243), UR(0.02, 0.042, 0.028), None),
    ("earL", U(-0.104, 1.095, 0.243), UR(0.02, 0.04, 0.028), None),
    ("browR", U(0.046, 1.143, 0.336), UR(0.052, 0.022, 0.028), (0, -14, 0)),
    ("browL", U(-0.048, 1.134, 0.336), UR(0.05, 0.025, 0.028), (0, 18, 0)),
    ("nose", U(0.011, 1.08, 0.362), UR(0.034, 0.029, 0.033), (0, -12, 0)),
    ("cheekR", U(0.068, 1.096, 0.312), UR(0.03, 0.021, 0.024), None),
    ("cheekL", U(-0.068, 1.096, 0.312), UR(0.03, 0.021, 0.024), None),
    ("chin", U(0.004, 1.0, 0.305), UR(0.066, 0.04, 0.048), None),
    ("jawR", U(0.068, 1.035, 0.276), UR(0.034, 0.05, 0.04), None),
    ("jawL", U(-0.068, 1.035, 0.276), UR(0.034, 0.05, 0.04), None),
    ("lipU", U(0.006, 1.049, 0.343), UR(0.04, 0.009, 0.01), None),
    ("lipL", U(0.004, 1.019, 0.334), UR(0.036, 0.011, 0.011), None),
]
SOCKETS = [(U(0.045, 1.114, 0.33), UR(0.03, 0.019, 0.016)), (U(-0.046, 1.11, 0.33), UR(0.029, 0.016, 0.016))]
STUBBLE = [(U(0.004, 1.0, 0.305), UR(0.075, 0.05, 0.06)), (U(0.07, 1.03, 0.276), UR(0.042, 0.06, 0.05)),
           (U(-0.07, 1.03, 0.276), UR(0.042, 0.06, 0.05)), (U(0.006, 1.05, 0.343), UR(0.047, 0.014, 0.016))]


def face_union():
    b = MB("MAT_Skin", 0.22, 0.0)
    for (n, c, r, rot) in FACE_PARTS:
        b.ellipsoid(tuple(c), r, QSkin, 28, 14, rot=rot)
    # nose bridge + neck as capsules
    a, c = U(0.002, 1.126, 0.346), U(0.012, 1.092, 0.368)
    for k in range(5):
        p = a.lerp(c, k / 4)
        b.ellipsoid(tuple(p), (0.0135, 0.0135, 0.0135), QSkin, 14, 8)
    a, c = U(0, 0.97, 0.14), U(0, 1.06, 0.22)
    for k in range(6):
        p = a.lerp(c, k / 5)
        b.ellipsoid(tuple(p), (0.058, 0.058, 0.058), QSkin, 18, 10)
    return b


def face_color(p):
    skin = ("MAT_Skin")
    d = min(organic.ell_dist(p, c, r) for (c, r) in SOCKETS)
    if d < 1.0:
        return (mixc(QSocket, QSkinShade, max(0.0, d - 0.6) / 0.4), (0.3, 0.0), skin)
    d = min(organic.ell_dist(p, c, r) for (c, r) in STUBBLE)
    if d < 1.0 and p.z < U(0, 1.065, 0).z:
        return (mixc(QStubble, QSkin, max(0.0, d - 0.75) / 0.25), (0.05, 0.0), skin)
    for (n, c, r, rot) in FACE_PARTS:
        if n.startswith("brow") and organic.ell_dist(p, c, (r[0] * 1.15, r[1] * 1.3, r[2] * 1.3)) < 1.0:
            return (QSkinShade, (0.2, 0.0), skin)
    nose = FACE_PARTS[7]
    if organic.ell_dist(p, nose[1], (0.04, 0.04, 0.04)) < 1.0:
        return (mixc(QSkin, C("#C98A78"), 0.35), (0.3, 0.0), skin)
    if p.z > U(0, 1.15, 0).z and p.y > U(0, 0, 0.25).y:
        return (QSkinLight, (0.25, 0.0), skin)
    if p.z < U(0, 1.0, 0).z:
        return (QSkinShade, (0.2, 0.0), skin)
    for s in (1, -1):
        if organic.ell_dist(p, U(s * 0.066, 1.056, 0.312), (0.03, 0.02, 0.032)) < 1.0:
            return (mixc(QSkinShade, QSkin, 0.4), (0.2, 0.0), skin)
    return (QSkin, (0.22, 0.0), skin)


def face_details(b):
    """Crisp overlays: eyes, pupils, mouth, teeth, bristly brows, forehead creases, nostrils."""
    b.m("MAT_Glass", 0.6, 0.0)
    b.ellipsoid(tuple(U(0.045, 1.114, 0.334)), UR(0.0155, 0.011, 0.009), QEyeWhite, 16, 8)
    b.ellipsoid(tuple(U(-0.046, 1.11, 0.334)), UR(0.0145, 0.0065, 0.009), QEyeWhite, 16, 8)
    b.m("MAT_Glass", 0.9, 0.0)
    b.ellipsoid(tuple(U(0.043, 1.113, 0.342)), UR(0.0066, 0.0066, 0.0032), QPupil, 12, 6)
    b.ellipsoid(tuple(U(-0.044, 1.11, 0.342)), UR(0.006, 0.0046, 0.0032), QPupil, 12, 6)
    b.m("MAT_Skin", 0.15, 0.0)
    b.ellipsoid(tuple(U(0.006, 1.031, 0.337)), UR(0.041, 0.011, 0.012), QMouth, 18, 8, rot=(0, 8, 0))
    b.m("MAT_Skin", 0.5, 0.0)
    teeth = [(-0.025, 0.012, 4.0), (-0.009, 0.016, 10.0), (0.013, 0.011, -3.0), (0.029, 0.015, -12.0)]
    for (x, h, rz) in teeth:
        b.rbox(tuple(U(x, 1.038 - h * 0.5 - x * 0.12, 0.346)), (0.0052, 0.003, h / 2), 0.0018, 1, QTeeth, rot=(0, -rz, 0))
    b.m("MAT_Cloth", 0.05, 0.0)
    for (cx, cy, cz, rz, s) in ((0.046, 1.153, 0.35, -14, 1), (-0.048, 1.145, 0.35, 18, -1)):
        for k in range(4):
            off = (k - 1.5) * 0.017
            b.ellipsoid(tuple(U(cx + off, cy - abs(off) * 0.25 * s * math.copysign(1, off) + 0.002 * hash01(k + s), cz - abs(off) * 0.12)),
                        UR(0.012, 0.006, 0.008), QBrow, 10, 5, rot=(0, rz - 20 * (k - 1.5), 0))
    b.m("MAT_Skin", 0.1, 0.0)
    for w in range(2):
        pts = []
        for k in range(9):
            t = k / 8
            x = -0.05 + 0.102 * t
            y = 1.18 + w * 0.017 + math.sin(t * math.pi * 2 + w) * 0.003
            pts.append(tuple(U(x, y, 0.338 - w * 0.003 - abs(x) * 0.12)))
        b.tube(pts, 0.0033, 6, QSkinShade)
    b.m("MAT_Skin", 0.1, 0.0)
    for x in (-0.002, 0.024):
        b.ellipsoid(tuple(U(x, 1.068, 0.374)), UR(0.0075, 0.0055, 0.006), QMouth, 10, 5)


# ---------------------------------------------------------------- hood
KEY = dict(zs=[-0.07, 0.0, 0.07, 0.14, 0.21, 0.27, 0.315], cy=[1.31, 1.255, 1.2, 1.155, 1.13, 1.115, 1.11],
           rx=[0.012, 0.085, 0.145, 0.178, 0.186, 0.178, 0.166], ry=[0.012, 0.08, 0.15, 0.192, 0.205, 0.2, 0.192],
           sh=[0.0, 0.0, 0.0, 0.03, 0.08, 0.14, 0.176])


def _cr(vals, t):
    """Catmull-Rom on a list at fractional index t."""
    n = len(vals)
    i = max(0, min(n - 2, int(t)))
    f = t - i
    p0, p1, p2, p3 = vals[max(i - 1, 0)], vals[i], vals[i + 1], vals[min(i + 2, n - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)


def hood(b):
    NS, NA = 20, 48
    outer = []
    for i in range(NS):
        t = 0.35 + (len(KEY["zs"]) - 1 - 0.35) * (i / (NS - 1)) ** 0.9
        z, cy, rx, ry, sh = (_cr(KEY[k], t) for k in ("zs", "cy", "rx", "ry", "sh"))
        row = []
        for k in range(NA):
            a = TAU * k / NA
            wob = 1 + (hash01(k * 5 + i * 3) - 0.5) * 0.03 * min(1.0, t / 3)
            up = max(0.0, math.sin(a))
            fold = 0.035 * folds(a, 41, 9, 0.35) * smooth_step(0.5, 2.5, t) * (1 - smooth_step(5.2, 6.0, t))
            dy = math.sin(a) * ry * (wob + fold) + up ** 3 * 0.035 * max(0.0, min(1.0, (t - 4) / 2))
            x = math.cos(a) * rx * (wob + fold)
            row.append(U(x, cy + dy, z + dy * sh))
        outer.append(row)
    # winding: the hood's outer surface must face away from its axis
    from parts_body import needs_flip
    mid = outer[NS // 2]
    cen = sum(mid, Vector()) / NA
    q = [outer[NS // 2][0], outer[NS // 2][1], outer[NS // 2 + 1][1], outer[NS // 2 + 1][0]]
    n = (q[1] - q[0]).cross(q[3] - q[0])
    flip = n.dot(((q[0] + q[2]) / 2) - cen) < 0
    # inner surface: offset toward the ring centre
    inner = []
    for i, row in enumerate(outer):
        c = sum(row, Vector()) / NA
        inner.append([p + (c - p).normalized() * 0.008 for p in row])

    def hcol(i, j):
        return QCloakDark if hash01(j * 7 + 3) < 0.15 else shade(QCloak, 0.95 + 0.12 * hash01(j * 3 + i))
    b.m("MAT_Cloth", 0.06, 0.0)
    oi = b.grid([[tuple(p) for p in r] for r in outer], QCloak, cv=True, flip=flip, colfn=hcol)
    ii = b.grid([[tuple(p) for p in r] for r in inner], QHoodIn, cv=True, flip=not flip)
    b.stitch([ii[0], oi[0]], QCloakDark, cv=True, flip=flip)
    b.stitch([oi[-1], ii[-1]], QHoodIn, cv=True, flip=flip)
    # rolled rim round the opening
    rim = []
    last = outer[-1]
    c = sum(last, Vector()) / NA
    for k in range(NA):
        p = last[k]
        rim.append(tuple(p + (c - p).normalized() * 0.004))
    b.m("MAT_Cloth", 0.08, 0.0)
    b.tube(rim, 0.0105, 10, shade(QCloak, 1.05), closed=True)
    return outer


def build_head():
    union = face_union().build("_face_union", sharp_deg=None)
    face = organic.remesh_union(union, voxel=0.0024, smooth=6, smooth_factor=0.6, target_tris=5200, name="_face")
    organic.paint(face, face_color, ["MAT_Skin"], uv_center=tuple(U(0, 1.1, 0.25)), uv_scale=1.0)
    b = MB("MAT_Cloth", 0.06, 0.0)
    hood(b)
    face_details(b)
    rest = b.build("_head_rest", sharp_deg=50.0)
    return organic.join_meshes([rest, face], "quasimodo_head_detailed")
