"""Ashen Winter level kit (runs inside Blender 5.2): the trim atlas, the palette and the environment pieces.

Contract (RoadGame/Toon, like every Blender pass of the project): 'Color' CORNER / FLOAT_COLOR (linear RGB, A < 1 =
self-lit), 'UVMap' (atlas strip / world tiling) and 'Unity_MaterialParams' (UV1: x gloss, y metal).
The modelling primitives come from the Toxic Wetlands kit (tw_lib.Acc) and the Ashen enemy kit (aw_lib: chipped
slabs, snow pillows, blades, cables, rings, pipes, railings, broken chimneys); LAcc paints them into the level's trim
atlas T_Trim_Ashen_BaseMap_2K.png instead of the creature atlas.
Blender x = Unity x, Blender y = Unity z (north), Blender z = up.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
PROJECT = os.path.abspath(os.path.join(ART, '..', '..', '..'))
for p in (os.path.join(PROJECT, 'ArtSource', 'Levels', 'ToxicWetlands', 'scripts'),
          os.path.join(PROJECT, 'ArtSource', 'Characters', 'AshenWinterEnemies', 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

import tw_lib as L  # noqa: E402
from tw_lib import Surf, hexlin, mixc, mulc, smooth_noise3  # noqa: E402,F401
import aw_lib as A  # noqa: E402
from aw_lib import (V, T, R, frame, basis, slab, snow_pillow, blade, cables, ring, pipe, railing,  # noqa: E402,F401
                    broken_chimney, horn, limb, ball, blob, lathe_at)

TRIM_STRIPS = ['plain', 'metal', 'rust', 'panel', 'corrugated', 'plank', 'concrete', 'hazard',
               'snow', 'ash', 'bark', 'grille', 'ice', 'tread', 'cloth', 'chevron']
TRIM_SCALE = {'plain': 4.0, 'metal': 4.0, 'rust': 3.0, 'panel': 4.0, 'corrugated': 4.0, 'plank': 4.0, 'concrete': 6.0,
              'hazard': 3.0, 'snow': 6.0, 'ash': 4.0, 'bark': 2.5, 'grille': 1.6, 'ice': 3.0, 'tread': 3.0, 'cloth': 3.0,
              'chevron': 64.0}
TRIM = 'AWL_Trim'
GROUND = 'AWL_Ground'
L.MAT_DEFS[TRIM] = dict(base='toon', tex='T_Trim_Ashen_BaseMap_2K.png')
L.MAT_DEFS[GROUND] = dict(base='ground', tex='T_Ground_Ashen_BaseMap_2K.png', world_uv=1.0 / 36.0)


def use_textures():
    L.TEX_DIR = os.path.join(ART, 'textures')


# lighter versions of the enemy kit's slab / snow pillow for the many pieces of a level (phone budget)
def slab(acc, c, size, surf=None, M_=Matrix(), seed=0, chip=0.05, e=0.16, segs=9, rings=6, sharp=None):
    return A.slab(acc, c, size, surf or P['concrete'], M_, seed, chip, e, segs, rings, sharp)


def snow_pillow(acc, c, half, M_=Matrix(), seed=0, surf=None, amp=0.25, segs=10, rings=5, k=0.78):
    return A.snow_pillow(acc, c, half, M_, seed, surf or P['snow'], amp, segs, rings, k)


def band(strip):
    if strip not in TRIM_STRIPS:
        strip = 'plain'
    i, n = TRIM_STRIPS.index(strip), len(TRIM_STRIPS)
    inset = 3.0 / 2048.0
    lo = 1.0 - (i + 1) / n
    return lo + inset, (1.0 / n) - 2 * inset


def S(h, gloss=0.05, metal=0.0, glow=0.0, strip='plain'):
    return Surf(h, gloss, metal, glow, strip, TRIM)


# Palette (art direction): dirty milky-grey snow, graphite / near-black ash, light neutral-grey concrete, dark steel
# with muted rust, cold grey-blue shadows (from the zone's shade), orange-amber accents (lamps, furnaces, stripes).
P = {
    'snow':        S('#DADDE2', 0.20, strip='snow'),
    'snow_dirty':  S('#BFC2C7', 0.16, strip='snow'),
    'snow_grey':   S('#A9ACB2', 0.12, strip='snow'),
    'ice':         S('#C3D2DE', 0.65, strip='ice'),
    'concrete':    S('#9D9B95', 0.04, strip='concrete'),
    'concrete_lt': S('#B4B2AB', 0.04, strip='concrete'),
    'concrete_dk': S('#73716B', 0.04, strip='concrete'),
    'concrete_bk': S('#4F4E4A', 0.04, strip='concrete'),
    'asphalt':     S('#3E3F42', 0.08, strip='concrete'),
    'asphalt_lt':  S('#55565A', 0.06, strip='concrete'),
    'ash':         S('#3D3C3C', 0.04, strip='ash'),
    'ash_lt':      S('#5E5C5B', 0.04, strip='ash'),
    'char':        S('#201E1E', 0.05, strip='ash'),
    'rock':        S('#5B5C60', 0.03, strip='concrete'),
    'rock_dk':     S('#424347', 0.03, strip='concrete'),
    'bark':        S('#3A3532', 0.03, strip='bark'),
    'bark_char':   S('#24201F', 0.03, strip='bark'),
    'rust':        S('#FFFFFF', 0.18, 0.25, strip='rust'),
    'rust_dk':     S('#6E3A22', 0.16, 0.25, strip='metal'),
    'rust_or':     S('#8E4E2A', 0.20, 0.25, strip='metal'),
    'steel':       S('#6A6E70', 0.45, 0.60, strip='metal'),
    'steel_dk':    S('#3C4042', 0.40, 0.55, strip='metal'),
    'panel':       S('#6E7072', 0.40, 0.50, strip='panel'),
    'corrugated':  S('#7A7C7E', 0.40, 0.45, strip='corrugated'),
    'hazard':      S('#FFFFFF', 0.36, 0.10, strip='hazard'),
    'chevron':     S('#FFFFFF', 0.10, 0.0, strip='chevron'),
    'paint_yel':   S('#D7A23A', 0.30, 0.05),
    'paint_or':    S('#C2622C', 0.30, 0.05),
    'stripe_red':  S('#A23A2E', 0.08, strip='concrete'),
    'stripe_wht':  S('#D9D7D2', 0.08, strip='concrete'),
    'grille':      S('#4A4C4E', 0.35, 0.50, strip='grille'),
    'black':       S('#141414', 0.30),
    'bore':        S('#0B0B0B', 0.10),
    'glass':       S('#2A3036', 0.80, 0.10),
    'lamp':        S('#FFC56A', 0.50, glow=0.80),
    'lamp_soft':   S('#F2A848', 0.40, glow=0.55),
    'fire':        S('#FF8A2A', 0.40, glow=0.88),
    'fire_core':   S('#FFD27A', 0.40, glow=0.95),
    'ember':       S('#C4501E', 0.30, glow=0.55),
    'wreck_red':   S('#7A3528', 0.22, 0.20, strip='metal'),
    'wreck_rust':  S('#8A4C2C', 0.18, 0.25, strip='rust'),
    'tire':        S('#262625', 0.20, strip='tread'),
    'tarp':        S('#5E6266', 0.08, strip='cloth'),
    'plank':       S('#5E5048', 0.05, strip='plank'),
    'cable':       S('#1E1E1E', 0.30),
}


class LAcc(L.Acc):
    """Mesh under construction, painted into the Ashen trim atlas."""

    def __init__(self, name, mat=TRIM):
        super().__init__(name, atlas='awl', mat=mat, box_tile=2.0)

    def paint(self, faces, surf, uv=None, sharp=None, smooth=True, part=None):
        pt = part or self.main
        mi = self.mat_index(surf.mat)
        rgba = surf.rgba
        prm = (surf.gloss, surf.metal)
        lo, h = band(surf.strip)
        us = TRIM_SCALE.get(surf.strip, 4.0)
        for f in faces:
            f.material_index = mi
            f.smooth = smooth
            if uv is None:
                n = f.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
            for lp in f.loops:
                lp[pt.lc] = rgba
                lp[pt.lp].uv = prm
                if uv is not None:
                    u, v = uv(lp, f)
                else:
                    co = lp.vert.co
                    u = (co.y, co.x, co.x)[ax] + 0.37 * (co.z, co.z, co.y)[ax]
                    v = 0.5
                lp[pt.luv].uv = (u / us, lo + max(0.0, min(1.0, v)) * h)
        if sharp is not None:
            self.sharpen(faces, sharp)
        return faces

    def subsurf_cage(self, cage_fn, levels=2, M_=Matrix(), sharp=None):
        raise NotImplementedError

    def build(self, name=None):
        me = super().build(name)
        me['tw_built'] = 'Ashen Winter pass'
        return me


def rnd(seed):
    return random.Random(seed)


prism_world = A.prism


def disc(acc, c, r, z, surf, segs=48, rim=None):
    """A flat disc (fan, counter-clockwise from above: normal up) at height z; rim=(r_out, z_out) adds a sloped skirt."""
    pts = [(c.x, c.y, z)]
    for k in range(segs):
        a = 2 * math.pi * k / segs
        pts.append((c.x + math.cos(a) * r, c.y + math.sin(a) * r, z))
    faces = [(0, 1 + k, 1 + (k + 1) % segs) for k in range(segs)]
    out = acc.poly(pts, faces, surf, sharp=None)
    if rim is not None:
        ro, zo = rim
        p2 = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            p2.append((c.x + math.cos(a) * r, c.y + math.sin(a) * r, z))
            p2.append((c.x + math.cos(a) * ro, c.y + math.sin(a) * ro, zo))
        f2 = [(2 * k, 2 * k + 1, (2 * k + 3) % (2 * segs), (2 * k + 2) % (2 * segs)) for k in range(segs)]
        out += acc.poly(p2, f2, surf, sharp=None)
    return out


def ring_band(acc, c, r0, r1, z, surf, nseg=24, gap=0.35, steps=4):
    """A dashed painted ring on a floor (counter-clockwise quads: normal up)."""
    out = []
    for k in range(nseg):
        a0 = 2 * math.pi * k / nseg
        a1 = a0 + 2 * math.pi / nseg * (1 - gap)
        pts = []
        for t in range(steps + 1):
            aa = a0 + (a1 - a0) * t / steps
            pts.append((c.x + math.cos(aa) * r0, c.y + math.sin(aa) * r0, z))
            pts.append((c.x + math.cos(aa) * r1, c.y + math.sin(aa) * r1, z))
        out += acc.poly(pts, [(2 * t, 2 * t + 1, 2 * t + 3, 2 * t + 2) for t in range(steps)], surf, sharp=None)
    return out


def recolor(acc, faces, fn):
    acc.recolor(faces, fn)


def snow_tint(acc, faces, up=0.5, k=0.9, surf=None):
    """Snow on top surfaces baked into the colours (no volume): faces whose normal points up go whiter."""
    surf = surf or P['snow']
    sc = surf.rgb
    acc.bm.normal_update()
    for f in faces:
        nz = f.normal.z
        if nz < up:
            continue
        t = min(1.0, (nz - up) / (1.0 - up)) * k
        for lp in f.loops:
            c = lp[acc.main.lc]
            lp[acc.main.lc] = (c[0] * (1 - t) + sc[0] * t, c[1] * (1 - t) + sc[1] * t, c[2] * (1 - t) + sc[2] * t, c[3])


def soot(lo, hi, k):
    return A.soot(lo, hi, k)


def ground_dirt(acc, faces, h=0.6, k=0.35):
    recolor(acc, faces, soot(0.0, h, k))


# ---------------------------------------------------------------------------------------------- road dressing

def jersey_barrier(acc, p, yaw, length=3.0, height=0.82, surf=None, seed=0, hazard=True):
    """A segmented concrete road barrier (jersey profile) centred at p (ground), long axis along yaw (deg from +y)."""
    surf = surf or P['concrete']
    prof = [(-0.30, 0.0), (-0.30, 0.08), (-0.20, 0.25), (-0.09, 0.75), (-0.09, height), (0.09, height), (0.09, 0.75),
            (0.20, 0.25), (0.30, 0.08), (0.30, 0.0)]
    n = len(prof)
    secs = []
    for y in (-length / 2, length / 2):
        secs.append([Vector((x, y, z)) for x, z in prof])
    M = T(p) @ R('Z', -yaw)
    faces = acc.loft(secs, surf, cap0=True, cap1=True, M=M, sharp=40)
    rr = rnd(seed)
    # chips on the ends, a hazard band near the top (the concept's orange-white marks), snow on the crown
    if hazard and seed % 3 != 1:
        acc.box((0.19, length * 0.36, 0.12), M @ T(V(0, rr.uniform(-0.6, 0.6), height - 0.22)), P['paint_or'], bevel=0.01)
    snow_tint(acc, faces, up=0.6, k=0.85)
    return faces


def lamp_post(acc, p, height=1.15, seed=0, glow=True):
    """A short concrete post with an amber caged lamp on top (the concept's road / rim lamps)."""
    acc.box((0.42, 0.42, height), T(V(p.x, p.y, p.z + height / 2)), P['concrete_lt'], bevel=0.03)
    top = V(p.x, p.y, p.z + height)
    acc.box((0.30, 0.30, 0.06), T(top + V(0, 0, 0.03)), P['steel_dk'], bevel=0.01)
    lathe_at(acc, [(0.0, 0.0), (0.12, 0.0), (0.13, 0.04), (0.13, 0.26), (0.10, 0.30), (0.0, 0.31)], top + V(0, 0, 0.06),
             V(0, 0, 1), P['lamp'] if glow else P['steel'], segs=10, sharp=40)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        acc.cyl_between(top + V(math.cos(a) * 0.14, math.sin(a) * 0.14, 0.06), top + V(math.cos(a) * 0.14, math.sin(a) * 0.14, 0.36),
                        0.012, P['steel_dk'], 4)
    acc.box((0.30, 0.30, 0.05), T(top + V(0, 0, 0.39)), P['steel_dk'], bevel=0.01)
    snow_pillow(acc, top + V(0, 0, 0.41), (0.12, 0.12, 0.035), seed=seed, surf=P['snow'])


# ---------------------------------------------------------------------------------------------- nature

def burnt_tree(acc, base, seed, height=6.0, lean=7.0, broken=None, branches=None):
    """A charred dead tree: tapered trunk (some broken off), a few big bare branches, snow in the forks."""
    r = rnd(seed)
    broken = r.random() < 0.45 if broken is None else broken
    h = height * (0.55 if broken else 1.0) * r.uniform(0.85, 1.15)
    lx, ly = math.radians(r.uniform(-lean, lean)), math.radians(r.uniform(-lean, lean))
    tip = base + V(math.sin(lx) * h, math.sin(ly) * h, h)
    pts = [base + V(0, 0, -0.2), base.lerp(tip, 0.33) + V(r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), 0),
           base.lerp(tip, 0.7) + V(r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 0), tip]
    r0 = r.uniform(0.22, 0.34) * height / 6.0
    faces = limb(acc, pts, [r0 * 1.25, r0, r0 * 0.7, r0 * (0.55 if broken else 0.08)], P['bark_char'] if r.random() < 0.5 else P['bark'],
                 segs=7, per=3)
    if broken:
        # a splintered top
        for k in range(4):
            a = 2 * math.pi * k / 4 + r.random()
            b0 = tip + V(math.cos(a) * r0 * 0.35, math.sin(a) * r0 * 0.35, -0.05)
            faces += horn(acc, b0, b0 + V(math.cos(a) * 0.05, math.sin(a) * 0.05, r.uniform(0.25, 0.6)), r0 * 0.35, P['bark'], segs=4, n=3)
    nb = (r.randint(2, 4) if branches is None else branches) if not broken else r.randint(1, 2)
    for k in range(nb):
        t = r.uniform(0.45, 0.85)
        b0 = base.lerp(tip, t)
        a = r.uniform(0, 2 * math.pi)
        L_ = h * r.uniform(0.25, 0.45)
        b1 = b0 + V(math.cos(a) * L_ * 0.7, math.sin(a) * L_ * 0.7, L_ * 0.6)
        faces += limb(acc, [b0, b0.lerp(b1, 0.5) + V(0, 0, L_ * 0.12), b1], [r0 * 0.45, r0 * 0.3, r0 * 0.06], P['bark_char'], segs=5, per=2)
        if r.random() < 0.6:
            b2 = b0.lerp(b1, 0.6)
            faces += limb(acc, [b2, b2 + V(math.cos(a + 0.9) * L_ * 0.35, math.sin(a + 0.9) * L_ * 0.35, L_ * 0.3)], [r0 * 0.18, 0.01],
                          P['bark_char'], segs=4, per=2)
        snow_pillow(acc, b0 + V(math.cos(a) * r0 * 0.6, math.sin(a) * r0 * 0.6, r0 * 0.4), (r0 * 0.9, r0 * 0.9, r0 * 0.35), seed=seed + k)
    # ash and snow round the foot
    acc.sphere((r0 * 3.0, r0 * 3.0, 0.16), T(base + V(0, 0, -0.06)), P['ash'], 10, 4)
    return faces


