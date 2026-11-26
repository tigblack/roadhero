"""v13 hard-surface rounding: rebuild a built mesh component by component.

Per welded component (a box, a beam, a post, a plank, a cylinder, ...):
  * box-like (OBB fit, volume >= 88 % of the box)      -> rounded box, multi-segment bevel (arc profile); radius
                                                           sized from the smallest dimension and the object role;
                                                           edges resting on the ground are kept tight (no gap);
  * prism-like (n-gon cylinder, n <= 20 sides)         -> true cylinder with 16-48 segments and rounded rims;
  * thin flat pieces (decals, signs, sheets < 6 mm)    -> unchanged;
  * anything else                                      -> bmesh bevel of edges sharper than 35 deg (2-4 segments,
                                                           clamped), i.e. the shape is kept, corners are rounded.
Attributes (Color, UVMap, Unity_MaterialParams, material index) are transferred per new face from the original
face with the closest normal (and position): colour/params copied, UVs by the source face's affine UV map, clamped
to the source face's trim-strip V range."""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L

ROLE = {   # role -> (radius factor of the smallest dimension, max radius, min radius)
    'structure': (0.30, 0.32, 0.015),
    'detail': (0.24, 0.08, 0.006),
    'prop': (0.24, 0.06, 0.005),
    'board': (0.30, 0.03, 0.004),
}


def _arrays(me):
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    ls = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', ls)
    lt = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt)
    mi = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    col = np.zeros(len(me.loops) * 4); me.color_attributes['Color'].data.foreach_get('color', col); col = col.reshape(-1, 4)
    uv = np.zeros(len(me.loops) * 2); me.uv_layers['UVMap'].data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    pr = np.zeros(len(me.loops) * 2); me.uv_layers['Unity_MaterialParams'].data.foreach_get('uv', pr); pr = pr.reshape(-1, 2)
    return dict(co=co, lv=lv, ls=ls, lt=lt, mi=mi, col=col, uv=uv, pr=pr)


