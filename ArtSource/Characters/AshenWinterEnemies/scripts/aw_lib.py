"""Ashen Winter enemies: modelling kit (runs inside Blender 5.2) on top of the Toxic Wetlands mutant kit (mut_lib).

The meshes follow the RoadGame/Toon contract of every Blender pass of the project:
  * 'Color'                 CORNER / FLOAT_COLOR, linear RGB = painted colour, A < 1 = self-lit amount (glow)
  * 'UVMap'                 UV0 into T_AshenEnemies_BaseMap_1K.png (16 strips of 64 px, see STRIPS)
  * 'Unity_MaterialParams'  UV1: x = gloss, y = metal
A creature is a hierarchy of rigid parts (mut_lib.Creature): every part object sits at its joint (pivot) with an
identity rotation, so the Unity animators (Scripts/World/AshenEnemies.cs) rotate parts about their joints.
Blender x right, y forward, z up; Unity (x, y, z) = Blender (x, z, y).

New shapes for this zone: chipped concrete slabs with snow pillows, twisted cable / sinew bundles, ragged feather
masses, ring joints, track belts with road wheels, skis, rotary multi-barrel guns, railings, coil springs, broken
chimneys and a worn orange / black hazard paint strip.
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
MUT_SCRIPTS = os.path.join(PROJECT, 'ArtSource', 'Characters', 'ToxicWetlandsMutants', 'scripts')
if MUT_SCRIPTS not in sys.path:
    sys.path.insert(0, MUT_SCRIPTS)

import mut_lib as M  # noqa: E402
from mut_lib import (V, T, R, look, catmull, interp, bezier, limb, horn, ball, blob, sweep, lathe_at, cyl,  # noqa: E402,F401
                     box, torus, displace, recolor, grad, tint, mottle, chain, Creature, vertex_ao, clear_scene)

L = M.L
from tw_lib import Surf, hexlin, mixc, mulc, smooth_noise3  # noqa: E402,F401

TEX_NAME = 'T_AshenEnemies_BaseMap_1K.png'
MAT = 'AW_Enemy'
L.MAT_DEFS[MAT] = dict(base='actor', tex=TEX_NAME)


def use_textures():
    """mut_lib points the texture folder at the mutants; the Ashen atlas lives next to these scripts."""
    L.TEX_DIR = os.path.join(ART, 'textures')


use_textures()

# ------------------------------------------------------------------------------------------------ atlas
STRIPS = ['plain', 'concrete', 'ash', 'feather', 'hide', 'cable', 'rust', 'metal',
          'snow', 'hazard', 'tread', 'cloth', 'bone', 'ice', 'grille', 'panel']
# metres of surface per full texture width, per strip
STRIP_SCALE = {'plain': 2.0, 'concrete': 2.2, 'ash': 1.2, 'feather': 0.55, 'hide': 1.0, 'cable': 0.6, 'rust': 1.2,
               'metal': 1.6, 'snow': 1.6, 'hazard': 1.1, 'tread': 2.4, 'cloth': 0.8, 'bone': 1.0, 'ice': 1.0,
               'grille': 0.6, 'panel': 2.4}


def band(strip):
    if strip not in STRIPS:
        strip = 'plain'
    i, n = STRIPS.index(strip), len(STRIPS)
    inset = 2.5 / 1024.0
    lo = 1.0 - (i + 1) / n
    return lo + inset, (1.0 / n) - 2 * inset


def S(h, gloss=0.2, metal=0.0, glow=0.0, strip='plain'):
    """An Ashen enemy surface: sRGB hex (or linear tuple), gloss, metal, self-lit glow 0..1, atlas strip."""
    return Surf(h, gloss, metal, glow, strip, MAT)


# Palette (art direction): graphite / near-black ash, dark steel with muted rust, light neutral-grey concrete, dirty
# milky snow, dark red-brown sinew cables, orange-amber accents; glow only in furnaces, sensors and the reactor.
C = {
    'snow':        S('#DCDFE4', 0.30, strip='snow'),
    'snow_dirty':  S('#C9CCD0', 0.26, strip='snow'),
    'ice':         S('#C8D8E4', 0.70, strip='ice'),
    'concrete':    S('#9C9A94', 0.06, strip='concrete'),
    'concrete_lt': S('#B2B0A9', 0.06, strip='concrete'),
    'concrete_dk': S('#74726C', 0.05, strip='concrete'),
    'ash':         S('#4A4848', 0.10, strip='ash'),
    'ash_dk':      S('#343233', 0.10, strip='ash'),
    'ash_lt':      S('#66625E', 0.08, strip='ash'),
    'feather':     S('#5A5A5E', 0.18, strip='feather'),
    'feather_dk':  S('#3E3E42', 0.16, strip='feather'),
    'feather_or':  S('#B8783A', 0.22, strip='feather'),
    'feather_lt':  S('#77777A', 0.18, strip='feather'),
    'hide':        S('#3E3638', 0.30, strip='hide'),
    'hide_dk':     S('#2E282A', 0.28, strip='hide'),
    'hide_red':    S('#5C3430', 0.32, strip='hide'),
    'cable':       S('#55302E', 0.42, strip='cable'),
    'cable_dk':    S('#3C2628', 0.40, strip='cable'),
    'cable_br':    S('#6E4434', 0.40, strip='cable'),
    'rust':        S('#FFFFFF', 0.22, 0.30, strip='rust'),
    'rust_dk':     S('#7A3C22', 0.22, 0.30, strip='metal'),
    'rust_or':     S('#9C5A2C', 0.26, 0.30, strip='metal'),
    'steel':       S('#5E6264', 0.45, 0.65, strip='metal'),
    'steel_dk':    S('#34383A', 0.40, 0.55, strip='metal'),
    'steel_lt':    S('#8A8E8E', 0.45, 0.65, strip='metal'),
    'gunmetal':    S('#2C2F31', 0.50, 0.70, strip='metal'),
    'panel':       S('#5A5E60', 0.40, 0.55, strip='panel'),
    'panel_dk':    S('#3E4244', 0.38, 0.50, strip='panel'),
    'hazard':      S('#FFFFFF', 0.36, 0.10, strip='hazard'),
    'tread':       S('#2B2B2A', 0.22, 0.20, strip='tread'),
    'rubber':      S('#262624', 0.24),
    'cloth':       S('#7E7360', 0.06, strip='cloth'),
    'fur':         S('#CDBFA4', 0.04, strip='cloth'),
    'cloth_dk':    S('#4E4A40', 0.06, strip='cloth'),
    'bone':        S('#D4CEC0', 0.26, strip='bone'),
    'bone_dk':     S('#9A9282', 0.22, strip='bone'),
    'claw':        S('#2E2A28', 0.45, strip='bone'),
    'grille':      S('#5A5856', 0.35, 0.50, strip='grille'),
    'black':       S('#121212', 0.40),
    'bore':        S('#0C0C0C', 0.10),
    'amber':       S('#FFB23A', 0.80, glow=0.75),
    'amber_soft':  S('#F09A30', 0.70, glow=0.45),
    'fire':        S('#FF8A2A', 0.60, glow=0.85),
    'fire_core':   S('#FFD27A', 0.60, glow=0.95),
    'ember':       S('#C8501E', 0.50, glow=0.55),
    'lamp':        S('#FFC870', 0.60, glow=0.80),
    'glass':       S('#3A4248', 0.85, 0.10),
}


# ------------------------------------------------------------------------------------------------ accumulator

class AAcc(M.MAcc):
    """Mesh under construction, painted into the Ashen enemy atlas."""

    def __init__(self, name):
        L.Acc.__init__(self, name, atlas='aw', mat=MAT, box_tile=1.0)

    def paint(self, faces, surf, uv=None, sharp=None, smooth=True, part=None):
        pt = part or self.main
        mi = self.mat_index(surf.mat)
        rgba = surf.rgba
        prm = (surf.gloss, surf.metal)
        lo, h = band(surf.strip)
        us = STRIP_SCALE.get(surf.strip, 1.0)
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
        tmp = AAcc('_cage')
        cage_fn(tmp)
        me = bpy.data.meshes.new('_cage_mesh')
        tmp.bm.to_mesh(me)
        tmp.bm.free()
        ob = bpy.data.objects.new('_cage_obj', me)
        bpy.context.scene.collection.objects.link(ob)
        mod = ob.modifiers.new('ss', 'SUBSURF')
        mod.levels = levels
        mod.render_levels = levels
        mod.uv_smooth = 'PRESERVE_BOUNDARIES'
        dg = bpy.context.evaluated_depsgraph_get()
        em = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        remap = [self.mat_index(k) for k in tmp.mats] or [self.mat_index(None)]
        pt = L._Part()
        pt.bm.from_mesh(em)
        faces = list(pt.bm.faces)
        for f in faces:
            f.material_index = remap[min(f.material_index, len(remap) - 1)]
            f.smooth = True
        if sharp is not None:
            self.sharpen(faces, sharp)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.meshes.remove(em)
        self.transform(faces, M_, pt)
        return self._commit(pt)

    def build(self, name=None):
        me = super().build(name)
        me['tw_built'] = 'Ashen Winter enemies pass'
        return me


# ------------------------------------------------------------------------------------------------ helpers

def frame(z_axis, x_hint=(1, 0, 0)):
    """Rotation whose local +Z points along z_axis and local +X as close as possible to x_hint."""
    z = Vector(z_axis).normalized()
    x = Vector(x_hint)
    x = (x - z * x.dot(z))
    if x.length < 1e-5:
        x = Vector((0, 1, 0)) - z * z.y
    x.normalize()
    y = z.cross(x).normalized()
    return Matrix((x, y, z)).transposed().to_4x4()


def basis(x, y, z):
    return Matrix((Vector(x).normalized(), Vector(y).normalized(), Vector(z).normalized())).transposed().to_4x4()


def slab(acc, c, size, surf=None, M_=Matrix(), seed=0, chip=0.05, e=0.16, segs=14, rings=10, sharp=None):
    """A thick chipped concrete slab / block: a rounded box (superellipsoid) with noisy chipped edges.
    size: full (x, y, z); c: centre; M_: rotation applied about the centre."""
    surf = surf or C['concrete']
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    rnd = random.Random(seed)
    # one or two corners knocked off (big chips), the rest small noise
    cuts = [Vector((rnd.choice((-1, 1)) * hx, rnd.choice((-1, 1)) * hy, rnd.choice((-1, 1)) * hz)) for _ in range(2)]
    depth = [chip * (2.0 + 2.5 * rnd.random()) for _ in cuts]

    def deform(co):
        d = Vector((co.x / max(hx, 1e-6), co.y / max(hy, 1e-6), co.z / max(hz, 1e-6)))
        edge = max(0.0, (abs(d.x) + abs(d.y) + abs(d.z) - 1.9)) / 1.1
        n = smooth_noise3(co * 1.0 + Vector((seed * 3.1, seed * 1.7, 0.0)), seed, 2.2)
        out = co - Vector((math.copysign(1, co.x), math.copysign(1, co.y), math.copysign(1, co.z))) * (chip * edge * (0.6 + 0.6 * n))
        for k, cp in enumerate(cuts):
            dist = (co - cp).length
            r = depth[k] * 2.2
            if dist < r:
                out = out - (cp.normalized() * depth[k] * (1.0 - dist / r))
        return out
    return acc.superellipsoid((hx, hy, hz), (e, e), T(c) @ M_, surf, segs, rings, deform=deform, sharp=sharp)


def snow_pillow(acc, c, half, M_=Matrix(), seed=0, surf=None, amp=0.25, segs=16, rings=8, k=0.78):
    """A soft lumpy cushion of snow (adds volume on top of a surface). c = centre of its base."""
    surf = surf or C['snow']
    hx, hy, hz = half[0] * k, half[1] * k, half[2] * 0.8

    def deform(co):
        n = smooth_noise3(co * 2.0 + Vector((seed, seed * 0.7, 0.0)), seed + 5, 1.6)
        k = 1.0 + amp * n
        z = co.z
        if z < 0:
            z *= 0.25          # flat underside sitting on the surface
        return Vector((co.x * (1.0 + 0.12 * n), co.y * (1.0 + 0.12 * n), z * k))
    return acc.superellipsoid((hx, hy, hz), (0.55, 0.7), T(c) @ M_, surf, segs, rings, deform=deform)


def cables(acc, a, b, n=4, r=0.05, R_=0.08, turns=0.8, surf=None, bulge=0.25, seed=0, segs=8, steps=12, sag=None):
    """Twisted sinew / cable bundle from a to b: n strands spiralling around the axis, thicker in the middle."""
    surf = surf or C['cable']
    a, b = Vector(a), Vector(b)
    ax = (b - a)
    Lg = ax.length
    z = ax.normalized()
    Mx = frame(z)
    u = Mx.col[0].xyz
    v = Mx.col[1].xyz
    rnd = random.Random(seed)
    out = []
    for k in range(n):
        ph0 = 2 * math.pi * (k / n) + rnd.random() * 0.4
        pts, rr = [], []
        for i in range(steps + 1):
            t = i / steps
            ph = ph0 + 2 * math.pi * turns * t
            w = R_ * (1.0 + bulge * math.sin(math.pi * t))
            p = a + ax * t + (u * math.cos(ph) + v * math.sin(ph)) * w
            if sag is not None:
                p = p + Vector(sag) * math.sin(math.pi * t)
            pts.append(p)
            rr.append(r * (0.85 + 0.3 * math.sin(math.pi * t)) * (0.9 + 0.2 * rnd.random()))
        out += acc.tube(pts, rr, surf, segs, caps=True)
    return out


def ring(acc, c, axis, r, w, thick, surf=None, segs=24):
    """A band / ring joint around 'axis' through c (outer radius r, width w along the axis, thickness radial)."""
    surf = surf or C['rust_dk']
    prof = [(r - thick, -w / 2), (r, -w / 2 + 0.01), (r, w / 2 - 0.01), (r - thick, w / 2)]
    return lathe_at(acc, prof, c, axis, surf, segs=segs, caps=(False, False), sharp=40)


def pipe(acc, pts, r, surf=None, segs=12, per=3, flanges=(), flange_surf=None):
    """Smooth pipe along control points, with flange rings at the given parameter positions (0..1)."""
    surf = surf or C['rust_dk']
    path = catmull(pts, per)
    out = acc.tube(path, r, surf, segs, caps=True)
    if flanges:
        lens = [0.0]
        for i in range(1, len(path)):
            lens.append(lens[-1] + (path[i] - path[i - 1]).length)
        tot = lens[-1]
        for f in flanges:
            target = f * tot
            for i in range(1, len(path)):
                if lens[i] >= target:
                    t = (target - lens[i - 1]) / max(lens[i] - lens[i - 1], 1e-6)
                    p = path[i - 1].lerp(path[i], t)
                    d = (path[i] - path[i - 1]).normalized()
                    out += ring(acc, p, d, r * 1.35, r * 0.55, r * 0.5, flange_surf or C['steel_dk'], segs=max(10, segs))
                    break
    return out


def feather(acc, base, tip, width, surf=None, bend=(0, 0, 0), thick=0.25, n=6):
    """A ragged pointed feather mass (flat blade) from base to tip."""
    surf = surf or C['feather']
    return horn(acc, base, tip, width, surf, bend=bend, segs=8, n=n, power=0.7, flat=thick)


def gatling(acc, c, fwd, n=4, rb=0.035, length=0.8, cluster=0.07, surf=None, ring_surf=None):
    """Rotary multi-barrel gun: n barrels around the axis from c along fwd, two clamp rings and a hub. Returns faces."""
    surf = surf or C['gunmetal']
    ring_surf = ring_surf or C['steel_dk']
    f = Vector(fwd).normalized()
    Mx = frame(f)
    u, v = Mx.col[0].xyz, Mx.col[1].xyz
    c = Vector(c)
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / n
        off = (u * math.cos(a) + v * math.sin(a)) * cluster
        out += acc.cyl_between(c + off, c + off + f * length, rb, surf, 10, caps=True)
        # dark bore at the muzzle end
        out += acc.cyl_between(c + off + f * (length - 0.005), c + off + f * (length + 0.002), rb * 0.55, C['bore'], 8, caps=True)
    for t in (0.08, 0.62, 0.96):
        out += ring(acc, c + f * (length * t), f, cluster + rb * 1.7, 0.05, cluster + rb * 1.5, ring_surf, segs=16)
    out += acc.cyl_between(c - f * 0.12, c + f * 0.06, cluster + rb * 1.2, ring_surf, 14, caps=True)
    return out


def coil_spring(acc, a, b, R_, r, turns=6, surf=None, segs=6):
    surf = surf or C['hazard'].with_(strip='plain', rgb='#C8762E')
    a, b = Vector(a), Vector(b)
    ax = b - a
    Mx = frame(ax)
    u, v = Mx.col[0].xyz, Mx.col[1].xyz
    pts = []
    steps = int(turns * 10)
    for i in range(steps + 1):
        t = i / steps
        ph = 2 * math.pi * turns * t
        pts.append(a + ax * t + (u * math.cos(ph) + v * math.sin(ph)) * R_)
    return acc.tube(pts, r, surf, segs, caps=True)


def railing(acc, pts, h=0.45, r=0.022, surf=None, posts_every=0.45, mid=True):
    """Thin rusty railing along a polyline on a deck: posts, top rail, optional mid rail."""
    surf = surf or C['rust_or']
    pts = [Vector(p) for p in pts]
    out = []
    out += acc.tube([p + Vector((0, 0, h)) for p in pts], r, surf, 6, caps=True)
    if mid:
        out += acc.tube([p + Vector((0, 0, h * 0.5)) for p in pts], r * 0.8, surf, 6, caps=True)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        n = max(1, int((b - a).length / posts_every))
        for k in range(n + (1 if i == len(pts) - 2 else 0)):
            p = a.lerp(b, k / n)
            out += acc.cyl_between(p, p + Vector((0, 0, h)), r, surf, 6, caps=False)
    return out


def broken_chimney(acc, base, h, r, surf=None, seed=0, wall=0.06, jag=0.35, segs=18):
    """A chimney stack with a ragged broken top and wall thickness (open bore)."""
    surf = surf or C['steel_dk']
    rnd = random.Random(seed)
    pt = L._Part()
    bm = pt.bm
    base = Vector(base)
    rings_ = []
    nz = 6
    tops = [h * (1.0 - jag * (0.5 + 0.5 * math.sin(3 * 2 * math.pi * s / segs + seed)) * rnd.random()) for s in range(segs)]
    for i in range(nz + 1):
        t = i / nz
        ring_o, ring_i = [], []
        for s in range(segs):
            a = 2 * math.pi * s / segs
            z = tops[s] * t
            ring_o.append(bm.verts.new(base + Vector((math.cos(a) * r, math.sin(a) * r, z))))
        rings_.append(ring_o)
    inner = []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        inner.append(bm.verts.new(base + Vector((math.cos(a) * (r - wall), math.sin(a) * (r - wall), tops[s] - 0.01))))
    inner_bot = []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        inner_bot.append(bm.verts.new(base + Vector((math.cos(a) * (r - wall), math.sin(a) * (r - wall), h * 0.25))))
    for i in range(nz):
        for s in range(segs):
            s1 = (s + 1) % segs
            bm.faces.new([rings_[i][s], rings_[i][s1], rings_[i + 1][s1], rings_[i + 1][s]])
    for s in range(segs):
        s1 = (s + 1) % segs
        bm.faces.new([rings_[nz][s], rings_[nz][s1], inner[s1], inner[s]])
        bm.faces.new([inner[s], inner[s1], inner_bot[s1], inner_bot[s]])
    bm.faces.new(list(reversed(inner_bot)))
    faces = list(bm.faces)
    bm.normal_update()
    acc.paint(faces, surf, None, part=pt)
    # the bore is dark
    for f in faces:
        cen = f.calc_center_median()
        if (Vector((cen.x, cen.y, 0)) - Vector((base.x, base.y, 0))).length < r - wall * 0.5:
            for lp in f.loops:
                lp[pt.lc] = C['bore'].rgba
    return acc._commit(pt)


def track_loop(acc, cx, y0, y1, r0, r1, zc, width, surf=None, thick=0.08, steps=40):
    """A track belt (side view in the y-z plane at x = cx): around a front wheel (y1, radius r1) and a rear sprocket
    (y0, radius r0) with straight runs. Strip u runs along the belt (metres), so a scrolling u offset moves the tread.
    Returns faces."""
    surf = surf or C['tread']
    pt = L._Part()
    bm = pt.bm
    # closed path: bottom run (rear -> front), front arc, top run (front -> rear), rear arc
    path = []
    n_run = steps // 4
    for i in range(n_run):
        t = i / n_run
        path.append((y0 + (y1 - y0) * t, zc - max(r0, r1) * 0.98))
    for i in range(n_run):
        a = -math.pi / 2 + math.pi * i / n_run
        path.append((y1 + r1 * math.cos(a), zc + r1 * math.sin(a) * 1.0 - (max(r0, r1) - r1) * (1 - (i / n_run)) * 0.0))
    for i in range(n_run):
        t = i / n_run
        path.append((y1 + (y0 - y1) * t, zc + max(r0, r1) * 0.98))
    for i in range(n_run):
        a = math.pi / 2 + math.pi * i / n_run
        path.append((y0 + r0 * math.cos(a), zc + r0 * math.sin(a)))
    npth = len(path)
    lens = [0.0]
    for i in range(1, npth + 1):
        pa, pb = path[i - 1], path[i % npth]
        lens.append(lens[-1] + math.hypot(pb[0] - pa[0], pb[1] - pa[1]))
    total = lens[-1]
    # outward normal of the loop at each point (approximate by the direction from the loop centre line)
    rings_ = []
    for i, (y, z) in enumerate(path):
        pa, pb = path[i - 1], path[(i + 1) % npth]
        ty, tz = pb[0] - pa[0], pb[1] - pa[1]
        tl = math.hypot(ty, tz) or 1.0
        ny, nz = tz / tl, -ty / tl          # right-hand normal (outward for this winding)
        outer = [(cx - width / 2, y + ny * thick, z + nz * thick), (cx + width / 2, y + ny * thick, z + nz * thick)]
        inner = [(cx + width / 2, y, z), (cx - width / 2, y, z)]
        rings_.append([bm.verts.new(Vector(p)) for p in outer + inner])
    vmap = {}
    for i, rg in enumerate(rings_):
        for k, vv in enumerate(rg):
            vmap[vv] = (lens[i], (0.0, 1.0, 1.0, 0.0)[k])
    faces = []
    for i in range(npth):
        a, b = rings_[i], rings_[(i + 1) % npth]
        for k in range(4):
            k1 = (k + 1) % 4
            faces.append(bm.faces.new([a[k], a[k1], b[k1], b[k]]))
    bm.normal_update()
    # u of the closing quads must not wrap back to 0 mid-face: the last ring's faces use total length
    for f in faces:
        us = []
        for lp in f.loops:
            us.append(vmap[lp.vert][0])
        hi = max(us)
        for lp in f.loops:
            u, v = vmap[lp.vert]
            if hi - u > total * 0.5:
                u += total
            lp[pt.luv].uv = (u, v)
    acc.paint(faces, surf, lambda lp, f: (lp[pt.luv].uv[0], lp[pt.luv].uv[1]), part=pt)
    for f in faces:
        f.smooth = False
    return acc._commit(pt)


def wheel(acc, c, axis, r, w, surf=None, hub=None, spokes=5):
    """Road wheel / sprocket: tyre-less steel wheel with a hub and lightening holes (dark discs)."""
    surf = surf or C['steel_dk']
    hub = hub or C['rust_dk']
    ax = Vector(axis).normalized()
    out = lathe_at(acc, [(0.0, -w / 2), (r * 0.92, -w / 2), (r, -w / 2 + 0.02), (r, w / 2 - 0.02), (r * 0.92, w / 2),
                         (0.0, w / 2)], c, ax, surf, segs=18, caps=(False, False), sharp=40)
    out += lathe_at(acc, [(0.0, -w / 2 - 0.03), (r * 0.32, -w / 2 - 0.03), (r * 0.32, w / 2 + 0.03), (0.0, w / 2 + 0.03)],
                    c, ax, hub, segs=12, caps=(False, False), sharp=40)
    Mx = frame(ax)
    u, v = Mx.col[0].xyz, Mx.col[1].xyz
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        p = Vector(c) + (u * math.cos(a) + v * math.sin(a)) * r * 0.62
        for sgn in (-1, 1):
            out += acc.cyl_between(p + ax * sgn * (w / 2 - 0.004), p + ax * sgn * (w / 2 + 0.004), r * 0.13, C['bore'], 8)
    return out


def ski(acc, c, length, width, surf=None, tip_rise=0.28, thick=0.05):
    """A ski along +y centred at c (bottom at c.z): flat run curving up into the tip at the front."""
    surf = surf or C['steel_dk']
    c = Vector(c)
    n = 14
    secs = []
    for i in range(n + 1):
        t = i / n
        y = c.y - length / 2 + length * t
        lift = 0.0
        if t > 0.72:
            k = (t - 0.72) / 0.28
            lift = tip_rise * (1 - math.cos(k * math.pi / 2)) ** 1.0 * 1.3
            y -= tip_rise * 0.35 * k * k
        hw = width / 2 * (1.0 - 0.25 * max(0.0, t - 0.85) / 0.15)
        z = c.z + lift
        secs.append([Vector((c.x - hw, y, z)), Vector((c.x + hw, y, z)), Vector((c.x + hw, y, z + thick)),
                     Vector((c.x - hw, y, z + thick))])
    return acc.loft(secs, surf, sharp=35)


def hazard_band_box(acc, c, size, M_=Matrix(), bevel=0.02):
    """A box painted with the worn orange / black diagonal stripes."""
    return acc.box(size, T(c) @ M_, C['hazard'], bevel=bevel, segs=2)


def glow_eye(acc, c, r, surf=None):
    surf = surf or C['amber']
    return ball(acc, c, r, surf, segs=12, rings=8)


def rebar(acc, base, direction, length, r=0.018, bend=None, surf=None):
    """A bent rusty rebar sticking out of concrete."""
    surf = surf or C['rust_dk']
    b = Vector(base)
    d = Vector(direction).normalized()
    pts = [b, b + d * length * 0.6]
    if bend is not None:
        pts.append(b + d * length * 0.6 + Vector(bend))
    else:
        pts.append(b + d * length)
    return acc.tube(pts, r, surf, 6, caps=True)


def snow_tint(acc, faces, up=0.55, k=0.85, surf=None):
    """Snow dusting baked into vertex colours where the surface faces up (adds no volume)."""
    surf = surf or C['snow']
    sc = surf.rgb
    for f in faces:
        nz = f.normal.z
        if nz < up:
            continue
        t = min(1.0, (nz - up) / (1.0 - up)) * k
        for lp in f.loops:
            c = lp[acc.main.lc]
            lp[acc.main.lc] = (c[0] * (1 - t) + sc[0] * t, c[1] * (1 - t) + sc[1] * t, c[2] * (1 - t) + sc[2] * t, c[3])


def soot(lo_z, hi_z, k=0.45):
    """Colour fn: darker toward the bottom (soot / dirt), unchanged above hi_z."""
    def fn(p, c):
        t = 1.0 - max(0.0, min(1.0, (p.z - lo_z) / max(hi_z - lo_z, 1e-6)))
        m = 1.0 - k * t
        return (c[0] * m, c[1] * m, c[2] * m, c[3])
    return fn


def blade(acc, base, tip, width, thick, wdir, surf=None, bend=(0, 0, 0), n=9, base_k=0.75, tip_k=0.0, belly=0.0,
          sharp=None, edge=None):
    """A flat curved blade (feather, ice-pick blade, claw, plate fin) from base to tip, bent toward 'bend'.
    wdir: the direction the blade is wide in (made perpendicular to the spine); thick: thickness at the widest point.
    The section is a lens (sharp front and back edges); width peaks a third of the way along and tapers to the tip.
    edge: optional surface for the cutting edge (a narrow strip along the +w side)."""
    surf = surf or C['bone']
    base, tip = Vector(base), Vector(tip)
    ctrl = (base + tip) * 0.5 + Vector(bend)
    pts = bezier(base, ctrl, tip, n)
    secs = []
    m = 10
    wd = Vector(wdir)
    for i, p in enumerate(pts):
        t = i / (n - 1)
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        tg = (b - a).normalized()
        w = (wd - tg * wd.dot(tg))
        if w.length < 1e-6:
            w = tg.orthogonal()
        w.normalize()
        th = tg.cross(w).normalized()
        prof = (base_k + (1 - base_k) * min(1.0, t / 0.33)) if t < 0.33 else (1.0 - (t - 0.33) / 0.67) ** 0.85
        prof = max(prof, tip_k if t < 1.0 else 0.0)
        ww = width * 0.5 * prof
        tt = thick * 0.5 * max(prof, 0.12) * (1.0 if t < 0.999 else 0.0)
        ring = []
        for k in range(m):
            ang = 2 * math.pi * k / m
            cx, cz = math.cos(ang), math.sin(ang)
            x = ww * cx
            z = tt * (abs(cz) ** 0.8) * math.copysign(1, cz) * (1.0 - 0.5 * abs(cx) ** 4)
            if cz < 0:
                z *= (1.0 - belly)
            ring.append(p + w * x + th * z)
        secs.append(ring)
    faces = acc.loft(secs, surf, sharp=sharp)
    if edge is not None:
        # the outer edge (+w) gets a lighter / sharper surface colour
        for f in faces:
            cen = f.calc_center_median()
            # find nearest section point
            best = min(range(len(pts)), key=lambda i: (pts[i] - cen).length)
            p = pts[best]
            a = pts[max(0, best - 1)]
            b = pts[min(n - 1, best + 1)]
            tg = (b - a).normalized()
            w = (wd - tg * wd.dot(tg)).normalized()
            if (cen - p).dot(w) > width * 0.18 * 0.5:
                for lp in f.loops:
                    lp[acc.main.lc] = edge.rgba
    return faces


def prism(acc, pts_bottom, pts_top, surf=None, sharp=30):
    """A closed solid between two rings of points (same count, counter-clockwise seen from above): wedges, plows."""
    surf = surf or C['steel_dk']
    nb = len(pts_bottom)
    coords = [tuple(p) for p in pts_bottom] + [tuple(p) for p in pts_top]
    faces = [list(reversed(range(nb))), list(range(nb, 2 * nb))]
    for i in range(nb):
        j = (i + 1) % nb
        faces.append([i, j, nb + j, nb + i])
    return acc.poly(coords, faces, surf, uv=None, sharp=sharp)


def mirror_x(cr):
    """Mirrors a finished creature across its YZ plane (mesh data, winding and joint pivots).
    The builders model a creature's left side at +x; Blender's +x is the right of a creature facing +y. After the
    mirror, the parts named ...L sit on the creature's left and the asymmetric arms match the concept sheet (the
    Executioner's cannon and the Black Reactor's block fist on the right side)."""
    S_ = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
    done = set()
    for o in cr.root.children_recursive:
        o.location.x = -o.location.x
        if o.type == 'MESH' and o.data.name not in done:
            done.add(o.data.name)
            me = o.data
            me.transform(S_)
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces), flip_multires=False)
            bm.to_mesh(me)
            bm.free()
            me.update()
    for k in list(cr.pivots.keys()):
        p = cr.pivots[k]
        cr.pivots[k] = Vector((-p.x, p.y, p.z))
    bpy.context.view_layer.update()
