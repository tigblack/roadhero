"""v13 checks: scene fingerprint (names, parents, collections, unity_* / editing_zone props, transforms, material
slots, mesh users), pipeline attributes, mesh sanity, and the drivable-surface agreement between the visual meshes
and the exact Unity floor heights (mounds, mesa floors, plateau, ramps, kickers, roads on hills)."""
import bpy, math, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ZONE = 'Zone_00_DustFlats + Intro'


def _props(o):
    out = {}
    for k in o.keys():
        if k.startswith('unity_') or k == 'editing_zone':
            v = o[k]
            out[k] = v.to_list() if hasattr(v, 'to_list') else v
    return out


def fingerprint():
    z = bpy.data.collections[ZONE]
    objs = {}
    for o in z.all_objects:
        objs[o.name] = dict(type=o.type, parent=o.parent.name if o.parent else None,
                            cols=sorted(c.name for c in o.users_collection), props=_props(o),
                            M=[round(v, 4) for row in o.matrix_world for v in row],
                            data=o.data.name if o.data else None,
                            slots=[s.material.name if s.material else None for s in o.material_slots],
                            users=o.data.users if o.data is not None and hasattr(o.data, 'users') else 0)
    return objs


def compare(base, now, allow_new_prefix=('AP_', )):
    issues = []
    for n, b in base.items():
        c = now.get(n)
        if c is None:
            issues.append(f'missing object {n}'); continue
        for k in ('type', 'parent', 'props'):
            if b[k] != c[k]:
                issues.append(f'{n}: {k} changed {b[k]} -> {c[k]}')
        if set(b['cols']) - set(c['cols']):
            issues.append(f'{n}: left collections {set(b["cols"]) - set(c["cols"])}')
        if max(abs(x - y) for x, y in zip(b['M'], c['M'])) > 1e-3:
            issues.append(f'{n}: transform changed')
    new = [n for n in now if n not in base]
    return issues, new


def attributes_ok(o):
    me = o.data
    bad = []
    ca = me.color_attributes.get('Color')
    if ca is None or ca.domain != 'CORNER' or ca.data_type != 'FLOAT_COLOR':
        bad.append('Color')
    if 'UVMap' not in me.uv_layers:
        bad.append('UVMap')
    if 'Unity_MaterialParams' not in me.uv_layers:
        bad.append('Unity_MaterialParams')
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    if not np.isfinite(co).all():
        bad.append('nan')
    return bad


def mesh_sanity(o):
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    if n == 0:
        return dict(tris=0, degenerate=0)
    area = np.zeros(n); me.loop_triangles.foreach_get('area', area)
    return dict(tris=n, degenerate=int((area < 1e-9).sum()))


def _bvh(objs):
    verts = []; polys = []; off = 0
    for o in objs:
        me = o.data; M = o.matrix_world
        me.calc_loop_triangles()
        vs = [M @ v.co for v in me.vertices]
        verts += vs
        for t in me.loop_triangles:
            polys.append([off + i for i in t.vertices])
        off += len(vs)
    return BVHTree.FromPolygons(verts, polys)


def surface_agreement(level):
    """Max |visual - Unity| over sample points of every drivable floor (centre lines and safe interiors)."""
    import rg_massif as MS
    import step13_terrain as T
    out = {}
    floors = {f['name']: f for f in level.floors}

    def sample(objs, pts, ref):
        bvh = _bvh(objs)
        d = []
        for (x, y), h in zip(pts, ref):
            hit = bvh.ray_cast(Vector((x, y, h + 3.0)), Vector((0, 0, -1)), 6.0)
            if hit[0] is not None:
                d.append(hit[0].z - h)
        d = np.array(d)
        return dict(n=int(len(d)), of=len(pts), max_abs=round(float(np.abs(d).max()), 3) if len(d) else None,
                    mean=round(float(d.mean()), 3) if len(d) else None)
    # mounds: interior points (rho < 0.92)
    for f in T.all_mounds(level):
        ob = bpy.data.objects.get(f['name'])
        if ob is None:
            continue
        C, R, F, hx, hz = T.rect_axes(f)
        pts = []
        for rho in (0.0, 0.3, 0.6, 0.85):
            for a in np.linspace(0, 2 * np.pi, 12, endpoint=False):
                lx = hx * rho * math.cos(a); lz = hz * rho * math.sin(a)
                pts.append((C[0] + R[0] * lx + F[0] * lz, C[1] + R[1] * lx + F[1] * lz))
        P = np.array(pts); ref = T.mound_height(f, P[:, 0], P[:, 1])
        out[f['name']] = sample([ob], pts, ref)
    # mesa floors + plateau (deck objects), ramps, kickers: points inside the rect shrunk by 0.8 m
    groups = {'MesaDecks': ['MesaS1', 'MesaH1', 'MesaS2', 'MesaH2', 'MesaS3', 'MesaL3', 'MesaTop'], 'Plateau': ['Plateau0'],
              'Ramp': ['IntroRamp'], 'Ramp.001': ['PlateauRamp0'], 'Ramp.002': ['BusJump'], 'Ramp.006': ['BigJump0'], 'Ramp.007': ['MesaJump'],
              'Kicker0a.001': ['Kicker0a'], 'Kicker0b.001': ['Kicker0b'], 'Kicker0c.001': ['Kicker0c'], 'Kicker0d.001': ['Kicker0d']}
    for obn, fls in groups.items():
        ob = bpy.data.objects.get(obn)
        if ob is None:
            continue
        objs = [ob] + ([bpy.data.objects['Road.022'], bpy.data.objects['Road.023'], bpy.data.objects['Road.024']] if obn == 'MesaDecks' else [])
        for fn in fls:
            if fn not in floors:
                continue
            Fl = MS.Floor(floors[fn])
            m = 0.8 if obn not in ('Kicker0a.001', 'Kicker0b.001', 'Kicker0c.001', 'Kicker0d.001') else 0.3
            pts = []; ref = []
            for u in np.linspace(-1, 1, 7):
                for v in np.linspace(-1, 1, 9):
                    lx = u * max(0.1, Fl.hx - m); lz = v * max(0.1, Fl.hz - m)
                    x, y = Fl.world(lx, lz)
                    pts.append((float(x), float(y))); ref.append(float(Fl.h_local(np.array([lz]))[0]))
            out[f'{obn}:{fn}'] = sample(objs, pts, np.array(ref))
    # road 0 over the road hills (centre line)
    rd = [r for r in level.md['roads'] if r.get('zone', 0) == 0 and r['index'] == 0][0]
    p = rd['points']; P = np.array([(p[i], p[i + 2]) for i in range(0, len(p), 3)])
    import step13_roads as RD
    C_, ss = RD.smooth_line(P, 0.5, 2.2, 0.3)
    hm = T.terrain_height(level, C_[:, 0], C_[:, 1])
    sel = hm > 0.05
    out['Road:on_hills'] = sample([bpy.data.objects['Road']], [tuple(c) for c in C_[sel]], hm[sel] + 0.035)
    return out
