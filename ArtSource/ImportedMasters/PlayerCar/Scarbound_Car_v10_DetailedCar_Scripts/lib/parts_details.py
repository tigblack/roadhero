"""Car exterior details (object "Details", body space), DetailedCar pass.
Positions follow ModelsCar.BuildCarExtras; written with P(x, up, forward) = Unity coordinates -> Blender."""
import math

from mathutils import Vector

import carshape as cs
import parts_body as pb
from carshape import (BedFloorY, BedFrontZ, BedRailY, BedRearZ, CarHalfWidth, CarTop, CarZFront, CarZRear, CabinRoofY,
                      BedInnerHalf, HoodY, TopY)
from mb import MB, C, TAU, circle, fillet, glow, hash01, mixc, resample, rrect, shade

CarPaintC, CarPaintLow = C("#3B4049"), C("#2C3037")
CarAccent, CarGlass, CarChrome = C("#34B4A2"), C("#45616F"), C("#DCE1E6")
CarTrim, CarRubber, CarSteel = C("#1F2125"), C("#302C2C"), C("#AEB6BE")
CarAlu, CarUnder, CarPipe = C("#C9CED4"), C("#1B1C1F"), C("#BDB6AC")
CarStripe = C("#EFE4CC")
BedWall, BedWoodA, BedWoodB, BedWoodEdge = C("#30343B"), C("#6C665E"), C("#605A53"), C("#3A3632")
Bolt = C("#9AA1A8")
Dark = C("#111214")


def P(x, y, z):
    return (x, z, y)


def H(x, y, z):
    return (x, z, y)


def catmull(pts, n_per=8):
    """Catmull-Rom through points (3D tuples)."""
    P_ = [Vector(p) for p in pts]
    P_ = [P_[0] * 2 - P_[1]] + P_ + [P_[-1] * 2 - P_[-2]]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        for k in range(n_per):
            t = k / n_per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    out.append(tuple(P_[-2]))
    return out


def side_x(z, y):
    """Outer skin x of the (closed) body section at height y (Unity)."""
    pts = pb.section_right(z, False)
    seg = pts[pb.J_SIDE0 - 1:pb.J_TOP0 + 1]
    for a, b in zip(seg, seg[1:]):
        if (a[1] - y) * (b[1] - y) <= 0 and abs(b[1] - a[1]) > 1e-9:
            t = (y - a[1]) / (b[1] - a[1])
            return a[0] + (b[0] - a[0]) * t
    return seg[-1][0]


def torus(b, c, R, r, segs=24, minor=8, col=(1, 1, 1, 1), rot=None):
    prof = [(R + r * math.cos(TAU * k / minor), r * math.sin(TAU * k / minor)) for k in range(minor)]
    with b.at(c, rot):
        b.lathe(prof, segs, col, closed_prof=True)


def bolt_head(b, c, normal, r=0.008, h=0.006, col=Bolt, hexa=True):
    a = Vector(c)
    d = Vector(normal).normalized()
    b.cyl(tuple(a - d * 0.001), tuple(a + d * h), r, 6 if hexa else 10, col)


