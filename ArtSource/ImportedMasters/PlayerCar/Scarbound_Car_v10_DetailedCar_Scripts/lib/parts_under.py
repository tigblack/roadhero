"""Underbody / chassis (object "Underbody", body space): visible below the 0.30 m floor and inside the wheel wells."""
import math

from mathutils import Vector

from mb import MB, C, TAU, fillet, rrect, shade
from parts_details import P, H, catmull, bolt_head

Frame, FrameDark, Steel, Rubber = C("#2E3135"), C("#202225"), C("#8A9097"), C("#1E1D1D")
Spring, Accent = C("#B9472F"), C("#34B4A2")


def build():
    b = MB("MAT_Metal", 0.35, 0.6)
    # frame rails with kick-ups at both ends
    for s in (-1, 1):
        path = catmull([P(s * 0.40, 0.31, -2.15), P(s * 0.40, 0.255, -1.92), P(s * 0.40, 0.255, 1.85), P(s * 0.40, 0.31, 2.1)], 10)
        b.sweep(path, rrect(0.055, 0.075, 0.008, 2), Frame, up=(0, 0, 1))
        for z in (-1.6, -1.0, -0.2, 0.6, 1.2):
            bolt_head(b, P(s * 0.428, 0.255, z), (s, 0, 0), 0.007, 0.004, col=Steel)
    # crossmembers
    for z in (-1.95, -0.6, 0.65, 1.85):
        b.rbox(P(0, 0.25, z), H(0.37, 0.028, 0.025), 0.008, 2, FrameDark)
    # engine sump + skid plate, transmission, driveshaft with U-joints
    b.rbox(P(0, 0.26, 1.5), H(0.2, 0.045, 0.26), 0.025, 2, FrameDark)
    b.cyl(P(0, 0.214, 1.62), P(0, 0.205, 1.62), 0.012, 6, Steel)
    b.rbox(P(0, 0.205, 1.55), H(0.3, 0.006, 0.38), 0.006, 2, shade(Steel, 0.6))
    for (x, z) in ((-0.27, 1.22), (0.27, 1.22), (-0.27, 1.88), (0.27, 1.88)):
        bolt_head(b, P(x, 0.2, z), (0, 0, -1)[::-1][::-1] if False else (0, 0, -1), 0.008, 0.005, col=Steel)
    with b.at(P(0, 0.29, 1.0), (90, 0, 0)):
        b.lathe(fillet([(0, 0), (0.12, 0), (0.12, 0.08), (0.075, 0.6), (0, 0.6)], [0, 0.01, 0.02, 0.01, 0], 2), 24, Frame)
    b.cyl(P(0, 0.29, 0.38), P(0, 0.31, -1.22), 0.03, 16, Steel, fillet_r=0.004)
    for z in (0.38, -1.22):
        b.rbox(P(0, 0.29 + (0.02 if z < 0 else 0.0), z), H(0.04, 0.04, 0.03), 0.008, 2, FrameDark)
    # fuel tank with straps
    b.rbox(P(0, 0.255, -1.98), H(0.31, 0.045, 0.14), 0.03, 3, C("#3A3F38"))
    for x in (-0.15, 0.15):
        b.rbox(P(x, 0.255, -1.98), H(0.018, 0.049, 0.145), 0.004, 1, Steel)
    # front suspension: lower A-arms + ball joints, upper arms, coilovers, tie rods
    ax = 1.45
    for s in (-1, 1):
        bj = P(s * 0.66, 0.225, ax)
        for zz in (ax - 0.16, ax + 0.14):
            b.cyl(P(s * 0.4, 0.25, zz), bj, 0.016, 12, Frame, fillet_r=0.004)
            b.cyl(P(s * 0.39, 0.25, zz - 0.02), P(s * 0.39, 0.25, zz + 0.02), 0.025, 12, Rubber, fillet_r=0.004)
        b.ellipsoid(bj, (0.026, 0.026, 0.026), Steel, 16, 8)
        ubj = P(s * 0.655, 0.58, ax)
        for zz in (ax - 0.1, ax + 0.1):
            b.cyl(P(s * 0.5, 0.6, zz), ubj, 0.013, 10, Frame)
        b.ellipsoid(ubj, (0.022, 0.022, 0.022), Steel, 14, 7)
        # coilover: damper body + rod + spring helix
        lo, hi = Vector(P(s * 0.61, 0.25, ax + 0.03)), Vector(P(s * 0.635, 0.72, ax + 0.03))
        b.cyl(tuple(lo), tuple(lo.lerp(hi, 0.55)), 0.024, 16, shade(Steel, 0.7), fillet_r=0.004)
        b.cyl(tuple(lo.lerp(hi, 0.55)), tuple(hi), 0.009, 10, Steel)
        d = (hi - lo).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        hel = []
        for k in range(121):
            t = k / 120
            ang = TAU * 6 * t
            c = lo.lerp(hi, 0.12 + 0.8 * t)
            hel.append(tuple(c + (u * math.cos(ang) + v * math.sin(ang)) * 0.042))
        b.m("MAT_CarPaint", 0.6, 0.3)
        b.tube(hel, 0.0075, 8, Spring)
        b.m("MAT_Metal", 0.35, 0.6)
        b.cyl(P(s * 0.22, 0.28, ax - 0.2), P(s * 0.64, 0.27, ax - 0.2), 0.012, 10, Steel, fillet_r=0.003)
        b.cyl(P(s * 0.25, 0.28, ax - 0.215), P(s * 0.25, 0.28, ax - 0.185), 0.02, 12, Rubber)
    # rear axle housing, differential, leaf springs with shackles, radius rods
    rax = -1.42
    b.cyl(P(-0.74, 0.44, rax), P(0.74, 0.44, rax), 0.045, 20, Frame, fillet_r=0.006)
    with b.at(P(0, 0.4, rax), (0, 0, 0)):
        b.ellipsoid((0, 0, 0), (0.13, 0.12, 0.13), FrameDark, 24, 12)
    with b.at(P(0, 0.4, rax - 0.11), (90, 0, 0)):
        b.lathe(fillet([(0, 0), (0.1, 0), (0.1, 0.018), (0, 0.03)], [0, 0.004, 0.006, 0], 2), 24, shade(Frame, 1.2))
        for k in range(10):
            a = TAU * k / 10
            bolt_head(b, (math.cos(a) * 0.088, math.sin(a) * 0.088, 0.018), (0, 0, 1), 0.006, 0.004, col=Steel)
    b.cyl(P(0, 0.4, rax + 0.12), P(0, 0.35, rax + 0.25), 0.04, 16, FrameDark)
    for s in (-1, 1):
        for k, (w, dz) in enumerate(((0.05, 0.0), (0.05, 0.012), (0.05, 0.024))):
            L = 0.52 - k * 0.12
            pts = []
            for i in range(17):
                t = i / 16 * 2 - 1
                pts.append(P(s * 0.45, 0.36 - 0.035 * (1 - t * t) - dz, rax + t * L))
            b.sweep(pts, rrect(w, 0.008, 0.003, 1), shade(Steel, 0.55 - 0.05 * k), up=(1, 0, 0))
        for zz in (rax - 0.52, rax + 0.52):
            b.cyl(P(s * 0.48, 0.36, zz), P(s * 0.42, 0.36, zz), 0.02, 12, Rubber)
        b.rbox(P(s * 0.45, 0.39, rax), H(0.035, 0.05, 0.04), 0.006, 2, FrameDark)
        b.cyl(P(s * 0.4, 0.26, rax + 0.5), P(s * 0.62, 0.42, rax + 0.06), 0.015, 12, Frame)
    return b
