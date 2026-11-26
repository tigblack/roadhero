"""Hood gun, DetailedCar pass: ~1.85x the v10 M249 (0.78 m -> 1.44 m), raised so the barrel clears the blower
and the cab roof in every yaw at rest pitch.

Spaces (Blender, metres; +Y forward, +Z up, +X right), all origins as in the game rig:
  HoodMount   TurretBase space: plate-top centre on the hood (fixed)
  Turntable   TurretYaw space: same origin, turns about +Z (yaw)
  GunCradle   TurretPitch space: trunnion axis = X, at z = PITCH_Z above the plate (pitch, no recoil)
  GunMesh     Barrel0 space: same origin as TurretPitch, recoils along -Y; bore axis at z = BY, muzzle at y = MUZZLE_Y
"""
import math

import carshape as cs
from mb import MB, C, TAU, fillet, rrect, shade

GunMetal, GunPolymer, GunBarrel = C("#646C74"), C("#222527"), C("#7A838B")
GunSteel, GunBore, GunPlate = C("#D2D8DD"), C("#0B0B0C"), C("#8A939B")
Accent = C("#5FAEE8")            # tier-1 (level 5) accent, as on the exported v10 car
Jacket = C("#A3ACB4")            # light steel: the jacket reads as a bright line on the graphite hood
JacketIn = C("#24272A")
Olive = C("#5A5D41")
Yoke = C("#555C63")

BY = 0.055            # bore axis above the trunnion
MUZZLE_Y = 1.02       # muzzle face ahead of the trunnion
PITCH_Z = 0.363       # trunnion above the plate top  -> bore at ~1.42 m over the ground
RECOIL = 0.05         # recoil travel along -Y (m)


def _along_y(b, y, z=BY, x=0.0, spin=0.0):
    """Frame whose local Z runs along +Y (lathes / tubes on the bore axis). Local X = world X."""
    return b.at((x, y, z), (-90, 0, spin))


