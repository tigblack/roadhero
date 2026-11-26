"""Toxic Wetlands environment kit: shared meshes for scatter, all on the TW_Trim atlas (one material).

Every builder returns a mesh datablock (Blender coords: z up, origin at the ground contact point). Instances of a
kit mesh share it (one buffer in the Unity bundle). Sizes follow the game camera (~0.05 m per pixel at the
default zoom): big readable silhouettes, rounded edges, a few large details, colour variation in the vertices.
Builders that stand in water take the water level into account through their placement (the scatter step).
"""
import math
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

import tw_lib as L
from tw_lib import Acc, P, Surf

T = Matrix.Translation


def R(ax, deg):
    return Matrix.Rotation(math.radians(deg), 4, ax)


def SC(x, y, z):
    return Matrix.Diagonal((x, y, z, 1.0))


def V(x, y, z):
    return Vector((x, y, z))


def S(h, gloss=0.05, metal=0.0, glow=0.0, strip='plain'):
    return Surf(h, gloss, metal, glow, strip, 'TW_Trim')


# environment palette on the trim atlas
E = {
    'dead':      S('#8A8272', 0.04, strip='bark'),
    'dead_dk':   S('#5C5446', 0.04, strip='bark'),
    'dead_wet':  S('#454033', 0.10, strip='bark'),
    'moss':      S('#FFFFFF', 0.05, strip='moss'),
    'moss_flat': S('#5F6B32', 0.05),
    'hangmoss':  S('#7E8866', 0.04),
    'reed':      S('#7E8446', 0.08),
    'reed_tip':  S('#B4A770', 0.05),
    'reed_dk':   S('#56612F', 0.08),
    'cattail':   S('#5B3A22', 0.10, strip='canvas'),
    'stalk':     S('#6E7A3E', 0.08),
    'shroom':    S('#C2A167', 0.20),
    'shroom_or': S('#B5652F', 0.25),
    'gill':      S('#E6D9B2', 0.10),
    'glowcap':   S('#B8E04A', 0.55, glow=0.55),
    'stone':     S('#707066', 0.03, strip='concrete'),
    'stone_dk':  S('#4F5048', 0.03, strip='concrete'),
    'mud':       S('#4B4632', 0.25, strip='mud'),
    'algae':     S('#5A7128', 0.25),
    'algae_dk':  S('#66802A', 0.25),
    'lily':      S('#5C7A34', 0.30),
    'toxic':     S('#B8E04A', 0.60, glow=0.55),
    'toxic_goo': S('#9BC23C', 0.65, glow=0.30),
    'drum_yel':  S('#D3A22F', 0.45, 0.12, strip='metal'),
    'drum_olive': S('#6C6D3D', 0.42, 0.12, strip='metal'),
    'drum_blue': S('#46637A', 0.42, 0.12, strip='metal'),
    'drum_red':  S('#9A3B2B', 0.42, 0.12, strip='metal'),
    'rust':      S('#FFFFFF', 0.18, 0.22, strip='rust'),
    'rust_pl':   S('#7E4025', 0.20, 0.25, strip='metal'),
    'steel':     S('#8E938F', 0.50, 0.70, strip='metal'),
    'steel_dk':  S('#454946', 0.45, 0.60, strip='metal'),
    'galv':      S('#A2A79F', 0.45, 0.55, strip='metal'),
    'tank':      S('#9A9F94', 0.40, 0.45, strip='panel'),
    'tank_dk':   S('#6F756C', 0.40, 0.45, strip='panel'),
    'tank_green': S('#6B7A5A', 0.40, 0.35, strip='panel'),
    'hazard':    S('#FFFFFF', 0.40, 0.10, strip='hazard'),
    'label':     S('#FFFFFF', 0.35, 0.05, strip='label'),
    'drips':     S('#FFFFFF', 0.30, 0.10, strip='drips'),
    'corr':      S('#8E9089', 0.40, 0.50, strip='corrugated'),
    'corr_rust': S('#9A6B4A', 0.30, 0.35, strip='corrugated'),
    'plank':     S('#7A6A52', 0.06, strip='plank'),
    'plank_dk':  S('#4F4436', 0.08, strip='plank'),
    'plank_gr':  S('#80796B', 0.05, strip='plank'),
    'post':      S('#4A3F31', 0.06, strip='bark'),
    'concrete':  S('#7A786C', 0.04, strip='concrete'),
    'concrete_dk': S('#5A5952', 0.04, strip='concrete'),
    'red':       S('#A23A26', 0.45, 0.15, strip='metal'),
    'yellow':    S('#D9A93A', 0.45, 0.10, strip='metal'),
    'black':     S('#202120', 0.35, 0.10),
    'tire':      S('#2A2B26', 0.18, strip='tire'),
    'glass':     S('#5E7A72', 0.85),
    'lamp':      S('#F2D27E', 0.40, glow=0.75),
    'tarp':      S('#6E7451', 0.08, strip='canvas'),
    'tarp_or':   S('#B5683A', 0.10, strip='canvas'),
    'mudsplat':  S('#FFFFFF', 0.12, strip='mud'),
}