def _components(A, weld=0.00002):
    co = A['co']
    key = np.round(co / weld).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    parent = np.arange(inv.max() + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for f in range(len(A['ls'])):
        vs = inv[A['lv'][A['ls'][f]:A['ls'][f] + A['lt'][f]]]
        r0 = find(vs[0])
        for v in vs[1:]:
            r1 = find(v)
            if r1 != r0:
                parent[r1] = r0
    froot = np.array([find(inv[A['lv'][A['ls'][f]]]) for f in range(len(A['ls']))])
    comps = {}
    for f, r in enumerate(froot):
        comps.setdefault(r, []).append(f)
    return list(comps.values())


class Face:
    __slots__ = ('n', 'c', 'area', 'col', 'pr', 'mi', 'uvA', 'vmin', 'vmax', 'pts', 'ccol')


def _face_info(A, f):
    ls, lt = A['ls'][f], A['lt'][f]
    li = np.arange(ls, ls + lt)
    P = A['co'][A['lv'][li]]
    n = np.zeros(3)
    for i in range(lt):
        n += np.cross(P[i] - P[0], P[(i + 1) % lt] - P[0])
    a = np.linalg.norm(n)
    F = Face()
    F.n = n / a if a > 1e-12 else np.array((0, 0, 1.0)); F.area = a * 0.5
    F.c = P.mean(0); F.pts = P
    F.col = A['col'][li].mean(0); F.pr = A['pr'][li].mean(0); F.mi = int(A['mi'][f]); F.ccol = A['col'][li]
    UV = A['uv'][li]
    # affine UV map: uv = [p, 1] @ M (with an extra constraint: moving along the normal keeps the uv)
    Pa = np.vstack([P, P + F.n]); UVa = np.vstack([UV, UV])
    Hm = np.c_[Pa, np.ones(len(Pa))]
    M, *_ = np.linalg.lstsq(Hm, UVa, rcond=None)
    F.uvA = M; F.vmin = UV[:, 1].min(); F.vmax = UV[:, 1].max()
    return F


def _obb(P, faces):
    """Axes from the face normals (largest area first), extents, centre."""
    fs = sorted(faces, key=lambda F: -F.area)
    a1 = fs[0].n
    a2 = None
    for F in fs[1:]:
        if abs(F.n.dot(a1)) < 0.2:
            v = F.n - a1 * F.n.dot(a1); v /= np.linalg.norm(v); a2 = v; break
    if a2 is None:
        t = np.array((1.0, 0, 0)) if abs(a1[0]) < 0.9 else np.array((0, 1.0, 0))
        a2 = t - a1 * t.dot(a1); a2 /= np.linalg.norm(a2)
    a3 = np.cross(a1, a2)
    R = np.stack([a1, a2, a3], 1)
    L_ = P @ R
    mn = L_.min(0); mx = L_.max(0)
    return R, (mn + mx) / 2, (mx - mn)


def _volume(A, faces_idx):
    v = 0.0
    for f in faces_idx:
        ls, lt = A['ls'][f], A['lt'][f]
        P = A['co'][A['lv'][ls:ls + lt]]
        for i in range(1, lt - 1):
            v += np.dot(P[0], np.cross(P[i], P[i + 1]))
    return abs(v) / 6.0


def _prism_axis(faces, P):
    """Detect an n-gon prism: an axis with >= 5 side faces perpendicular to it and two caps."""
    fs = sorted(faces, key=lambda F: -F.area)
    for cap in fs[:4]:
        ax = cap.n
        side = [F for F in faces if abs(F.n.dot(ax)) < 0.08]
        caps = [F for F in faces if abs(F.n.dot(ax)) > 0.92]
        if len(side) >= 5 and len(side) + len(caps) >= len(faces) * 0.9:
            ns = np.array([F.n for F in side])
            # side normals must spread around the axis (not just 4 directions = box)
            ang = np.unique(np.round(np.degrees(np.arctan2(ns @ np.cross(ax, _perp(ax)), ns @ _perp(ax))) / 3.0))
            if len(ang) >= 5:
                # regular n-gon only: every vertex at (almost) the same distance from the axis
                Q = P - P.mean(0)
                rad = np.linalg.norm(Q - np.outer(Q @ ax, ax), axis=1)
                if rad.mean() > 1e-6 and rad.std() / rad.mean() < 0.07:
                    return ax, side, caps
    return None


def _perp(a):
    t = np.array((1.0, 0, 0)) if abs(a[0]) < 0.9 else np.array((0, 1.0, 0))
    v = t - a * t.dot(a)
    return v / np.linalg.norm(v)


def _transfer(p, new_faces, src, prefer_pos=0.15):
    """Paint new bmesh faces from the closest-normal source face."""
    if not src:
        return
    N = np.array([F.n for F in src]); C = np.array([F.c for F in src])
    for f in new_faces:
        if not f.is_valid:
            continue
        n = np.array(f.normal[:]); c = np.array(f.calc_center_median()[:])
        sc = N @ n - prefer_pos * np.linalg.norm(C - c, axis=1) / (1.0 + np.linalg.norm(C - c, axis=1).max())
        F = src[int(np.argmax(sc))]
        f[p.fmat] = F.mi
        for l in f.loops:
            q = np.array(l.vert.co[:])
            uv = np.r_[q, 1.0] @ F.uvA
            if F.vmax - F.vmin < 0.2:          # trim strip: stay inside it
                uv[1] = min(max(uv[1], F.vmin), F.vmax)
            l[p.luv].uv = (float(uv[0]), float(uv[1]))
            d = np.linalg.norm(F.pts - q, axis=1)
            w = 1.0 / np.maximum(d, 1e-3) ** 2
            cc = (F.ccol * w[:, None]).sum(0) / w.sum()
            l[p.lc] = tuple(float(x) for x in cc)
            l[p.lp].uv = (float(F.pr[0]), float(F.pr[1]))


def _copy_faces(p, A, faces_idx):
    """Copy original faces unchanged into the part."""
    bm = p.bm
    vmap = {}
    for f in faces_idx:
        ls, lt = A['ls'][f], A['lt'][f]
        vs = []
        for li in range(ls, ls + lt):
            vi = A['lv'][li]
            if vi not in vmap:
                vmap[vi] = bm.verts.new(A['co'][vi])
            vs.append(vmap[vi])
        try:
            nf = bm.faces.new(vs)
        except ValueError:
            continue
        nf[p.fmat] = int(A['mi'][f])
        for k, l in enumerate(nf.loops):
            li = ls + k
            l[p.lc] = tuple(A['col'][li]); l[p.luv].uv = tuple(A['uv'][li]); l[p.lp].uv = tuple(A['pr'][li])


def rounded_box(p, size, R, ctr, radius, segs, ground_z=None):
    """Box (size along the local axes R columns) with arc-profile bevels; bottom edges left tight if grounded."""
    M = Matrix(((R[0, 0], R[0, 1], R[0, 2], ctr[0]), (R[1, 0], R[1, 1], R[1, 2], ctr[1]),
                (R[2, 0], R[2, 1], R[2, 2], ctr[2]), (0, 0, 0, 1)))
    Sm = Matrix.Diagonal((max(size[0], 1e-4), max(size[1], 1e-4), max(size[2], 1e-4), 1.0))
    res = bmesh.ops.create_cube(p.bm, size=1.0, matrix=M @ Sm)
    verts = res['verts']
    p.bm.normal_update()
    edges = list({e for v in verts for e in v.link_edges})
    if ground_z is not None:
        keep = []
        for e in edges:
            if all(abs(v.co.z - ground_z) < 0.02 for v in e.verts):
                continue
            keep.append(e)
        edges = keep
    r = min(radius, 0.49 * min(size))
    out = set(f for v in verts for f in v.link_faces)
    if r > 1e-4 and edges:
        bv = bmesh.ops.bevel(p.bm, geom=edges, offset=r, offset_type='OFFSET', segments=segs, profile=0.5,
                             affect='EDGES', clamp_overlap=True, miter_outer='ARC', harden_normals=False)
        out |= set(bv['faces'])
        out |= set(f for v in bv['verts'] for f in v.link_faces)
    p.bm.normal_update()
    return [f for f in out if f.is_valid]


def round_mesh(me, role='structure', role_fn=None, ground_z=0.02, cyl_min=8, cyl_max=40, angle=50.0, keep_fn=None,
               world=None, keep_below=0.0, special=None):
    """Returns (Part, stats). role_fn(component_extents, centre) -> role name overrides 'role'.
    keep_fn(P) -> True keeps a component unchanged. world: object matrix (for the ground test)."""
    A = _arrays(me)
    comps = _components(A)
    p = L.Part()
    st = dict(box=0, cyl=0, bevel=0, kept=0)
    Wm = np.array(world) if world is not None else np.eye(4)
    for faces_idx in comps:
        vidx = np.unique(np.concatenate([A['lv'][A['ls'][f]:A['ls'][f] + A['lt'][f]] for f in faces_idx]))
        P = A['co'][vidx]
        Pw = P @ Wm[:3, :3].T + Wm[:3, 3]
        ext = P.max(0) - P.min(0)
        if keep_fn is not None and keep_fn(Pw):
            _copy_faces(p, A, faces_idx); st['kept'] += 1; continue
        if special is not None:
            srcs = [_face_info(A, f) for f in faces_idx]
            if special(p, P, srcs):
                st.setdefault('special', 0); st['special'] += 1
                continue
        src = [_face_info(A, f) for f in faces_idx]
        R, ctr_l, size = _obb(P, src)
        smallest = float(np.min(size))
        rl = role_fn(size, P.mean(0)) if role_fn else role
        fac, rmax, rmin = ROLE[rl]
        if smallest < 0.006 or len(faces_idx) < 4:
            _copy_faces(p, A, faces_idx); st['kept'] += 1; continue
        vol = _volume(A, faces_idx)
        boxvol = float(np.prod(size))
        ctr = R @ ctr_l
        gz = None
        zmin_w = Pw[:, 2].min()
        if abs(zmin_w) < ground_z and abs(R[2, :]).max() > 0.98:
            gz = float(P[:, 2].min())
        radius = max(rmin, min(rmax, fac * smallest))
        segs = 1 if radius < 0.018 else (2 if radius < 0.06 else (3 if radius < 0.15 else 4))
        if radius < keep_below and len(faces_idx) >= 12:
            _copy_faces(p, A, faces_idx); st['kept'] += 1; continue
        if boxvol > 1e-9 and vol / boxvol > 0.88 and len(faces_idx) <= 60:
            nf = rounded_box(p, size, R, ctr, radius, segs, gz)
            _transfer(p, nf, src); st['box'] += 1
            continue
        pr = _prism_axis(src, P)
        if pr is not None and len(pr[1]) <= 20:
            ax, side, caps = pr
            u = _perp(ax); w = np.cross(ax, u)
            h_ = P @ ax
            rr = np.sqrt(((P - np.outer(P @ ax, ax)) - (np.mean(P - np.outer(P @ ax, ax), 0))) ** 2).sum(1)
            centre = np.mean(P - np.outer(P @ ax, ax), 0) + ax * (h_.min() + h_.max()) / 2
            rad = float(np.sqrt((np.linalg.norm((P - np.outer(P @ ax, ax)) - np.mean(P - np.outer(P @ ax, ax), 0), axis=1) ** 2).mean()))
            ns_ = np.array([F.n for F in side])
            nside = len(np.unique(np.round(np.degrees(np.arctan2(ns_ @ w, ns_ @ u)) / 3.0)))
            nside = max(5, nside)
            rad *= math.sqrt(nside / (2 * math.pi) * math.sin(2 * math.pi / nside))   # equal-area circle
            hgt = float(h_.max() - h_.min())
            segs_c = 8 if rad < 0.03 else (12 if rad < 0.08 else (16 if rad < 0.2 else (24 if rad < 0.5 else 32)))
            segs_c = int(min(cyl_max, segs_c))
            Mc = Matrix(((u[0], w[0], ax[0], centre[0]), (u[1], w[1], ax[1], centre[1]), (u[2], w[2], ax[2], centre[2]), (0, 0, 0, 1)))
            rim = min(0.45 * rad, 0.35 * hgt, max(rmin, min(rmax, fac * 2 * rad * 0.5)))
            if rad < 0.05:
                rim = 0.0
            f_, bf = p.cyl(rad, hgt, Mc, segs=segs_c, caps=len(caps) > 0, bevel=rim if len(caps) else 0.0, bsegs=2 if rad < 0.15 else 3)
            p.bm.normal_update()
            _transfer(p, f_ + bf, src); st['cyl'] += 1
            continue
        # generic: bevel the sharp edges of the original shape
        tmp = L.Part()
        _copy_faces(tmp, A, faces_idx)
        bm = tmp.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bm.normal_update()
        sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(angle)]
        newf = []
        if sharp:
            try:
                bv = bmesh.ops.bevel(bm, geom=sharp, offset=min(radius, 0.3 * smallest), offset_type='OFFSET', segments=segs,
                                     profile=0.5, affect='EDGES', clamp_overlap=True, miter_outer='ARC')
                newf = list(bv['faces'])
            except Exception:
                newf = []
        bm.normal_update()
        _transfer(tmp, newf, src, prefer_pos=0.6)
        a = tmp.arrays(); tmp.free()
        from rg_rocks import _append_arrays
        _append_arrays(p, a)
        st['bevel'] += 1
    return p, st


def rebuild_object_mesh(ob, role='structure', role_fn=None, note='v13: rounded', keep_fn=None, sharp_angle=40.0, **kw):
    """Round every component of ob's mesh; swaps the datablock for all users (instancing kept)."""
    me = ob.data
    mats = [s.material for s in ob.material_slots]
    old = sum(len(q.vertices) - 2 for q in me.polygons)
    p, st = round_mesh(me, role, role_fn, keep_fn=keep_fn, world=ob.matrix_world, **kw)
    acc = L.MeshAccumulator(); acc.add_part(p); p.free()
    new = acc.build(me.name + '__v13', materials=mats, sharp_angle=sharp_angle, weighted=True)
    nt = sum(len(q.vertices) - 2 for q in new.polygons)
    users, _ = L.swap_mesh(me, new, note=note + f" (boxes {st['box']}, cylinders {st['cyl']}, bevelled {st['bevel']}, kept {st['kept']})")
    for o in users:
        L.set_object_materials(o, mats)
    return dict(old=old, new=nt, **st, users=len(users))