def gun_mesh():
    b = MB("MAT_Metal", 0.45, 0.6)
    # ---------------- receiver: long box, feed cover + hinge, latch, rear sight, ribs, rivets, port, charging handle
    b.rbox((0, -0.065, 0.0275), (0.068, 0.235, 0.0875), 0.014, 2, GunMetal, flat=(1, 3, 1))
    b.rbox((0, -0.05, 0.1265), (0.060, 0.15, 0.0125), 0.008, 2, shade(GunMetal, 1.16))
    for x0, x1 in ((-0.058, -0.022), (0.022, 0.058)):
        b.cyl((x0, 0.101, 0.126), (x1, 0.101, 0.126), 0.0085, 12, shade(GunMetal, 0.9), fillet_r=0.002)
    b.rbox((0, -0.207, 0.133), (0.022, 0.009, 0.012), 0.004, 2, GunSteel)
    b.rbox((0, -0.17, 0.152), (0.013, 0.012, 0.014), 0.004, 2, GunMetal)
    b.cyl((0, -0.176, 0.164), (0, -0.164, 0.164), 0.009, 12, shade(GunMetal, 0.8))
    for s in (-1, 1):
        for z in (0.095, -0.04):
            b.rbox((s * 0.0695, -0.185, z), (0.004, 0.095, 0.006), 0.003, 1, shade(GunMetal, 1.08))
    b.m(gloss=0.85, metal=1.0)
    for s in (-1, 1):
        for y in (-0.27, -0.215, 0.11, 0.155):
            for z in (-0.035, 0.085):
                b.ellipsoid((s * 0.0685, y, z), (0.0055, 0.0055, 0.0055), GunSteel, 10, 5)
    b.m(gloss=0.1, metal=0.0)
    b.rbox((0.0688, -0.135, 0.04), (0.0015, 0.045, 0.019), 0.003, 1, GunBore)          # ejection port (right)
    b.m(gloss=0.5, metal=0.7)
    b.rbox((0.0712, -0.135, 0.066), (0.0022, 0.047, 0.005), 0.002, 1, shade(GunMetal, 1.2))
    b.m(gloss=0.85, metal=1.0)
    b.cyl((0.066, -0.245, 0.04), (0.098, -0.245, 0.04), 0.0065, 10, GunSteel, fillet_r=0.002)
    b.ellipsoid((0.102, -0.245, 0.04), (0.011, 0.013, 0.013), GunSteel, 14, 7)
    b.m(gloss=0.45, metal=0.6)
    b.rbox((-0.077, -0.055, 0.078), (0.011, 0.055, 0.03), 0.006, 2, shade(GunMetal, 0.85))   # left feed guide
    b.m(gloss=0.1, metal=0.0)
    b.rbox((-0.0885, -0.055, 0.082), (0.0012, 0.04, 0.012), 0.002, 1, GunBore)

    # ---------------- back plate, buffer, spade grips, butterfly trigger
    b.m("MAT_Metal", 0.45, 0.6)
    b.rbox((0, -0.3125, 0.03), (0.07, 0.0125, 0.0925), 0.008, 2, shade(GunMetal, 0.9))
    with _along_y(b, -0.36):
        b.lathe(fillet([(0, 0), (0.03, 0), (0.03, 0.04), (0, 0.04)], [0, 0.006, 0.004, 0], 2), 20, shade(GunMetal, 0.95))
    b.m(gloss=0.85, metal=1.0)
    for s in (-1, 1):
        b.tube([(s * 0.05, -0.325, 0.095), (s * 0.055, -0.36, 0.1), (s * 0.058, -0.395, 0.088)], 0.0085, 10, GunSteel)
        b.tube([(s * 0.05, -0.325, -0.045), (s * 0.055, -0.36, -0.058), (s * 0.058, -0.395, -0.058)], 0.0085, 10, GunSteel)
    b.m("MAT_Rubber", 0.25, 0.0)
    for s in (-1, 1):
        b.cyl((s * 0.058, -0.405, -0.07), (s * 0.058, -0.405, 0.1), 0.017, 16, GunPolymer, fillet_r=0.006)
        for z in (-0.04, -0.005, 0.03, 0.065):
            with b.at((s * 0.058, -0.405, z)):
                b.lathe([(0.0165, -0.004), (0.0172, -0.004), (0.0186, 0.0), (0.0172, 0.004), (0.0165, 0.004)], 16,
                        shade(GunPolymer, 1.35), closed_prof=True)
    b.m("MAT_Metal", 0.85, 1.0)
    b.rbox((0, -0.398, 0.015), (0.045, 0.005, 0.018), 0.004, 2, GunSteel)

    # ---------------- barrel support collar and notched ring nut at the receiver's front
    b.m("MAT_Metal", 0.45, 0.6)
    with _along_y(b, 0.165):
        b.lathe(fillet([(0, 0), (0.063, 0), (0.063, 0.07), (0, 0.07)], [0, 0.006, 0.006, 0], 2), 40, GunMetal)
    with _along_y(b, 0.235):
        b.lathe(fillet([(0, 0), (0.068, 0), (0.068, 0.024), (0, 0.024)], [0, 0.004, 0.004, 0], 2), 40, shade(GunMetal, 1.12))
        for k in range(8):
            a = TAU * (k + 0.5) / 8
            b.rbox((0.069 * math.cos(a), 0.069 * math.sin(a), 0.012), (0.006, 0.005, 0.011), 0.002, 1,
                   shade(GunMetal, 0.85), rot=(0, 0, math.degrees(a)))

    # ---------------- perforated cooling jacket (real through-slots), clamp rings, inner barrel
    J0, J1 = 0.257, 0.632
    JL = J1 - J0
    rings = [(0.0025, 0.022), (0.17, 0.2), (0.352, JL - 0.0025)]
    holes = []
    segs = 48
    for row, kc in enumerate((4, 12, 20, 28, 36, 44)):
        z = 0.035 + (0.0 if row % 2 == 0 else 0.03)
        while z + 0.042 < JL - 0.025:
            za, zb = round(z, 4), round(z + 0.042, 4)
            if all(zb + 0.008 < r0 or za - 0.008 > r1 for (r0, r1) in rings):
                holes.append((kc - 1, kc + 1, za, zb))
            z += 0.06
    b.m("MAT_Metal", 0.6, 0.85)
    with _along_y(b, J0):
        b.perf_tube(0.0, JL, 0.056, 0.0045, segs, holes, Jacket, JacketIn)
        b.m(gloss=0.5, metal=0.8)
        for (r0, r1) in rings:
            b.lathe(fillet([(0.049, r0), (0.0605, r0), (0.0605, r1), (0.049, r1)], [0, 0.003, 0.003, 0], 2), 48,
                    shade(GunMetal, 1.05), closed_prof=True)
        b.rbox((0, 0.066, 0.185), (0.012, 0.012, 0.016), 0.003, 1, shade(GunMetal, 1.05))   # clamp lug (underside)
    b.m(gloss=0.85, metal=1.0)
    b.cyl((-0.015, 0.185 + J0, BY - 0.07), (0.015, 0.185 + J0, BY - 0.07), 0.0055, 6, GunSteel)
    b.m(gloss=0.4, metal=0.85)
    with _along_y(b, 0.235):
        b.lathe([(0, 0), (0.031, 0), (0.031, J1 - 0.235 + 0.02), (0, J1 - 0.235 + 0.02)], 24, shade(GunBarrel, 0.6))
    b.m("MAT_Metal", 0.6, 0.85)
    with _along_y(b, J1 - 0.002):
        b.lathe(fillet([(0, 0), (0.0565, 0), (0.0565, 0.006), (0.04, 0.02), (0, 0.02)], [0, 0.002, 0.004, 0.002, 0], 2), 48, Jacket)

    # ---------------- exposed barrel: stepped profile, gas block + front sight, gas tube
    b.m("MAT_Metal", 0.55, 0.85)
    B0 = J1 + 0.012
    prof = [(0, 0), (0.0365, 0), (0.0365, 0.04), (0.0325, 0.048), (0.0325, 0.105), (0.0305, 0.11), (0.0305, 0.275), (0, 0.275)]
    with _along_y(b, B0):
        b.lathe(fillet(prof, [0, 0.003, 0.004, 0.004, 0.003, 0.003, 0.002, 0], 2), 40, GunBarrel)
    b.m(gloss=0.45, metal=0.6)
    with _along_y(b, 0.74):
        b.lathe(fillet([(0, 0), (0.046, 0), (0.046, 0.05), (0, 0.05)], [0, 0.006, 0.006, 0], 2), 40, GunMetal)
    b.rbox((0, 0.765, BY + 0.062), (0.006, 0.012, 0.022), 0.003, 1, GunMetal)
    for s in (-1, 1):
        b.rbox((s * 0.014, 0.765, BY + 0.056), (0.0035, 0.013, 0.016), 0.002, 1, GunMetal)
    b.rbox((0, 0.765, BY - 0.058), (0.013, 0.02, 0.016), 0.004, 2, GunMetal)
    b.m(gloss=0.55, metal=0.85)
    b.cyl((0, 0.262, BY - 0.074), (0, 0.775, BY - 0.074), 0.011, 14, GunBarrel, fillet_r=0.003)

    # ---------------- muzzle brake: chamber with side + top ports, chamfered face, deep dark bore
    M0 = 0.905
    b.m("MAT_Metal", 0.82, 1.0)
    with _along_y(b, M0):
        b.lathe(fillet([(0, -0.004), (0.036, -0.004), (0.05, 0.012), (0.05, 0.02), (0, 0.02)], [0, 0.003, 0.004, 0, 0], 2), 32, GunSteel)
        # spin 90deg: tube index 24 = right (+X), 8 = left, 16 = top
        with b.at((0, 0, 0), (0, 0, 90)):
            ports = []
            for za in (0.026, 0.05, 0.074):
                ports.append((22, 26, za, round(za + 0.016, 4)))
                ports.append((6, 10, za, round(za + 0.016, 4)))
            for za in (0.034, 0.062):
                ports.append((15, 17, za, round(za + 0.014, 4)))
            b.perf_tube(0.018, 0.1, 0.05, 0.011, 32, ports, GunSteel, GunBore)
        b.lathe([(0.022, 0.098), (0.05, 0.098), (0.05, 0.108), (0.0455, 0.115), (0.03, 0.115), (0.0215, 0.106)],
                48, GunSteel, closed_prof=True)
        b.m(gloss=0.1, metal=0.0)
        b.lathe([(0.0215, 0.03), (0.032, 0.03), (0.032, 0.098), (0.0215, 0.098)], 24, GunBore, closed_prof=True)
        b.lathe([(0.0, 0.035), (0.0216, 0.035), (0.0216, 0.04), (0.0, 0.04)], 24, GunBore)
    return b


