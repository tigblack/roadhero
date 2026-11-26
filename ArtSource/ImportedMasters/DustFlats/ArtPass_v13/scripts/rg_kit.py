"""Parametric construction kit on top of rg_lib.Part (boards, beams, sheets, pipes, bolts...).
All pieces are mapped onto the 2K trim sheet strips (see tex_gen.TRIM_STRIPS) and tinted by vertex colour."""
import math, random
from mathutils import Vector, Matrix
import rg_lib as L

STRIP = {
    'plain': (0.0, 0.0625), 'grime': (0.0625, 0.125), 'board_a': (0.125, 0.25), 'board_b': (0.25, 0.375),
    'corrugated': (0.375, 0.5), 'panel': (0.5, 0.625), 'rustplate': (0.625, 0.75), 'concrete': (0.75, 0.875),
    'hazard': (0.875, 0.9375), 'diamond': (0.9375, 1.0),
}
# small inset so bilinear filtering never bleeds between strips
def _strip(name):
    v0, v1 = STRIP[name]
    pad = 0.004
    return v0 + pad, v1 - pad


def frame(a, b, up=Vector((0, 0, 1))):
    """Matrix whose local X runs from a to b (centre at midpoint), Z as close to 'up' as possible."""
    a = Vector(a); b = Vector(b)
    x = (b - a); length = x.length
    x = x.normalized() if length > 1e-9 else Vector((1, 0, 0))
    up = Vector(up)
    if abs(x.dot(up.normalized())) > 0.98:
        up = Vector((0, 1, 0)) if abs(x.z) > 0.9 else Vector((0, 0, 1))
    y = up.cross(x).normalized(); z = x.cross(y).normalized()
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = (a + b) / 2
    return M, length


def finish(p, faces, bevel_faces, s, strip='plain', m_per_u=2.0, wear=None):
    p.paint(faces, s)
    if bevel_faces and wear is not None:
        p.paint(bevel_faces, wear)
    v0, v1 = _strip(strip)
    if strip == 'plain':
        p.uv_const(faces, (0.5, (v0 + v1) / 2))
    else:
        p.uv_trim(faces, v0, v1, m_per_u, auto=strip not in ANISO)


ANISO = ('corrugated', 'grime')   # patterns that only vary along U keep a fixed metres-per-U


def box(p, size, M, s, strip='plain', bevel=0.0, wear=None, m_per_u=2.0):
    f, bf = p.box(size, M, bevel=bevel)
    finish(p, f, bf, s, strip, m_per_u, wear)
    return f


def beam(p, a, b, w, h, s, strip='board_a', bevel=0.015, up=(0, 0, 1), wear=None, ext=0.0, roll=0.0):
    M, length = frame(a, b, up)
    if roll:
        M = M @ Matrix.Rotation(roll, 4, 'X')
    return box(p, (length + ext, w, h), M, s, strip, bevel, wear)


def board(p, a, b, width, thick, s, strip='board_a', up=(0, 0, 1), bevel=0.008):
    """Plank from a to b; 'up' is the plank's width direction hint (normal = across)."""
    M, length = frame(a, b, up)
    return box(p, (length, thick, width), M, s, strip, bevel)


def cyl_between(p, a, b, r, s, segs=12, strip='plain', r2=None, caps=True, bevel=0.0, m_per_u=1.0):
    a = Vector(a); b = Vector(b); d = b - a
    q = d.normalized().to_track_quat('Z', 'Y')
    M = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4()
    f, bf = p.cyl(r, d.length, M, segs=segs, r2=r2, caps=caps, bevel=bevel)
    p.paint(f, s)
    v0, v1 = _strip(strip)
    if strip == 'plain':
        p.uv_const(f, (0.5, (v0 + v1) / 2))
    else:
        p.uv_trim(f, v0, v1, m_per_u, auto=strip not in ANISO)
    return f


def pipe(p, pts, r, s, segs=10, strip='plain', joints=True):
    pts = [Vector(x) for x in pts]
    for a, b in zip(pts[:-1], pts[1:]):
        cyl_between(p, a, b, r, s, segs, strip)
    if joints:
        for q in pts[1:-1]:
            cyl_between(p, q - Vector((0, 0, r * 0.0)) + Vector((0, 0, -r * 1.25)), q + Vector((0, 0, r * 1.25)),
                        r * 1.25, s, segs, 'plain')


def bolt(p, c, n, r, s, h=0.03, segs=6):
    c = Vector(c); n = Vector(n).normalized()
    return cyl_between(p, c, c + n * h, r, s, segs)


def sheet(p, origin, u, v, thick, s, strip='corrugated', m_per_u=2.0, bevel=0.0):
    """Flat panel spanning origin + [0..1]u + [0..1]v with thickness along u x v."""
    origin = Vector(origin); u = Vector(u); v = Vector(v)
    n = u.cross(v).normalized()
    x = u.normalized(); y = n.cross(x).normalized()
    M = Matrix((x, y, n)).transposed().to_4x4()
    M.translation = origin + u / 2 + v / 2
    return box(p, (u.length, v.length, thick), M, s, strip, bevel, m_per_u=m_per_u)


