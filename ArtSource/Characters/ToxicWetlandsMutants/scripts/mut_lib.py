"""Toxic Wetlands mutants: modelling toolkit on top of the Toxic Wetlands level kit (runs inside Blender 5.2).

The meshes follow the same RoadGame/Toon contract as the level (ArtSource/Levels/ToxicWetlands/scripts/tw_lib.py):
  * 'Color'                 CORNER / FLOAT_COLOR, linear RGB = painted colour, A < 1 = self-lit amount (glow)
  * 'UVMap'                 UV0 into the mutant atlas T_Mutant_Wetlands_BaseMap_1K.png (16 strips of 64 px)
  * 'Unity_MaterialParams'  UV1: x = gloss, y = metal
A creature is a hierarchy of rigid parts. Every part object sits at its joint (pivot) with an identity rotation, so
Unity's procedural animators rotate parts about their joints (Blender x right, y forward, z up; Unity x, z, y).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
PROJECT = os.path.abspath(os.path.join(ART, '..', '..', '..'))
TW_SCRIPTS = os.path.join(PROJECT, 'ArtSource', 'Levels', 'ToxicWetlands', 'scripts')
if TW_SCRIPTS not in sys.path:
    sys.path.insert(0, TW_SCRIPTS)

import tw_lib as L  # noqa: E402
from tw_lib import Surf, hexlin, mixc, mulc, smooth_noise3  # noqa: E402,F401

TEX_NAME = 'T_Mutant_Wetlands_BaseMap_1K.png'
L.MAT_DEFS['TW_Mutant'] = dict(base='actor', tex=TEX_NAME)
L.TEX_DIR = os.path.join(ART, 'textures')

# ------------------------------------------------------------------------------------------------ atlas
# 1024 x 1024, 16 horizontal strips of 64 px (v from the bottom, OpenGL convention), u tiles.
STRIPS = ['plain', 'skin', 'warts', 'bark', 'chitin', 'gill', 'veins', 'rust',
          'metal', 'tire', 'bone', 'moss', 'flesh', 'cap', 'glass', 'hazard']
# metres of surface per full texture width, per strip
STRIP_SCALE = {'plain': 2.0, 'skin': 1.2, 'warts': 1.0, 'bark': 1.4, 'chitin': 1.2, 'gill': 0.8, 'veins': 1.0,
               'rust': 1.2, 'metal': 1.6, 'tire': 1.6, 'bone': 0.9, 'moss': 1.0, 'flesh': 1.0, 'cap': 1.0,
               'glass': 1.0, 'hazard': 1.0}


def band(strip):
    if strip not in STRIPS:
        strip = 'plain'
    i, n = STRIPS.index(strip), len(STRIPS)
    inset = 2.5 / 1024.0
    lo = 1.0 - (i + 1) / n
    return lo + inset, (1.0 / n) - 2 * inset


def S(h, gloss=0.2, metal=0.0, glow=0.0, strip='skin'):
    """A mutant surface: sRGB hex (or linear tuple), gloss, metal, self-lit glow 0..1, atlas strip."""
    return Surf(h, gloss, metal, glow, strip, 'TW_Mutant')


# Palette from the brief / concept: dark teal, muted purple, olive, rust orange, local acid glow.
C = {
    'teal':       S('#2F5D58', 0.42, strip='skin'),
    'teal_dk':    S('#1F3F3D', 0.40, strip='skin'),
    'teal_lt':    S('#4F8A7E', 0.40, strip='skin'),
    'purple':     S('#6E4A6E', 0.38, strip='skin'),
    'purple_dk':  S('#4A3150', 0.36, strip='skin'),
    'purple_lt':  S('#8E6A8C', 0.38, strip='skin'),
    'plum_wart':  S('#7A4E78', 0.40, strip='warts'),
    'magenta':    S('#94497C', 0.48, strip='flesh'),
    'flesh':      S('#A2566E', 0.50, strip='flesh'),
    'flesh_dk':   S('#6A3048', 0.45, strip='flesh'),
    'mouth':      S('#8E2E3C', 0.62, strip='flesh'),
    'throat':     S('#3A1018', 0.50, strip='flesh'),
    'olive':      S('#6B6B3E', 0.24, strip='skin'),
    'olive_dk':   S('#47482B', 0.22, strip='skin'),
    'ochre':      S('#C08C48', 0.36, strip='skin'),
    'belly':      S('#B39A66', 0.32, strip='skin'),
    'orange':     S('#C0662E', 0.40, strip='skin'),
    'bark':       S('#5E4430', 0.06, strip='bark'),
    'bark_dk':    S('#3E2C1E', 0.05, strip='bark'),
    'root':       S('#6E4E60', 0.10, strip='bark'),
    'root_dk':    S('#4E3446', 0.10, strip='bark'),
    'chitin':     S('#6A4670', 0.52, strip='chitin'),
    'chitin_dk':  S('#46304E', 0.50, strip='chitin'),
    'chitin_lt':  S('#8C6A92', 0.50, strip='chitin'),
    'bone':       S('#DCCDA6', 0.30, strip='bone'),
    'bone_dk':    S('#A8946C', 0.24, strip='bone'),
    'tooth':      S('#EDE2C4', 0.55, strip='bone'),
    'rust':       S('#FFFFFF', 0.22, 0.25, strip='rust'),
    'rust_or':    S('#B5602C', 0.26, 0.30, strip='rust'),
    'rust_dk':    S('#6E3420', 0.22, 0.28, strip='rust'),
    'rust_red':   S('#963826', 0.32, 0.25, strip='metal'),
    'steel':      S('#7C8280', 0.45, 0.60, strip='metal'),
    'steel_dk':   S('#3C403E', 0.40, 0.55, strip='metal'),
    'tire':       S('#2A2A26', 0.20, strip='tire'),
    'rubber':     S('#33342E', 0.24, strip='plain'),
    'moss':       S('#6E8A2E', 0.20, strip='moss'),
    'moss_dk':    S('#4A5E22', 0.18, strip='moss'),
    'cap':        S('#D98A5C', 0.30, strip='cap'),
    'cap_dk':     S('#B8643E', 0.28, strip='cap'),
    'gill':       S('#E8BC92', 0.20, strip='gill'),
    'reed':       S('#8C8A4E', 0.10, strip='bark'),
    'cattail':    S('#5A3A22', 0.12, strip='bark'),
    'web':        S('#B87A48', 0.40, strip='veins'),
    'glass':      S('#6E8E86', 0.85, strip='glass'),
    'black':      S('#151513', 0.50),
    'eye':        S('#F2C83A', 0.80, glow=0.55, strip='plain'),
    'eye_green':  S('#D6F04A', 0.80, glow=0.60, strip='plain'),
    'pupil':      S('#0E0D0A', 0.90, strip='plain'),
    'glow':       S('#C8F04A', 0.70, glow=0.70, strip='veins'),
    'glow_soft':  S('#A8D23A', 0.65, glow=0.45, strip='veins'),
    'glow_core':  S('#E6FF7A', 0.70, glow=0.85, strip='veins'),
    'gland':      S('#E8A83A', 0.70, glow=0.45, strip='veins'),
    'sac':        S('#C8E64A', 0.85, glow=0.42, strip='veins'),
    'hazard_y':   S('#E0B02E', 0.45, 0.10, strip='plain'),
    'goo':        S('#9CCB34', 0.70, glow=0.35, strip='veins'),
}


# ------------------------------------------------------------------------------------------------ accumulator

class MAcc(L.Acc):
    """Mesh under construction, painted into the mutant atlas."""

    def __init__(self, name):
        super().__init__(name, atlas='mut', mat='TW_Mutant', box_tile=1.0)

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

    def subsurf_cage(self, cage_fn, levels=2, M=Matrix(), sharp=None):
        tmp = MAcc('_cage')
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
        self.transform(faces, M, pt)
        return self._commit(pt)


# ------------------------------------------------------------------------------------------------ curves

def V(x, y, z):
    return Vector((x, y, z))


def T(p):
    return Matrix.Translation(Vector(p))


def R(ax, deg):
    return Matrix.Rotation(math.radians(deg), 4, ax)


def look(z_axis, up=(0, 0, 1)):
    """Rotation whose local +Z points along z_axis (for lathes / cones built along +Z)."""
    z = Vector(z_axis).normalized()
    u = Vector(up)
    if abs(z.dot(u.normalized())) > 0.98:
        u = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0))
    x = u.cross(z).normalized()
    y = z.cross(x).normalized()
    return Matrix((x, y, z)).transposed().to_4x4()


def catmull(pts, per=4):
    P = [Vector(p) for p in pts]
    if len(P) < 3 or per <= 1:
        return P
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def interp(vals, per):
    out = []
    for i in range(len(vals) - 1):
        for k in range(per):
            t = k / per
            t = t * t * (3 - 2 * t)
            out.append(vals[i] * (1 - t) + vals[i + 1] * t)
    out.append(vals[-1])
    return out


def bezier(a, c, b, n):
    a, c, b = Vector(a), Vector(c), Vector(b)
    return [(1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * b for t in (i / (n - 1) for i in range(n))]


# ------------------------------------------------------------------------------------------------ primitives

def limb(acc, pts, radii, surf, segs=12, per=4, caps=True, flat=1.0, twist=0.0):
    """Smooth organic tube through control points; radii per control point (smoothly interpolated)."""
    if len(pts) < 3:
        per = max(per, 2)
        pts = [Vector(pts[0]).lerp(Vector(pts[-1]), t) for t in (0.0, 0.5, 1.0)]
        radii = [radii[0], 0.5 * (radii[0] + radii[-1]), radii[-1]]
    path = catmull(pts, per)
    rr = interp(list(radii), per)
    return acc.tube(path, rr, surf, segs, caps=caps, flat=flat, twist=twist)


def horn(acc, base, tip, r0, surf, bend=(0, 0, 0), segs=8, n=7, r1=0.0, power=0.85, flat=1.0):
    """Curved cone (tooth, claw, spike, thorn) from base to tip, bent toward 'bend'."""
    base, tip = Vector(base), Vector(tip)
    ctrl = (base + tip) * 0.5 + Vector(bend)
    pts = bezier(base, ctrl, tip, n)
    radii = [r1 + (r0 - r1) * (1 - i / (n - 1)) ** power for i in range(n)]
    return acc.tube(pts, radii, surf, segs, caps=True, flat=flat)


def ball(acc, c, r, surf, segs=14, rings=9, M=Matrix()):
    rr = (r, r, r) if isinstance(r, (int, float)) else r
    return acc.sphere(rr, T(c) @ M, surf, segs, rings)


def blob(acc, c, half, surf, M=Matrix(), e=(0.85, 0.85), amp=0.0, freq=2.0, seed=0, segs=24, rings=14):
    """Rounded organic mass (superellipsoid) with optional noise displacement along its normals."""
    hx, hy, hz = half

    def deform(co):
        if amp <= 0:
            return co
        d = Vector((co.x / hx, co.y / hy, co.z / hz))
        n = Vector((d.x / hx, d.y / hy, d.z / hz)).normalized()
        return co + n * (amp * smooth_noise3(co, seed, freq))
    return acc.superellipsoid(half, e, T(c) @ M, surf, segs, rings, deform=deform if amp > 0 else None)


def sgnpow(x, p):
    return math.copysign(abs(x) ** p, x)


def sweep(acc, spine, hw, hh, surf, n=22, p=2.3, belly=0.0, up=(0, 0, 1), per=3, noise=None, top_bulge=0.0):
    """Organic body: superellipse sections along a smooth spine. hw / hh: half width / height per control point.
    belly flattens the underside, top_bulge raises the back. noise=(amp, freq, seed) displaces every section point
    outward. Ends close with the given (small) sections."""
    path = catmull(spine, per)
    W = interp(list(hw), per)
    H = interp(list(hh), per)
    upv = Vector(up)
    secs = []
    e = 2.0 / p
    for i, c in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        t = (b - a).normalized()
        u = (upv - t * upv.dot(t)).normalized()
        s = t.cross(u).normalized()
        ring = []
        for k in range(n):
            ang = 2 * math.pi * k / n
            cx, cz = math.cos(ang), math.sin(ang)
            x = W[i] * sgnpow(cx, e)
            z = H[i] * sgnpow(cz, e)
            if z < 0:
                z *= (1.0 - belly)
            else:
                z *= (1.0 + top_bulge * (1 - abs(cx)))
            q = c + s * x + u * z
            if noise:
                amp, freq, seed = noise
                d = (q - c)
                if d.length > 1e-6:
                    q = q + d.normalized() * amp * smooth_noise3(q, seed, freq)
            ring.append(q)
        secs.append(ring)
    return acc.loft(secs, surf)


def lathe_at(acc, prof, c, axis, surf, segs=20, caps=(True, True), sharp=50, spin=0.0):
    """Revolved profile [(radius, height)] around 'axis' through c."""
    M = T(c) @ look(axis) @ R('Z', spin)
    return acc.lathe(prof, segs, M, surf, caps[0], caps[1], sharp)


def cyl(acc, a, b, r, surf, segs=12, r2=None, caps=True, bevel=0.0):
    return acc.cyl_between(Vector(a), Vector(b), r, surf, segs, r2, caps, bevel)


def box(acc, c, size, surf, M=Matrix(), bevel=0.02):
    return acc.box(size, T(c) @ M, surf, bevel=bevel, segs=2)


def torus(acc, c, axis, R_, r, surf, segs=24, rsegs=8, arc=360.0, start=0.0):
    """Ring (or arc) tube around 'axis' through c."""
    Mr = T(c) @ look(axis)
    n = max(3, int(segs * arc / 360.0))
    pts = []
    for i in range(n + 1 if arc < 360 else n + 1):
        a = math.radians(start + arc * i / n)
        pts.append(Mr @ Vector((R_ * math.cos(a), R_ * math.sin(a), 0.0)))
    return acc.tube(pts, r, surf, rsegs, caps=arc < 360)


# ------------------------------------------------------------------------------------------------ paint helpers

def displace(acc, faces, amp, freq, seed=0, mask=None):
    """Moves the vertices of faces along their normals by smooth noise (organic lumps)."""
    acc.bm.normal_update()
    vs = {v for f in faces for v in f.verts}
    for v in vs:
        k = 1.0 if mask is None else mask(v.co)
        if k <= 0:
            continue
        v.co += v.normal * (amp * k * smooth_noise3(v.co, seed, freq))


def recolor(acc, faces, fn):
    acc.recolor(faces, fn)


def grad(lo_rgb, hi_rgb, a, b, axis=2, power=1.0):
    """Colour gradient along an axis between coordinates a (lo colour) and b (hi colour); keeps alpha."""
    lo = hexlin(lo_rgb) if isinstance(lo_rgb, str) else lo_rgb
    hi = hexlin(hi_rgb) if isinstance(hi_rgb, str) else hi_rgb

    def fn(p, c):
        t = (p[axis] - a) / (b - a) if abs(b - a) > 1e-9 else 0.0
        t = max(0.0, min(1.0, t)) ** power
        col = mixc(lo, hi, t)
        return (col[0], col[1], col[2], c[3])
    return fn


def tint(rgb, k):
    """fn multiplying painted colours toward rgb by k (0..1)."""
    target = hexlin(rgb) if isinstance(rgb, str) else rgb

    def fn(p, c):
        return (c[0] * (1 - k) + target[0] * k, c[1] * (1 - k) + target[1] * k, c[2] * (1 - k) + target[2] * k, c[3])
    return fn


def mottle(amount=0.18, freq=4.0, seed=0, dark=None, dark_thr=0.45, dark_k=0.45):
    """Organic colour variation; optional dark pits where the noise exceeds dark_thr."""
    def fn(p, c):
        n = smooth_noise3(p, seed, freq)
        k = 1.0 + amount * n
        r, g, b = c[0] * k, c[1] * k, c[2] * k
        if dark is not None:
            m = smooth_noise3(p, seed + 31, freq * 2.3)
            if m > dark_thr:
                t = min(1.0, (m - dark_thr) / 0.12) * dark_k
                d = hexlin(dark) if isinstance(dark, str) else dark
                r, g, b = r * (1 - t) + d[0] * t, g * (1 - t) + d[1] * t, b * (1 - t) + d[2] * t
        return (r, g, b, c[3])
    return fn


def chain(*fns):
    def fn(p, c):
        for f in fns:
            c = f(p, c)
        return c
    return fn


# ------------------------------------------------------------------------------------------------ shapes

def eye(acc, c, r, look_dir, iris=None, slit=True, lid=None, lid_k=0.35):
    """Glowing eye: iris facing look_dir with a black slit (or round) pupil; optional half lid (surf) over the top."""
    iris = iris or C['eye']
    f = ball(acc, c, r, iris, segs=16, rings=12)
    z = Vector(look_dir).normalized()
    x = Vector((0, 0, 1)).cross(z)
    if x.length < 1e-4:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x).normalized()
    cc = Vector(c)
    pup = hexlin('#0E0D0A')
    rim = mulc(iris.rgb, 0.55)

    def fn(p, col):
        d = (Vector(p) - cc).normalized()
        front = d.dot(z)
        px, py = d.dot(x), d.dot(y)
        if front < 0.2:
            return (rim[0], rim[1], rim[2], 1.0)
        if (slit and abs(px) < 0.09 + 0.06 * (1 - abs(py)) and front > 0.45) or (not slit and front > 0.86):
            return (pup[0], pup[1], pup[2], 1.0)
        return col
    acc.recolor(f, fn)
    if lid is not None:
        # heavy upper lid / brow: a squashed shell over the top of the eye, leaving the iris visible
        f += acc.sphere((r * 1.12, r * 1.12, r * 0.62), T(cc + y * r * (0.55 - lid_k * 0.4) - z * r * 0.12) @ look(z, y)
                        @ Matrix.Diagonal((1.0, 1.0, 1.0, 1.0)), lid, 14, 8)
    return f


def teeth_ring(acc, c, axis, r, n, length, surf=None, inward=0.35, r0=0.05, seed=0, jitter=0.25):
    """Teeth around a ring (sucker mouths, jaws), pointing along the axis and inward."""
    surf = surf or C['tooth']
    z = Vector(axis).normalized()
    M = look(z)
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        a = 2 * math.pi * (i + 0.5 * rnd.random() * jitter) / n
        radial = (M @ Vector((math.cos(a), math.sin(a), 0.0))).normalized()
        base = Vector(c) + radial * r
        L_ = length * (0.75 + 0.5 * rnd.random())
        tip = base + z * L_ * 0.55 - radial * L_ * inward
        out += horn(acc, base, tip, r0 * (0.85 + 0.3 * rnd.random()), surf, bend=z * L_ * 0.12, segs=6, n=5)
    return out


def shelf(acc, c, out_dir, rad, thick, surf_cap=None, surf_gill=None, droop=0.15, segs=20, M=Matrix()):
    """Bracket fungus: a flattened cap growing out of a surface along out_dir (horizontal-ish), gills underneath."""
    surf_cap = surf_cap or C['cap']
    surf_gill = surf_gill or C['gill']
    # sphere-like order (bottom / rim first, then up and in) keeps the normals outward
    prof_top = [(rad, 0.02 * rad), (rad * 0.93, thick * 0.32), (rad * 0.7, thick * 0.7), (rad * 0.35, thick * 0.95),
                (0.0, thick)]
    prof_bot = [(0.0, -0.12 * rad), (rad * 0.6, -0.1 * rad), (rad * 0.92, -0.06 * rad), (rad, 0.02 * rad)]
    d = Vector(out_dir)
    d.z = 0
    if d.length < 1e-6:
        d = Vector((0, 1, 0))
    d.normalize()
    side = Vector((0, 0, 1)).cross(d).normalized()
    # squash along the growth direction; shift so the inner edge sits in the surface
    B = Matrix((side, d, Vector((0, 0, 1)))).transposed().to_4x4()
    Mx = T(Vector(c) + d * rad * 0.45) @ B @ R('X', -droop * 40.0) @ Matrix.Diagonal((1.0, 0.62, 1.0, 1.0)) @ M
    top = acc.lathe(prof_top, segs, Mx, surf_cap, False, False, None)
    bot = acc.lathe(prof_bot, segs, Mx, surf_gill, False, False, None)
    return top + bot


def rivets(acc, pts, r, surf=None):
    surf = surf or C['steel_dk']
    out = []
    for p in pts:
        out += ball(acc, p, r, surf, segs=8, rings=5)
    return out


def drum(acc, c, axis, r, h, body, band_surf=None, ribs=2, segs=28):
    """Chemical drum with rolled rims and ribs along 'axis' (centre c)."""
    band_surf = band_surf or body.k(0.8)
    hh = h / 2
    prof = [(0.0, -hh), (r * 0.94, -hh), (r * 1.02, -hh + 0.02), (r, -hh + 0.05)]
    for i in range(ribs):
        z = -hh + h * (i + 1) / (ribs + 1)
        prof += [(r, z - 0.04), (r * 1.035, z - 0.015), (r * 1.035, z + 0.015), (r, z + 0.04)]
    prof += [(r, hh - 0.05), (r * 1.02, hh - 0.02), (r * 0.94, hh), (r * 0.6, hh - 0.01), (0.0, hh - 0.012)]
    return lathe_at(acc, prof, c, axis, body, segs, caps=(False, False), sharp=45)


def trefoil(acc, c, normal, size, up=(0, 0, 1)):
    """Yellow radiation / hazard disc with a black trefoil, floating 3 mm off a surface (decal geometry)."""
    n = Vector(normal).normalized()
    M = T(Vector(c) + n * 0.004) @ look(n, up)
    out = acc.lathe([(size, 0.0), (0.0, 0.0)], 24, M, C['hazard_y'], False, False, None)
    blk = C['black']
    for k in range(3):
        a0 = math.radians(90 + 120 * k - 30)
        a1 = math.radians(90 + 120 * k + 30)
        pts, idx = [], []
        ri, ro = size * 0.22, size * 0.86
        steps = 6
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            pts.append((ri * math.cos(a), ri * math.sin(a), 0.002))
            pts.append((ro * math.cos(a), ro * math.sin(a), 0.002))
        for s in range(steps):
            idx.append([2 * s, 2 * s + 1, 2 * s + 3, 2 * s + 2])
        out += acc.poly(pts, idx, blk, M=M, sharp=None)
    out += acc.lathe([(size * 0.14, 0.003), (0.0, 0.003)], 12, M, blk, False, False, None)
    return out


def webbed_foot(acc, ankle, fwd, toes=3, spread=55.0, length=0.22, r=0.035, skin=None, web=None, claw=None, lift=0.0):
    """Ground-contact foot: toes radiating forward from the ankle (on the ground), thin web between them."""
    skin = skin or C['ochre']
    web = web or C['web']
    claw = claw or C['bone_dk']
    f = Vector(fwd)
    f.z = 0
    f.normalize()
    side = Vector((0, 0, 1)).cross(f).normalized()
    a = Vector(ankle)
    out = []
    tips = []
    for i in range(toes):
        t = (i / (toes - 1) - 0.5) if toes > 1 else 0.0
        ang = math.radians(spread * t)
        d = (f * math.cos(ang) + side * math.sin(ang)).normalized()
        L_ = length * (1.0 - 0.18 * abs(t) * 2)
        p1 = a + d * L_ * 0.5 + Vector((0, 0, 0.02 + lift))
        p2 = a + d * L_ + Vector((0, 0, 0.012))
        out += limb(acc, [a + Vector((0, 0, 0.03)), p1, p2], [r * 1.1, r * 0.85, r * 0.55], skin, segs=8, per=3)
        out += horn(acc, p2, p2 + d * r * 1.6 + Vector((0, 0, -0.01)), r * 0.45, claw, segs=6, n=4)
        tips.append(p2)
    if toes > 1 and web is not None:
        pts = [a + Vector((0, 0, 0.03))]
        for p in tips:
            pts.append(p + Vector((0, 0, 0.012)))
        idx = [[0, i + 1, i + 2] for i in range(len(tips) - 1)]
        out += acc.poly(pts, idx, web, sharp=None)
        out += acc.poly(pts, [[0, i + 2, i + 1] for i in range(len(tips) - 1)], web, sharp=None)
    return out


# ------------------------------------------------------------------------------------------------ creature rig

class Creature:
    """A creature hierarchy: root empty + rigid part objects placed at their joints (identity rotations)."""

    def __init__(self, name, coll_name, unity_model, offset=(0, 0, 0)):
        self.name = name
        self.coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(self.coll)
        self.root = bpy.data.objects.new(name, None)
        self.root.empty_display_type = 'ARROWS'
        self.root.empty_display_size = 0.5
        self.root.location = offset
        self.root['mut_model'] = unity_model
        self.root['mut_root'] = True
        self.coll.objects.link(self.root)
        self.pivots = {name: Vector((0, 0, 0))}
        self.objs = {name: self.root}
        self.parts = []

    def part(self, pname, acc, pivot, parent=None, shadow=True):
        """acc: MAcc built in creature space (or None for a pure pivot). The mesh is moved into the part frame."""
        parent = parent or self.name
        pv = Vector(pivot)
        if acc is not None:
            me = acc.build(f'{self.name}_{pname}')
            me.transform(Matrix.Translation(-pv))
            me.update()
            ob = bpy.data.objects.new(f'{self.name}_{pname}', me)
        else:
            ob = bpy.data.objects.new(f'{self.name}_{pname}', None)
            ob.empty_display_type = 'SPHERE'
            ob.empty_display_size = 0.05
        ob['mut_part'] = pname
        if not shadow:
            ob['tw_no_shadow'] = True
        self.coll.objects.link(ob)
        ob.parent = self.objs[parent]
        ob.location = pv - self.pivots[parent]
        self.pivots[pname] = pv
        self.objs[pname] = ob
        if acc is not None:
            self.parts.append(ob)
        return ob

    def meshes(self):
        return [o for o in self.parts if o.type == 'MESH']

    def finish(self, ao=0.5, ao_dist=0.3, lod_ratio=0.5, lod_min_tris=500):
        bpy.context.view_layer.update()
        vertex_ao(self.meshes(), strength=ao, dist=ao_dist)
        tris = 0
        for o in list(self.meshes()):
            t = L.tri_count(o.data)
            tris += t
            if lod_ratio and t >= lod_min_tris:
                lm = L.lod_copy(o.data, lod_ratio, o.data.name + '_LOD1')
                for m in o.data.materials:
                    if m.name not in [x.name for x in lm.materials]:
                        lm.materials.append(m)
                lo = bpy.data.objects.new(o.name + '_LOD1', lm)
                lo['mut_part'] = o['mut_part'] + '_LOD1'
                lo['unity_lod_level'] = 1
                lo['unity_lod_of'] = o.name
                if o.get('tw_no_shadow'):
                    lo['tw_no_shadow'] = True
                self.coll.objects.link(lo)
                lo.parent = o
                lo.hide_render = True
                lo.hide_viewport = True
        self.root['mut_tris'] = tris
        return tris


def vertex_ao(objects, strength=0.5, dist=0.3, rays=24, seed=3):
    """Soft ambient occlusion baked into 'Color' on the assembled creature (all parts in their rest pose)."""
    verts, polys = [], []
    for o in objects:
        mw = o.matrix_world
        base = len(verts)
        verts.extend([mw @ v.co for v in o.data.vertices])
        polys.extend([[base + i for i in p.vertices] for p in o.data.polygons])
    if not polys:
        return 0
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    rnd = random.Random(seed)
    dirs = []
    for i in range(rays):
        u, v = (i + 0.5) / rays, rnd.random()
        r = math.sqrt(u)
        th = 2 * math.pi * v
        dirs.append((r * math.cos(th), r * math.sin(th), math.sqrt(max(0.0, 1 - u))))
    for o in objects:
        me = o.data
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        ao = []
        for v in me.vertices:
            p = mw @ v.co
            n = (nmat @ v.normal).normalized()
            t = n.orthogonal().normalized()
            b = n.cross(t)
            hit = 0
            for dx, dy, dz in dirs:
                d = t * dx + b * dy + n * dz
                loc, _, _, _ = tree.ray_cast(p + n * 0.004, d, dist)
                if loc is not None:
                    hit += 1
            ao.append(1.0 - hit / rays)
        col = me.color_attributes.get('Color')
        if col is None:
            continue
        for li, loop in enumerate(me.loops):
            a = ao[loop.vertex_index]
            k = 1.0 - strength * (1.0 - a)
            c = col.data[li].color
            col.data[li].color = (c[0] * k, c[1] * k, c[2] * k, c[3])
    return len(objects)


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