def cradle_mesh():
    """Pitch part: trunnion pin, cheeks, tray, ammo can on the pin's left end, belt chute into the feed guide."""
    b = MB("MAT_Metal", 0.85, 1.0)
    b.cyl((-0.136, 0, 0), (0.136, 0, 0), 0.019, 20, GunSteel, fillet_r=0.004)
    for s in (-1, 1):
        b.cyl((s * 0.127, 0, 0), (s * 0.141, 0, 0), 0.026, 6, shade(GunSteel, 0.85), fillet_r=0.002)
    b.m("MAT_Metal", 0.45, 0.6)
    for s in (-1, 1):
        b.rbox((s * 0.077, 0.0, -0.012), (0.007, 0.08, 0.05), 0.005, 2, Yoke)
        b.cyl((s * 0.071, 0, 0), (s * 0.0855, 0, 0), 0.03, 24, shade(Yoke, 1.1), fillet_r=0.003)
    b.rbox((0, -0.02, -0.071), (0.084, 0.16, 0.009), 0.004, 2, Yoke)
    # ammo can (painted olive steel) hanging on the pin's left end
    b.m("MAT_CarPaint", 0.3, 0.2)
    cx, cy, cz = -0.193, -0.03, -0.02
    b.rbox((cx, cy, cz), (0.052, 0.11, 0.08), 0.008, 2, Olive)
    b.rbox((cx, cy, cz + 0.083), (0.054, 0.112, 0.006), 0.004, 2, shade(Olive, 1.12))
    for y in (-0.06, 0.0, 0.06):
        b.rbox((cx - 0.0525, cy + y, cz - 0.01), (0.0025, 0.012, 0.055), 0.002, 1, shade(Olive, 0.92))
    b.m("MAT_Metal", 0.7, 0.9)
    b.rbox((cx - 0.054, cy + 0.075, cz + 0.07), (0.004, 0.012, 0.02), 0.003, 1, GunSteel)
    b.tube([(cx - 0.02, cy - 0.04, cz + 0.089), (cx - 0.02, cy - 0.04, cz + 0.104), (cx - 0.02, cy + 0.04, cz + 0.104),
            (cx - 0.02, cy + 0.04, cz + 0.089)], 0.0045, 8, GunSteel)
    b.m("MAT_Metal", 0.45, 0.6)
    b.rbox((-0.1405, 0.0, -0.005), (0.004, 0.035, 0.04), 0.003, 1, Yoke)
    # belt chute: from the can's top over the yoke into the receiver's feed guide (belt-wide along Y)
    path = [(-0.17, -0.055, 0.058), (-0.166, -0.055, 0.1), (-0.142, -0.055, 0.127), (-0.11, -0.055, 0.13),
            (-0.092, -0.055, 0.113), (-0.085, -0.055, 0.097)]
    b.m("MAT_Rubber", 0.35, 0.1)
    b.sweep(path, rrect(0.074, 0.028, 0.006, 2), shade(GunPolymer, 1.4), up=(0, 1, 0))
    return b


