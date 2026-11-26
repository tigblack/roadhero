"""Toxic Wetlands mutants: the seven creatures of the second zone (concept ToxicWetlands_Mutants_Concept_v1).

Every builder returns a mut_lib.Creature: a root empty (custom property mut_model = the Unity ModelId it replaces)
and rigid parts at their joints. Part names are the contract with Unity's MutantAnimator (Scripts/World/Mutants.cs):
creature space = Blender x right, y forward (the creature looks along +y), z up, metres, ground at z = 0,
already at the in-game size (the Brute's 1.45 and the boss's size are built in).
"""
import math
import random

from mathutils import Matrix, Vector

import mut_lib as M
from mut_lib import C, MAcc, S, V, ball, blob, box, chain, cyl, drum, eye, grad, horn, limb, lathe_at, look, mottle, \
    recolor, rivets, shelf, sweep, teeth_ring, tint, torus, trefoil, webbed_foot  # noqa: F401
from tw_lib import hexlin, mixc, smooth_noise3


# ------------------------------------------------------------------------------------------------ helpers

def grad3(lo, mid, hi, z_lo, z_mid, z_hi, axis=2):
    """Three-colour gradient (belly -> flank -> back) along an axis; keeps glow alpha."""
    lo, mid, hi = (hexlin(c) if isinstance(c, str) else c for c in (lo, mid, hi))

    def fn(p, c):
        z = p[axis]
        if z <= z_mid:
            t = max(0.0, min(1.0, (z - z_lo) / max(1e-6, z_mid - z_lo)))
            col = mixc(lo, mid, t * t * (3 - 2 * t))
        else:
            t = max(0.0, min(1.0, (z - z_mid) / max(1e-6, z_hi - z_mid)))
            col = mixc(mid, hi, t * t * (3 - 2 * t))
        return (col[0], col[1], col[2], c[3])
    return fn


def ribs(acc, faces, axis=1, period=0.11, amp=0.012, phase=0.0):
    """Segment rings (annuli) along an axis: radial ripples on organic bodies."""
    acc.bm.normal_update()
    vs = {v for f in faces for v in f.verts}
    for v in vs:
        v.co += v.normal * (amp * math.cos(2 * math.pi * (v.co[axis] + phase) / period))


def lumps(acc, faces, amp, freq, seed=0):
    M.displace(acc, faces, amp, freq, seed)


def band(acc, y, z, hw, hh, width, surf, belly=0.35, p=2.2, n=24, bolts=True):
    """A rusty strap around an elongated body at y (follows the body's section)."""
    f = sweep(acc, [(0, y - width / 2, z), (0, y, z), (0, y + width / 2, z)], [hw, hw * 1.01, hw], [hh, hh * 1.01, hh],
              surf, n=n, p=p, belly=belly, per=1)
    if bolts:
        pts = []
        for ang in (-60, -20, 20, 60):
            a = math.radians(90 + ang)
            pts.append((hw * 1.02 * math.cos(a), y, z + hh * 1.02 * math.sin(a)))
        f += rivets(acc, pts, 0.022, C['steel_dk'])
    return f


def scatter_glow(acc, pts, r, surf=None):
    out = []
    for p in pts:
        out += ball(acc, p, r, surf or C['glow_soft'], segs=10, rings=7)
    return out


# ================================================================================================ 01 LEECHLING

def leechling(off=(0, 0, 0)):
    """Scav -> Leechling: low elongated grub on four short splayed webbed legs, bulging segmented back strapped with
    rusted bands, round sucker mouth ringed with big teeth. Fast melee biter. ~2.2 m long, 0.7 m tall."""
    cr = M.Creature('Mut_Leechling', '01_Leechling', 'Scav', off)
    Z = 0.37
    body_col = grad3('#C8873E', '#3C7A6E', '#173835', Z - 0.26, Z + 0.0, Z + 0.26)
    mott = mottle(0.18, 5.0, 11, dark='#10231F', dark_thr=0.40, dark_k=0.40)

    def segment(acc, ys, hws, hhs, seed, zs=None):
        zs = zs or [Z] * len(ys)
        f = sweep(acc, [(0, y, z) for y, z in zip(ys, zs)], hws, hhs, C['teal'], n=26, p=2.3, belly=0.42, per=4,
                  top_bulge=0.10)
        ribs(acc, f, 1, 0.085, 0.011, seed * 0.03)
        lumps(acc, f, 0.016, 5.0, seed)
        recolor(acc, f, chain(body_col, mott))
        return f

    def strap(acc, y, hw, hh):
        f = band(acc, y, Z, hw + 0.03, hh + 0.028, 0.13, C['rust_or'], belly=0.42, p=2.3)
        return f

    # ---- Body: the middle segment (two bulges), front legs, straps over the creases
    a = MAcc('body')
    segment(a, [-0.52, -0.40, -0.22, 0.0, 0.22, 0.40, 0.52], [0.24, 0.34, 0.40, 0.35, 0.41, 0.35, 0.25],
            [0.21, 0.29, 0.33, 0.29, 0.34, 0.29, 0.22], 3)
    strap(a, 0.42, 0.34, 0.285)
    strap(a, -0.42, 0.33, 0.28)
    # rusted plate grown into the back, bolts and a pipe stub
    blob(a, (0.06, 0.08, Z + 0.33), (0.20, 0.17, 0.032), C['rust'], M=M.R('Y', 9) @ M.R('X', 5), e=(0.3, 0.6))
    rivets(a, [(-0.08, 0.17, Z + 0.355), (0.20, -0.02, Z + 0.345), (0.17, 0.19, Z + 0.35), (-0.07, -0.01, Z + 0.36)], 0.022)
    scatter_glow(a, [(0.37, 0.12, Z - 0.03), (0.38, -0.16, Z - 0.05), (-0.37, 0.08, Z - 0.03), (-0.36, -0.20, Z - 0.05)], 0.03)
    cr.part('Body', a, (0, 0, Z))

    # ---- Head: front bulge; the sucker mouth is a separate part (it gapes and snaps)
    h = MAcc('head')
    segment(h, [0.38, 0.52, 0.70, 0.86, 0.98, 1.04], [0.25, 0.37, 0.41, 0.40, 0.38, 0.34],
            [0.22, 0.31, 0.34, 0.33, 0.32, 0.28], 5)
    strap(h, 0.74, 0.38, 0.32)
    for x in (-0.16, 0.16):
        ball(h, (x, 0.93, Z + 0.27), 0.04, C['glow_soft'], 10, 7)
    cr.part('Head', h, (0, 0.42, Z), parent='Body')

    m = MAcc('mouth')
    mc = V(0, 1.05, Z)
    lathe_at(m, [(0.0, -0.22), (0.10, -0.13), (0.17, -0.04), (0.22, 0.03), (0.28, 0.06), (0.335, 0.03), (0.35, -0.02),
                 (0.34, -0.07)], mc, (0, 1, 0), C['mouth'], segs=28, caps=(False, False), sharp=None)
    torus(m, mc + V(0, 0.01, 0), (0, 1, 0), 0.325, 0.055, C['flesh'], segs=28, rsegs=9)
    teeth_ring(m, mc + V(0, 0.04, 0), (0, 1, 0), 0.29, 12, 0.21, C['tooth'], inward=0.55, r0=0.052, seed=4)
    teeth_ring(m, mc + V(0, -0.05, 0), (0, 1, 0), 0.18, 9, 0.12, C['tooth'], inward=0.7, r0=0.032, seed=7)
    ball(m, mc + V(0, -0.20, 0), (0.09, 0.04, 0.09), C['glow'], 12, 6)            # acid glow deep in the throat
    cr.part('Mouth', m, mc, parent='Head')

    # ---- Rear: last bulge and a short upturned tail
    r = MAcc('rear')
    segment(r, [-0.38, -0.50, -0.68, -0.86, -1.02, -1.12], [0.26, 0.36, 0.37, 0.27, 0.15, 0.05],
            [0.23, 0.30, 0.30, 0.22, 0.12, 0.04], 9, zs=[Z, Z, Z + 0.01, Z + 0.03, Z + 0.07, Z + 0.10])
    strap(r, -0.80, 0.30, 0.245)
    cyl(r, (0.07, -0.60, Z + 0.20), (0.19, -0.71, Z + 0.47), 0.055, C['rust'], segs=10)
    torus(r, V(0.18, -0.70, Z + 0.44), (0.45, -0.45, 1.0), 0.065, 0.02, C['rust_dk'], segs=14, rsegs=6)
    scatter_glow(r, [(0.33, -0.58, Z - 0.04), (-0.32, -0.64, Z - 0.05)], 0.028)
    cr.part('Rear', r, (0, -0.42, Z), parent='Body')

    # ---- legs: short, splayed sideways like a salamander, big webbed feet
    leg_col = grad('#6E4426', '#B8803F', 0.0, 0.30)
    for side, nm in ((1, 'R'), (-1, 'L')):
        for front in (True, False):
            l_ = MAcc('leg')
            y0 = 0.24 if front else -0.60
            hip = V(0.30 * side, y0, Z - 0.08)
            elbow = V(0.56 * side, y0 + (0.07 if front else -0.05), Z + 0.0)
            wrist = V(0.66 * side, y0 + (0.14 if front else -0.03), 0.06)
            f = limb(l_, [hip, elbow, wrist], [0.115, 0.09, 0.065], C['ochre'], segs=10, per=4)
            f += ball(l_, elbow, 0.092, C['ochre'], 10, 7)
            fwd = V(0.55 * side, 1.0, 0) if front else V(0.75 * side, 0.55, 0)
            f += webbed_foot(l_, V(wrist.x, wrist.y, 0.0), fwd, toes=3, spread=75, length=0.24, r=0.036,
                             skin=C['ochre'], web=C['web'])
            recolor(l_, f, leg_col)
            cr.part(('LegF' if front else 'LegB') + nm, l_, hip, parent='Body' if front else 'Rear')
    return cr