# ------------------------------------------------------------------ front
def front(b):
    zf = CarZFront
    b.m("MAT_CarPaint", 0.35, 0.0)
    b.rbox(P(0, 0.62, zf - 0.03), H(0.58, 0.12, 0.05), 0.035, 3, CarTrim)
    # grille: chrome surround, three chrome bars, dark slats behind
    b.m("MAT_Metal", 0.92, 1.0)
    out = rrect(0.29, 0.2, 0.035, 4)
    b.tube([P(x, 0.62 + y, zf + 0.024) for (x, y) in out], 0.0085, 10, CarChrome, closed=True, up=(0, 1, 0))
    for k, y in enumerate((0.57, 0.62, 0.67)):
        b.rbox(P(0, y, zf + 0.026), H(0.138, 0.011, 0.009), 0.007, 2, CarChrome)
    b.m("MAT_Metal", 0.3, 0.4)
    for k in range(9):
        x = -0.128 + k * 0.032
        b.rbox(P(x, 0.62, zf + 0.012), H(0.004, 0.092, 0.012), 0.002, 1, Dark)
    # four round lamps: chrome bezel with a lip, ribbed glowing lens, chrome bulb shield
    for x in (-0.44, -0.25, 0.25, 0.44):
        with b.at(P(x, 0.63, zf + 0.01), (-90, 0, 0)):
            b.m("MAT_Metal", 0.95, 1.0)
            b.lathe(fillet([(0.072, -0.03), (0.098, -0.03), (0.098, 0.0), (0.092, 0.014), (0.082, 0.018), (0.075, 0.012), (0.072, -0.03)][:-1],
                           [0, 0.003, 0.004, 0.003, 0.003, 0.0], 2), 28, CarChrome, closed_prof=True)
            b.m("MAT_Glass", 0.7, 0.0)
            lens = [(0.0, 0.028), (0.02, 0.0272), (0.024, 0.0262), (0.03, 0.026), (0.045, 0.0225), (0.049, 0.0205), (0.055, 0.02),
                    (0.066, 0.0145), (0.069, 0.012), (0.0745, 0.0085), (0.0745, -0.02), (0.0, -0.02)]
            b.lathe(lens[::-1], 28, glow(C("#FFF1C8"), 0.3))
            b.m("MAT_Metal", 0.95, 1.0)
            b.lathe(fillet([(0.0, 0.0255), (0.017, 0.0255), (0.017, 0.035), (0.0, 0.04)], [0, 0, 0.004, 0], 2), 16, CarChrome)
    # amber turn signals in chrome frames
    for s in (-1, 1):
        b.m("MAT_Metal", 0.9, 1.0)
        b.rbox(P(s * 0.52, 0.53, zf + 0.004), H(0.04, 0.022, 0.012), 0.01, 2, CarChrome)
        b.m("MAT_Glass", 0.7, 0.0)
        b.rbox(P(s * 0.52, 0.53, zf + 0.012), H(0.032, 0.015, 0.008), 0.007, 2, glow(C("#FFB347"), 0.45))
    # chrome bumper (denser sweep), brackets, overriders with rubber tips
    b.m("MAT_Metal", 0.9, 1.0)
    path = []
    for i in range(41):
        t = i / 40 * 2 - 1
        path.append(P(t * 0.86, 0.42, zf + 0.07 - abs(t) ** 5 * 0.3))
    b.sweep(path, rrect(0.13, 0.1, 0.038, 5), CarChrome, up=(0, 0, 1))
    b.m("MAT_Metal", 0.45, 0.7)
    for s in (-1, 1):
        b.rbox(P(s * 0.45, 0.42, zf + 0.0), H(0.035, 0.03, 0.06), 0.01, 2, shade(CarSteel, 0.55))
        for dz in (-0.02, 0.03):
            bolt_head(b, P(s * 0.485, 0.42, zf + dz), (s, 0, 0), 0.007, 0.005)
    for s in (-1, 1):
        b.m("MAT_Metal", 0.9, 1.0)
        b.rbox(P(s * 0.3, 0.46, zf + 0.115), H(0.022, 0.085, 0.03), 0.018, 3, CarChrome)
        b.m("MAT_Rubber", 0.2, 0.0)
        b.rbox(P(s * 0.3, 0.55, zf + 0.118), H(0.024, 0.014, 0.032), 0.012, 2, CarRubber)
    # chin spoiler with bolts
    b.m("MAT_CarPaint", 0.3, 0.0)
    b.rbox(P(0, 0.32, zf - 0.02), H(0.8, 0.035, 0.12), 0.018, 2, CarTrim, rot=(12, 0, 0))
    for k in range(7):
        x = -0.6 + k * 0.2
        bolt_head(b, P(x, 0.345, zf + 0.06), (0, -0.2, 1), 0.007, 0.005)
    # hood pins near the nose
    for s in (-1, 1):
        x, z = s * 0.42, 2.12
        y = HoodY(x, z)
        b.m("MAT_Metal", 0.9, 1.0)
        b.cyl(P(x, y - 0.004, z), P(x, y + 0.006, z), 0.024, 20, CarChrome, fillet_r=0.003)
        b.cyl(P(x, y + 0.006, z), P(x, y + 0.04, z), 0.0045, 10, CarChrome, fillet_r=0.0015)
        torus(b, P(x, y + 0.026, z + 0.0), 0.012, 0.0028, 16, 6, CarChrome, rot=(90, 0, 0))
        b.tube([P(x, y + 0.004, z - 0.016), P(x + s * 0.02, y + 0.003, z - 0.032), P(x + s * 0.03, y + 0.0, z - 0.055)], 0.0018, 6, shade(CarSteel, 0.7))