def rnd(seed):
    return random.Random(seed)


def jitter_path(r, pts, amp):
    return [Vector(p) + Vector((r.uniform(-amp, amp), r.uniform(-amp, amp), r.uniform(-amp * 0.4, amp * 0.4))) for p in pts]


def curve(a, b, c, n=6):
    """Quadratic bezier a -> b (control) -> c."""
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(a * (1 - t) ** 2 + b * 2 * t * (1 - t) + c * t * t)
    return out


# ------------------------------------------------------------------------------------------------ vegetation

def dead_tree(seed, height=5.5, lean=6.0, broken=False, moss=True):
    """Bare swamp tree: flared root collar, twisting trunk, upswept branches, hanging moss strands."""
    r = rnd(seed)
    a = Acc('TW_DeadTree_%d' % seed)
    base_r = 0.2 + height * 0.022
    # trunk as a gently bent tube
    lean_dir = Vector((math.cos(r.uniform(0, 6.28)), math.sin(r.uniform(0, 6.28)), 0)) * math.tan(math.radians(lean))
    pts, rads = [], []
    top = height * (0.72 if broken else 1.0)
    n = 9
    for i in range(n + 1):
        t = i / n
        p = V(0, 0, t * top) + lean_dir * (t * t * top) + V(math.sin(t * 5 + seed) * 0.12, math.cos(t * 4 + seed) * 0.12, 0)
        pts.append(p)
        rads.append(base_r * (1.0 - 0.78 * t) * (1.25 if i == 0 else 1.0) + (0.0 if t < 1 else 0.0))
    if broken:
        rads[-1] = base_r * 0.35
    a.tube(pts, rads, E['dead'], segs=9, caps=True)
    if broken:
        # jagged broken top: a few splinters
        for k in range(4):
            ang = k * 1.57 + r.uniform(-0.3, 0.3)
            b0 = pts[-1] + V(math.cos(ang) * rads[-1] * 0.6, math.sin(ang) * rads[-1] * 0.6, 0)
            a.tube([b0, b0 + V(math.cos(ang) * 0.05, math.sin(ang) * 0.05, r.uniform(0.25, 0.6))], [rads[-1] * 0.35, 0.0], E['dead'], segs=5)
    # flared roots into the mud
    nr = r.randint(4, 6)
    for k in range(nr):
        ang = 2 * math.pi * k / nr + r.uniform(-0.3, 0.3)
        d = V(math.cos(ang), math.sin(ang), 0)
        L_ = r.uniform(0.8, 1.5) * base_r * 4
        a.tube([V(0, 0, 0.5) + d * base_r * 0.3, V(0, 0, 0.18) + d * L_ * 0.45, V(0, 0, -0.12) + d * L_],
               [base_r * 0.55, base_r * 0.32, 0.02], E['dead_wet'], segs=7)
    # branches
    nb = r.randint(3, 5) if not broken else r.randint(1, 3)
    for k in range(nb):
        t = r.uniform(0.45, 0.85 if not broken else 0.95)
        i = min(n - 1, int(t * n))
        start = pts[i]
        ang = r.uniform(0, 6.28)
        d = V(math.cos(ang), math.sin(ang), 0)
        blen = height * r.uniform(0.28, 0.42) * (1.0 - t * 0.4)
        mid = start + d * blen * 0.45 + V(0, 0, blen * 0.35)
        end = start + d * blen + V(0, 0, blen * r.uniform(0.45, 0.8))
        bp = curve(start, mid, end, 5)
        br = rads[i] * 0.55
        a.tube(bp, [br * (1 - 0.85 * j / 5) for j in range(6)], E['dead'], segs=7)
        # twig
        tw0 = bp[3]
        tw1 = tw0 + V(-d.y, d.x, 0) * blen * 0.35 * r.choice((-1, 1)) + V(0, 0, blen * 0.3)
        a.tube([tw0, (tw0 + tw1) / 2 + V(0, 0, 0.1), tw1], [br * 0.35, br * 0.2, 0.0], E['dead'], segs=5)
        # hanging moss strands under the branch
        if moss:
            for m in range(r.randint(1, 3)):
                q = bp[r.randint(2, 5)]
                ln = r.uniform(0.5, 1.2)
                a.tube([q, q + V(r.uniform(-0.05, 0.05), r.uniform(-0.05, 0.05), -ln * 0.5), q + V(0, 0, -ln)],
                       [0.055, 0.04, 0.0], E['hangmoss'], segs=5, flat=0.6)
    # moss collar on the base
    if moss:
        a.sphere((base_r * 1.5, base_r * 1.5, 0.22), T(V(0, 0, 0.08)), E['moss'], 12, 5)
    return a.build()


