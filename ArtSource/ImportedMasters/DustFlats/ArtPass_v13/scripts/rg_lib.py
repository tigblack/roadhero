"""Core toolkit for the DustFlats v11 art pass (runs inside Blender).

Pipeline contract kept for every rebuilt or new mesh (RoadGame/Toon in Unity):
  * 'Color'                 CORNER / FLOAT_COLOR, linear RGB = painted colour, A < 1 = self-light amount
  * 'UVMap'                 UV0 for BaseMap (trim sheet / tiling texture)
  * 'Unity_MaterialParams'  UV1: x = gloss, y = metal (NOT a lightmap)
  * smooth shading with sharp edges by angle + face-area weighted custom normals
Parts are built as small bmeshes (bevel/convex-hull/etc. ops), then baked to numpy arrays and
appended to a MeshAccumulator with a transform. The accumulator writes one Blender mesh.
"""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

# ----------------------------------------------------------------------------------------------
# Surface palette: linear RGB, gloss, metal (conventions match the existing v10 vertex params:
# stone/sand/wood ~0 gloss, rubber 0.16, paint 0.45-0.55/0.1-0.15, rusty metal 0.3/0.25,
# steel 0.45-0.55/0.55-0.75, chrome 0.85/1)
# ----------------------------------------------------------------------------------------------
PAL = {
    'sand':          ((0.60, 0.37, 0.18), 0.00, 0.00),
    'sand_light':    ((0.70, 0.46, 0.25), 0.00, 0.00),
    'sand_packed':   ((0.52, 0.32, 0.17), 0.00, 0.00),
    'rock':          ((0.50, 0.21, 0.115), 0.00, 0.00),
    'rock_light':    ((0.62, 0.31, 0.17), 0.00, 0.00),
    'rock_dark':     ((0.34, 0.13, 0.075), 0.00, 0.00),
    'wood':          ((0.40, 0.25, 0.13), 0.10, 0.00),
    'wood_light':    ((0.55, 0.38, 0.22), 0.10, 0.00),
    'wood_dark':     ((0.21, 0.12, 0.065), 0.08, 0.00),
    'wood_grey':     ((0.43, 0.37, 0.31), 0.08, 0.00),
    'paint_red':     ((0.56, 0.09, 0.035), 0.50, 0.15),
    'paint_orange':  ((0.66, 0.22, 0.06), 0.48, 0.15),
    'paint_teal':    ((0.09, 0.30, 0.31), 0.50, 0.15),
    'paint_cream':   ((0.80, 0.69, 0.50), 0.45, 0.10),
    'paint_yellow':  ((0.95, 0.60, 0.04), 0.45, 0.10),
    'paint_olive':   ((0.27, 0.27, 0.15), 0.45, 0.12),
    'paint_grey':    ((0.36, 0.36, 0.37), 0.45, 0.15),
    'steel':         ((0.46, 0.45, 0.43), 0.55, 0.75),
    'steel_dark':    ((0.15, 0.15, 0.16), 0.45, 0.55),
    'galvanized':    ((0.52, 0.53, 0.54), 0.45, 0.60),
    'rust':          ((0.30, 0.11, 0.04), 0.16, 0.25),
    'rust_light':    ((0.48, 0.20, 0.07), 0.18, 0.22),
    'rubber':        ((0.040, 0.037, 0.035), 0.16, 0.00),
    'concrete':      ((0.42, 0.38, 0.34), 0.06, 0.00),
    'concrete_dark': ((0.25, 0.23, 0.22), 0.05, 0.00),
    'canvas':        ((0.68, 0.58, 0.41), 0.02, 0.00),
    'canvas_dark':   ((0.45, 0.37, 0.25), 0.02, 0.00),
    'black':         ((0.030, 0.030, 0.032), 0.40, 0.10),
    'bone':          ((0.80, 0.74, 0.62), 0.10, 0.00),
    'glass':         ((0.16, 0.26, 0.32), 0.85, 0.00),
    'cactus':        ((0.10, 0.30, 0.07), 0.05, 0.00),
}