# ------------------------------------------------------------------------------------------------ more helpers

def pits(acc, faces, freq, seed, depth, dark, thr=0.32, k=0.85):
    """Fungal holes: vertices sink where the noise is high and darken toward 'dark'."""
    acc.bm.normal_update()
    vs = {v for f in faces for v in f.verts}
    for v in vs:
        m = smooth_noise3(v.co, seed, freq)
        if m > thr:
            v.co -= v.normal * depth * min(1.0, (m - thr) / 0.15)
    d = hexlin(dark)

    def fn(p, c):
        m = smooth_noise3(p, seed, freq)
        if m <= thr - 0.04:
            return c
        t = min(1.0, (m - thr + 0.04) / 0.16) * k
        return (c[0] * (1 - t) + d[0] * t, c[1] * (1 - t) + d[1] * t, c[2] * (1 - t) + d[2] * t, c[3])
    acc.recolor(faces, fn)


def blotches(rgb, freq, seed, thr=0.25, k=0.75):
    d = hexlin(rgb)

    def fn(p, c):
        m = smooth_noise3(p, seed, freq)
        if m <= thr:
            return c
        t = min(1.0, (m - thr) / 0.12) * k
        return (c[0] * (1 - t) + d[0] * t, c[1] * (1 - t) + d[1] * t, c[2] * (1 - t) + d[2] * t, c[3])
    return fn


def drip(acc, p, length, r, surf, seed=0):
    """Hanging strand (moss, goo) from p straight down with a slight sway, thinning to a drop."""
    rnd = random.Random(seed)
    p = Vector(p)
    pts = [p, p + V(rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), -length * 0.45),
           p + V(rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), -length)]
    out = limb(acc, pts, [r, r * 0.6, r * 0.25], surf, segs=7, per=3)
    out += ball(acc, pts[-1], r * 0.55, surf, 8, 6)
    return out


def root_foot(acc, ankle, n, length, r, surf, seed=0, spread=360.0, start=0.0, fwd=(0, 1, 0)):
    """Roots radiating from an ankle over the ground (Spore Brute, Mire Mother)."""
    rnd = random.Random(seed)
    a = Vector(ankle)
    out = []
    f = Vector(fwd)
    base_ang = math.atan2(f.y, f.x)
    for i in range(n):
        ang = base_ang + math.radians(start + spread * ((i + 0.5) / n - 0.5) + rnd.uniform(-8, 8))
        d = V(math.cos(ang), math.sin(ang), 0)
        L_ = length * rnd.uniform(0.75, 1.15)
        p1 = a + d * L_ * 0.35 + V(0, 0, -a.z * 0.55)
        p2 = a + d * L_ * 0.75 + V(0, 0, -a.z * 0.95 + 0.02)
        p3 = a + d * L_ + V(0, 0, -a.z + 0.01)
        out += limb(acc, [a, p1, p2, p3], [r, r * 0.75, r * 0.45, r * 0.12], surf, segs=8, per=3)
    return out


def strands(acc, pts, rad, r, n=3, seed=0, turns=1.2):
    """Root strands twisting around a limb (bundle look): helices of radius rad about the smoothed path."""
    path = M.catmull(pts, 6)
    out = []
    for k in range(n):
        ph = 2 * math.pi * k / n + seed
        ring = []
        for i, p in enumerate(path):
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            t = (b - a).normalized()
            u = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            x = t.cross(u).normalized()
            y = t.cross(x).normalized()
            ang = ph + 2 * math.pi * turns * i / (len(path) - 1)
            ring.append(p + (x * math.cos(ang) + y * math.sin(ang)) * rad)
        out += acc.tube(ring, [r * (1.0 - 0.35 * i / (len(ring) - 1)) for i in range(len(ring))], C['root_dk'], 8, caps=True)
    return out


def tire(acc, c, r, w, lugs=12):
    """Chunky off-road tyre around the x axis with chevron lugs, rusted rim dishes and hub bolts (centre c)."""
    out = []
    hw = w / 2
    c = Vector(c)
    prof = [(r * 0.60, -hw * 0.90), (r * 0.80, -hw), (r * 0.95, -hw * 0.94), (r, -hw * 0.6), (r, hw * 0.6),
            (r * 0.95, hw * 0.94), (r * 0.80, hw), (r * 0.60, hw * 0.90)]
    out += lathe_at(acc, prof, c, (1, 0, 0), C['tire'], segs=24, caps=(False, False), sharp=None)
    for k in range(lugs):
        for sgn in (-1, 1):
            a = 2 * math.pi * k / lugs + sgn * 0.09
            d = V(0, math.cos(a), math.sin(a))
            ctr = c + d * (r + 0.016) + V(sgn * hw * 0.40, 0, 0)
            out += acc.box((0.11, w * 0.34, 0.05), M.T(ctr) @ look(d, (1, 0, 0)), C['tire'], bevel=0.0, segs=1)
    plus = [(r * 0.60, hw * 0.86), (r * 0.55, hw * 0.70), (r * 0.28, hw * 0.55), (r * 0.16, hw * 0.75), (0.0, hw * 0.78)]
    minus = [(rr, -z) for rr, z in reversed(plus)]
    out += lathe_at(acc, plus, c, (1, 0, 0), C['rust_or'], segs=18, caps=(False, False), sharp=40)
    out += lathe_at(acc, minus, c, (1, 0, 0), C['rust_or'], segs=18, caps=(False, False), sharp=40)
    for k in range(5):
        a = 2 * math.pi * k / 5
        for sgn in (-1, 1):
            out += ball(acc, c + V(sgn * hw * 0.70, math.cos(a) * r * 0.2, math.sin(a) * r * 0.2), 0.03, C['steel_dk'], 6, 4)
    return out


def coil(acc, base, top, r, wire, turns, surf):
    """Coil spring between two points (suspension)."""
    base, top = Vector(base), Vector(top)
    ax = (top - base)
    L_ = ax.length
    Mr = look(ax)
    pts = []
    n = int(turns * 10)
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        pts.append(base + Mr.to_3x3() @ V(r * math.cos(a), r * math.sin(a), L_ * t))
    return acc.tube(pts, wire, surf, 6, caps=True)


# ================================================================================================ 02 MIRE CRAB