def rock_outcrop(acc, c, size, seed, snow=True, surf=None):
    """A chunky rock / concrete outcrop: a few chipped blocks, snow on top. size: (x, y, z) of the main block."""
    r = rnd(seed)
    surf = surf or (P['rock'] if r.random() < 0.6 else P['rock_dk'])
    faces = []
    n = r.randint(2, 3)
    for k in range(n):
        s = (size[0] * r.uniform(0.5, 1.0), size[1] * r.uniform(0.5, 1.0), size[2] * r.uniform(0.45, 1.0) * (1.0 if k == 0 else 0.7))
        off = V(r.uniform(-0.35, 0.35) * size[0], r.uniform(-0.35, 0.35) * size[1], 0) if k else V(0, 0, 0)
        M = R('Z', r.uniform(0, 360)) @ R('X', r.uniform(-12, 12)) @ R('Y', r.uniform(-12, 12))
        p = c + off + V(0, 0, s[2] * 0.42)
        faces += slab(acc, p, s, surf, M_=M, seed=seed * 7 + k, chip=0.12 * max(s) / 2.0, e=0.35)
        if snow:
            top = p + (M @ Vector((0, 0, s[2] * 0.5)))
            snow_pillow(acc, top, (s[0] * 0.35, s[1] * 0.35, 0.08), M, seed=seed + k, surf=P['snow'])
    return faces


