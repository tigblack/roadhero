"""Wheels, DetailedCar pass (CarWheelMesh layout: axle = X, rim face toward +X for side = +1).
Tyre carcass with sidewall bulge + lettering band, staggered curved lugs that wrap the shoulder,
cream deep-dish rim with real round holes (boolean), lug nuts, valve, teal cap, brake disc + hub (spin with the wheel).
Brake calipers / knuckles are separate (they steer but don't spin)."""
import math

import bpy

from mb import MB, C, TAU, fillet, glow, shade

CarRubber, CarRim, CarChrome = C("#302C2C"), C("#E2D5BC"), C("#DCE1E6")
CarAccent, Lug = C("#34B4A2"), C("#3B3636")
DiscC, HubC = C("#8A8F94"), C("#3A3D41")


def _ring(prof):
    """Make a closed lathe profile positive (outward) regardless of traversal: shoelace in (r, z)."""
    a = 0.0
    for i in range(len(prof)):
        r0, z0 = prof[i]
        r1, z1 = prof[(i + 1) % len(prof)]
        a += r0 * z1 - r1 * z0
    return prof if a > 0 else prof[::-1]


def tyre(R, W, side, segs=52, lugs=20):
    b = MB("MAT_Rubber", 0.14, 0.0)
    hw = W / 2
    rIn = R * 0.62
    with b.at((0, 0, 0), (0, 90 * side, 0)):
        top = R - 0.002
        prof = [(rIn + 0.004, -hw + 0.026), (0.74 * R, -hw - 0.004), (0.84 * R, -hw - 0.012), (0.93 * R, -hw - 0.004),
                (top - 0.006, -hw + 0.03), (top, -hw + 0.07), (top, hw - 0.07), (top - 0.006, hw - 0.03),
                (0.93 * R, hw + 0.004), (0.84 * R, hw + 0.012), (0.74 * R, hw + 0.004), (rIn + 0.004, hw - 0.026)]
        prof = fillet(prof, [0, 0.01, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.01, 0], 1)
        b.lathe(_ring(prof), segs, CarRubber, closed_prof=True)
        # raised lettering band on the outer sidewall
        b.m(gloss=0.25)
        band = [(0.705 * R, hw + 0.0), (0.705 * R, hw + 0.0095), (0.775 * R, hw + 0.0115), (0.775 * R, hw + 0.002)]
        b.lathe(_ring(band), segs, C("#4A4444"), closed_prof=True)
        # lugs: two staggered rows, slanted down over the shoulder
        b.m(gloss=0.12)
        pitch = TAU / lugs
        for row in (1, -1):
            base = [(R - 0.016, 0.012), (R + 0.024, 0.012), (R + 0.024, hw - 0.062), (R + 0.008, hw - 0.018), (R - 0.026, hw - 0.03)]
            base = fillet(base, [0, 0.004, 0.004, 0.004, 0], 1)
            prof_l = [(r, h * row) for (r, h) in base]
            prof_l = _ring(prof_l)
            for k in range(lugs):
                a0 = k * pitch + (pitch * 0.5 if row < 0 else 0.0)
                b.lathe(prof_l, 3, Lug, a0=a0, a1=a0 + pitch * 0.52, closed_prof=True)
        # small sidewall blocks under the shoulder (outer side)
        for k in range(lugs):
            a0 = k * pitch + pitch * 0.25
            sb = _ring([(0.88 * R, hw - 0.006), (0.95 * R, hw - 0.022), (0.95 * R, hw - 0.004), (0.88 * R, hw + 0.011)])
            b.lathe(sb, 2, shade(Lug, 1.08), a0=a0, a1=a0 + pitch * 0.3, closed_prof=True)
    return b