def crab(off=(0, 0, 0)):
    """Raider -> Mire Crab: wide squat ridged carapace with a chemical drum grown into it, four thick bent walking legs,
    one huge and one small claw. Melee: the big claw pinches. ~2.9 m wide, 1.4 m tall."""
    cr = M.Creature('Mut_MireCrab', '02_MireCrab', 'Raider', off)
    Z = 0.62
    shell = chain(grad3('#382440', '#6E4A72', '#9C7298', Z - 0.20, Z + 0.10, Z + 0.42),
                  mottle(0.15, 4.0, 5, dark='#2A1A30', dark_thr=0.46, dark_k=0.40))
    a = MAcc('body')
    f = blob(a, (0, -0.04, Z + 0.06), (0.90, 0.66, 0.30), C['chitin'], e=(0.40, 0.6), amp=0.04, freq=3.0, seed=2,
             segs=34, rings=16)
    f += blob(a, (0, -0.08, Z + 0.25), (0.30, 0.52, 0.17), C['chitin'], e=(0.6, 0.7), amp=0.03, freq=4, seed=3)
    for sx in (1, -1):
        f += blob(a, (0.54 * sx, 0.0, Z + 0.20), (0.26, 0.44, 0.13), C['chitin'], M=M.R('Y', -16 * sx), e=(0.6, 0.7),
                  amp=0.03, freq=4, seed=4)
    recolor(a, f, shell)
    f = blob(a, (0, 0.0, Z - 0.16), (0.68, 0.52, 0.17), C['chitin_dk'], e=(0.6, 0.7), segs=24, rings=10)
    recolor(a, f, tint('#33243A', 0.45))

    def top_z(x, y):
        q = 1 - (abs(x) / 0.90) ** 2.6 - (abs(y + 0.04) / 0.66) ** 2.6
        return Z + 0.06 + 0.30 * max(0.0, q) ** 0.4

    for th in (-40, -15, 10, 34, 146, 170, 195, 220, 248, 272, 296):
        t = math.radians(th)
        base = V(0.86 * math.cos(t), 0.62 * math.sin(t) - 0.04, Z + 0.10)
        out = V(math.cos(t), math.sin(t), 0).normalized()
        horn(a, base, base + out * 0.27 + V(0, 0, 0.12), 0.07, C['chitin_lt'], bend=(0, 0, 0.04), segs=7, n=5)
        horn(a, base + V(0, 0, -0.12), base + out * 0.16 + V(0, 0, -0.16), 0.045, C['chitin_dk'], segs=6, n=4)
    rnd = random.Random(8)
    for i in range(16):
        x, y = rnd.uniform(-0.68, 0.68), rnd.uniform(-0.48, 0.44)
        if abs(x) < 0.36 and -0.55 < y < 0.05:
            continue
        ball(a, (x, y, top_z(x, y) - 0.005), rnd.uniform(0.04, 0.08), C['chitin_lt'] if i % 3 else C['bone_dk'], 10, 6)
    for sx in (1, -1):
        c = V(0.50 * sx, 0.30, top_z(0.50, 0.30) + 0.0)
        n = V(0.45 * sx, 0.32, 0.84).normalized()
        blob(a, c, (0.19, 0.14, 0.026), C['rust'], M=look(n, (0, 1, 0)), e=(0.25, 0.5))
        rivets(a, [c + V(0.11 * sx, 0.08, 0.03), c + V(-0.11 * sx, 0.08, 0.045), c + V(0.10 * sx, -0.08, 0.035)], 0.022)
    dc = V(0.06, -0.26, Z + 0.55)
    drum(a, dc, (1, 0.2, 0), 0.32, 0.78, C['rust_red'], ribs=2)
    trefoil(a, dc + V(-0.02, -0.12, 0.30), (0, -0.38, 0.93), 0.14, up=(1, 0.2, 0))
    f = blob(a, V(0.06, -0.26, Z + 0.30), (0.50, 0.36, 0.14), C['chitin_dk'], e=(0.7, 0.8), amp=0.03, freq=6, seed=4)
    recolor(a, f, shell)
    for i, (x, l_) in enumerate(((0.30, 0.34), (-0.20, 0.26), (0.44, 0.22))):
        drip(a, dc + V(x, 0.07, -0.25), l_, 0.024, C['goo'], seed=i)
    for sx in (1, -1):
        cyl(a, (0.18 * sx, 0.56, Z + 0.16), (0.22 * sx, 0.70, Z + 0.34), 0.04, C['chitin_dk'], segs=8)
        eye(a, (0.22 * sx, 0.71, Z + 0.38), 0.085, (0.15 * sx, 1.0, 0.25), iris=C['eye_green'], lid=C['chitin_dk'], lid_k=0.5)
        horn(a, (0.10 * sx, 0.62, Z - 0.04), (0.06 * sx, 0.80, Z - 0.22), 0.05, C['bone_dk'], bend=(0.03 * sx, 0.04, 0.0),
             segs=7, n=6)
    box(a, (0, 0.66, Z - 0.05), (0.18, 0.03, 0.07), C['throat'], bevel=0.012)
    cr.part('Body', a, (0, 0, Z))

    leg_col = chain(grad('#3A2440', '#82608A', 0.0, Z + 0.30), mottle(0.12, 6.0, 9))
    for sx, nm in ((1, 'R'), (-1, 'L')):
        for k, y in enumerate((0.10, -0.28)):
            l_ = MAcc('leg')
            dy = 0.12 if k == 0 else -0.16
            hip = V(0.72 * sx, y, Z - 0.02)
            knee = V(1.04 * sx, y + dy * 0.5, Z + 0.22)
            mid = V(1.25 * sx, y + dy * 0.85, Z * 0.46)
            tip = V(1.33 * sx, y + dy, 0.0)
            f = limb(l_, [hip, (hip + knee) * 0.5 + V(0, 0, 0.07), knee], [0.145, 0.135, 0.12], C['chitin'], segs=11)
            f += ball(l_, knee, 0.125, C['chitin_lt'], 11, 7)
            f += limb(l_, [knee, mid, tip], [0.115, 0.088, 0.02], C['chitin'], segs=10)
            for t_ in (0.3, 0.55, 0.8):
                pb = hip.lerp(knee, t_) + V(0, 0, 0.09)
                f += horn(l_, pb, pb + V(0.06 * sx, 0, 0.11), 0.03, C['chitin_lt'], segs=6, n=4)
            recolor(l_, f, leg_col)
            cr.part(f'Leg{k + 1}{nm}', l_, hip)

    def claw(sx, nm, k):
        arm = MAcc('arm')
        sh = V(0.50 * sx, 0.46, Z - 0.02)
        el = sh + V(0.40 * sx * k, 0.18 * k, 0.12 * k)
        wr = sh + V(0.36 * sx * k, 0.44 * k, -0.08 * k)
        f = limb(arm, [sh, (sh + el) * 0.5 + V(0, 0, 0.05 * k), el], [0.13 * k, 0.12 * k, 0.115 * k], C['chitin'], segs=10)
        f += ball(arm, el, 0.125 * k, C['chitin_lt'], 10, 7)
        f += limb(arm, [el, (el + wr) * 0.5, wr], [0.115 * k, 0.12 * k, 0.13 * k], C['chitin'], segs=10)
        f += horn(arm, el + V(0.03 * sx, 0, 0.08 * k), el + V(0.12 * sx * k, 0.03, 0.24 * k), 0.04 * k, C['chitin_lt'], segs=6, n=4)
        recolor(arm, f, leg_col)
        cr.part('Claw' + nm, arm, sh)
        pin = MAcc('pincer')
        pc = wr + V(0.03 * sx * k, 0.26 * k, -0.04 * k)
        f = blob(pin, pc, (0.27 * k, 0.32 * k, 0.25 * k), C['chitin'], M=M.R('X', 10), e=(0.7, 0.8), amp=0.025 * k, freq=5)
        recolor(pin, f, chain(grad('#6E4A72', '#C2682E', pc.y - 0.10 * k, pc.y + 0.26 * k, axis=1), mottle(0.1, 6, 3)))
        base = pc + V(0.08 * sx * k, 0.24 * k, -0.12 * k)
        tip = base + V(-0.07 * sx * k, 0.44 * k, -0.02 * k)
        horn(pin, base, tip, 0.135 * k, C['rust_or'], bend=(0.10 * sx * k, 0, -0.05 * k), segs=9, n=8)
        for t_ in (0.25, 0.45, 0.65):
            q = base.lerp(tip, t_) + V(-0.02 * sx * k, 0, 0.08 * k)
            horn(pin, q, q + V(0, 0.01, 0.07 * k), 0.03 * k, C['bone'], segs=5, n=3)
        cr.part('Pincer' + nm, pin, wr, parent='Claw' + nm)
        fg = MAcc('finger')
        fp = pc + V(-0.07 * sx * k, 0.22 * k, 0.14 * k)
        ft = fp + V(-0.02 * sx * k, 0.44 * k, -0.14 * k)
        horn(fg, fp, ft, 0.115 * k, C['rust_or'], bend=(-0.05 * sx * k, 0, 0.11 * k), segs=9, n=8)
        for t_ in (0.3, 0.5, 0.7):
            q = fp.lerp(ft, t_) + V(0, 0, -0.06 * k)
            horn(fg, q, q + V(0, 0.01, -0.06 * k), 0.026 * k, C['bone'], segs=5, n=3)
        cr.part('Finger' + nm, fg, fp, parent='Pincer' + nm)

    claw(1, 'R', 1.0)
    claw(-1, 'L', 0.56)
    return cr


# ================================================================================================ 03 REED STALKER

