"""Toxic Wetlands art pass: core modelling toolkit (runs inside Blender 5.2).

Every mesh written by this pass follows the RoadGame/Toon pipeline contract (same as the v13 Dust Flats pass):
  * 'Color'                 CORNER / FLOAT_COLOR, linear RGB = painted colour, A < 1 = self-lit amount (glow)
  * 'UVMap'                 UV0 for the BaseMap (trim / character atlas strips or box-projected tiling maps)
  * 'Unity_MaterialParams'  UV1: x = gloss, y = metal (NOT a lightmap)
  * smooth shading, sharp edges only where the part asks for them (angle per part)
Geometry is accumulated in one bmesh per mesh datablock (Acc). Primitives return the faces they created, so
painting / UVs / sharpness apply per part. Organic parts can go through a Subdivision Surface cage.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

# ----------------------------------------------------------------------------------------------------------- colour

def lin1(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip('#')
    return tuple(lin1(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def mixc(a, b, t):
    return tuple(x * (1 - t) + y * t for x, y in zip(a, b))


def mulc(a, k):
    if isinstance(k, (int, float)):
        return tuple(x * k for x in a)
    return tuple(x * y for x, y in zip(a, k))


class Surf:
    """Paint for a part: linear rgb, gloss, metal, glow (self-lit 0..1), atlas strip (or None) and material key."""
    __slots__ = ('rgb', 'gloss', 'metal', 'glow', 'strip', 'mat')

    def __init__(self, rgb, gloss=0.0, metal=0.0, glow=0.0, strip='plain', mat=None):
        self.rgb = tuple(hexlin(rgb)) if isinstance(rgb, str) else tuple(rgb)
        self.gloss, self.metal, self.glow, self.strip, self.mat = gloss, metal, glow, strip, mat

    def k(self, k):
        return Surf(mulc(self.rgb, k), self.gloss, self.metal, self.glow, self.strip, self.mat)

    def mix(self, other, t):
        o = other if isinstance(other, Surf) else Surf(other)
        return Surf(mixc(self.rgb, o.rgb, t), self.gloss * (1 - t) + o.gloss * t, self.metal * (1 - t) + o.metal * t,
                    self.glow, self.strip, self.mat)

    def with_(self, **kw):
        s = Surf(self.rgb, self.gloss, self.metal, self.glow, self.strip, self.mat)
        for k, v in kw.items():
            setattr(s, k, tuple(hexlin(v)) if (k == 'rgb' and isinstance(v, str)) else v)
        return s

    @property
    def rgba(self):
        return (self.rgb[0], self.rgb[1], self.rgb[2], 1.0 - self.glow)


# Swamp palette (sRGB hex -> linear on use). Gloss/metal conventions follow the v10/v13 vertex params:
# stone/mud/wood/cloth ~0, rubber 0.16-0.3, paint 0.45/0.12, rusty metal 0.2/0.25, steel 0.5/0.7, wet 0.35-0.6.
P = {
    # ground & nature
    'mud':          Surf('#4A4330', 0.10),
    'mud_wet':      Surf('#2E2A1E', 0.45),
    'mud_dry':      Surf('#6B6347', 0.02),
    'moss':         Surf('#5E6B33', 0.04),
    'moss_light':   Surf('#7C8740', 0.04),
    'moss_dark':    Surf('#3A4421', 0.04),
    'algae':        Surf('#7E9A2E', 0.30),
    'reed':         Surf('#8C8A4E', 0.06),
    'reed_dry':     Surf('#A69C68', 0.04),
    'reed_green':   Surf('#5F7134', 0.08),
    'cattail':      Surf('#5A3A22', 0.08),
    'bark':         Surf('#5C5446', 0.03),
    'bark_dark':    Surf('#3A342A', 0.03),
    'deadwood':     Surf('#8A8170', 0.03),
    'root':         Surf('#4E4434', 0.05),
    'shroom_cap':   Surf('#B9A06A', 0.20),
    'shroom_red':   Surf('#A8492E', 0.25),
    'shroom_stem':  Surf('#D9CFB2', 0.10),
    'stone':        Surf('#6E6E62', 0.02),
    'stone_dark':   Surf('#4C4D45', 0.02),
    'slag':         Surf('#55534A', 0.06),
    # industrial
    'concrete':     Surf('#8B897D', 0.04, strip='concrete'),
    'concrete_dk':  Surf('#5E5D55', 0.04, strip='concrete'),
    'steel':        Surf('#8E938F', 0.50, 0.70, strip='metal'),
    'steel_dk':     Surf('#3E4240', 0.45, 0.55, strip='metal'),
    'galv':         Surf('#9EA39F', 0.45, 0.60, strip='metal'),
    'rust':         Surf('#FFFFFF', 0.18, 0.22, strip='rust'),
    'rust_plain':   Surf('#7A3E22', 0.18, 0.25, strip='metal'),
    'rust_dark':    Surf('#4C2717', 0.15, 0.22, strip='metal'),
    'paint_olive':  Surf('#6B6B3E', 0.40, 0.12, strip='metal'),
    'paint_green':  Surf('#4F6A4A', 0.40, 0.12, strip='metal'),
    'paint_teal':   Surf('#3D6461', 0.42, 0.12, strip='metal'),
    'paint_cream':  Surf('#C9BE98', 0.40, 0.10, strip='metal'),
    'paint_yellow': Surf('#D9AE2E', 0.45, 0.10, strip='metal'),
    'paint_orange': Surf('#C2622E', 0.45, 0.12, strip='metal'),
    'paint_red':    Surf('#9C3A2A', 0.45, 0.12, strip='metal'),
    'hazard':       Surf('#FFFFFF', 0.40, 0.10, strip='hazard'),
    'label':        Surf('#FFFFFF', 0.35, 0.05, strip='label'),
    'corrugated':   Surf('#8E9089', 0.40, 0.50, strip='corrugated'),
    'panel':        Surf('#8A8C84', 0.40, 0.50, strip='panel'),
    'plank':        Surf('#7D6A50', 0.06, strip='plank'),
    'plank_dk':     Surf('#54473A', 0.06, strip='plank'),
    'plank_grey':   Surf('#7F786C', 0.05, strip='plank'),
    'tarp':         Surf('#6E7451', 0.08, strip='canvas'),
    'tarp_blue':    Surf('#4C6278', 0.10, strip='canvas'),
    'tarp_orange':  Surf('#B5683A', 0.10, strip='canvas'),
    'rubber':       Surf('#24251F', 0.22, strip='tire'),
    'black':        Surf('#1C1D1B', 0.35, 0.10),
    'glass':        Surf('#4E6A62', 0.85, 0.0),
    'drips':        Surf('#FFFFFF', 0.30, 0.10, strip='drips'),
    'grate':        Surf('#FFFFFF', 0.40, 0.50, strip='grate'),
    # toxic accents (self-lit amount in glow)
    'toxic':        Surf('#B8E04A', 0.55, 0.0, glow=0.55),
    'toxic_soft':   Surf('#9CC23C', 0.50, 0.0, glow=0.30),
    'toxic_goo':    Surf('#8DB332', 0.60, 0.0, glow=0.18),
    'lamp':         Surf('#F2D27E', 0.40, 0.0, glow=0.75),
}

# ----------------------------------------------------------------------------------------------- atlas layouts
# Trim atlas: 2048 x 2048, 16 horizontal strips of 128 px (v from the bottom of the image, OpenGL convention).
TRIM_STRIPS = ['plain', 'metal', 'rust', 'panel', 'corrugated', 'plank', 'concrete', 'hazard',
               'drips', 'moss', 'label', 'grate', 'bark', 'mud', 'canvas', 'tire']
# Character atlas: 1024 x 1024, 8 strips of 128 px.
CHAR_STRIPS = ['plain', 'rubber', 'canvas', 'leather', 'metal', 'rust', 'hazard', 'drips']


# metres of surface per full texture width, per strip (keeps every pattern at a readable game-camera size)
TRIM_SCALE = {'plain': 4.0, 'metal': 4.0, 'rust': 3.0, 'panel': 4.0, 'corrugated': 4.0, 'plank': 4.0, 'concrete': 6.0,
              'hazard': 6.0, 'drips': 8.0, 'moss': 3.0, 'label': 8.0, 'grate': 2.0, 'bark': 2.5, 'mud': 4.0,
              'canvas': 3.0, 'tire': 2.0}
CHAR_SCALE = {'plain': 2.0, 'rubber': 2.0, 'canvas': 1.5, 'leather': 1.5, 'metal': 2.0, 'rust': 1.5, 'hazard': 1.0,
              'drips': 2.5}


def strip_band(strip, atlas='trim'):
    names = CHAR_STRIPS if atlas == 'char' else TRIM_STRIPS
    if strip not in names:
        strip = 'plain' if 'plain' in names else names[0]
    i = names.index(strip)
    n = len(names)
    # 3 px inset against bilinear bleeding between strips
    inset = 3.0 / (128.0 * n)
    lo = 1.0 - (i + 1) / n
    return lo + inset, (1.0 / n) - 2 * inset


# --------------------------------------------------------------------------------------------- accumulator

class _Part:
    """A temporary bmesh with the three loop layers. Primitives are built (and bevelled / welded) here, then
    appended to the accumulator, so element deletions never disturb the accumulated face order."""

    def __init__(self):
        self.bm = bmesh.new()
        L = self.bm.loops.layers
        self.lc = L.float_color.new('Color')
        self.luv = L.uv.new('UVMap')
        self.lp = L.uv.new('Unity_MaterialParams')


class Acc:
    """One mesh datablock under construction. 'atlas': 'trim' / 'char' strip atlases, or 'box' (tiling map)."""

    def __init__(self, name, atlas='trim', mat='TW_Trim', box_tile=2.0):
        self.name = name
        self.atlas = atlas
        self.default_mat = mat
        self.box_tile = box_tile
        self.main = _Part()
        self.bm = self.main.bm
        self.mats = []

    # ---------------------------------------------------------------- helpers
    def mat_index(self, key):
        key = key or self.default_mat
        if key not in self.mats:
            self.mats.append(key)
        return self.mats.index(key)

    def _commit(self, pt):
        me = bpy.data.meshes.new('_tw_part')
        pt.bm.to_mesh(me)
        pt.bm.free()
        n0 = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.bm.faces.ensure_lookup_table()
        return [self.bm.faces[i] for i in range(n0, len(self.bm.faces))]

    def paint(self, faces, surf, uv=None, sharp=None, smooth=True, part=None):
        """Colour / params / material / uv for faces. uv: callable(loop, face) -> (u metres along, v 0..1 across)
        for strip atlases, or None for a projection (box atlas: 2D tiling, strip atlas: u only)."""
        pt = part or self.main
        mi = self.mat_index(surf.mat)
        rgba = surf.rgba
        prm = (surf.gloss, surf.metal)
        lo, h = strip_band(surf.strip, 'char' if self.atlas == 'char' else 'trim')
        us = (CHAR_SCALE if self.atlas == 'char' else TRIM_SCALE).get(surf.strip, 4.0)
        for f in faces:
            f.material_index = mi
            f.smooth = smooth
            if uv is None:
                n = f.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
            for l in f.loops:
                l[pt.lc] = rgba
                l[pt.lp].uv = prm
                if uv is not None:
                    u, v = uv(l, f)
                else:
                    co = l.vert.co
                    if ax == 0:
                        u, v = co.y, co.z
                    elif ax == 1:
                        u, v = co.x, co.z
                    else:
                        u, v = co.x, co.y
                    u, v = u / self.box_tile, v / self.box_tile
                    if self.atlas != 'box':
                        v = 0.5
                if self.atlas == 'box':
                    l[pt.luv].uv = (u, v)
                else:
                    l[pt.luv].uv = (u / us, lo + max(0.0, min(1.0, v)) * h)
        if sharp is not None:
            self.sharpen(faces, sharp)
        return faces

    @staticmethod
    def sharpen(faces, angle_deg):
        lim = math.radians(angle_deg)
        es = {e for f in faces for e in f.edges}
        for e in es:
            e.smooth = (e.calc_face_angle(0.0) < lim) if len(e.link_faces) == 2 else True

    def transform(self, faces, M, part=None):
        pt = part or self.main
        vs = list({v for f in faces for v in f.verts})
        bmesh.ops.transform(pt.bm, matrix=M, verts=vs)

    def recolor(self, faces, fn):
        """fn(position Vector, rgba tuple) -> rgba, applied per loop on accumulated faces (e.g. dirt gradients)."""
        for f in faces:
            for l in f.loops:
                l[self.main.lc] = fn(l.vert.co, tuple(l[self.main.lc]))

    # ---------------------------------------------------------------- primitives
    def box(self, size, M=Matrix(), surf=None, bevel=0.0, segs=3, sharp=None):
        """Rounded box centred at the origin of M. Bevel radius in metres (clamped to the part size)."""
        pt = _Part()
        S = Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        r = bmesh.ops.create_cube(pt.bm, size=1.0, matrix=S)
        if bevel > 0:
            b = min(bevel, 0.49 * min(size))
            verts = r['verts']
            edges = list({e for v in verts for e in v.link_edges})
            bmesh.ops.bevel(pt.bm, geom=edges + list(verts), offset=b, offset_type='OFFSET', segments=segs,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        faces = list(pt.bm.faces)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2

        def uvf(l, f):
            co = l.vert.co
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            if ax == 2:
                if hx >= hy:
                    return co.x, (co.y + hy) / max(2 * hy, 1e-6)
                return co.y, (co.x + hx) / max(2 * hx, 1e-6)
            return (co.x if ax == 1 else co.y), (co.z + hz) / max(2 * hz, 1e-6)
        self.paint(faces, surf or P['steel'], uvf, sharp=sharp if sharp is not None else (60 if bevel > 0 else 30), part=pt)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def lathe(self, prof, segs, M=Matrix(), surf=None, cap_bottom=True, cap_top=True, sharp=50, surf_fn=None,
              uscale=None, arc=(0.0, 2 * math.pi)):
        """Revolve profile [(radius, z), ...] (bottom -> top) about local Z. Radius 0 = a single pole vertex.
        surf_fn(i_band) -> Surf per profile band. Strip uv: u = arc length (m) around, v = 0..1 along the outline."""
        pt = _Part()
        bm = pt.bm
        full = abs(arc[1] - arc[0] - 2 * math.pi) < 1e-6
        cols = segs if full else segs + 1
        lengths = [0.0]
        for i in range(1, len(prof)):
            lengths.append(lengths[-1] + math.hypot(prof[i][0] - prof[i - 1][0], prof[i][1] - prof[i - 1][1]))
        tot = max(lengths[-1], 1e-6)
        rmax = max(max(r for r, _ in prof), 1e-4)
        vpar = {}
        rings = []
        for i, (r, z) in enumerate(prof):
            if r < 1e-6:
                v = bm.verts.new((0.0, 0.0, z))
                vpar[v] = lengths[i] / tot
                rings.append([v] * cols)
                continue
            ring = []
            for s in range(cols):
                a = arc[0] + (arc[1] - arc[0]) * s / segs
                v = bm.verts.new((r * math.cos(a), r * math.sin(a), z))
                vpar[v] = lengths[i] / tot
                ring.append(v)
            rings.append(ring)
        bands = []
        for i in range(len(prof) - 1):
            band = []
            for s in range(segs):
                s1 = (s + 1) % cols if full else s + 1
                q = [rings[i][s], rings[i][s1], rings[i + 1][s1], rings[i + 1][s]]
                out = []
                for v in q:
                    if not out or out[-1] is not v:
                        out.append(v)
                if len(out) > 1 and out[0] is out[-1]:
                    out.pop()
                if len(out) < 3:
                    continue
                try:
                    band.append(bm.faces.new(out))
                except ValueError:
                    pass
            bands.append(band)
        caps = []
        if full and cap_bottom and prof[0][0] > 1e-6:
            caps.append(bm.faces.new(list(reversed(rings[0]))))
        if full and cap_top and prof[-1][0] > 1e-6:
            caps.append(bm.faces.new(rings[-1]))
        us = uscale if uscale else rmax

        def uvf(l, f):
            co = l.vert.co
            c = f.calc_center_median()
            ac = math.atan2(c.y, c.x)
            if abs(co.x) + abs(co.y) < 1e-7:
                a = ac
            else:
                a = math.atan2(co.y, co.x)
                if a - ac > math.pi:
                    a -= 2 * math.pi
                elif ac - a > math.pi:
                    a += 2 * math.pi
            return a * us, vpar.get(l.vert, 0.5)
        for i, band in enumerate(bands):
            s = surf_fn(i) if surf_fn else (surf or P['steel'])
            self.paint(band, s, uvf, part=pt)
        if caps:
            s = surf_fn(len(bands) - 1) if surf_fn else (surf or P['steel'])
            self.paint(caps, s, lambda l, f: (l.vert.co.x, 0.5 + l.vert.co.y / (2 * rmax)), part=pt)
        faces = list(bm.faces)
        if sharp is not None:
            self.sharpen(faces, sharp)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def cyl(self, r, h, M=Matrix(), surf=None, segs=16, r2=None, caps=True, bevel=0.0, sharp=50):
        """Cylinder along local Z from z=0 to z=h. bevel rounds both rims (quarter circle)."""
        r2 = r if r2 is None else r2
        if bevel > 0:
            b = min(bevel, 0.45 * min(r, r2, h))
            prof = [(0.0, 0.0)] if caps else []
            for k in range(4):
                a = (k / 3) * math.pi / 2
                prof.append((r - b + b * math.sin(a), b - b * math.cos(a)))
            for k in range(4):
                a = (k / 3) * math.pi / 2
                prof.append((r2 - b + b * math.cos(a), h - b + b * math.sin(a)))
            if caps:
                prof.append((0.0, h))
            return self.lathe(prof, segs, M, surf, cap_bottom=False, cap_top=False, sharp=sharp)
        return self.lathe([(r, 0.0), (r2, h)], segs, M, surf, cap_bottom=caps, cap_top=caps, sharp=sharp)

    def cyl_between(self, a, b, r, surf=None, segs=12, r2=None, caps=True, bevel=0.0, roll=0.0, sharp=50):
        a, b = Vector(a), Vector(b)
        d = b - a
        if d.length < 1e-6:
            return []
        q = d.normalized().to_track_quat('Z', 'Y') @ Quaternion((0, 0, 1), roll)
        M = Matrix.Translation(a) @ q.to_matrix().to_4x4()
        return self.cyl(r, d.length, M, surf, segs, r2, caps, bevel, sharp)

    def sphere(self, rad, M=Matrix(), surf=None, segs=16, rings=10, sharp=None, deform=None):
        """UV ellipsoid with radii rad=(rx,ry,rz); deform(co) -> co applied before M."""
        if isinstance(rad, (int, float)):
            rad = (rad, rad, rad)
        prof = []
        for i in range(rings + 1):
            t = -math.pi / 2 + math.pi * i / rings
            prof.append((max(0.0, math.cos(t)) if 0 < i < rings else 0.0, math.sin(t)))
        if deform is None:
            S = Matrix.Diagonal((rad[0], rad[1], rad[2], 1.0))
            return self.lathe(prof, segs, M @ S, surf, False, False, sharp)
        pt_faces = self.lathe(prof, segs, Matrix.Diagonal((rad[0], rad[1], rad[2], 1.0)), surf, False, False, sharp)
        vs = {v for f in pt_faces for v in f.verts}
        for v in vs:
            v.co = deform(v.co)
        self.transform(pt_faces, M)
        return pt_faces

    def superellipsoid(self, half, e=(0.5, 0.5), M=Matrix(), surf=None, segs=20, rings=12, deform=None, sharp=None):
        """Rounded block (e near 0 = boxy, 1 = ellipsoid). deform(co) -> co before M."""
        e1, e2 = e

        def sgnpow(x, p):
            return math.copysign(abs(x) ** p, x)
        pt = _Part()
        bm = pt.bm
        rows = []
        bottom = bm.verts.new((0.0, 0.0, -half[2]))
        top = bm.verts.new((0.0, 0.0, half[2]))
        for i in range(1, rings):
            t = -math.pi / 2 + math.pi * i / rings
            row = []
            for s in range(segs):
                a = -math.pi + 2 * math.pi * s / segs
                ct, st = math.cos(t), math.sin(t)
                row.append(bm.verts.new((half[0] * sgnpow(ct, e1) * sgnpow(math.cos(a), e2),
                                         half[1] * sgnpow(ct, e1) * sgnpow(math.sin(a), e2),
                                         half[2] * sgnpow(st, e1))))
            rows.append(row)
        for s in range(segs):
            s1 = (s + 1) % segs
            bm.faces.new([bottom, rows[0][s1], rows[0][s]])
            bm.faces.new([top, rows[-1][s], rows[-1][s1]])
        for i in range(len(rows) - 1):
            for s in range(segs):
                s1 = (s + 1) % segs
                bm.faces.new([rows[i][s], rows[i][s1], rows[i + 1][s1], rows[i + 1][s]])
        if deform:
            for v in bm.verts:
                v.co = deform(v.co)
        faces = list(bm.faces)

        def uvf(l, f):
            co = l.vert.co
            return math.atan2(co.y, co.x) * max(half[0], half[1]), (co.z + half[2]) / (2 * half[2] + 1e-9)
        self.paint(faces, surf or P['steel'], uvf, part=pt)
        if sharp is not None:
            self.sharpen(faces, sharp)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def tube(self, pts, radii, surf=None, segs=10, caps=True, M=Matrix(), sharp=None, flat=1.0, twist=0.0):
        """Smooth tube along a polyline with parallel-transport frames. radii: float or per point.
        flat < 1 squashes the section (blades, straps); a radius of 0 at an end makes a point."""
        pts = [Vector(p) for p in pts]
        if len(pts) < 2:
            return []
        if isinstance(radii, (int, float)):
            radii = [radii] * len(pts)
        pt = _Part()
        bm = pt.bm
        tangents = []
        for i in range(len(pts)):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            tangents.append((b - a).normalized())
        t0 = tangents[0]
        up = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
        nrm = t0.cross(up).normalized()
        frames = []
        for i, t in enumerate(tangents):
            if i > 0:
                prev = tangents[i - 1]
                ax = prev.cross(t)
                if ax.length > 1e-8:
                    nrm = (Quaternion(ax.normalized(), prev.angle(t)) @ nrm).normalized()
            frames.append((nrm.copy(), t.cross(nrm).normalized()))
        acc_len = [0.0]
        for i in range(1, len(pts)):
            acc_len.append(acc_len[-1] + (pts[i] - pts[i - 1]).length)
        rings = []
        vmap = {}
        for i, p in enumerate(pts):
            n, b = frames[i]
            if radii[i] < 1e-5:
                v = bm.verts.new(p)
                vmap[v] = (acc_len[i], 0.5)
                rings.append([v] * segs)
                continue
            ring = []
            for s in range(segs):
                a = 2 * math.pi * s / segs + twist * i
                v = bm.verts.new(p + n * (math.cos(a) * radii[i]) + b * (math.sin(a) * radii[i] * flat))
                vmap[v] = (acc_len[i], s / segs)
                ring.append(v)
            rings.append(ring)
        for i in range(len(pts) - 1):
            for s in range(segs):
                s1 = (s + 1) % segs
                q = [rings[i][s], rings[i][s1], rings[i + 1][s1], rings[i + 1][s]]
                out = []
                for v in q:
                    if v not in out:
                        out.append(v)
                if len(out) >= 3:
                    bm.faces.new(out)
        if caps:
            if radii[0] >= 1e-5:
                bm.faces.new(list(reversed(rings[0])))
            if radii[-1] >= 1e-5:
                bm.faces.new(rings[-1])
        faces = list(bm.faces)
        self.paint(faces, surf or P['steel'], lambda l, f: vmap.get(l.vert, (0.0, 0.5)), part=pt)
        if sharp is not None:
            self.sharpen(faces, sharp)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def loft(self, sections, surf=None, cap0=True, cap1=True, M=Matrix(), sharp=None, closed=True):
        """sections: list of rings (lists of Vector with equal counts). Ring i is joined to ring i + 1."""
        pt = _Part()
        bm = pt.bm
        rings = [[bm.verts.new(Vector(p)) for p in sec] for sec in sections]
        n = len(rings[0])
        vmap = {}
        for i, ring in enumerate(rings):
            for s, v in enumerate(ring):
                vmap[v] = (s / n * 2.0, i / max(1, len(rings) - 1))
        for i in range(len(rings) - 1):
            for s in range(n if closed else n - 1):
                s1 = (s + 1) % n
                bm.faces.new([rings[i][s], rings[i][s1], rings[i + 1][s1], rings[i + 1][s]])
        if closed and cap0:
            bm.faces.new(list(reversed(rings[0])))
        if closed and cap1:
            bm.faces.new(rings[-1])
        faces = list(bm.faces)
        self.paint(faces, surf or P['steel'], lambda l, f: vmap.get(l.vert, (0.5, 0.5)), part=pt)
        if sharp is not None:
            self.sharpen(faces, sharp)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def poly(self, coords, faces_idx, surf=None, uv=None, M=Matrix(), sharp=30, smooth=True):
        pt = _Part()
        vs = [pt.bm.verts.new(Vector(c)) for c in coords]
        for fi in faces_idx:
            try:
                pt.bm.faces.new([vs[i] for i in fi])
            except ValueError:
                pass
        faces = list(pt.bm.faces)
        self.paint(faces, surf or P['steel'], uv, sharp=sharp, smooth=smooth, part=pt)
        self.transform(faces, M, pt)
        return self._commit(pt)

    def plank(self, a, b, width, thick, surf=None, up=(0, 0, 1), bevel=0.012, roll=0.0):
        """Board along a -> b, 'width' across, 'thick' along up."""
        a, b = Vector(a), Vector(b)
        d = b - a
        x = d.normalized()
        y = Vector(up).cross(x)
        if y.length < 1e-6:
            y = Vector((0, 1, 0)).cross(x)
        y.normalize()
        z = x.cross(y).normalized()
        R = Matrix((x, y, z)).transposed().to_4x4()
        M = Matrix.Translation((a + b) / 2) @ R @ Matrix.Rotation(roll, 4, 'X')
        return self.box((d.length, width, thick), M, surf or P['plank'], bevel=bevel, segs=2)

    def subsurf_cage(self, cage_fn, levels=2, M=Matrix(), sharp=None):
        """cage_fn(acc) builds a low cage into a temporary Acc (painted). Catmull-Clark subdivision (attributes
        interpolated), then appended here."""
        tmp = Acc('_cage', self.atlas, self.default_mat, self.box_tile)
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
        pt = _Part()
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

    # ---------------------------------------------------------------- output
    def build(self, name=None):
        name = name or self.name
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for key in self.mats:
            me.materials.append(get_material(key))
        me['tw_built'] = 'Toxic Wetlands pass'
        return me


# ------------------------------------------------------------------------------------------- materials

MAT_DEFS = {
    # name: (unity base, texture file (in textures/), world uv, tiling, roughness, extra)
    'TW_Trim':      dict(base='toon', tex='T_Trim_Wetlands_BaseMap_2K.png'),
    'TW_Character': dict(base='actor', tex='T_Character_Wetlands_BaseMap_1K.png'),
    'TW_Rock':      dict(base='toon', tex='T_Rock_Wetlands_BaseMap_1K.png'),
    'TW_Organic':   dict(base='toon', tex='T_Organic_Wetlands_BaseMap_1K.png'),
    'TW_GroundMud': dict(base='ground', tex='T_Ground_Wetlands_BaseMap_2K.png', world_uv=1.0 / 36.0),
    'TW_RoadMud':   dict(base='road', tex='T_Road_Wetlands_BaseMap_1Kx2K.png', tiling=(1.0, 0.5), color=(0.9, 0.89, 0.85, 1.0)),
    'TW_Water':     dict(base='water', tex=None, alpha=0.78),
    'TW_Plain':     dict(base='toon', tex=None),
}

TEX_DIR = None  # set by the build script


def get_material(key):
    key = key or 'TW_Plain'
    m = bpy.data.materials.get(key)
    if m is not None:
        return m
    d = MAT_DEFS.get(key, MAT_DEFS['TW_Plain'])
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    m['unity_shader'] = 'RoadGame/RiverWater' if d['base'] == 'water' else 'RoadGame/Toon'
    m['unity_base_color'] = list(d.get('color', (1.0, 1.0, 1.0, 1.0)))
    m['tw_unity_base'] = d['base']
    if d.get('world_uv'):
        m['unity_world_uv'] = d['world_uv']
    if d.get('tiling'):
        m['unity_base_map_tiling'] = list(d['tiling'])
    if d.get('alpha'):
        m['tw_alpha'] = d['alpha']
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
    uvp = nt.nodes.new('ShaderNodeUVMap'); uvp.uv_map = 'Unity_MaterialParams'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uvp.outputs['UV'], sep.inputs[0])
    # gloss -> roughness (1 - 0.85 gloss), metal -> metallic
    rough = nt.nodes.new('ShaderNodeMath'); rough.operation = 'MULTIPLY_ADD'
    rough.inputs[1].default_value = -0.85; rough.inputs[2].default_value = 0.92
    nt.links.new(sep.outputs['X'], rough.inputs[0])
    nt.links.new(rough.outputs[0], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs['Y'], bsdf.inputs['Metallic'])
    # self-lit: (1 - alpha) -> emission strength (water: alpha is the toxicity -> a soft glow)
    emk = nt.nodes.new('ShaderNodeMath'); emk.operation = 'MULTIPLY'
    if d['base'] == 'water':
        emk.inputs[1].default_value = 0.9
        nt.links.new(vc.outputs['Alpha'], emk.inputs[0])
    else:
        em = nt.nodes.new('ShaderNodeMath'); em.operation = 'SUBTRACT'; em.inputs[0].default_value = 1.0
        nt.links.new(vc.outputs['Alpha'], em.inputs[1])
        emk.inputs[1].default_value = 2.2
        nt.links.new(em.outputs[0], emk.inputs[0])
    nt.links.new(emk.outputs[0], bsdf.inputs['Emission Strength'])
    col_out = vc.outputs['Color']
    if d.get('tex') and TEX_DIR:
        import os
        path = os.path.join(TEX_DIR, d['tex'])
        img = bpy.data.images.get(d['tex'])
        if img is None and os.path.exists(path):
            img = bpy.data.images.load(path)
            img.name = d['tex']
        if img is not None:
            m['unity_base_map'] = 'textures/' + d['tex']
            tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Linear'
            if d.get('world_uv'):
                geo = nt.nodes.new('ShaderNodeNewGeometry')
                sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; sc.inputs[3].default_value = d['world_uv']
                nt.links.new(geo.outputs['Position'], sc.inputs[0])
                nt.links.new(sc.outputs[0], tex.inputs['Vector'])
            else:
                uv0 = nt.nodes.new('ShaderNodeUVMap'); uv0.uv_map = 'UVMap'
                if d.get('tiling'):
                    mp = nt.nodes.new('ShaderNodeVectorMath'); mp.operation = 'MULTIPLY'
                    mp.inputs[1].default_value = (d['tiling'][0], d['tiling'][1], 1.0)
                    nt.links.new(uv0.outputs['UV'], mp.inputs[0])
                    nt.links.new(mp.outputs[0], tex.inputs['Vector'])
                else:
                    nt.links.new(uv0.outputs['UV'], tex.inputs['Vector'])
            mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            nt.links.new(vc.outputs['Color'], mul.inputs['A'])
            nt.links.new(tex.outputs['Color'], mul.inputs['B'])
            col_out = mul.outputs['Result']
    nt.links.new(col_out, bsdf.inputs['Base Color'])
    nt.links.new(col_out, bsdf.inputs['Emission Color'])
    if d['base'] == 'water':
        # Blender preview of RoadGame/SwampWater: darker body, matte floating algae from a noise field
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.09
        nz.inputs['Detail'].default_value = 3.0; nz.inputs['Roughness'].default_value = 0.55
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.58; ramp.color_ramp.elements[1].position = 0.66
        nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
        dark = nt.nodes.new('ShaderNodeMix'); dark.data_type = 'RGBA'; dark.blend_type = 'MULTIPLY'
        dark.inputs['Factor'].default_value = 1.0; dark.inputs['B'].default_value = (0.62, 0.66, 0.55, 1.0)
        nt.links.new(vc.outputs['Color'], dark.inputs['A'])
        scum = nt.nodes.new('ShaderNodeMix'); scum.data_type = 'RGBA'
        scum.inputs['B'].default_value = (0.20, 0.27, 0.06, 1.0)
        nt.links.new(ramp.outputs['Color'], scum.inputs['Factor'])
        nt.links.new(dark.outputs['Result'], scum.inputs['A'])
        nt.links.new(scum.outputs['Result'], bsdf.inputs['Base Color'])
        nt.links.new(scum.outputs['Result'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Roughness'].default_value = 0.32
        bsdf.inputs['Specular IOR Level'].default_value = 0.3
        lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = d.get('alpha', 0.75); mr.inputs['To Max'].default_value = 0.95
        nt.links.new(lw.outputs['Facing'], mr.inputs['Value'])
        nt.links.new(mr.outputs['Result'], bsdf.inputs['Alpha'])
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m


# ------------------------------------------------------------------------------------------- objects

def ensure_collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def new_object(name, mesh, coll, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), props=None):
    o = bpy.data.objects.new(name, mesh)
    coll.objects.link(o)
    if parent is not None:
        o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale
    o['editing_zone'] = 1
    o['tw_stage'] = 'new in the Toxic Wetlands pass'
    if props:
        for k, v in props.items():
            o[k] = v
    return o


def swap_mesh(o, new_mesh, note='rebuilt in the Toxic Wetlands pass'):
    old = o.data
    o.data = new_mesh
    # v10 objects carry object-linked material slots; the rebuilt mesh brings its own materials
    for slot in o.material_slots:
        slot.link = 'DATA'
    if len(o.material_slots) != len(new_mesh.materials):
        o.data = new_mesh
    for k in ('unity_id', 'unity_mesh_id'):
        if old is not None and k in old:
            new_mesh['tw_replaces_' + k] = old[k]
    o['tw_stage'] = note
    return o


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def rng(seed):
    return random.Random(seed)


def smooth_noise3(p, seed=0, freq=1.0):
    """Cheap smooth 3D value noise in [-1, 1] using mathutils.noise (Perlin)."""
    from mathutils import noise
    return noise.noise(Vector((p[0] * freq + seed * 17.13, p[1] * freq - seed * 5.71, p[2] * freq + seed * 3.37)))


def lod_copy(mesh, ratio, name):
    """Quadric-collapse copy of a mesh (attributes interpolated by Blender's Decimate)."""
    ob = bpy.data.objects.new('_lod_tmp', mesh)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new('dec', 'DECIMATE')
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    out.name = name
    for m in mesh.materials:
        if m.name not in [x.name for x in out.materials]:
            pass
    bpy.data.objects.remove(ob)
    return out