# ------------------------------------------------------------------ blower
def blower(b):
    hy = CarTop(1.78) + cs.CarCrown(1.78) - 0.02
    z0 = 1.78
    b.m("MAT_Metal", 0.35, 0.5)
    b.rbox(P(0, hy + 0.04, z0), H(0.28, 0.04, 0.33), 0.02, 3, C("#2A2E34"))
    b.m("MAT_Metal", 0.85, 1.0)
    for k in range(12):
        a = TAU * (k + 0.5) / 12
        x, z = 0.255 * math.cos(a), z0 + 0.305 * math.sin(a)
        x = max(-0.255, min(0.255, x * 1.3))
        bolt_head(b, P(x, hy + 0.08, z), (0, 1, 0)[::-1] if False else (0, 0, 1), 0.0085, 0.006)
    # rotor case + ribs (aluminium), bolts along the ribs
    b.m("MAT_Metal", 0.6, 0.75)
    b.sweep([P(0, hy + 0.19, z0 - 0.24), P(0, hy + 0.19, z0 + 0.24)], rrect(0.24, 0.46, 0.09, 8), CarAlu, up=(0, 0, 1))
    for z in (-0.2, -0.067, 0.067, 0.2):
        b.sweep([P(0, hy + 0.19, z0 + z - 0.016), P(0, hy + 0.19, z0 + z + 0.016)], rrect(0.28, 0.5, 0.11, 8), shade(CarAlu, 0.86), up=(0, 0, 1))
        b.m("MAT_Metal", 0.85, 1.0)
        for s in (-1, 1):
            bolt_head(b, P(s * 0.25, hy + 0.19, z0 + z), (s, 0, 0), 0.007, 0.006)
        b.m("MAT_Metal", 0.6, 0.75)
    # teal front cover with bolts, grooved pulley, ribbed belt down into the hood
    b.m("MAT_CarPaint", 0.7, 0.25)
    b.rbox(P(0, hy + 0.18, z0 + 0.27), H(0.21, 0.12, 0.025), 0.025, 3, CarAccent)
    b.m("MAT_Metal", 0.85, 1.0)
    for (x, y) in ((-0.17, 0.08), (0.17, 0.08), (-0.17, -0.08), (0.17, -0.08), (0, 0.1), (0, -0.1)):
        bolt_head(b, P(x, hy + 0.18 + y, z0 + 0.295), (0, 1, 0), 0.008, 0.006)
    with b.at(P(0, hy + 0.2, z0 + 0.295), (-90, 0, 0)):
        prof = [(0.0, 0.0), (0.08, 0.0)]
        for k in range(4):
            z = 0.006 + k * 0.011
            prof += [(0.08, z), (0.072, z + 0.004), (0.08, z + 0.008)]
        prof += [(0.08, 0.05), (0.03, 0.05), (0.03, 0.062), (0.0, 0.064)]
        b.lathe(prof, 40, CarChrome)
    b.m("MAT_Rubber", 0.15, 0.0)
    belt = []
    for k in range(25):
        a = math.pi * k / 24
        belt.append(P(0.0815 * math.cos(a) * -1, hy + 0.2 + 0.0815 * math.sin(a), z0 + 0.323))
    belt = [P(-0.0815, hy - 0.06, z0 + 0.323)] + belt + [P(0.0815, hy - 0.06, z0 + 0.323)]
    b.sweep(belt, rrect(0.036, 0.008, 0.003, 2), CarRubber, up=(0, 1, 0))
    b.m("MAT_CarPaint", 0.3, 0.0)
    b.rbox(P(0, hy + 0.004, z0 + 0.323), H(0.12, 0.008, 0.03), 0.006, 2, Dark)
    # injector hat: chrome body, two hollow velocity stacks with butterflies, fuel lines
    b.m("MAT_Metal", 0.9, 1.0)
    b.rbox(P(0, hy + 0.315, z0 + 0.02), H(0.13, 0.05, 0.15), 0.035, 3, CarChrome)
    for s in (-1, 1):
        x = s * 0.06
        base = hy + 0.355
        out = rrect(0.13, 0.09, 0.02, 3)
        inn = rrect(0.114, 0.074, 0.013, 3)[::-1]
        oi = b.sweep([P(x, base, z0 + 0.05), P(x, base + 0.035, z0 + 0.05)], out, CarChrome, caps=False, up=(0, 1, 0))
        b.m("MAT_Metal", 0.1, 0.0)
        ii = b.sweep([P(x, base, z0 + 0.05), P(x, base + 0.035, z0 + 0.05)], inn, Dark, caps=False, up=(0, 1, 0))
        b.m("MAT_Metal", 0.9, 1.0)
        b.stitch([oi[-1], ii[-1][::-1]], CarChrome)
        b.m("MAT_Metal", 0.1, 0.0)
        b.rbox(P(x, base + 0.004, z0 + 0.05), H(0.042, 0.004, 0.057), 0.003, 1, Dark)
        b.m("MAT_Metal", 0.6, 0.9)
        b.rbox(P(x, base + 0.02, z0 + 0.05), H(0.038, 0.0025, 0.009), 0.002, 1, C("#9AA3AB"), rot=(0, 0, 0))
        b.cyl(P(x - 0.042, base + 0.02, z0 + 0.05), P(x + 0.042, base + 0.02, z0 + 0.05), 0.003, 8, C("#9AA3AB"))
    b.m("MAT_Metal", 0.6, 0.8)
    for s in (-1, 1):
        b.tube(catmull([P(s * 0.13, hy + 0.3, z0 - 0.05), P(s * 0.2, hy + 0.27, z0 - 0.1), P(s * 0.25, hy + 0.12, z0 - 0.2),
                        P(s * 0.27, hy + 0.04, z0 - 0.26)], 6), 0.007, 10, shade(CarSteel, 0.8))
        b.m("MAT_CarPaint", 0.7, 0.25)
        b.cyl(P(s * 0.128, hy + 0.3, z0 - 0.05), P(s * 0.15, hy + 0.296, z0 - 0.06), 0.011, 6, CarAccent)
        b.m("MAT_Metal", 0.6, 0.8)