def reed_clump(seed, radius=0.6, height=1.6, cattails=4, dry=0.3):
    """Reeds: curved flat blades from a muddy base, straw-coloured tips, a few cattail heads."""
    r = rnd(seed)
    a = Acc('TW_Reeds_%d' % seed)
    nblades = int(18 + radius * 26)
    for i in range(nblades):
        ang = r.uniform(0, 6.28)
        d = r.uniform(0, radius)
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.05)
        hgt = height * r.uniform(0.55, 1.05)
        bend = V(math.cos(ang), math.sin(ang), 0) * hgt * r.uniform(0.08, 0.32) + V(r.uniform(-0.1, 0.1), r.uniform(-0.1, 0.1), 0)
        pts = [base, base + bend * 0.15 + V(0, 0, hgt * 0.4), base + bend * 0.55 + V(0, 0, hgt * 0.78), base + bend + V(0, 0, hgt)]
        col = E['reed_dk'].mix(E['reed'], r.uniform(0.2, 1.0))
        if r.random() < dry:
            col = col.mix(E['reed_tip'], 0.6)
        a.tube(pts, [0.03, 0.026, 0.016, 0.0], col, segs=4, flat=0.32, caps=False)
    for i in range(cattails):
        ang = r.uniform(0, 6.28); d = r.uniform(0, radius * 0.8)
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.05)
        hgt = height * r.uniform(1.0, 1.2)
        top = base + V(r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), hgt)
        a.tube([base, (base + top) / 2 + V(0, 0, 0.02), top], 0.012, E['stalk'], segs=4)
        a.cyl(0.04, 0.2, T(top - V(0, 0, 0.26)), E['cattail'], segs=7, bevel=0.015)
    # muddy hummock
    a.sphere((radius * 0.9, radius * 0.9, 0.12), T(V(0, 0, -0.03)), E['mud'], 10, 4)
    return a.build()


def reed_clump_lite(seed, radius=0.55, height=1.5, cattails=2, dry=0.3, blades=22):
    """Scatter version of reed_clump (~350 triangles): three-point blades with triangular sections."""
    r = rnd(seed)
    a = Acc('TW_ReedsLite_%d' % seed)
    for i in range(blades):
        ang = r.uniform(0, 6.28)
        d = r.uniform(0, radius) ** 0.8
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.06)
        hgt = height * r.uniform(0.55, 1.05)
        bend = V(math.cos(ang), math.sin(ang), 0) * hgt * r.uniform(0.1, 0.32)
        col = E['reed_dk'].mix(E['reed'], r.uniform(0.2, 1.0))
        if r.random() < dry:
            col = col.mix(E['reed_tip'], 0.6)
        a.tube([base, base + bend * 0.35 + V(0, 0, hgt * 0.6), base + bend + V(0, 0, hgt)], [0.035, 0.024, 0.0], col, segs=3, flat=0.35, caps=False)
    for i in range(cattails):
        ang = r.uniform(0, 6.28)
        d = r.uniform(0, radius * 0.7)
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.06)
        top = base + V(r.uniform(-0.1, 0.1), r.uniform(-0.1, 0.1), height * r.uniform(1.0, 1.2))
        a.tube([base, top], 0.012, E['stalk'], segs=3, caps=False)
        a.cyl(0.04, 0.2, T(top - V(0, 0, 0.26)), E['cattail'], segs=6)
    return a.build()


def grass_tuft(seed, radius=0.35):
    r = rnd(seed)
    a = Acc('TW_Tuft_%d' % seed)
    a.sphere((radius, radius * 0.9, radius * 0.38), T(V(0, 0, 0.0)), E['moss'], 10, 5)
    for i in range(10):
        ang = r.uniform(0, 6.28); d = r.uniform(0, radius * 0.8)
        base = V(math.cos(ang) * d, math.sin(ang) * d, 0.05)
        top = base + V(math.cos(ang) * 0.15, math.sin(ang) * 0.15, r.uniform(0.25, 0.5))
        a.tube([base, (base + top) / 2 + V(0, 0, 0.05), top], [0.025, 0.02, 0.0], E['reed'].mix(E['reed_tip'], r.random() * 0.5), segs=4, flat=0.35, caps=False)
    return a.build()