def rim_parts(R, W, side, segs=48):
    """Rim without the dish (dish is boolean-cut separately)."""
    b = MB("MAT_Metal", 0.95, 1.0)
    hw = W / 2
    rIn = R * 0.62
    with b.at((0, 0, 0), (0, 90 * side, 0)):
        lip = [(rIn - 0.004, hw - 0.04), (rIn + 0.012, hw - 0.035), (rIn + 0.014, hw - 0.006), (rIn + 0.006, hw + 0.003),
               (rIn - 0.018, hw + 0.002), (rIn - 0.02, hw - 0.01)]
        b.lathe(_ring(fillet(lip, [0, 0.003, 0.003, 0.003, 0.002, 0], 2)), segs, CarChrome, closed_prof=True)
        b.m("MAT_CarPaint", 0.7, 0.2)
        cap = [(0.0, hw - 0.05), (0.28 * rIn, hw - 0.05), (0.28 * rIn, hw - 0.033), (0.22 * rIn, hw - 0.013), (0.0, hw - 0.005)]
        b.lathe(fillet(cap, [0, 0, 0.004, 0.006, 0], 2), 32, CarAccent)
        b.m("MAT_Metal", 0.95, 1.0)
        b.lathe(_ring([(0.17 * rIn, hw - 0.016), (0.205 * rIn, hw - 0.019), (0.205 * rIn, hw - 0.012), (0.17 * rIn, hw - 0.0085)]), 32, CarChrome, closed_prof=True)
        # lug nuts on conical seats, between the holes
        for i in range(5):
            a = math.radians(i * 72)
            x, y = math.cos(a) * 0.37 * rIn, math.sin(a) * 0.37 * rIn
            b.m("MAT_Metal", 0.85, 1.0)
            b.cyl((x, y, hw - 0.066), (x, y, hw - 0.054), 0.021, 12, shade(CarChrome, 0.8), r2=0.016)
            b.cyl((x, y, hw - 0.056), (x, y, hw - 0.04), 0.0145, 6, CarChrome, fillet_r=0.002)
        # valve stem
        a = math.radians(36 + 36)
        x, y = math.cos(a) * 0.86 * rIn, math.sin(a) * 0.86 * rIn
        b.m("MAT_Rubber", 0.2, 0.0)
        b.cyl((x, y, hw - 0.045), (x, y, hw - 0.018), 0.005, 8, CarRubber)
        b.m("MAT_Metal", 0.85, 1.0)
        b.cyl((x, y, hw - 0.02), (x, y, hw - 0.008), 0.0055, 8, CarChrome, fillet_r=0.001)
        # brake disc (slotted face), hat, hub - they spin with the wheel
        b.m("MAT_Metal", 0.55, 0.9)
        disc = [(0.35 * rIn, hw - 0.131), (0.86 * rIn, hw - 0.131), (0.86 * rIn, hw - 0.109), (0.35 * rIn, hw - 0.109)]
        b.lathe(_ring(fillet(disc, [0, 0.002, 0.002, 0], 1)), segs, DiscC, closed_prof=True)
        b.m("MAT_Metal", 0.2, 0.3)
        for i in range(12):
            a = TAU * i / 12
            rr = 0.62 * rIn
            b.rbox((math.cos(a) * rr, math.sin(a) * rr, hw - 0.1085), (0.04 * rIn, 0.004, 0.0012), 0.001, 1, HubC,
                   rot=(0, 0, math.degrees(a) + 25))
        b.m("MAT_Metal", 0.45, 0.8)
        hat = [(0.0, hw - 0.14), (0.36 * rIn, hw - 0.14), (0.36 * rIn, hw - 0.075), (0.3 * rIn, hw - 0.06), (0.0, hw - 0.06)]
        b.lathe(fillet(hat, [0, 0.004, 0.004, 0.004, 0], 2), 32, HubC)
        # dark back face closing the wheel from inside
        b.m("MAT_Rubber", 0.0, 0.0)
        b.lathe(_ring([(0.0, -hw + 0.02), (rIn + 0.006, -hw + 0.02), (rIn + 0.006, -hw + 0.03), (0.0, -hw + 0.03)]), 32, C("#141213"), closed_prof=True)
        # rim barrel (inside surface of the rim, seen through the holes)
        b.m("MAT_Metal", 0.5, 0.8)
        barrel = [(rIn - 0.03, -hw + 0.03), (rIn + 0.004, -hw + 0.03), (rIn + 0.004, hw - 0.04), (rIn - 0.03, hw - 0.045)]
        b.lathe(_ring(barrel), segs, shade(CarRim, 0.55), closed_prof=True)
    return b