def surf(kind, tint=1.0, alpha=1.0):
    """Return (r,g,b,a,gloss,metal) for a palette entry; tint scales brightness (float or rgb)."""
    rgb, g, m = PAL[kind] if isinstance(kind, str) else kind
    if isinstance(tint, (int, float)):
        rgb = tuple(c * tint for c in rgb)
    else:
        rgb = tuple(c * t for c, t in zip(rgb, tint))
    return (rgb[0], rgb[1], rgb[2], alpha, g, m)

def mix(a, b, t):
    return tuple(x * (1 - t) + y * t for x, y in zip(a, b))

def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)

# ----------------------------------------------------------------------------------------------
# Part: a small bmesh with the three loop layers
# ----------------------------------------------------------------------------------------------
class Part:
    def __init__(self):
        self.bm = bmesh.new()
        L = self.bm.loops.layers
        self.lc = L.float_color.new('Color')
        self.luv = L.uv.new('UVMap')
        self.lp = L.uv.new('Unity_MaterialParams')
        self.fmat = self.bm.faces.layers.int.new('mat')

    # -- creation ------------------------------------------------------------------------
    def _faces_of(self, verts):
        fs = set()
        for v in verts:
            fs.update(v.link_faces)
        return list(fs)

    def box(self, size, M=None, bevel=0.0, segs=1, profile=0.5):
        """Axis box of 'size' centered at origin, transformed by M. Returns (faces, bevel_faces)."""
        M = M or Matrix()
        S = Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M @ S)
        verts = r['verts']
        bf = []
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            b = min(bevel, 0.49 * min(size))
            res = bmesh.ops.bevel(self.bm, geom=edges + list(verts), offset=b, offset_type='OFFSET',
                                  segments=segs, profile=profile, affect='EDGES', clamp_overlap=True)
            bf = list(res['faces'])
            verts = list(set(verts) | set(res['verts']))
        faces = self._faces_of([v for v in verts if v.is_valid])
        return faces, bf

    def cyl(self, r, h, M=None, segs=16, r2=None, caps=True, bevel=0.0, bsegs=1):
        """Cylinder along local Z, centred at origin. Returns (faces, bevel_faces)."""
        M = M or Matrix()
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segs,
                                    radius1=r, radius2=(r if r2 is None else r2), depth=h, matrix=M)
        verts = res['verts']
        bf = []
        if bevel > 0 and caps:
            # bevel only the rim edges (edges between cap and side)
            edges = []
            for e in {e for v in verts for e in v.link_edges}:
                if len(e.link_faces) == 2:
                    n0, n1 = e.link_faces[0].normal, e.link_faces[1].normal
                    if n0.dot(n1) < 0.5:
                        edges.append(e)
            if edges:
                rr = bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=bsegs,
                                     profile=0.5, affect='EDGES', clamp_overlap=True)
                bf = list(rr['faces']); verts = list(set(verts) | set(rr['verts']))
        return self._faces_of([v for v in verts if v.is_valid]), bf

    def hull(self, pts):
        vs = [self.bm.verts.new(p) for p in pts]
        res = bmesh.ops.convex_hull(self.bm, input=vs, use_existing_faces=False)
        # remove interior / unused verts
        unused = [v for v in res.get('geom_unused', []) if isinstance(v, bmesh.types.BMVert)]
        interior = [v for v in res.get('geom_interior', []) if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.delete(self.bm, geom=list(set(unused) | set(interior)), context='VERTS')
        faces = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace) and f.is_valid]
        return faces

    def poly(self, coords, faces_idx):
        vs = [self.bm.verts.new(c) for c in coords]
        out = []
        for fi in faces_idx:
            try:
                out.append(self.bm.faces.new([vs[i] for i in fi]))
            except ValueError:
                pass
        return out

    def all_faces(self):
        return [f for f in self.bm.faces]

    # -- painting ------------------------------------------------------------------------
    def paint(self, faces, s, mat=None):
        """s = (r,g,b,a,gloss,metal)."""
        col = (s[0], s[1], s[2], s[3]); prm = (s[4], s[5])
        for f in faces:
            if not f.is_valid:
                continue
            if mat is not None:
                f[self.fmat] = mat
            for l in f.loops:
                l[self.lc] = col; l[self.lp].uv = prm

    def paint_fn(self, faces, fn, mat=None):
        """fn(co: Vector, normal: Vector, face) -> (r,g,b,a,gloss,metal) evaluated per corner."""
        for f in faces:
            if not f.is_valid:
                continue
            if mat is not None:
                f[self.fmat] = mat
            for l in f.loops:
                s = fn(l.vert.co, f.normal, f)
                l[self.lc] = (s[0], s[1], s[2], s[3]); l[self.lp].uv = (s[4], s[5])

    def shade(self, faces, fn):
        """Multiply existing colours by fn(co, normal) -> scalar or rgb."""
        for f in faces:
            if not f.is_valid:
                continue
            for l in f.loops:
                k = fn(l.vert.co, f.normal)
                c = l[self.lc]
                if isinstance(k, (int, float)):
                    l[self.lc] = (c[0] * k, c[1] * k, c[2] * k, c[3])
                else:
                    l[self.lc] = (c[0] * k[0], c[1] * k[1], c[2] * k[2], c[3])

    # -- UVs -----------------------------------------------------------------------------
    def uv_box(self, faces, tile=1.0, offset=(0.0, 0.0), M=None):
        """Box projection in (optionally transformed) metres; 'tile' metres per UV unit."""
        for f in faces:
            if not f.is_valid:
                continue
            n = f.normal if M is None else (M.to_3x3() @ f.normal)
            ax = max(range(3), key=lambda i: abs(n[i]))
            for l in f.loops:
                p = l.vert.co if M is None else M @ l.vert.co
                if ax == 2:
                    u, v = p.x, p.y
                elif ax == 1:
                    u, v = p.x, p.z
                else:
                    u, v = p.y, p.z
                l[self.luv].uv = (u / tile + offset[0], v / tile + offset[1])

    def uv_trim(self, faces, v0, v1, metres_per_u=2.0, across=None, u_offset=0.0, auto=False):
        """Trim-sheet mapping: each face's long axis runs along U (tiling), its short axis is squeezed
        into the strip [v0, v1]. 'across' = world size mapped onto the full strip height (defaults to face size)."""
        for f in faces:
            if not f.is_valid or len(f.loops) < 3:
                continue
            n = f.normal
            # longest edge direction as U
            le = max(f.edges, key=lambda e: e.calc_length())
            ud = (le.verts[1].co - le.verts[0].co).normalized()
            if abs(ud.z) > 0.7 and abs(n.z) < 0.5:   # vertical boards: keep U horizontal-ish if face is wide
                pass
            vd = n.cross(ud).normalized()
            pts = [l.vert.co for l in f.loops]
            us = [p.dot(ud) for p in pts]; vs = [p.dot(vd) for p in pts]
            vmin, vmax = min(vs), max(vs)
            span = across or max(1e-4, vmax - vmin)
            mpu = span / max(1e-6, (v1 - v0)) if auto else metres_per_u   # square texels on the strip
            for l, u, v in zip(f.loops, us, vs):
                t = (v - vmin) / span
                l[self.luv].uv = (u / mpu + u_offset, v0 + (v1 - v0) * min(1.0, max(0.0, t)))

    def uv_const(self, faces, uv):
        for f in faces:
            for l in f.loops:
                l[self.luv].uv = uv

    def free(self):
        self.bm.free()

    # -- bake ----------------------------------------------------------------------------
    def arrays(self):
        bm = self.bm
        bm.verts.index_update()
        co = np.array([v.co[:] for v in bm.verts], np.float64).reshape(-1, 3)
        fl = []; lv = []; col = []; uv = []; prm = []; mats = []
        for f in bm.faces:
            fl.append(len(f.loops)); mats.append(f[self.fmat])
            for l in f.loops:
                lv.append(l.vert.index); col.append(l[self.lc][:]); uv.append(l[self.luv].uv[:]); prm.append(l[self.lp].uv[:])
        return dict(co=co, flen=np.array(fl, np.int32), lv=np.array(lv, np.int32),
                    col=np.array(col, np.float32).reshape(-1, 4), uv=np.array(uv, np.float32).reshape(-1, 2),
                    prm=np.array(prm, np.float32).reshape(-1, 2), mat=np.array(mats, np.int32))