# ------------------------------------------------------------------ side pipes
def pipes(b):
    for s in (-1, 1):
        with b.at((0, 0, 0), None, (s, 1, 1)):
            pts = [P(0.84, 0.64, 1.06), P(0.97, 0.57, 0.96), P(1.05, 0.46, 0.8), P(1.075, 0.37, 0.6), P(1.075, 0.37, 0.0), P(1.08, 0.37, -0.84)]
            path = catmull(pts[:4], 10) + [P(1.075, 0.37, z) for z in (0.45, 0.3, 0.15, 0.0, -0.2, -0.4, -0.6)] + [P(1.08, 0.37, -0.845)]
            heat = C("#8D7F6E")

            def pc(i, j, n=len(path)):
                t = min(1.0, i / 18.0)
                return (mixc(heat, CarPipe, t), "MAT_Metal", (0.6, 0.85))
            b.m("MAT_Metal", 0.6, 0.85)
            b.sweep(path, circle(0.07, 24), CarPipe, up=(0, 0, 1), colfn=pc)
            # header flange where it leaves the fender, clamps
            b.m("MAT_Metal", 0.45, 0.7)
            d = (Vector(path[1]) - Vector(path[0])).normalized()
            c0 = Vector(path[0]) + d * 0.02
            b.cyl(tuple(c0 - d * 0.012), tuple(c0 + d * 0.012), 0.098, 24, shade(CarSteel, 0.6), fillet_r=0.004)
            for k in range(4):
                a = TAU * (k + 0.5) / 4
            for zc in (0.52, -0.66):
                with b.at(P(1.075, 0.37, zc), (-90, 0, 0)):
                    b.lathe(fillet([(0.068, -0.014), (0.079, -0.014), (0.079, 0.014), (0.068, 0.014)], [0, 0.003, 0.003, 0], 2), 32,
                            shade(CarSteel, 0.75), closed_prof=True)
                    b.rbox((0.0, -0.083, 0.0), (0.012, 0.012, 0.012), 0.003, 1, shade(CarSteel, 0.75))
            # slotted heat shield: half shell on the outer side with the open side toward the body
            b.m("MAT_Metal", 0.45, 0.7)
            holes = [(8, 16, 0.0, 0.84)]
            for kc in (22, 1):
                z = 0.06
                while z + 0.05 < 0.8:
                    holes.append((kc - 1, kc + 1, round(z, 4), round(z + 0.05, 4)))
                    z += 0.085
            with b.at(P(1.0775, 0.37, -0.46), (-90, 0, 0)):
                b.perf_tube(0.0, 0.84, 0.092, 0.004, 24, holes, C("#7E868E"), shade(C("#7E868E"), 0.45))
            for zc in (-0.36, 0.26):
                b.rbox(P(1.0775, 0.37 + 0.094, zc), H(0.03, 0.006, 0.02), 0.003, 1, shade(CarSteel, 0.5))
            # tip: rolled chrome rim, dark recessed bore
            with b.at(P(1.08, 0.37, -0.84), (90, 0, 0)):
                b.m("MAT_Metal", 0.9, 1.0)
                b.lathe([(0.06, -0.02), (0.074, -0.02), (0.078, -0.006), (0.077, 0.004), (0.07, 0.012), (0.062, 0.01), (0.06, 0.0)],
                        32, CarChrome, closed_prof=True)
                b.m("MAT_Metal", 0.1, 0.0)
                b.lathe([(0.06, 0.004), (0.06, -0.09), (0.0, -0.09)], 24, C("#0E0D0D"))
            # hangers up to the sill
            b.m("MAT_Metal", 0.4, 0.6)
            for zc in (0.2, -0.5):
                b.rbox(P(1.04, 0.42, zc), H(0.045, 0.012, 0.018), 0.005, 2, shade(CarSteel, 0.5), rot=(0, -35, 0))