def stalker(off=(0, 0, 0)):
    """Spearman -> Reed Stalker: tall thin predator on long backward-bent legs, hunched back sprouting reeds, long
    bone skull; one forelimb is a long bone spike for lunges. ~3 m tall."""
    cr = M.Creature('Mut_ReedStalker', '03_ReedStalker', 'Spearman', off)
    skin = chain(grad3('#7A9A80', '#3E6E60', '#21403A', 1.1, 1.8, 2.3), mottle(0.15, 5.0, 21, dark='#5E4430', dark_thr=0.45, dark_k=0.55))
    limb_col = chain(grad('#2A3E36', '#3E6E60', 0.1, 1.4), mottle(0.14, 6.0, 23, dark='#5E4430', dark_thr=0.48, dark_k=0.5))
    # ---- pelvis + whip tail
    p = MAcc('pelvis')
    f = blob(p, (0, -0.16, 1.52), (0.23, 0.21, 0.18), C['teal'], e=(0.8, 0.8), amp=0.02, freq=4, seed=2)
    f += limb(p, [(0, -0.30, 1.50), (0, -0.62, 1.38), (0, -0.92, 1.14), (0, -1.10, 0.92)], [0.10, 0.07, 0.04, 0.01],
              C['teal'], segs=9)
    for t_ in (0.2, 0.4, 0.6):
        q = V(0, -0.30 - 0.6 * t_, 1.52 - 0.40 * t_)
        f += horn(p, q + V(0, 0, 0.05), q + V(0, -0.10, 0.16), 0.025, C['bone_dk'], segs=5, n=4)
    recolor(p, f, limb_col)
    cr.part('Pelvis', p, (0, -0.15, 1.52))
    # ---- hunched torso with ribs, bark patches, dorsal spines and a clump of reeds
    t = MAcc('torso')
    f = sweep(t, [(0, -0.20, 1.56), (0, 0.02, 1.86), (0, 0.28, 2.07), (0, 0.50, 2.17), (0, 0.66, 2.17)],
              [0.20, 0.25, 0.25, 0.21, 0.13], [0.19, 0.24, 0.22, 0.18, 0.11], C['teal'], n=22, p=2.2, belly=0.15, per=4)
    M.displace(t, f, 0.015, 5.0, 3)
    recolor(t, f, skin)
    for sx in (1, -1):
        for k in range(4):
            y = 0.02 + 0.13 * k
            zc = 1.86 + 0.24 * min(1.0, (y + 0.2) / 0.6)
            arc = [V(0.24 * sx, y, zc + 0.08), V(0.28 * sx, y + 0.02, zc - 0.06), V(0.20 * sx, y + 0.04, zc - 0.20)]
            limb(t, arc, [0.022, 0.024, 0.015], C['bone_dk'], segs=6, per=3)
        blob(t, (0.16 * sx, 0.10, 2.06), (0.12, 0.16, 0.07), C['bark'], M=look((0.6 * sx, 0, 0.8)), e=(0.5, 0.6), amp=0.02, freq=8)
    for k in range(7):
        y = -0.10 + 0.11 * k
        zt = 1.80 + 0.40 * min(1.0, (y + 0.15) / 0.65) + 0.02
        L_ = 0.13 + 0.08 * math.sin(k * 1.3)
        horn(t, (0, y, zt), (0, y - 0.09, zt + L_), 0.035, C['bone'], bend=(0, -0.02, 0.0), segs=6, n=5)
    rnd = random.Random(5)
    for k in range(9):
        base = V(rnd.uniform(-0.09, 0.09), rnd.uniform(-0.02, 0.30), 2.02 + rnd.uniform(0.0, 0.08))
        tipd = V(rnd.uniform(-0.35, 0.35), rnd.uniform(-0.55, -0.15), 1.0).normalized()
        L_ = rnd.uniform(0.75, 1.25)
        tip = base + tipd * L_
        limb(t, [base, base.lerp(tip, 0.5) + V(0, -0.04, 0), tip], [0.016, 0.012, 0.008], C['reed'], segs=5, per=3)
        if k % 2 == 0:
            cyl(t, tip - tipd * 0.20, tip - tipd * 0.02, 0.034, C['cattail'], segs=8)
        else:
            blade = [base + V(0, 0.02, 0), base.lerp(tip, 0.6) + V(0.05, 0, 0), tip + V(0.08, 0.04, -0.08)]
            limb(t, blade, [0.03, 0.025, 0.002], C['reed'].with_(rgb=hexlin('#6E7A3A')), segs=5, per=3, flat=0.18)
    cr.part('Torso', t, (0, -0.12, 1.58), parent='Pelvis')
    # ---- neck + long bone skull; the lower jaw is a part (it gapes before a lunge)
    h = MAcc('head')
    f = limb(h, [(0, 0.60, 2.14), (0, 0.74, 2.27), (0, 0.86, 2.33)], [0.085, 0.075, 0.07], C['teal'], segs=10)
    recolor(h, f, skin)
    f = sweep(h, [(0, 0.80, 2.35), (0, 0.98, 2.37), (0, 1.20, 2.29), (0, 1.42, 2.17), (0, 1.62, 2.03)],
              [0.12, 0.125, 0.085, 0.045, 0.01], [0.13, 0.11, 0.07, 0.04, 0.01], C['bone'], n=18, p=2.4, belly=0.25)
    recolor(h, f, mottle(0.10, 7.0, 4))
    for sx in (1, -1):
        ball(h, (0.085 * sx, 0.98, 2.40), 0.05, C['black'], 10, 7)
        ball(h, (0.105 * sx, 1.005, 2.41), 0.02, C['eye_green'], 8, 6)
        horn(h, (0.05 * sx, 0.86, 2.44), (0.10 * sx, 0.66, 2.62), 0.04, C['bone'], bend=(0, 0, 0.05), segs=6, n=5)
    horn(h, (0, 0.90, 2.47), (0, 0.66, 2.72), 0.045, C['bone'], bend=(0, 0, 0.06), segs=6, n=5)
    cr.part('Head', h, (0, 0.62, 2.16), parent='Torso')
    j = MAcc('jaw')
    sweep(j, [(0, 0.84, 2.25), (0, 1.05, 2.22), (0, 1.30, 2.12), (0, 1.48, 2.04)], [0.08, 0.07, 0.04, 0.008],
          [0.045, 0.04, 0.025, 0.006], C['bone_dk'], n=14, p=2.4, per=3)
    for k in range(6):
        q = V(0.03 * (1 if k % 2 else -1), 0.96 + 0.08 * k, 2.25 - 0.035 * k)
        horn(j, q, q + V(0, 0.01, 0.045), 0.012, C['tooth'], segs=5, n=3)
    cr.part('Jaw', j, (0, 0.86, 2.26), parent='Head')
    # ---- legs: thigh (hip) -> shin + foot (knee), bent backward like a heron's
    for sx, nm in ((1, 'R'), (-1, 'L')):
        th = MAcc('thigh')
        hip = V(0.21 * sx, -0.14, 1.50)
        knee = V(0.27 * sx, 0.22, 0.98)
        f = limb(th, [hip, (hip + knee) * 0.5 + V(0.04 * sx, 0.03, 0), knee], [0.115, 0.095, 0.065], C['teal'], segs=10)
        f += ball(th, knee, 0.072, C['teal'], 10, 7)
        recolor(th, f, limb_col)
        blob(th, (hip + knee) * 0.5 + V(0.07 * sx, 0.03, 0.04), (0.06, 0.12, 0.05), C['bark'], M=look((sx, 0.2, 0.2)), e=(0.5, 0.6))
        cr.part('Thigh' + nm, th, hip, parent='Pelvis')
        sh = MAcc('shin')
        ankle = V(0.29 * sx, -0.22, 0.42)
        f = limb(sh, [knee, (knee + ankle) * 0.5, ankle], [0.062, 0.05, 0.045], C['teal_dk'], segs=9)
        f += ball(sh, ankle, 0.052, C['teal_dk'], 9, 6)
        toe0 = V(0.30 * sx, 0.06, 0.035)
        f += limb(sh, [ankle, V(0.30 * sx, -0.07, 0.15), toe0], [0.045, 0.04, 0.035], C['teal_dk'], segs=8)
        recolor(sh, f, limb_col)
        for dx, dy in ((0.13, 0.30), (0.0, 0.36), (-0.12, 0.29)):
            horn(sh, toe0, V(0.30 * sx + dx * sx, dy, 0.0), 0.03, C['bone_dk'], bend=(0, 0, 0.03), segs=6, n=5)
        horn(sh, toe0, V(0.30 * sx, -0.16, 0.0), 0.025, C['bone_dk'], segs=6, n=4)
        cr.part('Shin' + nm, sh, knee, parent='Thigh' + nm)
    # ---- right forelimb: a long bone spike (lunge); left forelimb: a thin three-claw hand
    sa = MAcc('spike_arm')
    sh_, el = V(0.22, 0.50, 2.04), V(0.30, 0.66, 1.74)
    f = limb(sa, [sh_, (sh_ + el) * 0.5 + V(0.03, 0, 0), el], [0.085, 0.075, 0.07], C['teal'], segs=10)
    recolor(sa, f, limb_col)
    ball(sa, el, 0.08, C['bone'], 10, 7)
    cr.part('ArmSpike', sa, sh_, parent='Torso')
    sp = MAcc('spike')
    tip = V(0.42, 2.12, 0.98)
    f = horn(sp, el, tip, 0.09, C['bone'], bend=(0.02, 0.0, 0.20), segs=10, n=12, power=0.65)
    recolor(sp, f, chain(grad('#E4D6B0', '#8E3A26', 1.4, 2.12, axis=1, power=2.0), mottle(0.08, 9, 6)))
    for t_ in (0.25, 0.42, 0.58):
        q = el.lerp(tip, t_) + V(0, 0, 0.05 + 0.03 * (1 - t_))
        horn(sp, q, q + V(0.0, -0.12, 0.07), 0.028, C['bone_dk'], segs=5, n=4)
    cr.part('Spike', sp, el, parent='ArmSpike')
    ca = MAcc('claw_arm')
    sh2, el2 = V(-0.22, 0.50, 2.04), V(-0.32, 0.68, 1.78)
    f = limb(ca, [sh2, (sh2 + el2) * 0.5, el2], [0.075, 0.065, 0.058], C['teal'], segs=9)
    f += ball(ca, el2, 0.06, C['teal_dk'], 9, 6)
    recolor(ca, f, limb_col)
    cr.part('ArmClaw', ca, sh2, parent='Torso')
    hd = MAcc('claw_hand')
    wr2 = V(-0.30, 0.86, 1.55)
    f = limb(hd, [el2, (el2 + wr2) * 0.5, wr2], [0.055, 0.05, 0.045], C['teal_dk'], segs=8)
    recolor(hd, f, limb_col)
    for dx, dy, dz in ((-0.07, 0.13, -0.24), (0.0, 0.17, -0.27), (0.07, 0.12, -0.24)):
        horn(hd, wr2, wr2 + V(dx, dy, dz), 0.028, C['bone'], bend=(0, 0.06, 0.02), segs=6, n=6)
    cr.part('HandClaw', hd, el2, parent='ArmClaw')
    return cr


# ================================================================================================ 04 BILE TOAD