def snow_drift(acc, c, half, yaw, seed, surf=None):
    """A wind-blown drift: a long low lumpy mound, steeper on the windward side."""
    surf = surf or P['snow']
    return snow_pillow(acc, c, half, R('Z', yaw), seed=seed, surf=surf, amp=0.35, k=1.0)


# ---------------------------------------------------------------------------------------------- wrecks and clutter

def car_wreck(acc, c, yaw, seed, kind='car'):
    """A burnt-out car (rusty shell, empty windows, sunk in snow) or a van / truck cab, snow on the roof and the hood."""
    r = rnd(seed)
    M = T(c) @ R('Z', yaw) @ R('X', r.uniform(-4, 4)) @ R('Y', r.uniform(-5, 5))
    body = P['wreck_rust'] if r.random() < 0.55 else P['wreck_red']
    faces = []
    if kind == 'car':
        faces += acc.box((1.8, 4.2, 0.62), M @ T(V(0, 0, 0.55)), body, bevel=0.12)
        faces += acc.box((1.62, 2.1, 0.52), M @ T(V(0, -0.25, 1.1)), body, bevel=0.12)
        for x in (-0.82, 0.82):
            faces += acc.box((0.06, 1.7, 0.36), M @ T(V(x, -0.25, 1.1)), P['bore'], bevel=0.02)
        faces += acc.box((1.5, 0.06, 0.34), M @ T(V(0, 0.83, 1.1)), P['bore'], bevel=0.02)
        for x in (-0.86, 0.86):
            for y in (-1.3, 1.3):
                faces += acc.cyl_between(M @ V(x - 0.1 * math.copysign(1, x), y, 0.32), M @ V(x + 0.05 * math.copysign(1, x), y, 0.32),
                                         0.30, P['rust_dk'], 10)
        snow_pillow(acc, M @ V(0, -0.25, 1.38), (0.7, 0.9, 0.12), M.to_3x3().to_4x4(), seed=seed, surf=P['snow'])
        snow_pillow(acc, M @ V(0, 1.4, 0.88), (0.75, 0.5, 0.08), M.to_3x3().to_4x4(), seed=seed + 1, surf=P['snow'])
    else:
        faces += acc.box((2.3, 2.2, 1.9), M @ T(V(0, 2.6, 1.35)), body, bevel=0.12)
        faces += acc.box((2.2, 0.06, 0.6), M @ T(V(0, 3.72, 1.75)), P['bore'], bevel=0.02)
        faces += acc.box((2.5, 6.2, 2.5), M @ T(V(0, -1.75, 1.75)), P['corrugated'], bevel=0.08)
        faces += acc.box((2.6, 7.6, 0.3), M @ T(V(0, -0.7, 0.55)), P['steel_dk'], bevel=0.04)
        for y in (2.7, -0.6, -3.6):
            for x in (-1.1, 1.1):
                faces += acc.cyl_between(M @ V(x * 1.02, y, 0.48), M @ V(x * 1.18, y, 0.48), 0.48, P['tire'], 12)
        snow_pillow(acc, M @ V(0, -1.75, 3.0), (1.1, 2.9, 0.16), M.to_3x3().to_4x4(), seed=seed, surf=P['snow'])
        snow_pillow(acc, M @ V(0, 2.6, 2.3), (1.0, 0.9, 0.1), M.to_3x3().to_4x4(), seed=seed + 2, surf=P['snow'])
    acc.sphere((2.2 if kind == 'car' else 3.0, 3.0 if kind == 'car' else 5.0, 0.35), M @ T(V(0, 0, 0.0)), P['snow_dirty'], 14, 5)
    return faces