# ------------------------------------------------------------------ bed (planks, stakes, tie-downs, tailgate inner ribs)
def bed(b):
    y0, y1 = BedFloorY - 0.0255, BedFloorY          # planks sit on the floor 25 mm below the deck line
    zr, zfr = BedRearZ + 0.006, BedFrontZ - 0.006
    b.m("MAT_Wood", 0.12, 0.0)
    edges = [0.0, 0.117, 0.234, 0.351, 0.468, 0.585]
    k = 0
    for s in (-1, 1):
        for i in range(5):
            xa, xb = edges[i] + 0.003, edges[i + 1] - 0.003
            col = BedWoodA if (i + (s > 0)) % 2 == 0 else BedWoodB
            col = shade(col, 0.93 + 0.12 * hash01(i * 7 + (s > 0) * 13))
            xc = s * (xa + xb) / 2
            # some boards are two pieces with a butt joint
            if hash01(i * 3 + (s > 0) * 5 + 1) > 0.55:
                zj = -1.1 - 0.7 * hash01(i * 11 + (s > 0))
                parts = [(zr, zj - 0.002), (zj + 0.002, zfr)]
            else:
                parts = [(zr, zfr)]
            for (za, zb) in parts:
                b.rbox(P(xc, (y0 + y1) / 2, (za + zb) / 2), H((xb - xa) / 2, (y1 - y0) / 2, (zb - za) / 2), 0.0045, 1, col, flat=(1, 3, 1))
                b.m("MAT_Metal", 0.4, 0.6)
                for zz in (za + 0.03, zb - 0.03):
                    for dx in (-0.032, 0.032):
                        b.cyl(P(xc + dx, y1 - 0.001, zz), P(xc + dx, y1 + 0.0025, zz), 0.0065, 8, shade(Bolt, 0.6))
                b.m("MAT_Wood", 0.12, 0.0)
            k += 1
        # outermost narrow board (stops where the walls round in at the tailgate)
        b.rbox(P(s * 0.629, (y0 + y1) / 2, (-1.98 + zfr) / 2), H(0.041, (y1 - y0) / 2, (zfr + 1.98) / 2), 0.0045, 1, BedWoodEdge, flat=(1, 3, 1))
    # stakes on the inner walls
    b.m("MAT_CarPaint", 0.45, 0.1)
    for z in (-0.98, -1.3, -1.62, -1.94):
        xi = BedInnerHalf(z)
        for s in (-1, 1):
            hh = (BedRailY - BedFloorY - 0.04) / 2
            b.rbox(P(s * (xi - 0.012), BedFloorY + 0.02 + hh, z), H(0.013, hh, 0.0225), 0.007, 2, CarPaintC)
            b.m("MAT_Metal", 0.85, 1.0)
            for yy in (0.68, 0.9):
                bolt_head(b, P(s * (xi - 0.025), yy, z), (-s, 0, 0), 0.006, 0.004)
            b.m("MAT_CarPaint", 0.45, 0.1)
    # tie-down rings
    b.m("MAT_Metal", 0.7, 0.9)
    for z in (-0.84, -2.06):
        xi = BedInnerHalf(z)
        for s in (-1, 1):
            b.rbox(P(s * (xi - 0.004), 0.69, z), H(0.004, 0.025, 0.03), 0.003, 1, shade(CarSteel, 0.7))
            torus(b, P(s * (xi - 0.012), 0.672, z), 0.022, 0.005, 20, 6, CarSteel, rot=(0, 90, 0))
    # tailgate inner face: two pressed ribs, latch handles at the top corners
    b.m("MAT_CarPaint", 0.4, 0.0)
    zt = BedRearZ + 0.006
    for y in (0.73, 0.86):
        b.rbox(P(0, y, zt), H(0.52, 0.018, 0.008), 0.008, 2, shade(BedWall, 1.12))
    b.m("MAT_Metal", 0.7, 0.9)
    for s in (-1, 1):
        b.rbox(P(s * 0.5, 0.955, zt + 0.004), H(0.045, 0.012, 0.012), 0.006, 2, CarSteel)
    # tailgate support cables
    b.m("MAT_Metal", 0.6, 0.9)
    for s in (-1, 1):
        xi = BedInnerHalf(-2.12)
        b.tube(catmull([P(s * (xi - 0.004), 0.93, -2.05), P(s * (xi - 0.008), 0.9, -2.11), P(s * (xi - 0.01), 0.935, BedRearZ + 0.01)], 6),
               0.004, 6, CarSteel)