def toad(off=(0, 0, 0)):
    """Crossbow -> Bile Toad: wide heavy toad on four legs, glowing glands on the back, tube mouth, a huge translucent
    poison throat sac that swells before the spit. Ranged: acid gob from the mouth. ~1.9 m wide, 1.4 m tall."""
    cr = M.Creature('Mut_BileToad', '04_BileToad', 'Crossbow', off)
    Z = 0.64
    skin = chain(grad3('#A8966A', '#6E4C72', '#4C3256', Z - 0.36, Z + 0.02, Z + 0.46),
                 blotches('#8A5A34', 3.2, 41, thr=0.28, k=0.65), mottle(0.12, 6.0, 43))
    b = MAcc('body')
    f = blob(b, (0, -0.14, Z), (0.75, 0.72, 0.47), C['purple'], e=(0.8, 0.8), amp=0.045, freq=2.6, seed=3, segs=34, rings=18)
    recolor(b, f, skin)
    rnd = random.Random(12)
    for i in range(22):
        th = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.15, 0.95)
        x, y = 0.70 * rr * math.cos(th), -0.14 + 0.66 * rr * math.sin(th)
        z = Z + 0.47 * math.sqrt(max(0.0, 1 - (x / 0.75) ** 2 - ((y + 0.14) / 0.72) ** 2)) - 0.03
        ball(b, (x, y, z), rnd.uniform(0.035, 0.065), C['plum_wart'], 9, 6)
    for (x, y, z, r) in ((0.30, -0.18, 0.40, 0.13), (0.44, -0.02, 0.34, 0.10), (0.18, -0.38, 0.38, 0.11),
                         (0.40, -0.32, 0.30, 0.085), (0.08, -0.12, 0.45, 0.075), (0.52, -0.20, 0.22, 0.07),
                         (-0.24, -0.30, 0.38, 0.08), (0.26, 0.08, 0.40, 0.06)):
        ball(b, (x, y, Z + z), r, C['gland'], 14, 10)
    cr.part('Body', b, (0, -0.14, Z))
    hd = MAcc('head')
    f = blob(hd, (0, 0.54, Z + 0.16), (0.56, 0.40, 0.30), C['purple'], e=(0.8, 0.85), amp=0.03, freq=3, seed=6, segs=28, rings=14)
    recolor(hd, f, skin)
    for sx in (1, -1):
        eye(hd, (0.30 * sx, 0.56, Z + 0.42), 0.13, (0.30 * sx, 1.0, 0.22), iris=C['eye'], lid=C['purple_dk'], lid_k=0.55)
    cyl(hd, (0, 0.82, Z + 0.14), (0, 1.07, Z + 0.20), 0.115, C['flesh'], segs=16, r2=0.095)
    torus(hd, V(0, 1.055, Z + 0.197), (0, 1.0, 0.22), 0.098, 0.032, C['rust'], segs=18, rsegs=7)
    lathe_at(hd, [(0.07, -0.03), (0.0, -0.06)], V(0, 1.065, Z + 0.20), (0, 1.0, 0.22), C['glow'], segs=12, caps=(False, False))
    cr.part('Head', hd, (0, 0.40, Z + 0.10), parent='Body')
    cr.part('Muzzle', None, (0, 1.10, Z + 0.21), parent='Head')
    sc = MAcc('sac')
    f = ball(sc, (0, 0.80, Z - 0.24), (0.42, 0.38, 0.33), C['sac'], segs=26, rings=16)
    M.displace(sc, f, 0.02, 5.0, 9)
    recolor(sc, f, mottle(0.18, 4.0, 15, dark='#6A8A1E', dark_thr=0.30, dark_k=0.45))
    cr.part('Sac', sc, (0, 0.62, Z - 0.02), parent='Head')
    leg_col = chain(grad('#5A3E30', '#6E4C72', 0.0, Z), mottle(0.12, 6, 5))
    for sx, nm in ((1, 'R'), (-1, 'L')):
        a = MAcc('arm')
        shp, elb, wr = V(0.50 * sx, 0.30, Z - 0.12), V(0.74 * sx, 0.42, Z - 0.24), V(0.76 * sx, 0.58, 0.07)
        f = limb(a, [shp, elb, wr], [0.14, 0.10, 0.07], C['purple'], segs=10)
        f += ball(a, elb, 0.10, C['purple'], 10, 7)
        f += webbed_foot(a, V(wr.x, wr.y, 0.0), V(0.35 * sx, 1, 0), toes=4, spread=80, length=0.22, r=0.035,
                         skin=C['purple'], web=C['web'])
        recolor(a, f, leg_col)
        cr.part('Arm' + nm, a, shp, parent='Body')
        tg = MAcc('thigh')
        hip, kn = V(0.56 * sx, -0.48, Z - 0.12), V(0.94 * sx, -0.20, Z - 0.16)
        f = limb(tg, [hip, (hip + kn) * 0.5 + V(0.04 * sx, -0.04, 0.10), kn], [0.21, 0.19, 0.13], C['purple'], segs=12)
        f += ball(tg, kn, 0.13, C['purple'], 12, 8)
        recolor(tg, f, leg_col)
        cr.part('Thigh' + nm, tg, hip, parent='Body')
        sh = MAcc('shin')
        an = V(0.84 * sx, -0.62, 0.09)
        f = limb(sh, [kn, (kn + an) * 0.5 + V(0.05 * sx, 0, 0), an], [0.12, 0.10, 0.07], C['purple'], segs=10)
        f += webbed_foot(sh, V(an.x, an.y, 0.0), V(0.55 * sx, 1.0, 0), toes=4, spread=70, length=0.38, r=0.04,
                         skin=C['purple'], web=C['web'])
        recolor(sh, f, leg_col)
        cr.part('Shin' + nm, sh, kn, parent='Thigh' + nm)
    return cr


# ================================================================================================ 05 SPORE BRUTE

def brute(off=(0, 0, 0)):
    """Brute -> Spore Brute: asymmetric mass of roots, bark and fungal flesh; one huge club arm and one small claw arm,
    head sunk between the shoulders, big bracket fungi on the back. ~3.4 m tall (the 1.45 scale is built in)."""
    cr = M.Creature('Mut_SporeBrute', '05_SporeBrute', 'Brute', off)
    s = 1.45

    def P(x, y, z):
        return V(x * s, y * s, z * s)

    flesh = chain(grad3('#3E2A44', '#6E4670', '#8A5E82', 1.1 * s, 1.55 * s, 2.0 * s), mottle(0.14, 3.5, 31))
    bark_col = chain(grad('#3A2A1C', '#6E5038', 0.0, 1.0 * s), mottle(0.15, 5.0, 33))
    # ---- pelvis
    pe = MAcc('pelvis')
    f = blob(pe, P(0, -0.02, 0.88), (0.36 * s, 0.27 * s, 0.22 * s), C['bark'], e=(0.8, 0.8), amp=0.03, freq=4, seed=4)
    recolor(pe, f, bark_col)
    cr.part('Pelvis', pe, P(0, 0, 0.88))
    # ---- torso: hunched fungal mass, bark plates, moss, sunk head, mushroom shelves
    t = MAcc('torso')
    f = blob(t, P(0.05, 0.10, 1.40), (0.64 * s, 0.48 * s, 0.50 * s), C['purple'], M=M.R('X', 24), e=(0.85, 0.85),
             amp=0.06, freq=2.2, seed=7, segs=32, rings=18)
    recolor(t, f, flesh)
    pits(t, f, 4.2, 17, 0.03, '#1C1020', thr=0.30)
    f = blob(t, P(0.56, 0.12, 1.7), (0.38 * s, 0.36 * s, 0.32 * s), C['purple'], e=(0.85, 0.85), amp=0.04, freq=3, seed=8)
    recolor(t, f, flesh)
    pits(t, f, 4.5, 19, 0.025, '#1C1020', thr=0.32)
    f = blob(t, P(-0.44, 0.14, 1.6), (0.25 * s, 0.25 * s, 0.22 * s), C['purple'], e=(0.85, 0.85), amp=0.03, freq=3, seed=9)
    recolor(t, f, flesh)
    for (x, y, z, hx, hy, hz, nx, ny, nz) in ((0.1, -0.24, 1.68, 0.34, 0.26, 0.07, 0, -0.6, 0.8),
                                              (0.62, -0.02, 1.94, 0.22, 0.2, 0.06, 0.4, -0.3, 0.86),
                                              (-0.3, -0.16, 1.76, 0.2, 0.18, 0.06, -0.4, -0.5, 0.75)):
        f = blob(t, P(x, y, z), (hx * s, hy * s, hz * s), C['bark'], M=look((nx, ny, nz)), e=(0.45, 0.6), amp=0.02, freq=7)
        recolor(t, f, bark_col)
    for (x, y, z, r) in ((0.4, 0.18, 1.98, 0.16), (-0.42, 0.18, 1.78, 0.12), (0, -0.02, 1.9, 0.14)):
        f = blob(t, P(x, y, z), (r * s, r * s, r * 0.45 * s), C['moss'], e=(0.9, 0.9), amp=0.02, freq=9, seed=2)
    # sunk head: a knot of bark with a heavy brow, deep sockets with glowing pupils, a cracked mouth and hanging moss
    f = blob(t, P(0, 0.50, 1.50), (0.20 * s, 0.18 * s, 0.17 * s), C['bark'], e=(0.75, 0.75), amp=0.035, freq=7, seed=3)
    recolor(t, f, bark_col)
    f = blob(t, P(0, 0.63, 1.60), (0.21 * s, 0.09 * s, 0.065 * s), C['bark_dk'], M=M.R('X', -12), e=(0.6, 0.6), amp=0.02, freq=9, seed=5)
    recolor(t, f, bark_col)
    for sx in (1, -1):
        horn(t, P(0.14 * sx, 0.60, 1.66), P(0.24 * sx, 0.56, 1.80), 0.045 * s, C['bark_dk'], bend=P(0.02 * sx, 0, 0.03), segs=6, n=5)
        ball(t, P(0.08 * sx, 0.645, 1.52), 0.058 * s, C['black'], 10, 7)
        ball(t, P(0.085 * sx, 0.67, 1.525), 0.03 * s, C['eye_green'], 8, 6)
    box(t, P(0, 0.665, 1.42), (0.17 * s, 0.03 * s, 0.038 * s), C['throat'], bevel=0.01)
    for k in range(4):
        x = -0.06 + 0.04 * k
        horn(t, P(x, 0.675, 1.44), P(x * 0.9, 0.685, 1.385), 0.014 * s, C['tooth'], segs=5, n=3)
    for k, x in enumerate((-0.10, 0.07)):
        drip(t, P(x, 0.62, 1.37), 0.22 * s, 0.018 * s, C['moss'], seed=40 + k)
    shelf(t, P(0.05, 0.42, 1.67), (0.3, 1, 0), 0.10 * s, 0.03 * s, droop=0.15)
    for (x, y, z, dx, dy, r) in ((0.3, -0.28, 1.92, 0.4, -1, 0.34), (-0.14, -0.32, 1.82, -0.3, -1, 0.3),
                                 (0.62, -0.16, 2.08, 0.8, -0.6, 0.26), (0.05, -0.34, 1.52, 0.1, -1, 0.26),
                                 (-0.48, -0.1, 1.86, -1, -0.4, 0.22), (0.7, 0.1, 2.16, 1, 0.2, 0.2),
                                 (0.42, -0.22, 1.6, 0.7, -0.7, 0.2)):
        shelf(t, P(x, y, z), (dx, dy, 0), r * s, 0.09 * s * r / 0.3, droop=0.25)
    cr.part('Torso', t, P(0, 0, 1.0), parent='Pelvis')
    # ---- huge club arm (right)
    ar = MAcc('arm_r')
    shp, elb = P(0.66, 0.10, 1.70), P(0.84, 0.24, 1.16)
    f = limb(ar, [shp, (shp + elb) * 0.5 + P(0.04, 0, 0), elb], [0.22 * s, 0.20 * s, 0.18 * s], C['root'], segs=12)
    f += ball(ar, elb, 0.19 * s, C['root'], 12, 8)
    recolor(ar, f, bark_col)
    cr.part('ArmR', ar, shp, parent='Torso')
    cl = MAcc('club')
    wr = P(0.86, 0.42, 0.56)
    f = limb(cl, [elb, (elb + wr) * 0.5 + P(0.04, 0, 0), wr], [0.19 * s, 0.24 * s, 0.28 * s], C['root'], segs=14)
    f += blob(cl, P(0.87, 0.48, 0.40), (0.33 * s, 0.31 * s, 0.27 * s), C['bark'], e=(0.75, 0.8), amp=0.04, freq=5, seed=5)
    recolor(cl, f, bark_col)
    for dx, dy in ((-0.14, 0.20), (0.0, 0.26), (0.14, 0.20), (0.24, 0.06)):
        q = P(0.87 + dx, 0.48 + dy * 0.6, 0.30)
        horn(cl, q, q + P(dx * 0.4, dy * 0.6, -0.16), 0.08 * s, C['bark_dk'], segs=7, n=5)
    for (x, y, z, dx, dy, r) in ((1.08, 0.30, 0.84, 1, -0.3, 0.16), (0.72, 0.16, 0.92, -0.6, -0.8, 0.14)):
        shelf(cl, P(x, y, z), (dx, dy, 0), r * s, 0.05 * s, droop=0.2)
    pits(cl, f, 5.0, 23, 0.02, '#2A1A12', thr=0.36)
    cr.part('ClubR', cl, elb, parent='ArmR')
    # ---- small claw arm (left)
    al = MAcc('arm_l')
    shl, ell = P(-0.50, 0.18, 1.62), P(-0.62, 0.34, 1.26)
    f = limb(al, [shl, (shl + ell) * 0.5, ell], [0.10 * s, 0.085 * s, 0.075 * s], C['root'], segs=9)
    f += ball(al, ell, 0.08 * s, C['root'], 9, 6)
    recolor(al, f, bark_col)
    cr.part('ArmL', al, shl, parent='Torso')
    hl = MAcc('hand_l')
    wl = P(-0.58, 0.54, 1.02)
    f = limb(hl, [ell, (ell + wl) * 0.5, wl], [0.07 * s, 0.065 * s, 0.06 * s], C['root'], segs=8)
    recolor(hl, f, bark_col)
    for dx, dy, dz in ((-0.08, 0.12, -0.20), (0.0, 0.16, -0.22), (0.08, 0.12, -0.20)):
        horn(hl, wl, wl + P(dx, dy, dz), 0.03 * s, C['bark_dk'], bend=P(0, 0.05, 0.02), segs=6, n=5)
    cr.part('HandL', hl, ell, parent='ArmL')
    # ---- root legs: thigh -> shin with a spreading root foot
    for sx, nm in ((1, 'R'), (-1, 'L')):
        tg = MAcc('thigh')
        hip, kn = P(0.32 * sx, 0.0, 0.86), P(0.40 * sx, 0.20, 0.48)
        f = limb(tg, [hip, (hip + kn) * 0.5 + P(0.05 * sx, -0.02, 0), kn], [0.20 * s, 0.19 * s, 0.15 * s], C['root'], segs=12)
        f += ball(tg, kn, 0.15 * s, C['root'], 11, 7)
        M.displace(tg, f, 0.02 * s, 7.0, 11 if sx > 0 else 12)
        recolor(tg, f, bark_col)
        cr.part('Thigh' + nm, tg, hip, parent='Pelvis')
        sh = MAcc('shin')
        an = P(0.40 * sx, 0.02, 0.15)
        f = limb(sh, [kn, (kn + an) * 0.5 + P(0, -0.04, 0), an], [0.14 * s, 0.14 * s, 0.17 * s], C['root'], segs=11)
        M.displace(sh, f, 0.02 * s, 7.0, 13 if sx > 0 else 14)
        f += root_foot(sh, an, 6, 0.50 * s, 0.09 * s, C['root'], seed=3 if sx > 0 else 5, spread=230, fwd=(0.2 * sx, 1, 0))
        recolor(sh, f, bark_col)
        cr.part('Shin' + nm, sh, kn, parent='Thigh' + nm)
    return cr