class MeshAccumulator:
    """Collects baked part arrays (with transforms) and writes a single Blender mesh."""
    def __init__(self):
        self.chunks = []

    def add(self, arr, M=None, uv_world=None):
        co = arr['co']
        if M is not None:
            A = np.array(M)
            co = co @ A[:3, :3].T + A[:3, 3]
        a = dict(arr); a['co'] = co
        self.chunks.append(a)

    def add_part(self, part, M=None):
        self.add(part.arrays(), M)

    def empty(self):
        return not self.chunks

    def build(self, name, materials=None, sharp_angle=40.0, weighted=True, merge_dist=0.0, drop_degenerate=True):
        co = []; fl = []; lv = []; col = []; uv = []; prm = []; mat = []
        off = 0
        for c in self.chunks:
            co.append(c['co']); fl.append(c['flen']); lv.append(c['lv'] + off); col.append(c['col'])
            uv.append(c['uv']); prm.append(c['prm']); mat.append(c['mat']); off += len(c['co'])
        co = np.concatenate(co); fl = np.concatenate(fl); lv = np.concatenate(lv)
        col = np.concatenate(col); uv = np.concatenate(uv); prm = np.concatenate(prm); mat = np.concatenate(mat)
        if drop_degenerate and len(fl):
            ls_ = np.concatenate([[0], np.cumsum(fl)[:-1]])
            area = np.zeros(len(fl))
            for k in range(1, int(fl.max()) - 1):
                m = fl > k + 1
                a0 = co[lv[ls_[m]]]; a1 = co[lv[ls_[m] + k]]; a2 = co[lv[ls_[m] + k + 1]]
                area[m] += 0.5 * np.linalg.norm(np.cross(a1 - a0, a2 - a0), axis=1)
            keep = area > 1e-9
            if not keep.all():
                lk = np.repeat(keep, fl)
                lv = lv[lk]; col = col[lk]; uv = uv[lk]; prm = prm[lk]; fl = fl[keep]; mat = mat[keep]
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(co)); me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        me.loops.add(len(lv)); me.loops.foreach_set('vertex_index', lv)
        me.polygons.add(len(fl))
        ls = np.concatenate([[0], np.cumsum(fl)[:-1]]).astype(np.int32)
        me.polygons.foreach_set('loop_start', ls)
        me.polygons.foreach_set('material_index', mat)
        me.update(calc_edges=True)
        uvl = me.uv_layers.new(name='UVMap'); uvl.data.foreach_set('uv', uv.ravel())
        pl = me.uv_layers.new(name='Unity_MaterialParams'); pl.data.foreach_set('uv', prm.ravel())
        me.uv_layers.active = uvl; uvl.active_render = True
        ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER'); ca.data.foreach_set('color', col.ravel())
        me.color_attributes.active_color = ca
        me.color_attributes.render_color_index = 0
        try:
            me.color_attributes.active_color_name = 'Color'
        except Exception:
            pass
        if materials:
            for m in materials:
                me.materials.append(m)
        me.validate(clean_customdata=False)
        if merge_dist > 0:
            bm = bmesh.new(); bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
            bm.to_mesh(me); bm.free()
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        if weighted:
            me = weighted_normals(me)
        return me