def stump(seed, radius=0.4, height=0.7):
    r = rnd(seed)
    a = Acc('TW_Stump_%d' % seed)
    prof = [(radius * 1.35, -0.1), (radius * 1.15, 0.08), (radius, 0.25), (radius * 0.95, height * 0.8), (radius * 0.9, height)]
    a.lathe(prof, 12, Matrix(), E['dead'], cap_bottom=False, cap_top=False)
    # jagged broken top
    for k in range(6):
        ang = k * 1.047 + r.uniform(-0.2, 0.2)
        p0 = V(math.cos(ang) * radius * 0.6, math.sin(ang) * radius * 0.6, height - 0.02)
        a.tube([p0, p0 + V(math.cos(ang) * 0.05, math.sin(ang) * 0.05, r.uniform(0.1, 0.35))], [radius * 0.32, 0.0], E['dead'], segs=5)
    a.lathe([(0.0, height - 0.02), (radius * 0.88, height - 0.02), (radius * 0.9, height)], 12, Matrix(), E['dead_dk'], cap_bottom=True, cap_top=False)
    for k in range(4):
        ang = k * 1.57 + r.uniform(-0.4, 0.4)
        d = V(math.cos(ang), math.sin(ang), 0)
        a.tube([d * radius * 0.7 + V(0, 0, 0.25), d * radius * 1.6 + V(0, 0, 0.05), d * radius * 2.4 + V(0, 0, -0.1)],
               [radius * 0.35, radius * 0.22, 0.02], E['dead_wet'], segs=6)
    # bracket fungi
    for k in range(r.randint(1, 3)):
        ang = r.uniform(0, 6.28)
        z = r.uniform(0.25, height - 0.1)
        p = V(math.cos(ang) * radius, math.sin(ang) * radius, z)
        a.sphere((0.16, 0.16, 0.045), T(p) @ R('Z', math.degrees(ang)), E['shroom_or'], 10, 4)
    a.sphere((radius * 1.3, radius * 1.3, 0.12), T(V(0, 0, 0.02)), E['moss'], 10, 4)
    return a.build()


def glow_shrooms(seed, n=5):
    r = rnd(seed)
    a = Acc('TW_GlowShrooms_%d' % seed)
    for i in range(n):
        ang = r.uniform(0, 6.28); d = r.uniform(0, 0.35)
        h = r.uniform(0.12, 0.32)
        c = V(math.cos(ang) * d, math.sin(ang) * d, 0)
        a.cyl(0.03, h, T(c), E['gill'], segs=8)
        cr = r.uniform(0.07, 0.15)
        a.lathe([(0.0, h + cr * 0.55), (cr * 0.7, h + cr * 0.45), (cr, h + cr * 0.12), (cr * 0.9, h), (0.0, h + 0.02)], 12, T(c), E['glowcap'], sharp=None)
    a.sphere((0.42, 0.42, 0.08), Matrix(), E['moss'], 10, 4)
    return a.build()


def boulder(seed, size=1.0, mossy=True):
    r = rnd(seed)
    a = Acc('TW_Boulder_%d' % seed)
    hx, hy, hz = size * r.uniform(0.8, 1.1), size * r.uniform(0.65, 0.9), size * r.uniform(0.45, 0.62)

    def deform(co):
        n = L.smooth_noise3(co, seed, 1.6 / size)
        k = 1.0 + 0.16 * n
        return Vector((co.x * k, co.y * k, max(co.z * k, -0.25 * hz)))
    faces = a.superellipsoid((hx, hy, hz), (0.55, 0.6), T(V(0, 0, hz * 0.55)), E['stone'], 18, 11, deform=deform)
    if mossy:
        # moss on the top surfaces: recolour loops by their height / normal
        for f in faces:
            if f.normal.z > 0.55:
                for l in f.loops:
                    l[a.main.lc] = E['moss_flat'].rgba
    return a.build()


def lily_mat(seed, radius=1.2, toxic=False):
    """Floating algae / duckweed mat (flat, irregular), sits on the water surface."""
    r = rnd(seed)
    a = Acc('TW_Algae_%d' % seed)
    n = 20
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        rr = radius * (0.86 + 0.1 * math.sin(ang * 2 + seed) + 0.05 * math.sin(ang * 5 + seed * 3) + r.uniform(-0.04, 0.04))
        pts.append((math.cos(ang) * rr, math.sin(ang) * rr * 0.8, 0.012))
    coords = [(0, 0, 0.016)] + pts
    faces = [(0, i + 1, (i + 1) % n + 1) for i in range(n)]
    a.poly(coords, faces, E['toxic_goo'] if toxic else E['algae'], sharp=None)
    # a few lily pads around
    for i in range(r.randint(2, 5)):
        ang = r.uniform(0, 6.28); d = radius * r.uniform(0.9, 1.4)
        c = V(math.cos(ang) * d, math.sin(ang) * d, 0.01)
        a.cyl(r.uniform(0.18, 0.3), 0.02, T(c), E['lily'], segs=10)
    return a.build()