def concrete_block(acc, c, yaw, seed, size=(1.6, 1.0, 0.8)):
    f = slab(acc, c + V(0, 0, size[2] / 2), size, P['concrete'] if seed % 2 else P['concrete_lt'], M_=R('Z', yaw), seed=seed,
             chip=0.05, e=0.18)
    snow_pillow(acc, c + V(0, 0, size[2]), (size[0] * 0.4, size[1] * 0.4, 0.06), R('Z', yaw), seed=seed, surf=P['snow'])
    return f


def drum(acc, c, seed, lying=False):
    r = rnd(seed)
    surf = P['rust'] if r.random() < 0.5 else P['steel_dk']
    M = T(c) @ (R('X', 90) @ R('Z', r.uniform(0, 360)) if lying else R('Z', r.uniform(0, 360)))
    z0 = 0.3 if lying else 0.0
    f = A.lathe_at(acc, [(0.0, 0.0), (0.29, 0.0), (0.3, 0.04), (0.29, 0.30), (0.305, 0.32), (0.29, 0.34), (0.29, 0.86),
                         (0.3, 0.9), (0.0, 0.9)], c + V(0, 0, z0) if not lying else c + V(0, 0, 0.3),
                   (M.to_3x3() @ Vector((0, 0, 1))), surf, segs=14, sharp=45)
    return f