def weighted_normals(me, weight=50):
    """Bake face-area weighted custom normals (keeps sharp edges) into a new mesh; returns it."""
    sc = bpy.context.scene
    ob = bpy.data.objects.new('__wn_tmp', me)
    sc.collection.objects.link(ob)
    mod = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
    mod.mode = 'FACE_AREA'; mod.weight = weight; mod.keep_sharp = True; mod.thresh = 0.01
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    out = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    name = me.name
    bpy.data.objects.remove(ob)
    mats = list(me.materials)
    bpy.data.meshes.remove(me)
    out.name = name
    if not out.materials and mats:
        for m in mats:
            out.materials.append(m)
    return out


# ----------------------------------------------------------------------------------------------
# Scene helpers
# ----------------------------------------------------------------------------------------------
def swap_mesh(old, new, note='rebuilt in v11 art pass'):
    """Replace mesh datablock 'old' by 'new' for every user, keeping name, unity_* props and instancing."""
    name = old.name
    props = {k: old[k] for k in old.keys()}
    users = [o for o in bpy.data.objects if o.type == 'MESH' and o.data == old]
    slot_mats = {o.name: [s.material for s in o.material_slots] for o in users}
    old.name = name + '__v10_replaced'
    new.name = name
    for k, v in props.items():
        new[k] = v
    new['artpass_v11'] = note
    for o in users:
        o.data = new
    bpy.data.meshes.remove(old)
    return users, slot_mats