# ================================================================================================ 06 FLESH ENGINE

def engine(off=(0, 0, 0)):
    """Buggy -> Flesh Engine: the buggy itself mutated. Rusted body and roll cage grown through with purple flesh and
    tendons, a living engine pulsing under the hood, the right headlight turned into an eye, the grille into a jaw.
    Four spinning wheels, steering front axle. Ranged: spits acid bursts from the jaw. ~3.5 x 2.2 x 2.1 m."""
    cr = M.Creature('Mut_FleshEngine', '06_FleshEngine', 'Buggy', off)
    rust = C['rust_or']
    fl = chain(grad('#5E2A4A', '#A2567E', 0.6, 1.3), mottle(0.16, 5.0, 61, dark='#3A1428', dark_thr=0.45, dark_k=0.4))
    rustc = chain(mottle(0.12, 3.0, 63, dark='#5A2A16', dark_thr=0.35, dark_k=0.45))
    b = MAcc('body')
    box(b, (0, -0.05, 0.60), (1.34, 2.95, 0.16), C['rust_dk'], bevel=0.04)
    f = blob(b, (0, 1.12, 0.86), (0.74, 0.58, 0.17), rust, M=M.R('X', 9), e=(0.3, 0.5), amp=0.015, freq=5)
    f += blob(b, (0, -0.86, 0.94), (0.82, 0.72, 0.30), rust, e=(0.3, 0.5), amp=0.015, freq=5, seed=3)
    for sx in (1, -1):
        f += blob(b, (0.90 * sx, 1.05, 0.90), (0.31, 0.56, 0.17), rust, e=(0.35, 0.6), amp=0.015, freq=6, seed=4)
        f += blob(b, (0.95 * sx, -1.05, 1.02), (0.32, 0.64, 0.19), rust, e=(0.35, 0.6), amp=0.015, freq=6, seed=5)
        f += box(b, (0.72 * sx, -0.02, 0.86), (0.10, 1.05, 0.40), rust, bevel=0.03)
    recolor(b, f, rustc)
    # cockpit flesh: a pulsing mass where the driver sat, veins on it
    f = blob(b, (0, -0.10, 1.08), (0.46, 0.42, 0.30), C['magenta'], e=(0.8, 0.8), amp=0.04, freq=4, seed=6)
    recolor(b, f, fl)
    # roll cage, roof sheet, cracked windshield
    posts = [(0.56, 0.42), (-0.56, 0.42), (0.62, -0.62), (-0.62, -0.62)]
    for x, y in posts:
        cyl(b, (x, y, 0.95), (x * 0.92, y, 1.88), 0.045, C['rust_dk'], segs=8)
    for (x0, y0), (x1, y1) in (((0.56, 0.42), (-0.56, 0.42)), ((0.62, -0.62), (-0.62, -0.62)),
                               ((0.56, 0.42), (0.62, -0.62)), ((-0.56, 0.42), (-0.62, -0.62))):
        cyl(b, (x0 * 0.92, y0, 1.88), (x1 * 0.92, y1, 1.88), 0.045, C['rust_dk'], segs=8)
    cyl(b, (0.57, -0.62, 1.0), (-0.52, 0.40, 1.84), 0.04, C['rust_dk'], segs=8)
    box(b, (0.0, -0.18, 1.93), (1.02, 0.78, 0.04), C['rust'], M=M.R('Y', 3), bevel=0.01)
    box(b, (0.0, 0.47, 1.40), (1.02, 0.03, 0.62), C['glass'], M=M.R('X', -18), bevel=0.01)
    # flesh bursting from the gaps and tendons strapped over the panels
    for (x, y, z, hx, hy, hz) in ((0.60, 0.70, 0.98, 0.20, 0.24, 0.12), (-0.62, 0.66, 0.98, 0.18, 0.22, 0.11),
                                  (0.70, -0.40, 1.08, 0.18, 0.30, 0.14), (-0.70, -0.46, 1.06, 0.18, 0.28, 0.13),
                                  (0.0, -1.40, 1.02, 0.42, 0.16, 0.15)):
        f = blob(b, (x, y, z), (hx, hy, hz), C['magenta'], e=(0.8, 0.8), amp=0.03, freq=6, seed=int(x * 10 + 9))
        recolor(b, f, fl)
    tendons = [[(0.92, 1.38, 0.86), (0.45, 1.25, 1.04), (-0.05, 1.18, 1.06), (-0.55, 1.28, 1.02), (-0.93, 1.40, 0.84)],
               [(0.95, 0.70, 0.95), (0.40, 0.62, 1.05), (-0.40, 0.64, 1.06), (-0.96, 0.72, 0.94)],
               [(0.62, 0.42, 1.30), (0.30, 0.10, 1.25), (0.0, -0.10, 1.30)],
               [(0.98, -0.60, 1.18), (0.70, -1.00, 1.24), (0.30, -1.30, 1.12)],
               [(-0.98, -0.66, 1.16), (-0.66, -1.06, 1.22), (-0.24, -1.36, 1.10)],
               [(1.05, 1.28, 0.80), (1.10, 1.10, 0.62), (1.02, 1.0, 0.42)],
               [(-1.05, 1.26, 0.80), (-1.10, 1.08, 0.62), (-1.02, 0.98, 0.42)]]
    for k, pts in enumerate(tendons):
        f = limb(b, pts, [0.05 + 0.02 * (k % 2)] * len(pts), C['flesh'], segs=8, per=4)
        recolor(b, f, fl)
    for (x, y, z, hx, hy, hz) in ((0.0, 0.86, 1.04, 0.60, 0.36, 0.13), (0.86, 1.20, 1.04, 0.24, 0.38, 0.10),
                                  (-0.86, 1.18, 1.04, 0.24, 0.36, 0.10), (0.96, -1.02, 1.20, 0.24, 0.46, 0.10),
                                  (-0.96, -1.06, 1.20, 0.24, 0.44, 0.10), (0.0, -0.95, 1.22, 0.55, 0.30, 0.10)):
        f = blob(b, (x, y, z), (hx, hy, hz), C['magenta'], e=(0.75, 0.8), amp=0.025, freq=6, seed=int(abs(x) * 20 + y * 7 + 30))
        recolor(b, f, fl)
    for pts in (((-0.5, 0.80, 1.16), (-0.1, 0.92, 1.18), (0.3, 0.80, 1.17), (0.55, 0.62, 1.12)),
                ((0.80, 1.36, 1.12), (0.92, 1.10, 1.14), (0.86, 0.86, 1.10)),
                ((-0.9, -0.7, 1.29), (-0.96, -1.0, 1.31), (-0.9, -1.35, 1.27)),
                ((0.3, -0.85, 1.32), (0.0, -1.0, 1.33), (-0.3, -0.88, 1.32))):
        limb(b, list(pts), [0.016] * len(pts), C['glow_soft'], segs=5, per=4)
    # suspension coils wrapped by sinew
    for sx in (1, -1):
        for y, zb in ((1.05, 0.52), (-1.05, 0.58)):
            coil(b, (0.62 * sx, y, zb + 0.06), (0.66 * sx, y, zb + 0.46), 0.08, 0.018, 4.5, C['orange'])
            limb(b, [(0.60 * sx, y + 0.06, zb + 0.10), (0.70 * sx, y - 0.02, zb + 0.28), (0.62 * sx, y + 0.05, zb + 0.48)],
                 [0.025, 0.03, 0.025], C['flesh_dk'], segs=6, per=3)
    # upper fangs under the hood lip, left headlight, the eye socket's fleshy lids, exhaust
    for k in range(7):
        x = -0.45 + 0.15 * k
        horn(b, (x, 1.62, 0.76), (x * 0.95, 1.70, 0.56 - 0.05 * (k % 2)), 0.055, C['tooth'], bend=(0, 0.03, 0), segs=7, n=5)
    ball(b, (-0.55, 1.62, 0.92), (0.13, 0.08, 0.13), C['glass'], 12, 8)
    torus(b, V(-0.55, 1.64, 0.92), (0, 1, 0), 0.14, 0.025, C['rust_dk'], segs=16, rsegs=6)
    torus(b, V(0.55, 1.62, 0.92), (0, 1, 0), 0.19, 0.05, C['flesh'], segs=18, rsegs=8)
    blob(b, (0.55, 1.62, 1.08), (0.22, 0.10, 0.07), C['flesh_dk'], M=M.R('X', -10), e=(0.8, 0.8))
    f = limb(b, [(0.52, -1.30, 1.00), (0.58, -1.45, 1.30), (0.62, -1.55, 1.78)], [0.07, 0.07, 0.065], C['rust'], segs=10)
    torus(b, V(0.62, -1.55, 1.78), (0.05, -0.1, 1.0), 0.07, 0.022, C['rust_dk'], segs=12, rsegs=6)
    ball(b, (0, 1.34, 0.86), (0.36, 0.26, 0.12), C['throat'], 14, 8)
    torus(b, V(0, 1.24, 1.02), (0, 0.15, 1.0), 0.40, 0.04, C['rust_dk'], segs=22, rsegs=6)
    for k in range(10):
        a_ = 2 * math.pi * k / 10
        q = V(0.40 * math.cos(a_), 1.24 + 0.40 * math.sin(a_), 1.03)
        horn(b, q, q + V(0.07 * math.cos(a_), 0.07 * math.sin(a_), 0.09), 0.035, C['rust_dk'], segs=5, n=3)
    cr.part('Body', b, (0, 0, 0.75))
    # ---- the living engine (pulses), the eye (looks around), the jaw (opens to spit)
    e = MAcc('engine')
    ec = V(0, 1.24, 1.05)
    f = blob(e, ec, (0.34, 0.30, 0.19), C['glow'], e=(0.8, 0.8), amp=0.03, freq=6, seed=7)
    recolor(e, f, mottle(0.2, 6.0, 65, dark='#5A8A14', dark_thr=0.25, dark_k=0.5))
    for k in range(4):
        box(e, ec + V(-0.21 + 0.14 * k, -0.02, 0.15), (0.05, 0.36, 0.08), C['steel_dk'], bevel=0.012)
    limb(e, [ec + V(0.22, 0.08, 0.06), ec + V(0.40, 0.18, 0.12), ec + V(0.48, 0.32, 0.06)], [0.05, 0.05, 0.045], C['flesh'], segs=8)
    cr.part('Engine', e, ec, parent='Body')
    ey = MAcc('eye')
    eye(ey, (0.55, 1.66, 0.92), 0.165, (0.12, 1.0, 0.05), iris=C['eye'], slit=True)
    cr.part('Eye', ey, (0.55, 1.62, 0.92), parent='Body')
    jw = MAcc('jaw')
    f = blob(jw, (0, 1.70, 0.58), (0.62, 0.26, 0.09), C['magenta'], e=(0.5, 0.6), amp=0.02, freq=6, seed=8)
    recolor(jw, f, fl)
    for k in range(6):
        x = -0.42 + 0.168 * k
        box(jw, (x, 1.76, 0.64), (0.035, 0.36, 0.06), C['rust_dk'], bevel=0.01)
    for k in range(6):
        x = -0.40 + 0.16 * k
        horn(jw, (x, 1.86, 0.62), (x * 0.95, 1.90, 0.82 + 0.04 * (k % 2)), 0.06, C['tooth'], bend=(0, 0.03, 0), segs=7, n=5)
    cr.part('Jaw', jw, (0, 1.46, 0.62), parent='Body')
    cr.part('Muzzle', None, (0, 1.88, 0.76), parent='Body')
    # ---- wheels: front pair on steering pivots
    for sx, nm in ((1, 'R'), (-1, 'L')):
        fc = V(0.96 * sx, 1.05, 0.52)
        cr.part('SteerF' + nm, None, fc, parent='Body')
        w = MAcc('wheel_f')
        tire(w, fc, 0.52, 0.36)
        cr.part('WheelF' + nm, w, fc, parent='SteerF' + nm)
        rc = V(0.99 * sx, -1.05, 0.58)
        w = MAcc('wheel_b')
        tire(w, rc, 0.58, 0.42)
        cr.part('WheelB' + nm, w, rc, parent='Body')
    return cr


