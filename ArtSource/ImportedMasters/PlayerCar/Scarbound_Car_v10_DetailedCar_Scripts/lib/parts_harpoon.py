"""Harpoon turret, DetailedCar pass: same dimensions / pivots as ModelsActors (base, column+yoke, launcher, harpoon tip),
higher resolution, fillets, bolts, rope wound on the reel, knurled grips, sharper barbed head."""
import math

from mathutils import Vector

from mb import MB, C, TAU, fillet, hash01, shade

HSteel, HSteelDark, HSteelLight, HGripC = C("#59616A"), C("#464D55"), C("#8E979F"), C("#2B2622")
CarAccent, CarRope, CarSteel = C("#34B4A2"), C("#E6D6B0"), C("#AEB6BE")
PIVOT_Z = 0.80


def Y(b, y, z=0.0, x=0.0):
    return b.at((x, y, z), (-90, 0, 0))


def base_mesh():
    b = MB("MAT_Metal", 0.4, 0.6)
    b.lathe(fillet([(0, 0), (0.23, 0), (0.23, 0.026), (0.214, 0.036), (0, 0.036)], [0, 0.003, 0.004, 0.003, 0], 2), 64, HSteelDark)
    b.m(gloss=0.85, metal=1.0)
    for i in range(8):
        a = math.radians(22.5 + i * 45)
        x, y = math.cos(a) * 0.195, math.sin(a) * 0.195
        b.cyl((x, y, 0.034), (x, y, 0.038), 0.02, 16, shade(HSteelLight, 0.9))
        b.cyl((x, y, 0.038), (x, y, 0.049), 0.0135, 6, HSteelLight, fillet_r=0.002)
    return b


def column_mesh():
    b = MB("MAT_Metal", 0.45, 0.6)
    b.lathe(fillet([(0, 0.036), (0.165, 0.036), (0.165, 0.1), (0.15, 0.115), (0, 0.115)], [0, 0.003, 0.004, 0.004, 0], 2), 56, HSteel)
    b.m(gloss=0.6, metal=0.3)
    b.lathe([(0.163, 0.062), (0.169, 0.064), (0.169, 0.086), (0.163, 0.088)], 56, CarAccent, closed_prof=True)
    b.m(gloss=0.85, metal=1.0)
    for i in range(12):
        a = TAU * (i + 0.5) / 12
        b.cyl((math.cos(a) * 0.13, math.sin(a) * 0.13, 0.113), (math.cos(a) * 0.13, math.sin(a) * 0.13, 0.121), 0.008, 6, HSteelLight)
    b.m(gloss=0.5, metal=0.7)
    b.lathe(fillet([(0, 0.112), (0.11, 0.112), (0.075, 0.205), (0.072, 0.63), (0.0, 0.63)], [0, 0.006, 0.02, 0, 0], 3), 40, HSteel)
    for z in (0.3, 0.45):
        b.lathe([(0.07, z - 0.012), (0.078, z - 0.008), (0.078, z + 0.008), (0.07, z + 0.012)], 40, shade(HSteel, 1.12), closed_prof=True)
    b.m(gloss=0.4, metal=0.6)
    b.rbox((0, 0, 0.652), (0.155, 0.075, 0.0225), 0.01, 2, HSteelDark)
    for s in (-1, 1):
        b.rbox((s * 0.137, 0, 0.735), (0.015, 0.065, 0.075), 0.007, 2, HSteelDark)
        b.cyl((s * 0.122, 0, PIVOT_Z), (s * 0.152, 0, PIVOT_Z), 0.065, 40, HSteelDark, fillet_r=0.006)
        b.m(gloss=0.85, metal=1.0)
        b.cyl((s * 0.152, 0, PIVOT_Z), (s * 0.168, 0, PIVOT_Z), 0.034, 24, HSteelLight, fillet_r=0.004)
        for k in range(6):
            a = TAU * k / 6
            b.cyl((s * 0.151, math.cos(a) * 0.05, PIVOT_Z + math.sin(a) * 0.05), (s * 0.158, math.cos(a) * 0.05, PIVOT_Z + math.sin(a) * 0.05),
                  0.0065, 6, HSteelLight)
        b.m(gloss=0.4, metal=0.6)
        b.prism([(0.0, 0.675), (0.06, 0.675), (0.0, 0.73)], 0.014, shade(HSteelDark, 1.1)) if False else None
    return b


