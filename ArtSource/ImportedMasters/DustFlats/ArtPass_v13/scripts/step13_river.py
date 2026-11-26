"""v13 step: river kept (smooth channel, gentle banks, shallow water, two bridges, fords from v12); its rocks rounded:
the boulder dams in the inlet / outlet gaps and the boulders on the outer bends become flat-capped sandstone
blocks on the same footprints (the dams keep their blocking footprint for the colliders)."""
import bpy
import numpy as np
import rg_lib as L
from step13_massif import cluster_stacks, boulder_from_group, comp_list, full_arrays, with_mat, replace_mesh


def rebuild(ob, seed, ctx):
    arr = full_arrays(ob.data); Mw = np.array(ob.matrix_world)
    arr_w = dict(arr); arr_w['co'] = arr['co'] @ Mw[:3, :3].T + Mw[:3, 3]
    comp, comps = comp_list(arr_w)
    groups = cluster_stacks(comps, 0.4)
    bl = [with_mat(boulder_from_group(g, seed + i, flat=0.4, lumpy=0.17, strata=0.6, bury=0.2), 0) for i, g in enumerate(groups)]
    mats = [s.material for s in ob.material_slots][:1]
    return replace_mesh(ob, bl, mats, f'v13: {len(bl)} rounded flat-capped sandstone boulders on the v12 footprints', sharp=80.0)


def run(ctx):
    st = {}
    for i, nm in enumerate(['AP_River_GapBoulders', 'AP_River_Boulders']):
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            st[nm] = rebuild(ob, 8100 + 300 * i, ctx)
    ctx['stats']['river'] = st
    print('STEP13 river', st, flush=True)
