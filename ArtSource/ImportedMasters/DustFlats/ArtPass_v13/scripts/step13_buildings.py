"""v13 step: buildings rounded component by component (rg_round).

Garage, Mammoth Works (hangar walls, roof, door, entrance arch, tunnel & lids, interior, vents, sign), gate
towers & barrier, repair pad, billboard, palisades, camp shacks / tents / watch towers (all instances through
their shared meshes). Wall slabs, plinths, copings and caps get radii sized for the game camera (up to 0.32 m on
the big masses -> soft plastic silhouettes, rounded cornices & bases), beams / frames 2-4 segment bevels, planks
small radii, posts / pipes / tanks become true 16-40 segment cylinders with rounded rims. Roofs stay separate
objects; flat decals, glows and lamp pools are kept as they were."""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix
import rg_round as RR
import rg_kit as K


def stake_special(p, P, srcs):
    """Palisade stake (tall, thin, pointed n-gon prism) -> 8-sided rounded stake with a soft pointed tip."""
    if len(srcs) > 90:
        return False
    c = P.mean(0); Q = P - c
    w, v = np.linalg.eigh(Q.T @ Q); ax = v[:, 2]
    if ax[2] < 0:
        ax = -ax
    if ax[2] < 0.6:
        return False
    t = Q @ ax
    L_ = float(t.max() - t.min())
    thick = np.linalg.norm(Q - np.outer(t, ax), axis=1).max() * 2
    if not (L_ > 0.9 and thick < 0.62 and L_ > 3.0 * thick):
        return False
    base = c + ax * t.min()
    perp = Q - np.outer(t, ax)
    lo = t < t.min() + 0.75 * L_
    r = float(np.sqrt((perp[lo] ** 2).sum(1)).mean()) * 0.97
    tip = min(0.6 * L_, max(0.18, 2.6 * r))
    prof = [(r, 0.0, 'b'), (r, L_ - tip, 'b'), (r * 0.8, L_ - tip * 0.62, 'b'), (r * 0.36, L_ - tip * 0.22, 'b'),
            (r * 0.06, L_ - 0.008, 'b')]
    z = Vector(ax.tolist()); x = Vector((1, 0, 0)) if abs(ax[0]) < 0.9 else Vector((0, 1, 0))
    x = (x - z * x.dot(z)).normalized(); y = z.cross(x)
    M = Matrix(((x[0], y[0], z[0], base[0]), (x[1], y[1], z[1], base[1]), (x[2], y[2], z[2], base[2]), (0, 0, 0, 1)))
    faces = K.lathe(p, prof, 8, M, lambda tag, i, j: (0.4, 0.3, 0.2, 1, 0, 0), 'plain', cap_bottom=True, cap_top=True)
    p.bm.normal_update()
    RR._transfer(p, faces, srcs)
    return True

BUILDINGS = ['GarageWallN', 'GarageWallS', 'GarageRoof', 'GarageFloor',
             'HangarWallE', 'HangarWallN', 'HangarWallS', 'HangarWallW', 'HangarWallW2', 'HangarRoof.001', 'HangarDoor',
             'WorksEntrance', 'WorksHangar', 'WorksTunnel', 'TunnelLid0', 'TunnelLid1', 'TunnelLid2', 'Vents', 'WorksSign',
             'GateTowers', 'GateBarrier', 'Pad', 'Billboard', 'Palisade', 'Palisade.001', 'Palisade.002']
SPAWN_MESHES = ['Shack_0_0', 'Shack_1_0', 'Shack_2_0', 'Tent_0_0', 'Tent_1_0', 'Tent_2_0', 'Tower_0_0', 'Tower_1_0', 'Tower_2_0']


def role_for(size, c):
    s = np.sort(size)
    if s[0] < 0.065 and s[2] > 0.4:
        return 'board'
    if s[0] >= 0.25 and s[2] >= 1.5:
        return 'structure'
    return 'detail'


def run(ctx):
    st = {}
    done = set()
    for nm in BUILDINGS:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH' or ob.data.name in done:
            continue
        done.add(ob.data.name)
        special = stake_special if nm.startswith('Palisade') else None
        st[nm] = RR.rebuild_object_mesh(ob, role_fn=role_for, note='v13: rounded building (multi-segment arc bevels sized for the game camera, true cylinders)',
                                        keep_below=0.016, special=special)
    for mn in SPAWN_MESHES:
        me = bpy.data.meshes.get(mn)
        if me is None:
            continue
        users = [o for o in bpy.data.objects if o.type == 'MESH' and o.data == me]
        if not users:
            continue
        st[mn] = RR.rebuild_object_mesh(users[0], role_fn=role_for, note='v13: rounded camp building (shared by all instances)', keep_below=0.012)
    ctx['stats']['buildings'] = st
    print('STEP13 buildings', {k: (v['old'], v['new'], v['box'], v['cyl'], v['bevel'], v.get('special', 0), v['kept'], v['users']) for k, v in st.items()}, flush=True)