def fallen_log(seed, length=4.5, radius=0.28):
    r = rnd(seed)
    a = Acc('TW_Log_%d' % seed)
    pts = [V(-length / 2 + length * i / 6, math.sin(i + seed) * 0.12, radius * 0.6 + math.sin(i * 0.7) * 0.05) for i in range(7)]
    a.tube(pts, [radius * (1.1 - 0.25 * i / 6) for i in range(7)], E['dead_wet'], segs=9)
    for k in range(3):
        p = pts[r.randint(1, 5)]
        a.tube([p, p + V(r.uniform(-0.3, 0.3), r.uniform(0.2, 0.5) * r.choice((-1, 1)), r.uniform(0.2, 0.45))], [radius * 0.4, 0.0], E['dead'], segs=5)
    a.sphere((length * 0.25, radius * 1.6, 0.1), T(pts[2] + V(0, 0, radius * 0.55)), E['moss'], 10, 4)
    return a.build()


# ------------------------------------------------------------------------------------------------ industrial

def drum(variant='yel', state='upright', seed=0, leak=False):
    """Chemical drum (0.6 x 0.88 m): rolled rims, two hoops, label band. state: upright / tipped / sunk."""
    a = Acc('TW_Drum_%s_%s_%d' % (variant, state, seed))
    body = {'yel': E['drum_yel'], 'olive': E['drum_olive'], 'blue': E['drum_blue'], 'red': E['drum_red'], 'rust': E['rust']}[variant]
    prof = [(0.0, 0.0), (0.27, 0.0), (0.295, 0.02), (0.3, 0.06), (0.3, 0.19), (0.315, 0.21), (0.3, 0.23), (0.3, 0.33),
            (0.302, 0.35), (0.302, 0.53), (0.3, 0.55), (0.3, 0.65), (0.315, 0.67), (0.3, 0.69), (0.3, 0.82), (0.295, 0.86),
            (0.27, 0.88), (0.0, 0.88)]
    bands = []
    for i in range(len(prof) - 1):
        if 8 <= i <= 9 and variant in ('yel', 'olive', 'blue'):
            bands.append(E['label'] if variant == 'yel' else E['hazard'])
        else:
            bands.append(body)
    M = Matrix()
    if state == 'tipped':
        M = T(V(0, 0, 0.3)) @ R('Y', 90) @ T(V(0, 0, -0.44))
    elif state == 'sunk':
        M = T(V(0, 0, -0.32)) @ R('X', 18) @ R('Y', 10)
    a.lathe(prof, 18, M, surf_fn=lambda i: bands[i], sharp=60)
    # bung on the lid
    a.cyl(0.04, 0.025, M @ T(V(0.13, 0.0, 0.88)), E['steel_dk'], segs=8)
    if leak:
        top = (M @ V(0.25, 0.0, 0.5)) if state != 'tipped' else (M @ V(0.0, 0.0, 0.88))
        a.tube([top, top + V(0.06, 0.0, -0.2), V(top.x + 0.1, top.y, 0.02)], [0.04, 0.03, 0.02], E['toxic'], segs=6)
        a.cyl(0.45, 0.012, T(V(top.x + 0.2, top.y, 0.0)) @ SC(1.0, 0.75, 1.0), E['toxic_goo'], segs=14)
    return a.build()