def turntable_mesh():
    """Yaw part: bearing race with tier band, deck with bolts, tapered pedestal, gussets, yoke and trunnion bosses."""
    b = MB("MAT_Metal", 0.5, 0.6)
    b.lathe(fillet([(0.06, 0.0), (0.142, 0.0), (0.142, 0.026), (0.136, 0.032), (0.06, 0.032)], [0, 0.002, 0.003, 0.002, 0], 2),
            56, GunMetal, closed_prof=True)
    b.m(gloss=0.6, metal=0.3)
    b.lathe([(0.141, 0.009), (0.1438, 0.011), (0.1438, 0.021), (0.141, 0.023)], 56, Accent, closed_prof=True)
    b.m(gloss=0.5, metal=0.6)
    b.lathe(fillet([(0, 0.03), (0.128, 0.03), (0.128, 0.05), (0.118, 0.058), (0, 0.058)], [0, 0.002, 0.004, 0.004, 0], 2), 56, shade(GunMetal, 1.08))
    b.m(gloss=0.85, metal=1.0)
    for k in range(10):
        a = TAU * (k + 0.5) / 10
        x, y = 0.105 * math.cos(a), 0.105 * math.sin(a)
        b.cyl((x, y, 0.056), (x, y, 0.064), 0.008, 6, GunSteel, fillet_r=0.0015)
    b.m(gloss=0.5, metal=0.6)
    b.lathe(fillet([(0, 0.055), (0.08, 0.055), (0.072, 0.082), (0.06, 0.24), (0.0, 0.24)], [0, 0.004, 0.025, 0.0, 0], 3), 40, GunMetal)
    b.lathe([(0.058, 0.15), (0.0675, 0.152), (0.0675, 0.168), (0.058, 0.17)], 40, Accent, closed_prof=True)
    for k in range(4):
        with b.at((0, 0, 0), (0, 0, 45 + 90 * k)):
            b.prism([(0.06, 0.058), (0.118, 0.058), (0.118, 0.07), (0.062, 0.2)], 0.012, shade(GunMetal, 0.95))
    b.rbox((0, 0, 0.25), (0.122, 0.058, 0.02), 0.009, 2, Yoke)
    for s in (-1, 1):
        b.rbox((s * 0.1, 0, 0.3), (0.012, 0.042, 0.068), 0.006, 2, Yoke)
        b.cyl((s * 0.088, 0, PITCH_Z), (s * 0.124, 0, PITCH_Z), 0.034, 32, shade(Yoke, 1.08), fillet_r=0.004)
        b.m(gloss=0.85, metal=1.0)
        b.cyl((s * 0.1, 0, PITCH_Z + 0.03), (s * 0.1, 0, PITCH_Z + 0.046), 0.004, 8, GunSteel)
        b.m(gloss=0.5, metal=0.6)
        b.tube([(s * 0.1, 0.0, 0.236), (s * 0.108, 0.0, 0.15), (s * 0.112, 0.0, 0.062)], 0.009, 12, shade(Yoke, 0.95))
    return b