def sag_sheet(p, c00, c10, c01, c11, nu, nv, sag, thick, s, strip='plain', seed=0, m_per_u=2.0):
    """Closed thin slab over a bilinear patch, sagging along its normal (canvas, tarps)."""
    r = random.Random(seed)
    c00, c10, c01, c11 = map(Vector, (c00, c10, c01, c11))
    n = (c10 - c00).cross(c01 - c00).normalized()
    bm = p.bm
    top = []; bot = []
    for j in range(nv + 1):
        rt = []; rb = []
        for i in range(nu + 1):
            u = i / nu; v = j / nv
            q = c00.lerp(c10, u).lerp(c01.lerp(c11, u), v)
            w = math.sin(math.pi * u) * math.sin(math.pi * v)
            q = q - n * (sag * w + r.uniform(-0.15, 0.15) * sag * w)
            rt.append(bm.verts.new(q + n * thick * 0.5)); rb.append(bm.verts.new(q - n * thick * 0.5))
        top.append(rt); bot.append(rb)
    faces = []
    for j in range(nv):
        for i in range(nu):
            faces.append(bm.faces.new([top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]]))
            faces.append(bm.faces.new([bot[j][i], bot[j + 1][i], bot[j + 1][i + 1], bot[j][i + 1]]))
    # rims
    ring = [(0, i) for i in range(nu)] + [(j, nu) for j in range(nv)] + [(nv, i) for i in range(nu, 0, -1)] + [(j, 0) for j in range(nv, 0, -1)]
    nxt = ring[1:] + ring[:1]
    for (j0, i0), (j1, i1) in zip(ring, nxt):
        try:
            faces.append(bm.faces.new([top[j0][i0], bot[j0][i0], bot[j1][i1], top[j1][i1]]))
        except ValueError:
            pass
    bm.normal_update()
    p.paint(faces, s)
    v0, v1 = _strip(strip)
    if strip == 'plain':
        p.uv_const(faces, (0.5, (v0 + v1) / 2))
    else:
        p.uv_trim(faces, v0, v1, m_per_u)
    return faces


def prism(p, pts2d, z0, z1, M, s, strip='plain', bevel=0.0):
    """Extruded polygon (pts in local XY) from z0 to z1, transformed by M."""
    bm = p.bm
    vb = [bm.verts.new(M @ Vector((x, y, z0))) for x, y in pts2d]
    vt = [bm.verts.new(M @ Vector((x, y, z1))) for x, y in pts2d]
    faces = [bm.faces.new(list(reversed(vb))), bm.faces.new(vt)]
    n = len(pts2d)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new([vb[i], vb[j], vt[j], vt[i]]))
    bm.normal_update()
    bf = []
    if bevel > 0:
        import bmesh
        edges = list({e for f in faces for e in f.edges})
        res = bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=1, profile=0.5,
                              affect='EDGES', clamp_overlap=True)
        bf = list(res['faces'])
        faces = list({f for v in vb + vt + list(res['verts']) if v.is_valid for f in v.link_faces})
    finish(p, faces, bf, s, strip)
    return faces


def tint(kind, k=1.0, alpha=1.0, jitter=0.0, r=None):
    if jitter and r is not None:
        k = k * (1 + r.uniform(-jitter, jitter))
    return L.surf(kind, k, alpha)


def lathe(p, profile, segs, M, paint_fn, strip='plain', cap_bottom=True, cap_top=True, disp=None):
    """Surface of revolution around local Z. profile = [(r, z, tag), ...] bottom->top.
    paint_fn(tag, ring_index, seg_index) -> surf tuple. disp(i_ring, j_seg) -> radial offset."""
    bm = p.bm
    rings = []
    for i, (r, z, tag) in enumerate(profile):
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            rr = r + (disp(i, j) if disp else 0.0)
            ring.append(bm.verts.new(M @ Vector((math.cos(a) * rr, math.sin(a) * rr, z))))
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        tag = profile[i][2]
        for j in range(segs):
            k = (j + 1) % segs
            a, b, c, d = rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]
            if a.co == d.co and b.co == c.co:
                continue
            try:
                f = bm.faces.new([a, b, c, d])
            except ValueError:
                continue
            s = paint_fn(tag, i, j)
            p.paint([f], s); faces.append(f)
    if cap_bottom and profile[0][0] > 1e-4:
        f = bm.faces.new(list(reversed(rings[0]))); p.paint([f], paint_fn(profile[0][2], 0, 0)); faces.append(f)
    if cap_top and profile[-1][0] > 1e-4:
        f = bm.faces.new(rings[-1]); p.paint([f], paint_fn(profile[-1][2], len(profile) - 1, 0)); faces.append(f)
    bm.normal_update()
    v0, v1 = _strip(strip)
    if strip == 'plain':
        p.uv_const(faces, (0.5, (v0 + v1) / 2))
    else:
        p.uv_trim(faces, v0, v1, 1.0)
    return faces