def storage_tank(seed=0, radius=2.6, height=4.6, color='tank'):
    """Leaking vertical storage tank: domed roof with a railing, ladder, rust streaks, valve and outlet pipe."""
    r = rnd(seed)
    a = Acc('TW_Tank_%d' % seed)
    body = E[color]
    # plinth
    a.cyl(radius + 0.25, 0.3, T(V(0, 0, -0.1)), E['concrete'], segs=28, bevel=0.06)
    prof = [(radius, 0.2), (radius, height * 0.33), (radius + 0.03, height * 0.34), (radius, height * 0.35), (radius, height * 0.66),
            (radius + 0.03, height * 0.67), (radius, height * 0.68), (radius, height)]
    bands = [body, E['steel_dk'], E['steel_dk'], body, E['steel_dk'], E['steel_dk'], E['drips']]
    a.lathe(prof, 30, Matrix(), surf_fn=lambda i: bands[min(i, len(bands) - 1)], cap_bottom=False, cap_top=False, sharp=60)
    dome = [(radius, height), (radius * 0.94, height + 0.18), (radius * 0.7, height + 0.42), (radius * 0.35, height + 0.56), (0.0, height + 0.6)]
    a.lathe(dome, 30, Matrix(), E['tank_dk'], cap_bottom=False, cap_top=False, sharp=None)
    # hazard band and big label
    a.lathe([(radius + 0.01, height * 0.82), (radius + 0.01, height * 0.9)], 30, Matrix(), E['hazard'], cap_bottom=False, cap_top=False)
    a.box((0.04, 1.0, 1.0), T(V(radius + 0.02, 0, height * 0.5)) @ R('Z', 0), E['label'], bevel=0.01)
    # rail on the roof edge
    for k in range(16):
        ang = 2 * math.pi * k / 16
        p = V(math.cos(ang) * (radius - 0.1), math.sin(ang) * (radius - 0.1), height + 0.1)
        a.cyl(0.025, 0.7, T(p), E['yellow'], segs=6)
    a.lathe([(radius - 0.08, height + 0.78), (radius - 0.12, height + 0.78), (radius - 0.12, height + 0.82), (radius - 0.08, height + 0.82)], 30,
            Matrix(), E['yellow'], cap_bottom=False, cap_top=False)
    # ladder
    ang = math.radians(200)
    d = V(math.cos(ang), math.sin(ang), 0)
    side = V(-d.y, d.x, 0)
    for s in (-1, 1):
        a.cyl_between(d * (radius + 0.18) + side * s * 0.22 + V(0, 0, 0.2), d * (radius + 0.18) + side * s * 0.22 + V(0, 0, height + 0.9), 0.03, E['steel'], segs=6)
    for k in range(int(height / 0.4)):
        z = 0.5 + k * 0.4
        a.cyl_between(d * (radius + 0.18) + side * -0.22 + V(0, 0, z), d * (radius + 0.18) + side * 0.22 + V(0, 0, z), 0.02, E['steel'], segs=5)
    # outlet pipe, valve wheel and a toxic leak
    ang2 = math.radians(r.uniform(-40, 40))
    d2 = V(math.cos(ang2), math.sin(ang2), 0)
    o0 = d2 * radius + V(0, 0, 0.7)
    o1 = d2 * (radius + 1.4) + V(0, 0, 0.7)
    o2 = d2 * (radius + 1.9) + V(0, 0, 0.25)
    a.tube([o0, o1, o2], 0.16, E['rust'], segs=10)
    a.cyl(0.24, 0.08, T(o1 * 0.5 + o0 * 0.5) @ (d2.to_track_quat('Z', 'Y').to_matrix().to_4x4()), E['steel_dk'], segs=12)
    vw = o0 * 0.5 + o1 * 0.5 + V(0, 0, 0.42)
    a.cyl_between(o0 * 0.5 + o1 * 0.5 + V(0, 0, 0.12), vw, 0.04, E['steel_dk'], segs=6)
    a.lathe([(0.2, -0.02), (0.24, -0.03), (0.25, 0.0), (0.24, 0.03), (0.2, 0.02), (0.2, -0.02)], 18, T(vw), E['red'], cap_bottom=False, cap_top=False)
    a.tube([o2, o2 + d2 * 0.25 + V(0, 0, -0.3)], [0.13, 0.11], E['toxic'], segs=8)
    a.cyl(1.2, 0.02, T(o2 + d2 * 0.6 + V(0, 0, -0.24)) @ SC(1.0, 0.8, 1.0), E['toxic_goo'], segs=18)
    return a.build()


def tank_collider(radius, height, name):
    a = Acc(name)
    a.cyl(radius + 0.2, height + 0.6, Matrix(), E['steel'], segs=12)
    return a.build()


def pipe_run(seed, pts, radius=0.42, support_every=6.0, rusty=True, name=None):
    """Pipeline on H-frame supports along a polyline (Blender coords, z = pipe centre height)."""
    a = Acc(name or 'TW_Pipe_%d' % seed)
    pts = [Vector(p) for p in pts]
    body = E['rust'] if rusty else E['galv']
    a.tube(pts, radius, body, segs=14)
    # flanges every few metres and supports
    total = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
    s = 0.0
    k = 0
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = (p1 - p0).length
        d = (p1 - p0).normalized()
        q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        t = support_every * 0.5 if i == 0 else 0.0
        while t < seg:
            c = p0 + d * t
            a.cyl(radius + 0.07, 0.12, T(c - d * 0.06) @ q, E['steel_dk'], segs=14, bevel=0.02)
            side = d.cross(V(0, 0, 1)).normalized()
            gz = 0.0
            for sgn in (-1, 1):
                foot = c + side * sgn * (radius + 0.2)
                a.box((0.16, 0.16, c.z + 0.2), T(V(foot.x, foot.y, (c.z + 0.2) / 2 - 0.1)), E['steel_dk'], bevel=0.03)
            a.box(((radius + 0.2) * 2 + 0.2, 0.18, 0.14), T(V(c.x, c.y, c.z - radius - 0.07)) @ R('Z', math.degrees(math.atan2(side.y, side.x))),
                  E['steel_dk'], bevel=0.03)
            a.box((0.6, 0.6, 0.2), T(V(c.x + side.x * (radius + 0.2), c.y + side.y * (radius + 0.2), -0.05)), E['concrete'], bevel=0.05)
            a.box((0.6, 0.6, 0.2), T(V(c.x - side.x * (radius + 0.2), c.y - side.y * (radius + 0.2), -0.05)), E['concrete'], bevel=0.05)
            t += support_every
            k += 1
    return a.build()