def set_object_materials(o, mats):
    """Object-linked slots like the v10 importer (slot.link = 'OBJECT')."""
    me = o.data
    while len(me.materials) < len(mats):
        me.materials.append(bpy.data.materials.get('Unassigned — white'))
    for i, m in enumerate(mats):
        s = o.material_slots[i]
        s.link = 'OBJECT'
        s.material = m


def ensure_collection(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        parent.children.link(c)
    return c


def new_object(name, mesh, collection, parent=None, mats=None, zone=0, note='new in v11 art pass', world_matrix=None):
    if name in bpy.data.objects:
        old = bpy.data.objects[name]
        bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, mesh)
    collection.objects.link(o)
    if parent is not None:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    if world_matrix is not None:
        o.matrix_world = world_matrix
    o['editing_zone'] = zone
    o['artpass_v11'] = note
    if mats:
        set_object_materials(o, mats)
    return o


def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
    return mn, mx


def mesh_components(me, weld=0.01):
    """Welded connected components -> list of (Nx3 local coords array, face count)."""
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bm.verts.ensure_lookup_table()
    seen = set(); comps = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]; ids = []; seen.add(v.index)
        while stack:
            x = stack.pop(); ids.append(x.index)
            for e in x.link_edges:
                y = e.other_vert(x)
                if y.index not in seen:
                    seen.add(y.index); stack.append(y)
        comps.append(ids)
    co = np.array([v.co[:] for v in bm.verts]).reshape(-1, 3)
    # average colour per component (from loops)
    lc = bm.loops.layers.float_color.get('Color')
    vcol = np.zeros((len(bm.verts), 4)); cnt = np.zeros(len(bm.verts))
    if lc is not None:
        for f in bm.faces:
            for l in f.loops:
                vcol[l.vert.index] += np.array(l[lc][:]); cnt[l.vert.index] += 1
        vcol /= np.maximum(cnt, 1)[:, None]
    bm.free()
    return [(co[c], vcol[c]) for c in comps]


def pca_frame(pts):
    """Oriented frame of a point cloud with Z kept vertical: returns centre, yaw, half extents (x,y,z), zmin."""
    c2 = pts[:, :2].mean(0)
    d = pts[:, :2] - c2
    cov = d.T @ d / max(1, len(d))
    w, v = np.linalg.eigh(cov)
    ax = v[:, 1]
    yaw = math.atan2(ax[1], ax[0])
    R = np.array([[math.cos(-yaw), -math.sin(-yaw)], [math.sin(-yaw), math.cos(-yaw)]])
    loc = d @ R.T
    mn = loc.min(0); mx = loc.max(0)
    mid = (mn + mx) / 2
    centre_xy = c2 + np.array([[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]) @ mid
    zmin, zmax = pts[:, 2].min(), pts[:, 2].max()
    return (Vector((centre_xy[0], centre_xy[1], zmin)), yaw,
            Vector(((mx - mn)[0] / 2, (mx - mn)[1] / 2, (zmax - zmin))), zmin)


def rng(seed):
    return random.Random(seed)