# ------------------------------------------------------------------ rear outer face
def rear(b):
    zr = CarZRear + 0.02
    b.m("MAT_CarPaint", 0.78, 0.0)
    b.rbox(P(0, 0.735, zr - 0.006), H(0.62, 0.205, 0.008), 0.008, 3, CarPaintC)
    b.rbox(P(0, 0.905, zr - 0.0145), H(0.5, 0.006, 0.0025), 0.0025, 1, shade(CarPaintC, 0.8))
    b.m("MAT_CarPaint", 0.35, 0.0)
    for sx in (-1, 1):
        b.rbox(P(sx * 0.47, 0.79, zr - 0.018), H(0.135, 0.115, 0.012), 0.022, 3, CarTrim)
    for x in (-0.53, -0.41, 0.41, 0.53):
        b.m("MAT_Metal", 0.9, 1.0)
        b.rbox(P(x, 0.79, zr - 0.03), H(0.042, 0.092, 0.005), 0.01, 2, CarChrome)
        b.m("MAT_Glass", 0.7, 0.0)
        red = glow(C("#F0412E"), 0.4)
        b.rbox(P(x, 0.79, zr - 0.036), H(0.036, 0.085, 0.006), 0.009, 2, red)
        for k in range(6):
            y = 0.725 + k * 0.026
            b.rbox(P(x, y, zr - 0.043), H(0.033, 0.0035, 0.003), 0.002, 1, glow(C("#C9301F"), 0.45))
    # badge, handle, licence plate
    with b.at(P(0, 0.8, zr - 0.014), (90, 0, 0)):
        b.m("MAT_Metal", 0.95, 1.0)
        b.lathe(fillet([(0, 0), (0.058, 0), (0.058, 0.012), (0.05, 0.02), (0, 0.02)], [0, 0.002, 0.004, 0.002, 0], 2), 36, CarChrome)
        b.m("MAT_CarPaint", 0.7, 0.25)
        b.lathe([(0, 0.019), (0.034, 0.019), (0.034, 0.024), (0, 0.025)], 28, CarAccent)
    b.m("MAT_Metal", 0.9, 1.0)
    b.rbox(P(0, 0.68, zr - 0.02), H(0.09, 0.012, 0.01), 0.008, 2, CarChrome)
    b.m("MAT_CarPaint", 0.3, 0.0)
    b.rbox(P(0, 0.68, zr - 0.012), H(0.1, 0.022, 0.003), 0.004, 1, Dark)
    b.m("MAT_CarPaint", 0.5, 0.3)
    b.rbox(P(0, 0.585, zr - 0.016), H(0.15, 0.065, 0.004), 0.008, 2, C("#D9CBA8"))
    b.m("MAT_CarPaint", 0.4, 0.0)
    for k in range(4):
        b.rbox(P(-0.09 + k * 0.06, 0.585, zr - 0.021), H(0.019, 0.032, 0.0025), 0.002, 1, C("#2A2522"))
    b.m("MAT_Metal", 0.85, 1.0)
    for (x, y) in ((-0.12, 0.63), (0.12, 0.63), (-0.12, 0.54), (0.12, 0.54)):
        bolt_head(b, P(x, y, zr - 0.02), (0, 0, -1), 0.006, 0.004, hexa=False)
    # bumper, brackets, rubber end caps, hitch receiver with a ball
    b.m("MAT_Metal", 0.9, 1.0)
    path = []
    for i in range(41):
        t = i / 40 * 2 - 1
        path.append(P(t * 0.86, 0.48, CarZRear - 0.06 + abs(t) ** 5 * 0.28))
    b.sweep(path, rrect(0.12, 0.1, 0.036, 5), CarChrome, up=(0, 0, 1))
    b.m("MAT_Metal", 0.45, 0.7)
    for s in (-1, 1):
        b.rbox(P(s * 0.45, 0.48, CarZRear - 0.005), H(0.035, 0.03, 0.05), 0.01, 2, shade(CarSteel, 0.55))
    b.m("MAT_Metal", 0.4, 0.6)
    b.rbox(P(0, 0.4, CarZRear - 0.03), H(0.032, 0.032, 0.07), 0.006, 2, shade(CarSteel, 0.45))
    b.cyl(P(-0.045, 0.4, CarZRear - 0.07), P(0.045, 0.4, CarZRear - 0.07), 0.006, 10, CarSteel)
    b.m("MAT_Metal", 0.9, 1.0)
    b.rbox(P(0, 0.425, CarZRear - 0.105), H(0.03, 0.006, 0.03), 0.004, 1, CarChrome)
    b.cyl(P(0, 0.43, CarZRear - 0.115), P(0, 0.46, CarZRear - 0.115), 0.012, 12, CarChrome)
    b.ellipsoid(P(0, 0.475, CarZRear - 0.115), H(0.024, 0.024, 0.024), CarChrome, 20, 10)


