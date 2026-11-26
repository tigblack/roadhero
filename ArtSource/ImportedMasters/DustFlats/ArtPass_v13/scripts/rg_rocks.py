"""Stylized faceted, layered rock generator (Scarbound terracotta).

A rock is built in a local frame: footprint ellipse half-extents (hx, hy), height hz, base at z = 0.
  1. convex hull of jittered rings -> big flat planes, asymmetric silhouette
  2. split into 1-3 strata slabs along a (slightly tilted) bedding plane; upper slabs shrink -> ledges
  3. chipped corners (planar cuts), optional through-crack (two halves pulled apart)
  4. chamfer (bevel) on hard edges for soft broad highlights
  5. vertex colours: per-rock tone, alternating strata tone, sand dust on up-facing planes,
     darker contact near the ground, lighter worn chamfers, dark crack faces
Face kinds (int layer 'kind'): 0 surface, 1 strata cap/ledge, 2 crack face, 3 chamfer, 4 chip
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import rg_lib as L

ROCK_BASE = (0.50, 0.205, 0.112)
ROCK_TONES = [(0.54, 0.215, 0.135), (0.58, 0.245, 0.15), (0.50, 0.195, 0.125), (0.56, 0.26, 0.17), (0.60, 0.225, 0.14), (0.52, 0.23, 0.16)]
SAND_DUST = (0.70, 0.46, 0.27)


def _ring(r, n, rx, ry, z, kmin, kmax, zj=0.0, a0=None):
    a0 = r.uniform(0, 2 * math.pi) if a0 is None else a0
    out = []
    for i in range(n):
        a = a0 + 2 * math.pi * i / n + r.uniform(-0.6, 0.6) * math.pi / n
        k = r.uniform(kmin, kmax)
        out.append(Vector((math.cos(a) * rx * k, math.sin(a) * ry * k, z + r.uniform(-zj, zj))))
    return out


def rock_points(r, hx, hy, hz, style):
    pts = []
    small = max(hx, hy) < 1.2
    pts += _ring(r, r.randint(5, 7) if not small else 5, hx, hy, -0.18 * min(1.0, hz), 0.80, 0.97)
    if style == 'spire':
        pts += _ring(r, r.randint(5, 7), hx * 0.92, hy * 0.92, hz * r.uniform(0.3, 0.45), 0.85, 1.0, hz * 0.08)
        pts += _ring(r, r.randint(5, 6), hx * 0.66, hy * 0.66, hz * r.uniform(0.62, 0.78), 0.8, 1.0, hz * 0.06)
        pts += _ring(r, r.randint(4, 5), hx * 0.48, hy * 0.48, hz * r.uniform(0.92, 1.0), 0.7, 1.0, hz * 0.03)
    elif style == 'slab':
        pts += _ring(r, r.randint(6, 8), hx, hy, hz * r.uniform(0.35, 0.55), 0.9, 1.0, hz * 0.1)
        pts += _ring(r, r.randint(5, 7), hx * 0.86, hy * 0.86, hz * r.uniform(0.9, 1.0), 0.78, 1.0, hz * 0.03)
    elif style == 'block':
        pts += _ring(r, r.randint(6, 8), hx, hy, hz * r.uniform(0.45, 0.65), 0.9, 1.0, hz * 0.1)
        pts += _ring(r, r.randint(5, 7), hx * 0.86, hy * 0.86, hz * r.uniform(0.9, 1.0), 0.78, 1.0, hz * 0.03)
    else:  # 'round' boulder, still faceted
        pts += _ring(r, r.randint(6, 8), hx, hy, hz * r.uniform(0.3, 0.5), 0.88, 1.0, hz * 0.12)
        pts += _ring(r, r.randint(5, 6), hx * 0.78, hy * 0.78, hz * r.uniform(0.72, 0.86), 0.72, 1.0, hz * 0.06)
        pts += _ring(r, 4, hx * 0.42, hy * 0.42, hz * r.uniform(0.95, 1.0), 0.6, 1.0, hz * 0.03)
    return pts


def _kind_layer(bm):
    return bm.faces.layers.int.get('kind') or bm.faces.layers.int.new('kind')


def _bisect_keep(bm, co, no, keep_positive, kind_cap=1):
    """Cut bm with plane; keep the positive (along no) or negative side; cap the hole. Returns cap faces."""
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=no,
                           clear_outer=not keep_positive, clear_inner=keep_positive)
    edges = [e for e in bm.edges if e.is_boundary]
    caps = []
    if edges:
        res = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        caps = res['faces']
        kl = _kind_layer(bm)
        for f in caps:
            f[kl] = kind_cap
    return caps


def _hull_part(pts):
    p = L.Part()
    p.hull(pts)
    bmesh.ops.dissolve_limit(p.bm, angle_limit=math.radians(6.0), use_dissolve_boundaries=False,
                             verts=list(p.bm.verts), edges=list(p.bm.edges), delimit=set())
    bmesh.ops.recalc_face_normals(p.bm, faces=list(p.bm.faces))
    _kind_layer(p.bm)
    return p


def _xform(bm, M, verts=None):
    bmesh.ops.transform(bm, matrix=M, verts=list(verts if verts is not None else bm.verts))


def make_rock(seed, hx, hy, hz, style='round', strata=None, tilt=(0.0, 0.0), crack=None, tone=None,
              bevel=None, chips=None, dust=1.0, uv_tile=6.0, detail=1.0):
    """Returns a Part (local frame, base at z=0, footprint within the hx/hy ellipse)."""
    r = random.Random(seed)
    pts = rock_points(r, hx, hy, hz, style)
    size = max(hx, hy, hz)
    if strata is None:
        strata = 1 if hz < 1.0 else (2 if hz < 2.8 else r.choice([2, 3, 3]))
    nrm = Vector((math.sin(tilt[0]) * math.cos(tilt[1]), math.sin(tilt[0]) * math.sin(tilt[1]), math.cos(tilt[0]))).normalized()
    cuts = sorted(r.uniform(lo, hi) * hz for lo, hi in ((0.32, 0.5), (0.6, 0.78))[:strata - 1])
    if crack is None:
        crack = (hx * hy > 6.0 and hz > 1.2 and r.random() < 0.4)
    crack_plane = None
    if crack:
        ca = r.uniform(0, math.pi)
        cn = Vector((math.cos(ca), math.sin(ca), r.uniform(-0.15, 0.15))).normalized()
        cp = Vector((r.uniform(-0.25, 0.25) * hx, r.uniform(-0.25, 0.25) * hy, 0))
        crack_plane = (cp, cn, r.uniform(0.09, 0.17) * min(1.5, size / 4), r.uniform(1.5, 4.0))
    out = L.Part()
    tone = tone or r.choice(ROCK_TONES)
    shrink_acc_x = shrink_acc_y = 1.0
    off_acc = Vector((0, 0, 0))
    for si in range(strata):
        halves = [None] if crack_plane is None or (si == 0 and strata > 2 and r.random() < 0.5) else [True, False]
        sx = 1.0 if si == 0 else r.uniform(0.84, 0.96)
        sy = 1.0 if si == 0 else r.uniform(0.84, 0.96)
        shrink_acc_x = sx * (shrink_acc_x if si > 0 else 1.0)
        shrink_acc_y = sy * (shrink_acc_y if si > 0 else 1.0)
        if si > 0:
            ang = r.uniform(0, 2 * math.pi)
            off_acc += Vector((math.cos(ang) * (1 - sx) * hx * 0.8, math.sin(ang) * (1 - sy) * hy * 0.8, 0))
        yaw = r.uniform(-0.06, 0.06) if si > 0 else 0.0
        layer_tone = (1.0, 0.91, 1.06, 0.95)[si % 4] * r.uniform(0.97, 1.03)
        for half in halves:
            p = _hull_part(pts)
            bm = p.bm
            if si > 0:
                _bisect_keep(bm, Vector((0, 0, cuts[si - 1])) , nrm, True)
            if si < strata - 1:
                _bisect_keep(bm, Vector((0, 0, cuts[si])), nrm, False)
            if half is not None:
                cp, cn, gap, ang = crack_plane
                _bisect_keep(bm, cp, cn, half, kind_cap=2)
            if len(bm.faces) < 4:
                p.free(); continue
            # chips: planar cuts at a couple of upper corners
            nch = chips if chips is not None else (r.randint(1, 3) if size > 1.5 else r.randint(0, 1))
            if si == strata - 1 or r.random() < 0.3:
                c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
                for k in range(nch):
                    vs = sorted(bm.verts, key=lambda v: -(v.co.z + r.uniform(0, hz * 0.4)))
                    if not vs:
                        break
                    v = vs[r.randint(0, min(3, len(vs) - 1))]
                    d = (v.co - c); d.z *= 0.6
                    if d.length < 1e-3:
                        continue
                    n = (d.normalized() + Vector((r.uniform(-.3, .3), r.uniform(-.3, .3), 0.35))).normalized()
                    depth = r.uniform(0.10, 0.22) * min(hx, hy, max(hz, 0.5))
                    _bisect_keep(bm, v.co - n * depth, n, False, kind_cap=4)
                    if len(bm.verts) < 6:
                        break
            # pull crack halves apart, tilt the smaller one
            if half is not None:
                cp, cn, gap, ang = crack_plane
                sgn = 1 if half else -1
                M = Matrix.Translation(cn * (gap * 0.5 * sgn))
                if half:
                    pivot = cp + cn * 0.0
                    axis = cn.cross(Vector((0, 0, 1)))
                    if axis.length > 1e-3:
                        M = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(ang) * sgn * 0.5, 4, axis.normalized()) @ Matrix.Translation(-pivot) @ M
                _xform(bm, M)
            # strata shrink / offset / yaw (about rock axis)
            if si > 0:
                zc = cuts[si - 1]
                M = (Matrix.Translation(off_acc) @ Matrix.Translation((0, 0, zc)) @ Matrix.Rotation(yaw, 4, 'Z') @
                     Matrix.Diagonal((shrink_acc_x, shrink_acc_y, 1.0, 1.0)) @ Matrix.Translation((0, 0, -zc)))
                _xform(bm, M)
            # bevel hard edges only
            kl = _kind_layer(bm)
            bv = bevel if bevel is not None else min(0.16, max(0.025, 0.018 * size)) * detail
            hard = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].normal.dot(e.link_faces[1].normal) < math.cos(math.radians(22))]
            if hard and bv > 0:
                try:
                    res = bmesh.ops.bevel(bm, geom=hard, offset=bv, offset_type='OFFSET', segments=1, profile=0.5,
                                          affect='EDGES', clamp_overlap=True)
                    for f in res['faces']:
                        f[kl] = 3
                except Exception:
                    pass
            bm.normal_update()
            # paint
            sd = SAND_DUST
            def fn(co, no, f, _tone=tone, _lt=layer_tone, _kl=kl):
                k = f[_kl]
                c = tuple(x * _lt for x in _tone)
                nz = no.z
                if k == 2:
                    c = tuple(x * 0.55 for x in _tone)
                else:
                    # up-facing planes and ledges catch blown sand
                    t = L.smoothstep(0.45, 0.92, nz) * (0.62 if k in (0, 1, 4) else 0.4) * dust
                    c = L.mix(c, sd, t)
                    if k == 3:
                        c = tuple(min(1.0, x * 1.12) for x in c)
                    if k == 4:
                        c = tuple(min(1.0, x * 1.07) for x in c)
                # darker towards the ground contact, faint dust right at the base
                g = L.smoothstep(-0.1, min(1.2, hz * 0.45), co.z)
                c = tuple(x * (0.80 + 0.20 * g) for x in c)
                if co.z < 0.35:
                    c = L.mix(c, sd, 0.22 * (1 - co.z / 0.35) * dust)
                # slight top-light warm gradient
                c = tuple(x * (0.97 + 0.06 * min(1.0, co.z / max(hz, 0.1))) for x in c)
                return (c[0], c[1], c[2], 1.0, 0.0, 0.0)
            faces = list(bm.faces)
            p.paint_fn(faces, fn)
            p.uv_box(faces, uv_tile, offset=(r.random(), r.random()))
            # merge into out
            arr = p.arrays()
            _append_arrays(out, arr)
            p.free()
    return out


def _append_arrays(part, arr):
    """Append baked arrays into another Part's bmesh (keeps loop data)."""
    bm = part.bm
    vs = [bm.verts.new(c) for c in arr['co']]
    li = 0
    for fi, n in enumerate(arr['flen']):
        idx = arr['lv'][li:li + n]
        try:
            f = bm.faces.new([vs[i] for i in idx])
        except ValueError:
            li += n; continue
        f[part.fmat] = int(arr['mat'][fi])
        for k, l in enumerate(f.loops):
            l[part.lc] = arr['col'][li + k]; l[part.luv].uv = arr['uv'][li + k]; l[part.lp].uv = arr['prm'][li + k]
        li += n