def launcher_mesh():
    b = MB("MAT_Metal", 0.55, 0.8)
    with Y(b, -0.2):
        b.lathe(fillet([(0, -0.05), (0.06, -0.044), (0.08, -0.02), (0.08, 0.58), (0, 0.58)], [0, 0.02, 0.015, 0, 0], 3), 40, HSteel)
    b.m(gloss=0.4, metal=0.6)
    b.cyl((-0.122, 0, 0), (0.122, 0, 0), 0.04, 24, HSteelDark, fillet_r=0.004)
    # rope reel: teal flanges, drum, rope wound in coils
    b.m(gloss=0.6, metal=0.35)
    for z in (0.08, 0.28):
        with Y(b, z):
            b.lathe(fillet([(0.075, 0.0), (0.145, 0.0), (0.145, 0.02), (0.075, 0.02)], [0, 0.004, 0.004, 0], 2), 48, CarAccent, closed_prof=True)
        b.m(gloss=0.85, metal=1.0)
        for k in range(6):
            a = TAU * (k + 0.5) / 6
            p = (math.cos(a) * 0.12, z + (0.02 if z > 0.1 else 0.0) + (-0.002 if z > 0.1 else 0.0), math.sin(a) * 0.12)
            b.cyl((p[0], z - 0.003, p[2]), (p[0], z + 0.023, p[2]), 0.0065, 6, HSteelLight)
        b.m(gloss=0.6, metal=0.35)
    b.m("MAT_Cloth", 0.2, 0.0)
    with Y(b, 0.1):
        b.lathe([(0, 0), (0.1, 0), (0.1, 0.18), (0, 0.18)], 40, shade(CarRope, 0.8))
    n_coils = 9
    for c in range(n_coils):
        z0 = 0.1 + 0.009 + c * (0.162 / n_coils)
        pts = []
        for k in range(33):
            a = TAU * k / 32
            pts.append((math.cos(a) * 0.107, z0, math.sin(a) * 0.107))
        b.tube(pts[:-1], 0.0095, 7, shade(CarRope, 0.92 + 0.12 * hash01(c)), closed=True, up=(0, 1, 0))
    # barrel, muzzle ring with a flared mouth, dark bore
    b.m("MAT_Metal", 0.75, 0.9)
    with Y(b, 0.38):
        b.lathe(fillet([(0, 0), (0.05, 0), (0.05, 0.15), (0, 0.15)], [0, 0.004, 0.004, 0], 2), 36, HSteelLight)
    b.m(gloss=0.85, metal=1.0)
    with Y(b, 0.515):
        b.lathe([(0.04, 0.0), (0.062, 0.0), (0.066, 0.03), (0.07, 0.055), (0.062, 0.058), (0.042, 0.05)], 40, CarSteel, closed_prof=True)
        b.m(gloss=0.1, metal=0.0)
        b.lathe([(0.0405, 0.05), (0.0405, -0.04), (0.0, -0.04)], 24, C("#121315"))
    # sight with a peep ring
    b.m("MAT_Metal", 0.4, 0.6)
    b.rbox((0, 0.0, 0.095), (0.011, 0.03, 0.0175), 0.005, 2, HSteelDark)
    b.cyl((0, -0.006, 0.124), (0, 0.006, 0.124), 0.012, 16, HSteelDark)
    # T-handle and knurled rubber grips (r 0.027, as the hands are fitted to them)
    b.cyl((0, -0.24, 0), (0, -0.262, 0), 0.03, 20, HSteelDark, fillet_r=0.004)
    b.cyl((-0.115, -0.262, 0), (0.115, -0.262, 0), 0.02, 16, HSteelDark, fillet_r=0.004)
    b.m("MAT_Rubber", 0.2, 0.0)
    for s in (-1, 1):
        b.cyl((s * 0.112, -0.262, 0), (s * 0.205, -0.262, 0), 0.027, 20, HGripC, fillet_r=0.006)
        for k in range(7):
            xk = s * (0.122 + k * 0.012)
            with b.at((xk, -0.262, 0), (0, 90, 0)):
                b.lathe([(0.0265, -0.003), (0.0285, 0.0), (0.0265, 0.003), (0.026, 0.0)], 20, shade(HGripC, 1.25), closed_prof=True)
    return b


def harpoon_tip_mesh():
    b = MB("MAT_Metal", 0.5, 0.8)
    with Y(b, -0.36):
        b.lathe(fillet([(0, 0), (0.032, 0), (0.032, 0.46), (0, 0.46)], [0, 0.004, 0.004, 0], 1), 20, C("#3E444A"))
    b.m("MAT_Cloth", 0.2, 0.0)
    for k in range(7):
        y = -0.355 + k * 0.011
        pts = [(math.cos(TAU * j / 20) * 0.039, y, math.sin(TAU * j / 20) * 0.039) for j in range(20)]
        b.tube(pts, 0.0062, 6, shade(CarRope, 0.95 + 0.08 * hash01(k)), closed=True, up=(0, 1, 0))
    b.m("MAT_Metal", 0.9, 1.0)
    head = C("#E6EBEF")
    with b.at((0, 0.06, 0), (-90, 0, 0)):
        with b.at((0, 0, 0), None, (1.0, 0.5, 1.0)):
            b.lathe(fillet([(0.0, -0.01), (0.035, -0.01), (0.122, 0.1), (0.07, 0.262), (0.0, 0.365)], [0, 0.004, 0.006, 0.01, 0], 2), 24, head)
    for s in (-1, 1):
        b.cyl((s * 0.04, 0.1, 0), (s * 0.15, -0.06, 0), 0.022, 12, head, r2=0.006, fillet_r=0.004)
    return b