def outfall(seed, radius=0.45):
    """Broken pipe end pouring glowing sludge (placed at a pool edge)."""
    a = Acc('TW_Outfall_%d' % seed)
    a.tube([V(-3.0, 0, 0.5), V(-0.5, 0, 0.55), V(0, 0, 0.55)], radius, E['rust'], segs=14)
    a.cyl(radius + 0.06, 0.1, T(V(-0.05, 0, 0.55)) @ R('Y', 90), E['steel_dk'], segs=14, bevel=0.02)
    a.box((1.2, 1.4, 0.9), T(V(-2.4, 0, 0.3)), E['concrete'], bevel=0.12)
    a.tube([V(0.05, 0, 0.45), V(0.35, 0, 0.25), V(0.55, 0, -0.05)], [0.28, 0.22, 0.2], E['toxic'], segs=10, flat=0.55)
    a.cyl(1.0, 0.03, T(V(0.9, 0, -0.05)) @ SC(1.0, 0.8, 1.0), E['toxic'], segs=16)
    return a.build()


def pump_unit(seed=0):
    """Sludge pump: concrete pad, motor, pump volute, flywheel, in/out pipes, red valve wheel, hazard rail."""
    a = Acc('TW_Pump_%d' % seed)
    a.box((3.0, 2.0, 0.3), T(V(0, 0, 0.1)), E['concrete'], bevel=0.08)
    a.box((1.2, 0.9, 0.9), T(V(-0.7, 0, 0.75)), E['tank_green'], bevel=0.12)
    for i in range(5):
        a.box((0.04, 0.95, 0.75), T(V(-1.2 + i * 0.12, 0, 0.75)), E['steel_dk'], bevel=0.01)
    a.cyl(0.55, 0.5, T(V(0.5, 0.25, 0.85)) @ R('X', 90), E['rust'], segs=18, bevel=0.06)
    a.cyl(0.6, 0.12, T(V(0.5, -0.3, 0.85)) @ R('X', 90), E['steel_dk'], segs=18, bevel=0.03)
    a.cyl_between(V(0.5, 0.3, 0.85), V(0.5, 1.4, 0.85), 0.22, E['rust_pl'], segs=12)
    a.tube([V(0.5, 0.0, 1.35), V(0.5, 0.0, 1.9), V(1.2, 0.0, 2.1), V(1.8, 0.0, 1.9)], 0.18, E['galv'], segs=10)
    a.cyl_between(V(1.0, 0.0, 1.9), V(1.0, 0.0, 2.45), 0.04, E['steel_dk'], segs=6)
    a.lathe([(0.25, -0.025), (0.3, -0.035), (0.31, 0.0), (0.3, 0.035), (0.25, 0.025), (0.25, -0.025)], 20, T(V(1.0, 0.0, 2.45)), E['red'], cap_bottom=False, cap_top=False)
    a.cyl(0.35, 0.1, T(V(-1.35, 0.0, 0.75)) @ R('Y', 90), E['steel'], segs=16, bevel=0.02)
    for x in (-1.45, 1.45):
        for y in (-0.95, 0.95):
            a.cyl(0.04, 1.0, T(V(x, y, 0.25)), E['yellow'], segs=6)
    for y in (-0.95, 0.95):
        a.cyl_between(V(-1.45, y, 1.2), V(1.45, y, 1.2), 0.03, E['yellow'], segs=6)
    return a.build()


def boardwalk(seed, length=6.0, width=1.5, broken=0.25):
    """Rotten plank boardwalk on posts (x along its length), deck at z=0 + 0.12 (placed at water level)."""
    r = rnd(seed)
    a = Acc('TW_Boardwalk_%d' % seed)
    n = int(length / 0.32)
    for i in range(n):
        if r.random() < broken * (0.6 if 1 < i < n - 2 else 0.1):
            continue
        x = -length / 2 + (i + 0.5) * length / n
        tilt = r.uniform(-4, 4) if r.random() < 0.3 else 0.0
        drop = r.uniform(-0.12, 0.0) if r.random() < 0.2 else 0.0
        a.box((0.28, width * r.uniform(0.85, 1.0), 0.06), T(V(x, r.uniform(-0.05, 0.05), 0.12 + drop)) @ R('X', tilt) @ R('Z', r.uniform(-3, 3)),
              E['plank_gr'].mix(E['plank_dk'], r.random() * 0.6), bevel=0.012, segs=1)
    for sgn in (-1, 1):
        a.box((length, 0.1, 0.12), T(V(0, sgn * width * 0.42, 0.04)), E['plank_dk'], bevel=0.02, segs=1)
    k = int(length / 2.0) + 1
    for i in range(k):
        x = -length / 2 + i * length / max(1, k - 1)
        for sgn in (-1, 1):
            if r.random() < 0.15:
                continue
            a.cyl(0.07, 0.75 + r.uniform(0, 0.3), T(V(x, sgn * width * 0.48, -0.6)), E['post'], segs=7, bevel=0.02)
    return a.build()