# ------------------------------------------------------------------ sides: mirrors, handles, hinges, filler, flares
def sides(b):
    for s in (-1, 1):
        with b.at((0, 0, 0), None, (s, 1, 1)):
            # mirror on the door top
            b.m("MAT_CarPaint", 0.6, 0.0)
            b.rbox(P(0.762, 1.0, 0.43), H(0.02, 0.012, 0.04), 0.008, 2, CarTrim)
            b.m("MAT_Metal", 0.85, 1.0)
            b.tube(catmull([P(0.768, 1.008, 0.43), P(0.84, 1.05, 0.44), P(0.89, 1.07, 0.44)], 6), 0.007, 10, CarChrome)
            b.m("MAT_CarPaint", 0.78, 0.0)
            b.rbox(P(0.94, 1.08, 0.445), H(0.068, 0.046, 0.02), 0.016, 3, CarPaintC, rot=(0, 0, -8))
            b.m("MAT_Glass", 0.95, 0.6)
            b.rbox(P(0.94, 1.08, 0.424), H(0.058, 0.037, 0.003), 0.008, 2, C("#A7B4BC"), rot=(0, 0, -8))
            # door handle: chrome pull over a dark dish
            z, y = -0.33, 0.86
            x = pb_side = side_x(z, y)
            b.m("MAT_CarPaint", 0.3, 0.0)
            b.rbox(P(x + 0.001, y, z), H(0.004, 0.022, 0.06), 0.004, 1, Dark)
            b.m("MAT_Metal", 0.92, 1.0)
            b.rbox(P(x + 0.011, y + 0.004, z), H(0.008, 0.011, 0.055), 0.006, 2, CarChrome)
            b.rbox(P(x + 0.006, y + 0.004, z + 0.05), H(0.006, 0.008, 0.008), 0.003, 1, CarChrome)
            b.cyl(P(x + 0.005, y + 0.004, z - 0.04), P(x + 0.012, y + 0.004, z - 0.04), 0.008, 12, shade(CarChrome, 0.8))
            # door hinge knuckles at the front seam
            b.m("MAT_Metal", 0.6, 0.8)
            for yy in (0.62, 0.84):
                xx = side_x(0.535, yy)
                b.cyl(P(xx + 0.004, yy - 0.04, 0.535), P(xx + 0.004, yy + 0.04, 0.535), 0.012, 12, shade(CarSteel, 0.6), fillet_r=0.003)
                b.rbox(P(xx, yy, 0.515), H(0.006, 0.03, 0.02), 0.004, 1, shade(CarSteel, 0.6))
            # fuel filler (right side only in the game's sense; both sides here would mirror -> right only)
            if s > 0:
                z, y = -1.18, 0.82
                x = side_x(z, y)
                with b.at(P(x, y, z), (0, 90, 0)):
                    b.m("MAT_Metal", 0.9, 1.0)
                    b.lathe(fillet([(0.0, -0.004), (0.05, -0.004), (0.05, 0.006), (0.042, 0.012), (0.0, 0.012)], [0, 0.002, 0.003, 0.003, 0], 2), 28, CarChrome)
                    b.lathe(fillet([(0.0, 0.011), (0.03, 0.011), (0.03, 0.022), (0.0, 0.024)], [0, 0, 0.004, 0], 2), 20, shade(CarChrome, 0.85))
            # bolted fender flares round both wheels (arcs about the axle, set over the skin)
            for (axle, R) in ((cs.CarFrontAxleZ, cs.CarFrontWheelR), (cs.CarRearAxleZ, cs.CarRearWheelR)):
                yc = R
                r_in, r_out = R + 0.045, R + 0.118
                n = 30
                rows = []
                prof = rrect(0.06, r_out - r_in, 0.012, 2)
                for k in range(n + 1):
                    th = math.radians(14 + (180 - 28) * k / n)
                    zz = axle + math.cos(th) * (r_in + r_out) / 2
                    yy = yc + math.sin(th) * (r_in + r_out) / 2
                    xs = max(side_x(zz, min(yy, 0.86)), 0.6)
                    radial = Vector((0, math.cos(th), math.sin(th)))          # Blender (x, fwd, up)
                    centre = Vector(P(xs + 0.012, yy, zz))
                    row = []
                    for (px, py) in prof:
                        row.append(tuple(centre + Vector((px, 0, 0)) + radial * py))
                    rows.append(row)
                b.m("MAT_CarPaint", 0.55, 0.1)
                idx = b.grid(rows, CarPaintLow, cv=True)
                for end, k in ((0, 0), (len(rows) - 1, 1)):
                    ring = idx[end]
                    cen = sum((Vector(rows[end][j]) for j in range(len(prof))), Vector()) / len(prof)
                    ci = b.vs([tuple(cen)])[0]
                    th = math.radians(14 if k == 0 else 166)
                    tdir = Vector((0, -math.sin(th), math.cos(th))) * (-1 if k == 0 else 1)
                    for j in range(len(ring)):
                        b.face_out([ci, ring[j], ring[(j + 1) % len(ring)]], ("d", tuple(tdir)), col=CarPaintLow)
                b.m("MAT_Metal", 0.85, 1.0)
                for k in range(9):
                    th = math.radians(24 + 132 * k / 8)
                    zz = axle + math.cos(th) * (r_in + r_out) / 2
                    yy = yc + math.sin(th) * (r_in + r_out) / 2
                    xs = max(side_x(zz, min(yy, 0.86)), 0.6)
                    bolt_head(b, P(xs + 0.042, yy, zz), (1, 0, 0), 0.0075, 0.005)