def dish(R, W, side, segs=56):
    b = MB("MAT_CarPaint", 0.55, 0.3)
    hw = W / 2
    rIn = R * 0.62
    with b.at((0, 0, 0), (0, 90 * side, 0)):
        d = [(rIn - 0.018, hw + 0.001), (rIn - 0.04, hw - 0.04), (0.7 * rIn, hw - 0.068), (0.36 * rIn, hw - 0.062), (0.27 * rIn, hw - 0.04),
             (0.27 * rIn, hw - 0.055), (0.36 * rIn, hw - 0.074), (0.7 * rIn, hw - 0.08), (rIn - 0.05, hw - 0.052), (rIn - 0.03, hw - 0.006)]
        b.lathe(_ring(fillet(d, [0, 0.01, 0.02, 0.01, 0, 0, 0.01, 0.02, 0.01, 0], 1)), segs, CarRim, closed_prof=True)
    return b


def dish_cutter(R, W, side):
    b = MB("MAT_CarPaint", 0.3, 0.0)
    hw = W / 2
    rIn = R * 0.62
    with b.at((0, 0, 0), (0, 90 * side, 0)):
        for i in range(5):
            a = math.radians(i * 72 + 36)
            x, y = math.cos(a) * 0.6 * rIn, math.sin(a) * 0.6 * rIn
            b.cyl((x, y, hw - 0.12), (x, y, hw + 0.02), 0.14 * rIn, 24, shade(CarRim, 0.6))
    return b


def caliper(R, W, side, front):
    """Non-spinning parts on the steer / suspension pivot: caliper over the disc edge, bracket, knuckle + steering arm."""
    b = MB("MAT_CarPaint", 0.7, 0.25)
    hw = W / 2
    rIn = R * 0.62
    with b.at((0, 0, 0), (0, 90 * side, 0)):
        ang = math.radians(225 if side > 0 else -45)   # top-rear of the disc in both mirrored frames
        prof = _ring(fillet([(0.7 * rIn, hw - 0.15), (0.94 * rIn, hw - 0.15), (0.94 * rIn, hw - 0.092), (0.7 * rIn, hw - 0.092)],
                            [0, 0.008, 0.008, 0], 2))
        b.lathe(prof, 6, CarAccent, a0=ang - 0.32, a1=ang + 0.32, closed_prof=True)
        b.m("MAT_Metal", 0.85, 1.0)
        for da in (-0.2, 0.2):
            x, y = math.cos(ang + da) * 0.9 * rIn, math.sin(ang + da) * 0.9 * rIn
            b.cyl((x, y, hw - 0.092), (x, y, hw - 0.084), 0.008, 6, CarChrome)
        b.m("MAT_Metal", 0.4, 0.6)
        x, y = math.cos(ang) * 0.55 * rIn, math.sin(ang) * 0.55 * rIn
        b.rbox((x, y, hw - 0.165), (0.03, 0.05, 0.012), 0.006, 2, HubC, rot=(0, 0, math.degrees(ang)))
        if front:
            b.rbox((0, 0, hw - 0.19), (0.11, 0.05, 0.02), 0.012, 2, HubC)
            b.tube([(0, -0.02, hw - 0.19), (0.0, -0.09, hw - 0.2), (0.0, -0.15, hw - 0.24)], 0.012, 10, HubC)
    return b
