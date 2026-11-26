"""Procedural mesh builder for the Scarbound DetailedCar pass (Blender 5.2).

Mirrors the game's C# MeshBuilder idea (per-face palette colour + gloss/metal), but at production density:
uniform multi-segment rounded boxes, filleted lathes, parallel-transport sweeps, lofts and perforated tubes.
Every mesh it builds carries the RoadGame service attributes:
  Color                 FLOAT_COLOR, corner  (linear RGB; alpha < 1 = self-lit, as in RoadToon)
  UVMap                 UV, corner           (metre-scaled parametric UVs, packed later per texture set)
  Unity_MaterialParams  UV, corner           (x = gloss, y = metal)
Faces also carry a surface material (MAT_*), used for the Blender procedural materials and the bakes.
"""
import math
from contextlib import contextmanager

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

TAU = math.tau


# ------------------------------------------------------------------ colour helpers (Unity hex = sRGB)
def s2l(x):
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def l2s(x):
    x = max(0.0, x)
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


def C(h, a=1.0):
    """Unity hex colour -> linear RGBA (what the Color attribute stores)."""
    h = h.lstrip("#")
    return tuple(s2l(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def shade(c, k):
    """Unity's Shade(): multiply the sRGB values."""
    return tuple(s2l(min(1.0, l2s(v) * k)) for v in c[:3]) + (c[3],)


def mixc(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


def glow(c, a=0.35):
    return c[:3] + (a,)


def hash01(k):
    v = math.sin(k * 12.9898 + 78.233) * 43758.5453
    return v - math.floor(v)


# ------------------------------------------------------------------ 2D profile helpers
def fillet(pts, r, n=3):
    """Round the interior corners of a 2D polyline with circular arcs (r may be a list per point)."""
    if len(pts) < 3:
        return list(pts)
    out = [tuple(pts[0])]
    for i in range(1, len(pts) - 1):
        rr = r[i] if isinstance(r, (list, tuple)) else r
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        d0, d1 = p0 - p1, p2 - p1
        l0, l1 = d0.length, d1.length
        if rr <= 0 or l0 < 1e-9 or l1 < 1e-9:
            out.append(tuple(p1))
            continue
        d0 /= l0
        d1 /= l1
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            out.append(tuple(p1))
            continue
        t = min(rr / math.tan(ang / 2), l0 * 0.49, l1 * 0.49)
        rr = t * math.tan(ang / 2)
        a, b = p1 + d0 * t, p1 + d1 * t
        c = p1 + (d0 + d1).normalized() * (rr / math.sin(ang / 2))
        va, vb = a - c, b - c
        th = math.atan2(va.x * vb.y - va.y * vb.x, va.dot(vb))
        for k in range(n + 1):
            q = th * k / n
            cs, sn = math.cos(q), math.sin(q)
            out.append((c.x + va.x * cs - va.y * sn, c.y + va.x * sn + va.y * cs))
    out.append(tuple(pts[-1]))
    return out


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def rrect(w, h, r, n=3):
    """Closed rounded rectangle profile (counter-clockwise), centre at origin."""
    r = min(r, w / 2 * 0.999, h / 2 * 0.999)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, math.pi / 2),
                       (-w / 2 + r, -h / 2 + r, math.pi), (w / 2 - r, -h / 2 + r, 1.5 * math.pi)):
        pts += arc(cx, cy, r, a0, a0 + math.pi / 2, n)
    return pts


def circle(r, n):
    return [(r * math.cos(TAU * k / n), r * math.sin(TAU * k / n)) for k in range(n)]


def resample(pts, step):
    """Resample a 2D/3D polyline at roughly uniform spacing (keeps the end points)."""
    P = [Vector(p) for p in pts]
    L = [0.0]
    for i in range(1, len(P)):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    n = max(1, int(round(L[-1] / step)))
    out = []
    j = 0
    for k in range(n + 1):
        s = L[-1] * k / n
        while j < len(P) - 2 and L[j + 1] < s:
            j += 1
        seg = max(1e-12, L[j + 1] - L[j])
        t = (s - L[j]) / seg
        out.append(tuple(P[j].lerp(P[j + 1], min(1.0, max(0.0, t)))))
    return out


def _res(res):
    """colfn result -> (colour, mat, gm). Accepts a colour tuple or (colour, mat[, gm])."""
    if res is None:
        return None
    if isinstance(res[0], (tuple, list)):
        return res[0], (res[1] if len(res) > 1 else None), (res[2] if len(res) > 2 else None)
    return res, None, None


def frame_from_z(d, up_hint=None):
    """Rotation matrix whose local Z points along d."""
    z = Vector(d).normalized()
    up = Vector(up_hint) if up_hint is not None else Vector((0, 0, 1))
    if abs(z.dot(up.normalized())) > 0.98:
        up = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0))
    x = up.cross(z).normalized()
    y = z.cross(x).normalized()
    return Matrix((x, y, z)).transposed()