def mount_mesh(base_world=(cs.GunX, cs.GunZ, cs.GunMountY)):
    """Fixed part on the hood (TurretBase space): doubler plate following the hood, bolted flange, edge bolts."""
    b = MB("MAT_Metal", 0.45, 0.55)
    gx, gz, gy = base_world

    def hood_local(lx, ly):
        return cs.HoodY(gx + lx, gz + ly) - gy

    def outline(theta, hw=0.2, hl=0.19, rc=0.06):
        dx, dy = math.cos(theta), math.sin(theta)
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            x, y = dx * mid, dy * mid
            qx, qy = max(abs(x) - (hw - rc), 0.0), max(abs(y) - (hl - rc), 0.0)
            inside = abs(x) <= hw and abs(y) <= hl and math.hypot(qx, qy) <= rc
            lo, hi = (mid, hi) if inside else (lo, mid)
        return dx * lo, dy * lo

    N = 72
    S = [0.5, 0.65, 0.8, 0.93, 1.0]
    bound = [outline(TAU * k / N) for k in range(N)]
    top, bot = [], []
    for s in S:
        rt, rb = [], []
        for k in range(N):
            x, y = bound[k][0] * s, bound[k][1] * s
            h = hood_local(x, y)
            rt.append((x, y, h + 0.012 - (0.004 if s >= 0.999 else 0.0)))
            rb.append((x, y, h - 0.006))
        top.append(rt)
        bot.append(rb)
    ti = b.grid(top, GunPlate, cv=True, flip=True)
    bi = b.grid(bot, shade(GunPlate, 0.6), cv=True)
    b.stitch([ti[-1], bi[-1]], shade(GunPlate, 0.9), flip=True)
    b.stitch([ti[0], bi[0]], shade(GunPlate, 0.6))
    b.m(gloss=0.85, metal=1.0)
    for k in range(12):
        bx, byy = outline(TAU * (k + 0.5) / 12)
        x, y = bx * 0.84, byy * 0.84
        h = hood_local(x, y) + 0.012
        b.cyl((x, y, h - 0.002), (x, y, h + 0.002), 0.012, 16, shade(GunSteel, 0.85))
        b.cyl((x, y, h + 0.002), (x, y, h + 0.009), 0.0085, 6, GunSteel, fillet_r=0.0015)
    b.m(gloss=0.45, metal=0.6)
    b.lathe(fillet([(0, -0.03), (0.172, -0.03), (0.172, -0.006), (0.166, 0.0), (0, 0.0)], [0, 0.002, 0.004, 0.003, 0], 2), 64,
            shade(GunPlate, 0.92))
    b.m(gloss=0.85, metal=1.0)
    for k in range(8):
        a = TAU * k / 8
        x, y = 0.157 * math.cos(a), 0.157 * math.sin(a)
        b.cyl((x, y, -0.001), (x, y, 0.007), 0.008, 6, GunSteel, fillet_r=0.0015)
    return b
