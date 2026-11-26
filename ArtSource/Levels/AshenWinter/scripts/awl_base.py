"""Step 0: the editable base for the Ashen Winter pass from a COPY of the v10 world snapshot.

    Blender -b ArtSource/Levels/AshenWinter/source/RoadGame_AllZones_v10_source_copy.blend \
        --python ArtSource/Levels/AshenWinter/scripts/awl_base.py -- --out <base.blend>

Keeps only the third zone (index 2, collection Zone_02_SaltFlats in v10), the empties that hold its hierarchy (spawn
roots, Scale / Leg / Arm pivots, structure groups) and the reference car. The zone 1 / zone 2 boundary walls at
z = 300 (Cliff.016 / Cliff.017, node_000701 / node_000703) are the Toxic Wetlands bundle's (its north levee is built
on them up to z ~ 305.6): they are left out here, so the two bundles never own the same node, mesh or collider.
Every kept mesh and material is made single-user with the AW_ prefix. Unity IDs (unity_id, unity_local_*),
hierarchy names and attributes stay as they were. The source file is never written.
"""
import argparse
import sys

import bpy

ZONE_SRC = 'Zone_02_SaltFlats'
ZONE_DST = 'Zone_02_AshenWinter'
WETLANDS_OWNED = {'node_000701', 'node_000703'}   # Cliff.016 / Cliff.017 at z = 300 (Toxic Wetlands bundle)


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def main():
    a = args()
    src_path = bpy.data.filepath
    zone = bpy.data.collections[ZONE_SRC]
    keep = {o for o in zone.all_objects if str(o.get('unity_id')) not in WETLANDS_OWNED}
    for o in list(keep):
        p = o.parent
        while p is not None:
            keep.add(p)
            p = p.parent
    # muzzle points etc.: empties under kept meshes
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.parent in keep and o.parent.type == 'MESH':
            keep.add(o)
    refs = bpy.data.collections.get('References — vehicle and scale guides')
    ref_objs = set(refs.all_objects) if refs else set()
    for o in list(bpy.data.objects):
        if o in keep or o in ref_objs:
            continue
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name.startswith(('Zone_00', 'Zone_01', 'Zone_03', 'PREVIEW')):
            bpy.data.collections.remove(c)
    zone.name = ZONE_DST
    zone['aw_source_collection'] = ZONE_SRC
    zone['aw_note'] = 'Third zone (index 2) of RoadGame, reworked into Ashen Winter. Unity IDs kept.'
    for c in zone.children:
        c.name = c.name.replace(ZONE_SRC, ZONE_DST)
    mesh_map, mat_map = {}, {}
    for o in keep:
        if o.type != 'MESH':
            continue
        me = o.data
        if me not in mesh_map:
            new = me.copy()
            new.name = 'AW_' + me.name
            if 'unity_id' in me:
                new['tw_source_mesh_id'] = me['unity_id']
            mesh_map[me] = new
        o.data = mesh_map[me]
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            if m not in mat_map:
                nm = m.copy()
                nm.name = 'AW_' + m.name
                nm['tw_source_material'] = m.name
                mat_map[m] = nm
            slot.material = mat_map[m]
    for o in keep:
        o['editing_zone'] = 2
        o['tw_stage'] = 'v10 snapshot (unchanged)'
    for _ in range(4):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.context.scene['aw_base_source'] = src_path
    print('AW_BASE kept objects', len(keep), 'meshes', len(mesh_map), 'materials', len(mat_map),
          'total objects', len(bpy.data.objects), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True, copy=False)


if __name__ == '__main__':
    main()