# ------------------------------------------------------------------ the builder
class MB:
    def __init__(self, mat="MAT_Metal", gloss=0.5, metal=0.0):
        self.co = []
        self.faces = []
        self.fuv = []
        self.fcol = []
        self.fgm = []
        self.fmat = []
        self.stack = [Matrix.Identity(4)]
        self.cur_mat = mat
        self.gm = (gloss, metal)

    # ---------------- state
    def m(self, mat=None, gloss=None, metal=None):
        if mat is not None:
            self.cur_mat = mat
        if gloss is not None or metal is not None:
            self.gm = (self.gm[0] if gloss is None else gloss, self.gm[1] if metal is None else metal)
        return self

    def push(self, t=(0, 0, 0), r=None, s=None):
        M = Matrix.Translation(Vector(t))
        if r is not None:
            if isinstance(r, Quaternion):
                R = r.to_matrix().to_4x4()
            elif isinstance(r, Matrix):
                R = r.to_4x4() if len(r) == 3 else r
            else:
                R = Euler([math.radians(a) for a in r], "XYZ").to_matrix().to_4x4()
            M = M @ R
        if s is not None:
            if isinstance(s, (int, float)):
                s = (s, s, s)
            M = M @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))
        self.stack.append(self.stack[-1] @ M)
        return self

    def pop(self):
        self.stack.pop()
        return self

    @contextmanager
    def at(self, t=(0, 0, 0), r=None, s=None):
        self.push(t, r, s)
        try:
            yield self
        finally:
            self.pop()

    @property
    def M(self):
        return self.stack[-1]

    # ---------------- raw geometry
    def vs(self, pts):
        M = self.M
        base = len(self.co)
        for p in pts:
            self.co.append(tuple(M @ Vector(p)))
        return list(range(base, base + len(pts)))

    def face(self, idx, uvs=None, col=(1, 1, 1, 1), mat=None, gm=None):
        clean, cuv = [], []
        for k, i in enumerate(idx):
            if clean and clean[-1] == i:
                continue
            clean.append(i)
            cuv.append(uvs[k] if uvs is not None else (0.0, 0.0))
        if len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
            cuv.pop()
        if len(set(clean)) < 3:
            return
        if self.M.determinant() < 0:
            clean.reverse()
            cuv.reverse()
        self.faces.append(tuple(clean))
        self.fuv.append(tuple(cuv))
        self.fcol.append(tuple(col))
        self.fgm.append(gm if gm is not None else self.gm)
        self.fmat.append(mat if mat is not None else self.cur_mat)

    def face_out(self, idx, toward, uvs=None, col=(1, 1, 1, 1), mat=None, gm=None):
        """Add a face, flipping it so its normal points toward world point/dir `toward` (('p', vec) or ('d', vec))."""
        P = [Vector(self.co[i]) for i in idx]
        n = Vector((0, 0, 0))
        for k in range(len(P)):
            a, b = P[k], P[(k + 1) % len(P)]
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        kind, v = toward
        v = self.M @ Vector(v) if kind == "p" else (self.M.to_3x3() @ Vector(v))
        ref = (v - sum(P, Vector()) / len(P)) if kind == "p" else v
        idx = list(idx)
        uvs = list(uvs) if uvs is not None else None
        if n.dot(ref) < 0:
            idx.reverse()
            if uvs:
                uvs.reverse()
        # face() would flip again under a mirrored matrix; compensate
        if self.M.determinant() < 0:
            idx.reverse()
            if uvs:
                uvs.reverse()
        self.face(idx, uvs, col, mat, gm)

    # ---------------- grids / lofts
    def grid(self, P, col=(1, 1, 1, 1), cu=False, cv=False, colfn=None, skip=None, uvscale=1.0, flip=False):
        """P[i][j] rows of points. Quads (i,j)->(i,j+1)->(i+1,j+1)->(i+1,j). Returns the index grid."""
        nu, nv = len(P), len(P[0])
        idx = [self.vs(row) for row in P]
        mid_j, mid_i = nv // 2, nu // 2
        U = [0.0]
        for i in range(1, nu + (1 if cu else 0)):
            U.append(U[-1] + (Vector(P[i % nu][mid_j]) - Vector(P[i - 1][mid_j])).length)
        V = [0.0]
        for j in range(1, nv + (1 if cv else 0)):
            V.append(V[-1] + (Vector(P[mid_i][j % nv]) - Vector(P[mid_i][j - 1])).length)
        for i in range(nu - 1 + (1 if cu else 0)):
            for j in range(nv - 1 + (1 if cv else 0)):
                if skip and skip(i, j):
                    continue
                i1, j1 = (i + 1) % nu, (j + 1) % nv
                q = [idx[i][j], idx[i][j1], idx[i1][j1], idx[i1][j]]
                uv = [(U[i] * uvscale, V[j] * uvscale), (U[i] * uvscale, V[j + 1] * uvscale),
                      (U[i + 1] * uvscale, V[j + 1] * uvscale), (U[i + 1] * uvscale, V[j] * uvscale)]
                if flip:
                    q.reverse()
                    uv.reverse()
                if colfn:
                    res = _res(colfn(i, j))
                    if res is None:
                        continue
                    self.face(q, uv, res[0], res[1], res[2])
                else:
                    self.face(q, uv, col)
        return idx

    def stitch(self, rows, col=(1, 1, 1, 1), cv=True, flip=False, colfn=None):
        """Quads between existing vertex-index rows (same length), e.g. to close a rim between two grids."""
        nu, nv = len(rows), len(rows[0])
        for i in range(nu - 1):
            for j in range(nv - 1 + (1 if cv else 0)):
                j1 = (j + 1) % nv
                q = [rows[i][j], rows[i][j1], rows[i + 1][j1], rows[i + 1][j]]
                if flip:
                    q.reverse()
                c = _res(colfn(i, j)) if colfn else (col, None, None)
                if c is None:
                    continue
                self.face(q, [(j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1)], c[0], c[1], c[2])

    # ---------------- lathe (around local Z)
    def lathe(self, prof, segs, col=(1, 1, 1, 1), a0=0.0, a1=TAU, colfn=None, closed_prof=False):
        """prof: [(r, z), ...]; outward = right-hand side of the profile direction in (r, z)."""
        full = abs((a1 - a0) - TAU) < 1e-9
        na = segs if full else segs + 1
        rings = []
        rmax = max(max(p[0] for p in prof), 1e-4)
        for (r, z) in prof:
            if r < 1e-7:
                rings.append(self.vs([(0, 0, z)]) * na)
            else:
                rings.append(self.vs([(r * math.cos(a0 + (a1 - a0) * k / segs), r * math.sin(a0 + (a1 - a0) * k / segs), z)
                                      for k in range(na)]))
        L = [0.0]
        npf = len(prof)
        for i in range(1, npf + (1 if closed_prof else 0)):
            L.append(L[-1] + math.hypot(prof[i % npf][0] - prof[i - 1][0], prof[i % npf][1] - prof[i - 1][1]))
        circ = rmax * (a1 - a0)
        for i in range(npf - 1 + (1 if closed_prof else 0)):
            c = _res(colfn(i)) if colfn else (col, None, None)
            if c is None:
                continue
            i1 = (i + 1) % npf
            for k in range(segs):
                k1 = (k + 1) % na
                q = [rings[i][k], rings[i][k1], rings[i1][k1], rings[i1][k]]
                u0, u1 = circ * k / segs, circ * (k + 1) / segs
                uv = [(u0, L[i]), (u1, L[i]), (u1, L[i + 1]), (u0, L[i + 1])]
                self.face(q, uv, c[0], c[1], c[2])
        if closed_prof and not full:
            # end caps of a partial revolution of a closed profile (curved blocks, arc segments)
            cc = _res(colfn(0)) if colfn else (col, None, None)
            for k, d in ((0, (math.sin(a0), -math.cos(a0), 0.0)), (na - 1, (-math.sin(a1), math.cos(a1), 0.0))):
                self.face_out([rings[i][k] for i in range(npf)], ("d", d), [(p[0], p[1]) for p in prof], cc[0], cc[1], cc[2])
        return rings

    def prism(self, poly, depth, col=(1, 1, 1, 1), y0=None):
        """Extrude a convex 2D polygon [(x, z)] along local Y (closed solid); y0 = start (default centred)."""
        n = len(poly)
        ya = -depth / 2 if y0 is None else y0
        yb = ya + depth
        A = self.vs([(x, ya, z) for (x, z) in poly])
        B = self.vs([(x, yb, z) for (x, z) in poly])
        cx = sum(p[0] for p in poly) / n
        cz = sum(p[1] for p in poly) / n
        self.face_out(A, ("d", (0, -1, 0)), [(x, z) for (x, z) in poly], col=col)
        self.face_out(B, ("d", (0, 1, 0)), [(x, z) for (x, z) in poly], col=col)
        for k in range(n):
            k1 = (k + 1) % n
            mx, mz = (poly[k][0] + poly[k1][0]) / 2, (poly[k][1] + poly[k1][1]) / 2
            el = math.hypot(poly[k1][0] - poly[k][0], poly[k1][1] - poly[k][1])
            self.face_out([A[k], A[k1], B[k1], B[k]], ("d", (mx - cx, 0, mz - cz)), [(0, 0), (el, 0), (el, depth), (0, depth)], col=col)
        return self

    # ---------------- sweeps
    def frames(self, path, closed=False, up=None):
        P = [Vector(p) for p in path]
        n = len(P)
        T = []
        for i in range(n):
            if closed:
                t = P[(i + 1) % n] - P[i - 1]
            else:
                t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
            T.append(t.normalized())
        up = Vector(up) if up is not None else Vector((0, 0, 1))
        if abs(T[0].dot(up)) > 0.98:
            up = Vector((1, 0, 0)) if abs(T[0].x) < 0.9 else Vector((0, 1, 0))
        N = [(up - T[0] * up.dot(T[0])).normalized()]
        for i in range(1, n):
            v = N[-1] - T[i] * N[-1].dot(T[i])
            if v.length < 1e-8:
                v = N[-1]
            N.append(v.normalized())
        if closed:
            # distribute the residual twist so the loop closes cleanly
            last = N[-1] - T[0] * N[-1].dot(T[0])
            last.normalize()
            ang = math.atan2(T[0].dot(last.cross(N[0])), last.dot(N[0]))
            for i in range(n):
                q = Quaternion(T[i], ang * i / n)
                N[i] = (q @ N[i]).normalized()
        B = [T[i].cross(N[i]).normalized() for i in range(n)]
        return P, T, N, B

    def sweep(self, path, prof, col=(1, 1, 1, 1), closed_path=False, closed_prof=True, caps=True,
              up=None, scale=None, colfn=None, twist=0.0):
        """Sweep a 2D profile [(x, y)] along a 3D path. x maps to the frame normal, y to the binormal."""
        P, T, N, B = self.frames(path, closed_path, up)
        n = len(P)
        rows = []
        for i in range(n):
            s = scale(i / max(1, n - 1)) if scale else 1.0
            sx, sy = (s, s) if not isinstance(s, tuple) else s
            q = Quaternion(T[i], twist * i / max(1, n - 1))
            Ni, Bi = q @ N[i], q @ B[i]
            rows.append([tuple(P[i] + Ni * (x * sx) + Bi * (y * sy)) for (x, y) in prof])
        # orientation: profile counter-clockwise (x->N, y->B) with T forward gives outward normals
        idx = self.grid(rows, col, cu=closed_path, cv=closed_prof, colfn=colfn, flip=False)
        if caps and not closed_path and closed_prof:
            for end, sign in ((0, -1), (n - 1, 1)):
                ring = idx[end]
                cen = self.vs([tuple(sum((Vector(rows[end][k]) for k in range(len(prof))), Vector()) / len(prof))])[0]
                tip = Vector(rows[end][0])
                for k in range(len(ring)):
                    k1 = (k + 1) % len(ring)
                    tri = [cen, ring[k], ring[k1]]
                    self.face_out(tri, ("d", tuple(T[end] * sign)), col=col if not colfn else self.fcol[-1], mat=None if not colfn else self.fmat[-1], gm=None if not colfn else self.fgm[-1])
        return idx

    def tube(self, path, r, segs=16, col=(1, 1, 1, 1), closed=False, caps=True, up=None, scale=None, colfn=None):
        return self.sweep(path, circle(r, segs), col, closed, True, caps, up, scale, colfn)

    # ---------------- solids
    def rbox(self, c, half, r=0.01, m=2, col=(1, 1, 1, 1), rot=None, flat=1, colfn=None):
        """Rounded box with uniform 2*m-segment arcs on every edge (quads only, exact flat faces)."""
        hx, hy, hz = half
        r = max(0.0, min(r, hx * 0.98, hy * 0.98, hz * 0.98))
        if r < 1e-6:
            m = 0

        def coords(h, flat_n):
            inner = h - r
            pts = []
            for k in range(m, 0, -1):
                pts.append(-inner - r * math.tan(math.radians(45.0 * k / m)))
            if inner > 1e-6:
                for k in range(flat_n + 1):
                    pts.append(-inner + 2 * inner * k / flat_n)
            else:
                pts.append(0.0)
            for k in range(1, m + 1):
                pts.append(inner + r * math.tan(math.radians(45.0 * k / m)))
            if m == 0:
                pts = [-h, h] if flat_n == 1 else [-h + 2 * h * k / flat_n for k in range(flat_n + 1)]
            return pts

        fl = flat if isinstance(flat, (list, tuple)) else (flat, flat, flat)
        ax = [coords(hx, fl[0]), coords(hy, fl[1]), coords(hz, fl[2])]
        inner = (hx - r, hy - r, hz - r)
        cache = {}

        def vid(s):
            key = (round(s[0], 7), round(s[1], 7), round(s[2], 7))
            if key in cache:
                return cache[key]
            cc = [max(-inner[i], min(inner[i], s[i])) for i in range(3)]
            d = Vector((s[0] - cc[0], s[1] - cc[1], s[2] - cc[2]))
            p = Vector(cc) + d.normalized() * r if d.length > 1e-9 and r > 0 else Vector(s)
            cache[key] = self.vs([tuple(p)])[0]
            return cache[key]

        # faces: (axis, sign) with (u axis, v axis) so that u x v = outward
        spec = [(0, 1, 1, 2), (0, -1, 2, 1), (1, 1, 2, 0), (1, -1, 0, 2), (2, 1, 0, 1), (2, -1, 1, 0)]
        halfs = (hx, hy, hz)
        self.push(c, rot)
        for (a, sg, ua, va) in spec:
            us, vs_ = ax[ua], ax[va]
            for iu in range(len(us) - 1):
                for iv in range(len(vs_) - 1):
                    q = []
                    uv = []
                    for (du, dv) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        s = [0, 0, 0]
                        s[a] = sg * halfs[a]
                        s[ua] = us[iu + du]
                        s[va] = vs_[iv + dv]
                        q.append(vid(s))
                        uv.append((s[ua], s[va]))
                    cc = _res(colfn(a, sg)) if colfn else (col, None, None)
                    self.face(q, uv, cc[0], cc[1], cc[2])
        self.pop()
        return self

    def cyl(self, a, b, r, segs=24, col=(1, 1, 1, 1), r2=None, caps=True, fillet_r=0.0, fseg=2, up=None):
        """Cylinder/cone between points a and b, optional filleted cap edges."""
        a, b = Vector(a), Vector(b)
        d = b - a
        L = d.length
        r2 = r if r2 is None else r2
        prof = []
        if caps:
            prof.append((0.0, 0.0))
        prof += [(r, 0.0), (r2, L)]
        if caps:
            prof.append((0.0, L))
        if fillet_r > 0 and caps:
            prof = fillet(prof, [0, fillet_r, fillet_r, 0], fseg)
        R = frame_from_z(d, up)
        with self.at(tuple(a), R):
            self.lathe(prof, segs, col)
        return self

    def ellipsoid(self, c, radii, col=(1, 1, 1, 1), nu=24, nv=12, rot=None):
        prof = [(math.sin(math.pi * k / nv), -math.cos(math.pi * k / nv)) for k in range(nv + 1)]
        prof[0] = (0.0, -1.0)
        prof[-1] = (0.0, 1.0)
        with self.at(c, rot, radii):
            self.lathe(prof, nu, col)
        return self

    def disc(self, c, r, segs, col, normal=(0, 0, 1)):
        R = frame_from_z(normal)
        with self.at(c, R):
            ring = self.vs([(r * math.cos(TAU * k / segs), r * math.sin(TAU * k / segs), 0) for k in range(segs)])
            cen = self.vs([(0, 0, 0)])[0]
            for k in range(segs):
                self.face([cen, ring[k], ring[(k + 1) % segs]], [(0, 0), (r * math.cos(TAU * k / segs), r * math.sin(TAU * k / segs)),
                                                                (r * math.cos(TAU * (k + 1) / segs), r * math.sin(TAU * (k + 1) / segs))], col)
        return self

    def perf_tube(self, z0, z1, r_out, t, segs, holes, col, inner_col, zs_extra=(), caps=True):
        """Tube along local Z with real through-holes. holes: [(k0, k1, za, zb)] in angle-index units."""
        zs = sorted(set([z0, z1] + [h[2] for h in holes] + [h[3] for h in holes] + list(zs_extra)))
        r_in = r_out - t

        def ring(r, z):
            return [(r * math.cos(TAU * k / segs), r * math.sin(TAU * k / segs), z) for k in range(segs)]

        O = [self.vs(ring(r_out, z)) for z in zs]
        I = [self.vs(ring(r_in, z)) for z in zs]
        zi = {z: i for i, z in enumerate(zs)}

        def in_hole(i, k):
            for (k0, k1, za, zb) in holes:
                if zi[za] <= i < zi[zb] and k0 <= k < k1:
                    return True
            return False

        circ = r_out * TAU
        for i in range(len(zs) - 1):
            for k in range(segs):
                if in_hole(i, k):
                    continue
                k1 = (k + 1) % segs
                u0, u1 = circ * k / segs, circ * (k + 1) / segs
                self.face([O[i][k], O[i][k1], O[i + 1][k1], O[i + 1][k]], [(u0, zs[i]), (u1, zs[i]), (u1, zs[i + 1]), (u0, zs[i + 1])], col)
                self.face([I[i][k], I[i + 1][k], I[i + 1][k1], I[i][k1]], [(u0, zs[i]), (u0, zs[i + 1]), (u1, zs[i + 1]), (u1, zs[i])], inner_col)
        for (k0, k1, za, zb) in holes:
            ia, ib = zi[za], zi[zb]
            cz = (za + zb) / 2
            cang = TAU * (k0 + k1) / 2 / segs
            rm = (r_out + r_in) / 2
            cen = (rm * math.cos(cang), rm * math.sin(cang), cz)
            edges = ([((ia, k), (ia, k + 1)) for k in range(k0, k1)] if ia > 0 else []) + \
                    ([((ib, k), (ib, k + 1)) for k in range(k0, k1)] if ib < len(zs) - 1 else [])
            edges += [((i, k0), (i + 1, k0)) for i in range(ia, ib)] + [((i, k1), (i + 1, k1)) for i in range(ia, ib)]
            for (p, q) in edges:
                pi_, pk = p
                qi_, qk = q
                quad = [O[pi_][pk % segs], O[qi_][qk % segs], I[qi_][qk % segs], I[pi_][pk % segs]]
                self.face_out(quad, ("p", cen), col=inner_col)
        if caps:
            for i, sgn, cell in ((0, -1, 0), (len(zs) - 1, 1, len(zs) - 2)):
                for k in range(segs):
                    if in_hole(cell, k):
                        continue            # a hole reaching the tube end leaves that end open (no duplicate wall)
                    k1 = (k + 1) % segs
                    self.face_out([O[i][k], O[i][k1], I[i][k1], I[i][k]], ("d", (0, 0, sgn)), col=col)
        return O, I

    # ---------------- output
    def build(self, name, sharp_deg=32.0, mesh=None):
        me = mesh if mesh is not None else bpy.data.meshes.new(name)
        if mesh is not None:
            me.clear_geometry()
        mats = []
        for mname in self.fmat:
            if mname not in mats:
                mats.append(mname)
        used = sorted({i for f in self.faces for i in f})
        if len(used) < len(self.co):
            remap = {old: new for new, old in enumerate(used)}
            co = [self.co[i] for i in used]
            faces = [tuple(remap[i] for i in f) for f in self.faces]
        else:
            co, faces = self.co, self.faces
        me.from_pydata(co, [], faces)
        nf = len(self.faces)
        assert len(me.polygons) == nf, (len(me.polygons), nf)
        me.materials.clear()
        for mname in mats:
            mat = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
            me.materials.append(mat)
        mi = {mname: i for i, mname in enumerate(mats)}
        me.polygons.foreach_set("material_index", np.array([mi[m] for m in self.fmat], np.int32))
        tot = np.array([len(f) for f in self.faces])
        rep = np.repeat(np.arange(nf), tot)
        col = np.array(self.fcol, np.float32)[rep]
        gm = np.array(self.fgm, np.float32)[rep]
        uv = np.array([c for f in self.fuv for c in f], np.float32)
        for a in list(me.color_attributes):
            me.color_attributes.remove(a)
        ca = me.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
        ca.data.foreach_set("color", col.ravel())
        me.color_attributes.active_color = ca
        try:
            me.color_attributes.render_color_index = 0
        except Exception:
            pass
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        u0 = me.uv_layers.new(name="UVMap")
        u0.data.foreach_set("uv", uv.ravel())
        u1 = me.uv_layers.new(name="Unity_MaterialParams")
        u1.data.foreach_set("uv", gm.ravel())
        me.uv_layers.active = u0
        u0.active_render = True
        me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
        if sharp_deg is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_deg))
        me.update()
        return me

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)


def replace_mesh(ob, me, keep_old=True):
    """Give an object new mesh data; materials follow the mesh (slot link DATA)."""
    old = ob.data
    ob.data = me
    for s in ob.material_slots:
        s.link = "DATA"
    if not keep_old and old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def tri_count(ob, evaluated=True):
    if ob.type != "MESH":
        return 0
    if evaluated:
        dg = bpy.context.evaluated_depsgraph_get()
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        me.calc_loop_triangles()
        n = len(me.loop_triangles)
        eo.to_mesh_clear()
        return n
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)