# ------------------------------------------------------------------ cowl wipers, roof drip rails
def cowl_roof(b):
    for s in (-1, 1):
        px = s * 0.36 if s > 0 else -0.02
        z = 0.535
        y = CabinRoofY(z) + 0.008
        slope = math.atan2(CabinRoofY(z - 0.02) - CabinRoofY(z + 0.02), 0.04)
        b.m("MAT_Metal", 0.4, 0.6)
        b.cyl(P(px, y - 0.012, z + 0.012), P(px, y + 0.008, z + 0.012), 0.012, 12, CarTrim, fillet_r=0.003)
        with b.at(P(px - 0.17, y + 0.004, z), (-math.degrees(slope), 0, 0)):
            b.rbox((0, 0, 0), (0.17, 0.006, 0.004), 0.003, 1, CarTrim)
            b.m("MAT_Rubber", 0.2, 0.0)
            b.rbox((0.0, -0.012, 0.004), (0.2, 0.004, 0.006), 0.003, 1, CarRubber)
    # drip rails along the roof edges
    b.m("MAT_Metal", 0.85, 1.0)
    for s in (-1, 1):
        path = []
        z = 0.12
        while z >= -0.62:
            ring = pb.cab_ring(z)
            p = ring[12]
            q = ring[13]
            nx, ny = (q[1] - ring[11][1]), -(q[0] - ring[11][0])
            L = math.hypot(nx, ny) or 1
            path.append(P(s * (p[0] + nx / L * 0.004), p[1] + ny / L * 0.004, z))
            z -= 0.04
        b.tube(path, 0.0055, 8, shade(CarChrome, 0.9))


def build():
    b = MB("MAT_CarPaint")
    front(b)
    blower(b)
    pipes(b)
    bed(b)
    rear(b)
    sides(b)
    cowl_roof(b)
    return b