# ---------------------------------------------------------------------------------------------- landmarks

def lattice_pylon(acc, base, height=18.0, width=4.0, seed=0, top_width=1.2, arms=True, surf=None):
    """A lattice power pylon (four legs, X-bracing, cross arms with insulators), rusty."""
    surf = surf or P['rust_or']
    r = rnd(seed)
    faces = []
    legs = [V(sx, sy, 0) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    levels = 7
    def P_(k, li):
        t = li / levels
        w = width * (1 - t) + top_width * t
        return base + V(legs[k].x * w / 2, legs[k].y * w / 2, height * t)
    rr = 0.07 * height / 18.0
    for k in range(4):
        faces += acc.tube([P_(k, li) for li in range(levels + 1)], rr * 1.3, surf, 6, caps=True)
    for li in range(levels):
        for k in range(4):
            a0, a1 = P_(k, li), P_((k + 1) % 4, li)
            b0, b1 = P_(k, li + 1), P_((k + 1) % 4, li + 1)
            faces += acc.cyl_between(a0, b1, rr * 0.6, surf, 4)
            faces += acc.cyl_between(a1, b0, rr * 0.6, surf, 4)
            faces += acc.cyl_between(b0, b1, rr * 0.7, surf, 4)
    if arms:
        for zt, span in ((0.78, 3.2), (0.93, 2.4)):
            z = height * zt
            w = width * (1 - zt) + top_width * zt
            for s in (-1, 1):
                a = base + V(s * w / 2, 0, z)
                b = base + V(s * (w / 2 + span), 0, z + 0.1)
                faces += acc.cyl_between(a + V(0, -0.25, 0), b, rr * 0.8, surf, 4)
                faces += acc.cyl_between(a + V(0, 0.25, 0), b, rr * 0.8, surf, 4)
                faces += acc.cyl_between(a + V(0, 0, -0.9), b, rr * 0.6, surf, 4)
                for k in range(3):
                    faces += acc.cyl_between(b + V(0, 0, -0.05 * k), b + V(0, 0, -0.55), 0.05 + 0.02 * (k == 1), P['glass'] if k == 1 else P['steel_dk'], 6)
    return faces


def arm_points(base, height=18.0, width=4.0, top_width=1.2):
    """Wire attachment points (insulator ends) of a lattice_pylon: [(x offset side, z)] in world."""
    pts = []
    for zt, span in ((0.78, 3.2), (0.93, 2.4)):
        z = height * zt
        w = width * (1 - zt) + top_width * zt
        for s in (-1, 1):
            pts.append(base + V(s * (w / 2 + span), 0, z + 0.1 - 0.55))
    return pts


def wire(acc, a, b, sag, r=0.022, n=14):
    """A sagging cable between a and b (catenary approximated by a parabola)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t) + V(0, 0, -4 * sag * t * (1 - t))
        pts.append(p)
    return acc.tube(pts, r, P['cable'], 5, caps=True)


def broken_wire(acc, a, length, seed):
    """A snapped cable hanging from a, curling at the end."""
    r = rnd(seed)
    d = V(r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), -1).normalized()
    pts = [a, a + d * length * 0.5, a + d * length + V(r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5), 0.2)]
    return acc.tube(A.catmull(pts, 3), 0.02, P['cable'], 5, caps=True)


def cooling_tower(acc, base, r_base, r_waist, r_top, height, seed=0, crack_az=150.0, crack_w=22.0, segs=64, rings=22, lod=False):
    """A hyperboloid cooling tower with a thick shell (inner wall), a faded red-white band under the rim, a big
    vertical crack (a V-shaped notch through the shell) and snow on the rim. crack_az: compass degrees (0 = +y)."""
    pt = L._Part()
    bm = pt.bm
    wall = 0.65
    waist_t = 0.72

    def radius(t):
        # hyperbola through base / waist / top
        if t <= waist_t:
            k = (waist_t - t) / waist_t
            return r_waist + (r_base - r_waist) * k ** 1.7
        k = (t - waist_t) / (1 - waist_t)
        return r_waist + (r_top - r_waist) * k ** 1.5
    segs = 40 if lod else segs
    rings = 12 if lod else rings

    def crack_depth(az_deg):
        d = abs(((az_deg - crack_az + 180) % 360) - 180)
        return max(0.0, 1.0 - d / (crack_w * 0.5))
    outer, inner = [], []
    for j in range(rings + 1):
        t = j / rings
        ro, ri = [], []
        for s in range(segs):
            a = 2 * math.pi * s / segs
            az = (90 - math.degrees(a)) % 360
            cd = crack_depth(az)
            # the crack: the shell is missing above a jagged line that drops toward the crack's centre
            jag = 0.06 * math.sin(s * 2.3 + seed) + 0.04 * math.sin(s * 5.1)
            limit = 1.0 - 0.62 * cd + jag * cd
            tt = min(t, limit) if cd > 0 else t
            rr = radius(tt)
            z = height * tt
            ro.append(bm.verts.new(base + V(math.cos(a) * rr, math.sin(a) * rr, z)))
            ri.append(bm.verts.new(base + V(math.cos(a) * (rr - wall), math.sin(a) * (rr - wall), z)))
        outer.append(ro)
        inner.append(ri)
    faces = []
    for j in range(rings):
        for s in range(segs):
            s1 = (s + 1) % segs
            for ring_, flip in ((outer, False), (inner, True)):
                q = [ring_[j][s], ring_[j][s1], ring_[j + 1][s1], ring_[j + 1][s]]
                try:
                    faces.append(bm.faces.new(list(reversed(q)) if flip else q))
                except ValueError:
                    pass
    for s in range(segs):
        s1 = (s + 1) % segs
        try:
            faces.append(bm.faces.new([outer[rings][s], outer[rings][s1], inner[rings][s1], inner[rings][s]]))
        except ValueError:
            pass
    bm.normal_update()
    # remove collapsed faces (where the crack flattened rings onto each other)
    dead = [f for f in faces if f.is_valid and f.calc_area() < 1e-5]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    faces = [f for f in bm.faces]
    acc.paint(faces, P['concrete'], None, part=pt)
    # colours: a faded red-white band under the rim, darker weathering streaks, snow on the rim, dark inside
    for f in faces:
        cen = f.calc_center_median()
        t = (cen.z - base.z) / height
        rr = (Vector((cen.x, cen.y)) - Vector((base.x, base.y))).length
        inside = rr < radius(min(1.0, max(0.0, t))) - wall * 0.5
        for lp in f.loops:
            p = lp.vert.co
            tt = (p.z - base.z) / height
            if inside:
                c = (0.10, 0.10, 0.11, 1.0)
            elif 0.84 < tt < 0.92:
                c = P['stripe_red'].rgba
            elif 0.80 < tt <= 0.84 or 0.92 <= tt < 0.95:
                c = P['stripe_wht'].rgba
            else:
                n = smooth_noise3(V(p.x * 0.15, p.y * 0.15, p.z * 0.05), seed, 1.0)
                k = 0.82 + 0.14 * n - 0.15 * (1 - tt) ** 2
                base_c = P['concrete'].rgb
                c = (base_c[0] * k, base_c[1] * k, base_c[2] * k, 1.0)
            lp[pt.lc] = c
    return acc._commit(pt)


def striped_chimney(acc, base, r_base, r_top, height, bands=8, segs=24):
    """The tall red-white chimney of the plant: alternating bands, a dark rim, a gallery ring."""
    prof = [(0.0, 0.0)]
    surfs = []
    for k in range(bands):
        t0, t1 = k / bands, (k + 1) / bands
        prof.append((r_base + (r_top - r_base) * t0, height * t0))
        prof.append((r_base + (r_top - r_base) * t1, height * t1))
    prof.append((r_top * 0.86, height))
    prof.append((r_top * 0.86, height - 1.0))
    surf_fn = lambda i: (P['stripe_red'] if (i // 2) % 2 == 0 else P['stripe_wht'])
    faces = acc.lathe(prof, segs, T(base), P['stripe_wht'], True, False, 50, surf_fn=surf_fn)
    for zt in (0.62, 0.9):
        faces += ring(acc, base + V(0, 0, height * zt), V(0, 0, 1), r_base + (r_top - r_base) * zt + 0.35, 0.15, 0.35, P['steel_dk'], segs=24)
    return faces


def workshop(acc, c, half_x, half_z, height, seed=0, opening=True, lod=False):
    """A ruined reactor workshop: concrete frame with storeys, broken floor slabs, a rusty steel roof truss, and a hot
    furnace opening in the front (south) wall. c: centre of the footprint on the ground (Blender x, y)."""
    r = rnd(seed)
    faces = []
    nx, nfl = 4, 3
    fh = height / (nfl + 0.6)
    # columns and beams
    for i in range(nx + 1):
        x = -half_x + 2 * half_x * i / nx
        for y in (-half_z, half_z):
            hcol = height * (1.0 if r.random() > 0.25 else r.uniform(0.6, 0.9))
            faces += acc.box((0.7, 0.7, hcol), T(c + V(x, y, hcol / 2)), P['concrete'], bevel=0.03)
    for k in range(1, nfl + 1):
        z = fh * k
        for y in (-half_z, half_z):
            faces += acc.box((2 * half_x + 0.7, 0.6, 0.55), T(c + V(0, y, z)), P['concrete_dk'], bevel=0.02)
        # floor slabs, some broken (tilted / missing)
        for i in range(nx):
            x0 = -half_x + 2 * half_x * i / nx
            if r.random() < 0.25:
                continue
            tilt = R('Y', r.uniform(-14, 14)) if r.random() < 0.3 else Matrix()
            faces += slab(acc, c + V(x0 + half_x / nx, 0, z + 0.2), (2 * half_x / nx - 0.2, 2 * half_z - 0.3, 0.32),
                          P['concrete_lt'], M_=tilt, seed=seed * 13 + i * 7 + k, chip=0.06, e=0.12)
    # back wall (north, +y) and side walls, partly broken (lower storeys)
    faces += acc.box((2 * half_x, 0.5, fh * 2.2), T(c + V(0, half_z - 0.1, fh * 1.1)), P['concrete_dk'], bevel=0.04)
    for s in (-1, 1):
        faces += acc.box((0.5, 2 * half_z, fh * 1.6), T(c + V(s * (half_x - 0.1), 0, fh * 0.8)), P['concrete_dk'], bevel=0.04)
    # front wall with the furnace opening
    if opening:
        ow, oh = 2 * half_x * 0.36, fh * 1.45
        for s in (-1, 1):
            w = (2 * half_x - ow) / 2
            faces += acc.box((w, 0.6, fh * 1.8), T(c + V(s * (ow / 2 + w / 2), -half_z + 0.1, fh * 0.9)), P['concrete'], bevel=0.04)
        faces += acc.box((ow + 0.4, 0.6, fh * 0.35), T(c + V(0, -half_z + 0.1, oh + fh * 0.17)), P['concrete'], bevel=0.04)
        # the furnace: a glowing arch inside, ember floor, a rusty frame
        lathe_at(acc, [(0.0, 0.0), (ow * 0.42, 0.0), (ow * 0.42, oh * 0.55), (0.0, oh * 0.55)],
                 c + V(0, -half_z + 1.6, oh * 0.45), V(0, 1, 0), P['fire'], segs=16, sharp=40)
        faces += acc.box((ow * 0.9, 1.2, oh * 0.7), T(c + V(0, -half_z + 2.4, oh * 0.38)), P['fire_core'], bevel=0.05)
        faces += acc.box((ow * 1.1, 2.6, 0.12), T(c + V(0, -half_z + 1.4, 0.06)), P['ember'], bevel=0.02)
        for k in range(5):
            x = -ow / 2 + ow * k / 4
            faces += acc.box((0.18, 0.25, oh), T(c + V(x, -half_z - 0.15, oh / 2)), P['rust_dk'], bevel=0.02)
        faces += acc.box((ow + 0.6, 0.3, 0.3), T(c + V(0, -half_z - 0.15, oh)), P['rust_dk'], bevel=0.02)
        # steps up to the opening
        for k in range(3):
            faces += acc.box((ow + 1.5 - k * 0.4, 0.9, 0.22), T(c + V(0, -half_z - 0.8 + k * 0.5, 0.11 + 0.22 * k)), P['concrete_dk'], bevel=0.02)
    # rusty roof truss frame on top (skeleton), a few hanging girders
    zt = height
    for i in range(nx + 1):
        x = -half_x + 2 * half_x * i / nx
        faces += acc.cyl_between(c + V(x, -half_z, zt - 0.2), c + V(x, 0, zt + 2.6), 0.14, P['rust_or'], 5)
        faces += acc.cyl_between(c + V(x, half_z, zt - 0.2), c + V(x, 0, zt + 2.6), 0.14, P['rust_or'], 5)
        if not lod:
            faces += acc.cyl_between(c + V(x, -half_z * 0.5, zt + 1.2), c + V(x, half_z * 0.5, zt + 1.2), 0.08, P['rust_or'], 4)
    faces += acc.cyl_between(c + V(-half_x, 0, zt + 2.6), c + V(half_x * 0.6, 0, zt + 2.6), 0.16, P['rust_or'], 5)
    faces += acc.cyl_between(c + V(half_x * 0.6, 0, zt + 2.6), c + V(half_x * 0.85, 0.4, zt - 1.5), 0.14, P['rust_or'], 5)
    snow_tint(acc, faces, up=0.55, k=0.85)
    return faces


def arc_rib(acc, base, yaw, height, span, seed, thick=1.0, broken=True):
    """A broken curved concrete rib (the arena's perimeter arcs, as in the concept's arena inset): a stack of big
    chipped concrete blocks with open joints that rises and curls inward, snapped at the top with rebar sticking out,
    snow on the upward faces. yaw: the direction it leans toward (deg, from +y)."""
    r = rnd(seed)
    n = 6
    pts = []
    for i in range(n + 1):
        t = i / n
        if broken and t > 0.92:
            t = 0.92
        a = t * math.pi * 0.5
        # up first, then curling over toward the lean direction (a broken quarter arch, its tip over the deck's rim)
        pts.append(V(0, (1 - math.cos(a)) ** 1.5 * span, math.sin(a) * height))
    Mr = R('Z', -yaw)
    faces = []
    side = Vector((1, 0, 0))
    for i in range(n):
        a_, b_ = pts[i], pts[i + 1]
        tg = (b_ - a_)
        ln = tg.length
        tg = tg.normalized()
        yv = tg.cross(side).normalized()
        basis_m = Matrix((side, yv, tg)).transposed().to_4x4()
        jit = R('X', r.uniform(-3.0, 3.0)) @ R('Y', r.uniform(-2.5, 2.5))
        k = i / max(1, n - 1)
        w = thick * (1.25 - 0.3 * k)
        d = thick * (1.05 - 0.2 * k)
        ctr = base + Mr @ ((a_ + b_) * 0.5)
        f = slab(acc, ctr, (w, d, ln * 0.9), P['concrete_lt'] if i % 2 == 0 else P['concrete'], M_=Mr @ basis_m @ jit,
                 seed=seed * 10 + i, chip=0.09, e=0.1)
        snow_tint(acc, f, up=0.45, k=0.9)
        faces += f
    top = base + Mr @ pts[-1]
    for k in range(5):
        dv = Mr @ V(r.uniform(-0.45, 0.45), r.uniform(-0.2, 0.6), 1).normalized()
        faces += A.rebar(acc, top + Mr @ V(r.uniform(-0.35, 0.35), r.uniform(-0.25, 0.25), -0.15), dv, r.uniform(0.6, 1.3),
                         r=0.045, bend=V(r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0.1) if r.random() < 0.5 else None,
                         surf=P['rust_dk'])
    faces += slab(acc, base + V(0, 0, 0.5), (thick * 1.7, thick * 1.9, 1.0), P['concrete_dk'], M_=Mr, seed=seed, chip=0.08)
    return faces


def viaduct_pier(acc, base, height, seed, width=3.0, depth=2.2, deck_w=9.0):
    """A massive concrete pier with a hammerhead cap; chipped edges, icicles under the cap, snow on top."""
    r = rnd(seed)
    faces = slab(acc, base + V(0, 0, height / 2), (width, depth, height), P['concrete'], seed=seed, chip=0.08, e=0.1)
    cap = base + V(0, 0, height + 0.5)
    faces += slab(acc, cap, (deck_w * 0.85, depth + 0.6, 1.0), P['concrete_dk'], seed=seed + 1, chip=0.1, e=0.12)
    for k in range(7):
        x = r.uniform(-deck_w * 0.4, deck_w * 0.4)
        p = cap + V(x, r.uniform(-0.8, 0.8), -0.5)
        faces += horn(acc, p, p + V(0, 0, -r.uniform(0.3, 0.9)), r.uniform(0.04, 0.09), P['ice'], segs=5, n=3)
    faces += slab(acc, base + V(0, 0, 0.35), (width + 1.0, depth + 1.0, 0.7), P['concrete_dk'], seed=seed + 2, chip=0.08)
    return faces


def viaduct_span(acc, a, b, top_z, deck_w=9.0, seed=0, stub=False):
    """A deck span from a to b (Blender points, ground), its top at top_z: a box girder with railing posts and a
    snowed broken edge when it is a stub."""
    d = b - a
    Lg = d.length
    yaw = math.degrees(math.atan2(d.x, d.y))
    M = T((a + b) / 2) @ R('Z', -yaw)
    faces = []
    faces += slab(acc, (a + b) / 2 + V(0, 0, top_z - 0.75), (deck_w, Lg + (0.0 if stub else 0.4), 1.5), P['concrete'],
                  M_=R('Z', -yaw), seed=seed, chip=0.15 if stub else 0.05, e=0.08)
    for s in (-1, 1):
        faces += acc.box((0.35, Lg, 0.6), M @ T(V(s * (deck_w / 2 - 0.2), 0, top_z + 0.3)), P['concrete_lt'], bevel=0.04)
    rr = rnd(seed)
    for k in range(int(Lg / 4)):
        t = (k + 0.5) / int(Lg / 4)
        p = a.lerp(b, t) + V(rr.uniform(-deck_w * 0.3, deck_w * 0.3), 0, top_z + 0.02)
        snow_pillow(acc, p, (rr.uniform(0.8, 2.0), rr.uniform(0.7, 1.6), 0.07), R('Z', rr.uniform(0, 180)), seed=seed + k, surf=P['snow'])
    return faces