# ================================================================================================ 07 MIRE MOTHER

def mother(off=(0, 0, 0)):
    """BossBaron -> Mire Mother: a huge root-legged mother of the swamp. A rusted industrial tank is fused into the
    centre of her body as a heart, the glowing core bulging through a torn hatch; a crown of roots over it, bracket
    fungi on the flanks, glowing light-organs on the brow, moss hanging from everything. ~7.5 m wide, 6.3 m tall."""
    cr = M.Creature('Mut_MireMother', '07_MireMother', 'BossBaron', off)
    Z = 2.55
    flesh = chain(grad3('#2A2636', '#3C6A62', '#5C4A68', 1.3, 2.6, 3.7), mottle(0.16, 1.5, 51, dark='#1E1A2A', dark_thr=0.4, dark_k=0.4))
    rootc = chain(grad('#40283C', '#7E5874', 0.0, 4.6), mottle(0.15, 2.2, 53), blotches('#5E4430', 1.6, 55, thr=0.3, k=0.6))
    b = MAcc('body')
    f = blob(b, (0, 0.10, Z), (2.05, 2.25, 1.30), C['teal'], e=(0.8, 0.8), amp=0.14, freq=1.1, seed=5, segs=40, rings=22)
    recolor(b, f, flesh)
    pits(b, f, 1.8, 57, 0.10, '#120E16', thr=0.30)
    for sx in (1, -1):
        for sy in (1, -1):
            f = limb(b, [(1.45 * sx, 1.30 * sy, 2.45), (1.25 * sx, 1.00 * sy, 3.20), (0.75 * sx, 0.55 * sy, 3.62)],
                     [0.52, 0.36, 0.16], C['root'], segs=12)
            f += limb(b, [(1.75 * sx, 0.9 * sy, 2.2), (2.0 * sx, 0.2 * sy, 2.85), (1.6 * sx, -0.3 * sy, 3.3)],
                      [0.30, 0.24, 0.10], C['root'], segs=10)
            f += limb(b, [(1.2 * sx, 1.6 * sy, 2.0), (0.6 * sx, 2.1 * sy, 2.55), (0.1 * sx, 2.0 * sy, 3.2)],
                      [0.26, 0.2, 0.08], C['root'], segs=10)
            recolor(b, f, rootc)
    tc = V(0, -0.15, 3.98)
    f = ball(b, tc, 1.25, C['rust_or'], segs=34, rings=18)
    recolor(b, f, chain(grad('#6E3018', '#B8642E', tc.z - 1.2, tc.z + 1.1), mottle(0.12, 2.5, 59, dark='#4A2414', dark_thr=0.38, dark_k=0.5)))
    for dz in (-0.62, 0.0, 0.62):
        rr = math.sqrt(1.25 ** 2 - dz ** 2) + 0.03
        torus(b, tc + V(0, 0, dz), (0, 0, 1), rr, 0.06, C['rust_dk'], segs=34, rsegs=7)
    rv = []
    for k in range(18):
        a = 2 * math.pi * k / 18
        if 0.9 < a < 2.25:
            continue
        rv.append(tc + V(1.29 * math.cos(a), 1.29 * math.sin(a), 0.07))
    rivets(b, rv, 0.045)
    torus(b, tc + V(0, 0.95, 0), (0, 1, 0), 0.82, 0.09, C['rust_dk'], segs=26, rsegs=8)
    for k in range(9):
        a = 2 * math.pi * k / 9
        q = tc + V(0.82 * math.cos(a), 0.98, 0.82 * math.sin(a))
        horn(b, q, q + V(0.10 * math.cos(a), 0.18, 0.10 * math.sin(a)), 0.07, C['rust_dk'], segs=5, n=3)
    for sx in (1, -1):
        n = V(0.95 * sx, -0.15, 0.25).normalized()
        wc = tc + n * 1.255
        lathe_at(b, [(0.30, 0.0), (0.0, 0.0)], wc, n, C['glow'], segs=18, caps=(False, False))
        torus(b, wc, n, 0.31, 0.05, C['rust_dk'], segs=18, rsegs=6)
        limb(b, [tc + V(1.10 * sx, -0.45, -0.45), tc + V(1.55 * sx, -0.70, -1.0), V(1.75 * sx, -0.70, 2.95)],
             [0.11, 0.11, 0.11], C['rust'], segs=10)
        torus(b, tc + V(1.32 * sx, -0.58, -0.72), (0.6 * sx, -0.3, -0.7), 0.15, 0.04, C['rust_dk'], segs=12, rsegs=6)
    limb(b, [tc + V(-0.5, -1.05, -0.3), V(-0.75, -1.55, 3.30), V(-0.85, -1.95, 2.70)], [0.10, 0.10, 0.10], C['rust'], segs=10)
    top = tc + V(0, 0, 1.25)
    torus(b, top + V(0, 0, 0.38), (0, 0, 1), 0.66, 0.04, C['steel_dk'], segs=26, rsegs=6)
    for k in range(8):
        a = 2 * math.pi * k / 8
        p0 = tc + V(0.62 * math.cos(a), 0.62 * math.sin(a), math.sqrt(1.25 ** 2 - 0.62 ** 2) - 0.02)
        cyl(b, p0, V(p0.x, p0.y, top.z + 0.38), 0.03, C['steel_dk'], segs=6)
    cyl(b, top + V(0, 0, -0.05), top + V(0, 0, 0.12), 0.32, C['rust_dk'], segs=18)
    f = blob(b, (0, -0.15, 3.12), (1.42, 1.42, 0.48), C['teal'], e=(0.8, 0.8), amp=0.08, freq=2.0, seed=6)
    recolor(b, f, flesh)
    for a in (0.3, 1.2, 2.2, 3.4, 4.3, 5.3):
        p0 = tc + V(1.0 * math.cos(a), 1.0 * math.sin(a), -0.78)
        f = limb(b, [p0, tc + V(1.22 * math.cos(a), 1.22 * math.sin(a), -0.2), tc + V(1.18 * math.cos(a), 1.18 * math.sin(a), 0.42)],
                 [0.16, 0.11, 0.05], C['root'], segs=9)
        recolor(b, f, rootc)
    for (x, y, z, r) in ((0.0, 2.30, 2.75, 0.30), (0.75, 2.12, 2.55, 0.22), (-0.78, 2.10, 2.60, 0.24), (0.42, 2.25, 2.20, 0.16),
                         (-0.40, 2.26, 2.18, 0.15), (1.32, 1.72, 2.85, 0.18), (-1.30, 1.75, 2.82, 0.17), (1.85, 0.6, 2.95, 0.16),
                         (-1.88, 0.4, 2.90, 0.15), (0.2, 2.18, 3.18, 0.14)):
        ball(b, (x, y, z), r, C['glow'], 14, 10)
        torus(b, V(x, y, z) + (V(x, y, z) - V(0, 0, z)).normalized() * r * 0.2, (x, y, 0.1), r * 1.05, r * 0.2, C['flesh_dk'], segs=14, rsegs=6)
    for (x, y, z, dx, dy, r) in ((2.02, 0.50, 2.95, 1, 0.1, 0.62), (2.05, -0.40, 2.45, 1, -0.2, 0.52), (1.80, -1.20, 2.95, 0.8, -0.6, 0.45),
                                 (-2.02, 0.30, 2.90, -1, 0.1, 0.60), (-2.0, -0.60, 2.40, -1, -0.2, 0.50), (-1.75, -1.30, 3.0, -0.8, -0.6, 0.42),
                                 (0.95, -2.05, 3.05, 0.4, -1, 0.40), (-0.85, -2.05, 2.75, -0.4, -1, 0.38)):
        shelf(b, (x, y, z), (dx, dy, 0), r, 0.16 * r / 0.5, droop=0.2, segs=22)
    rnd = random.Random(71)
    for k in range(22):
        a = rnd.uniform(0, 2 * math.pi)
        p0 = V(1.85 * math.cos(a), 0.10 + 2.0 * math.sin(a), 1.55 + rnd.uniform(-0.1, 0.25))
        drip(b, p0, rnd.uniform(0.35, 0.95), rnd.uniform(0.035, 0.06), C['moss'], seed=k)
    cr.part('Body', b, (0, 0, Z))
    core = MAcc('core')
    f = blob(core, tc + V(0, 0.62, 0), (0.80, 0.72, 0.80), C['glow_core'], e=(0.85, 0.85), amp=0.05, freq=3.0, seed=9, segs=28, rings=16)
    recolor(core, f, mottle(0.18, 4.0, 67, dark='#86B82A', dark_thr=0.2, dark_k=0.55))
    cr.part('Core', core, tc, parent='Body')
    cw = MAcc('crown')
    for k in range(8):
        a = 2 * math.pi * (k + 0.25) / 8
        d = V(math.cos(a), math.sin(a), 0)
        p0 = tc + d * 0.95 + V(0, 0, 0.62)
        p1 = tc + d * 1.45 + V(0, 0, 1.35)
        p2 = tc + d * 1.85 + V(0, 0, 2.05 + 0.15 * (k % 3))
        p3 = tc + d * 2.35 + V(0, 0, 2.15 + 0.1 * (k % 2))
        f = limb(cw, [p0, p1, p2, p3], [0.20, 0.15, 0.09, 0.02], C['root'], segs=10)
        q = p1.lerp(p2, 0.5)
        f += limb(cw, [q, q + d * 0.35 + V(0, 0, 0.45), q + d * 0.65 + V(0.1, 0.1, 0.55)], [0.07, 0.04, 0.01], C['root'], segs=7)
        recolor(cw, f, rootc)
        if k % 2 == 0:
            drip(cw, p2 + V(0, 0, -0.05), 0.55, 0.045, C['moss'], seed=100 + k)
    cr.part('Crown', cw, tc + V(0, 0, 0.9), parent='Body')
    for sx, sy, nm in ((1, 1, 'FR'), (-1, 1, 'FL'), (1, -1, 'BR'), (-1, -1, 'BL')):
        up = MAcc('leg_up')
        hip, knee = V(1.45 * sx, 1.30 * sy, 2.35), V(2.78 * sx, 2.48 * sy, 3.18)
        f = limb(up, [hip, (hip + knee) * 0.5 + V(0, 0, 0.45), knee], [0.80, 0.66, 0.55], C['root'], segs=14)
        f += ball(up, knee, 0.56, C['root'], 14, 9)
        M.displace(up, f, 0.06, 2.6, 81 + int(sx + 2 * sy))
        f += strands(up, [hip, (hip + knee) * 0.5 + V(0, 0, 0.45), knee], 0.62, 0.17, 3, seed=int(5 + sx + 3 * sy))
        recolor(up, f, rootc)
        if sy > 0:
            shelf(up, (hip + knee) * 0.5 + V(0.25 * sx, 0.1 * sy, 0.42), (sx, sy * 0.4, 0), 0.40, 0.12, droop=0.2)
        cr.part('Leg' + nm, up, hip, parent='Body')
        lo = MAcc('leg_lo')
        ankle = V(3.15 * sx, 2.95 * sy, 0.70)
        f = limb(lo, [knee, (knee + ankle) * 0.5 + V(0.18 * sx, 0.18 * sy, 0.0), ankle], [0.56, 0.50, 0.56], C['root'], segs=14)
        M.displace(lo, f, 0.05, 2.6, 91 + int(sx + 2 * sy))
        f += strands(lo, [knee, (knee + ankle) * 0.5 + V(0.18 * sx, 0.18 * sy, 0.0), ankle], 0.52, 0.15, 3, seed=int(9 + sx + 3 * sy))
        f += root_foot(lo, ankle, 7, 1.85, 0.33, C['root'], seed=7 + int(sx * 3 + sy), spread=300, fwd=(sx, sy, 0))
        recolor(lo, f, rootc)
        for k in range(3):
            drip(lo, knee + V(0.1 * k * sx, -0.1 * k * sy, -0.35), 0.5 + 0.2 * k, 0.05, C['moss'], seed=200 + k)
        cr.part('Shin' + nm, lo, knee, parent='Leg' + nm)
    return cr