def scree_piece(seed, size):
    r = random.Random(seed)
    hx = size * r.uniform(0.8, 1.2); hy = size * r.uniform(0.6, 1.0); hz = size * r.uniform(0.45, 0.8)
    return make_rock(seed, hx, hy, hz, style=r.choice(['round', 'slab', 'block']), strata=1, crack=False,
                     chips=r.randint(0, 1), bevel=max(0.02, 0.06 * size), uv_tile=3.0)


def sand_drift_arrays(seed, length, width, height, ground_col_fn, M, segs_u=10, segs_v=6):
    """Low wind-blown sand mound (elliptic), coloured from the ground below so the rim is seamless.
    Built directly in object-local space via matrix M (local mound frame -> object local)."""
    r = random.Random(seed)
    p = L.Part(); bm = p.bm
    grid = []
    for j in range(segs_v + 1):
        row = []
        for i in range(segs_u + 1):
            u = -1 + 2 * i / segs_u; v = -1 + 2 * j / segs_v
            rr = math.sqrt(u * u + v * v)
            # elliptic mask with asymmetric (wind) profile: steeper on +u side
            prof = max(0.0, 1 - min(1.0, rr)) ** 1.6
            skew = 1.0 + 0.35 * u
            h = height * prof * skew * (0.85 + 0.3 * r.random() * prof)
            x = u * length * 0.5 * (1 + 0.08 * math.sin(v * 3 + seed)); y = v * width * 0.5
            z = h - 0.03
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(segs_v):
        for i in range(segs_u):
            bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
    bm.normal_update()
    faces = list(bm.faces)
    def fn(co, no, f):
        w = M @ co
        g = ground_col_fn(w.x, w.y)
        hk = max(0.0, co.z) / max(height, 1e-3)
        c = L.mix(g, (g[0] * 1.10, g[1] * 1.10, g[2] * 1.06), hk)
        return (c[0], c[1], c[2], 1.0, 0.0, 0.0)
    p.paint_fn(faces, fn)
    return p