def car_roof(seed):
    """Half-sunken car: rusty rounded body tilted into the mud, a mossy roof, broken window."""
    r = rnd(seed)
    a = Acc('TW_SunkCar_%d' % seed)
    M = T(V(0, 0, -0.25)) @ R('X', r.uniform(-8, 8)) @ R('Y', r.uniform(6, 14))
    a.box((1.8, 3.6, 0.7), M @ T(V(0, 0, 0.35)), E['rust'], bevel=0.25)
    a.box((1.5, 1.8, 0.55), M @ T(V(0, -0.2, 0.95)), E['rust_pl'], bevel=0.2)
    a.box((1.42, 0.05, 0.36), M @ T(V(0, 0.72, 0.95)) @ R('X', -30), E['glass'], bevel=0.02)
    a.sphere((0.7, 0.85, 0.08), M @ T(V(0, -0.2, 1.22)), E['moss'], 12, 4)
    for x in (-0.95, 0.95):
        a.cyl(0.38, 0.25, M @ T(V(x * 0.98, 1.05, 0.2)) @ R('Y', 90) @ T(V(0, 0, -0.12)), E['tire'], segs=12, bevel=0.06)
    return a.build()


def crate_stack(seed):
    r = rnd(seed)
    a = Acc('TW_Crates_%d' % seed)
    for i in range(r.randint(2, 4)):
        s = r.uniform(0.6, 0.9)
        p = V(r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), 0) if i < 2 else V(r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0.75)
        a.box((s, s, s), T(p + V(0, 0, s / 2)) @ R('Z', r.uniform(-25, 25)), E['plank'].mix(E['plank_dk'], r.random() * 0.5), bevel=0.05)
    return a.build()


def warning_sign(seed):
    a = Acc('TW_Sign_%d' % seed)
    a.cyl(0.05, 1.7, Matrix(), E['post'], segs=7)
    a.box((0.06, 0.8, 0.8), T(V(0.06, 0, 1.55)) @ R('X', 45), E['label'], bevel=0.02)
    return a.build()


def fence_run(seed, length=8.0):
    r = rnd(seed)
    a = Acc('TW_Fence_%d' % seed)
    k = int(length / 2.0) + 1
    tops = []
    for i in range(k):
        x = -length / 2 + i * length / (k - 1)
        h = r.uniform(1.0, 1.4)
        tilt = r.uniform(-8, 8)
        a.cyl(0.06, h + 0.2, T(V(x, 0, -0.2)) @ R('Y', tilt), E['post'], segs=6)
        tops.append(V(x + math.sin(math.radians(tilt)) * h, 0, h - 0.15))
    for z0 in (0.0, -0.4):
        for i in range(k - 1):
            p0, p1 = tops[i] + V(0, 0, z0), tops[i + 1] + V(0, 0, z0)
            mid = (p0 + p1) / 2 + V(0, 0, -0.18)
            a.tube([p0, mid, p1], 0.012, E['steel_dk'], segs=4)
    return a.build()


def concrete_slab(seed, w=2.5, d=1.6):
    r = rnd(seed)
    a = Acc('TW_Slab_%d' % seed)
    a.box((w, d, 0.3), T(V(0, 0, 0.05)) @ R('X', r.uniform(-12, 12)) @ R('Y', r.uniform(-8, 8)), E['concrete_dk'], bevel=0.06)
    for i in range(3):
        a.cyl_between(V(r.uniform(-w / 2, w / 2), r.uniform(-d / 2, d / 2), 0.15), V(r.uniform(-w / 2, w / 2), r.uniform(-d / 2, d / 2), 0.5), 0.02, E['rust_pl'], segs=5)
    return a.build()


def puddle(seed, radius=1.0):
    """Shallow surface puddle on dry mud (visual only, sits 5 mm over the ground)."""
    r = rnd(seed)
    a = Acc('TW_Puddle_%d' % seed)
    n = 16
    pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        rr = radius * (0.75 + 0.25 * math.sin(ang * 2 + seed) + r.uniform(-0.08, 0.08))
        pts.append((math.cos(ang) * rr, math.sin(ang) * rr * 0.7, 0.006))
    a.poly([(0, 0, 0.006)] + pts, [(0, i + 1, (i + 1) % n + 1) for i in range(n)], S('#3A402A', 0.6), sharp=None)
    return a.build()