# parts that cast shadows in the game (the rest only receive): keeps a crowd of creatures cheap on phones
SHADOW_PARTS = {
    'Mut_Leechling': {'Body', 'Head', 'Rear'},
    'Mut_MireCrab': {'Body', 'PincerR', 'Leg1R', 'Leg2R', 'Leg1L', 'Leg2L'},
    'Mut_ReedStalker': {'Pelvis', 'Torso', 'Head', 'ThighR', 'ThighL', 'ShinR', 'ShinL', 'Spike'},
    'Mut_BileToad': {'Body', 'Head', 'Sac'},
    'Mut_SporeBrute': {'Torso', 'ArmR', 'ClubR', 'ThighR', 'ThighL'},
    'Mut_FleshEngine': {'Body', 'WheelFR', 'WheelFL', 'WheelBR', 'WheelBL'},
    'Mut_MireMother': {'Body', 'Crown', 'LegFR', 'LegFL', 'LegBR', 'LegBL'},
}


def apply_shadows(cr):
    keep = SHADOW_PARTS.get(cr.name)
    if keep is None:
        return
    for o in cr.parts:
        if o.get('mut_part') not in keep:
            o['tw_no_shadow'] = True


BUILDERS = {'leechling': leechling, 'crab': crab, 'stalker': stalker, 'toad': toad, 'brute': brute,
            'engine': engine, 'mother': mother}
