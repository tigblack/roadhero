"""Step 0: make the editable base for the Toxic Wetlands pass from a COPY of the v10 world snapshot.

    Blender -b ArtSource/Levels/ToxicWetlands/source/RoadGame_AllZones_v10_source_copy.blend \
        --python ArtSource/Levels/ToxicWetlands/scripts/tw_base.py -- --out <base.blend>

Keeps only the second zone (index 1, collection Zone_01_RustCanyon in v10), the empties that hold its
hierarchy (spawn roots, Scale/Leg/Arm pivots, structure groups) and the reference car. Every kept mesh and
material is made single-user and renamed with the TW_ prefix, so nothing is shared with another zone's
instances. Unity IDs (unity_id, unity_local_*), names of the hierarchy and UV/colour attributes stay as they were.
The source file is never written.
"""
import argparse
import sys

import bpy

ZONE_SRC = 'Zone_01_RustCanyon'
ZONE_DST = 'Zone_01_ToxicWetlands'
NORTH_WALL_IDS = {'node_000701', 'node_000703'}   # Cliff.016 / Cliff.017 at z = 300


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def main():
    a = args()
    src_path = bpy.data.filepath
    zone = bpy.data.collections[ZONE_SRC]
    keep = set(zone.all_objects)
    # the zone 1 / zone 2 boundary walls are generated with the second zone's colours (World.cs: boundary b uses
    # Zones[b - 1]) but the v10 importer filed them under Zone_02: they belong to this zone's edge
    north = [o for o in bpy.data.objects if str(o.get('unity_id')) in NORTH_WALL_IDS]
    for o in north:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        zone.objects.link(o)
        o['tw_note'] = 'zone 1 / zone 2 boundary wall (second zone colours), moved from Zone_02_SaltFlats'
        keep.add(o)
    # ancestors (spawn roots and pivots are empties in the 'EDITABLE LEVEL' collection)
    for o in list(keep):
        p = o.parent
        while p is not None:
            keep.add(p)
            p = p.parent
    # Muzzle points are empties under kept meshes (Buggy Gun): keep empties whose parent is a kept mesh
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.parent in keep and o.parent.type == 'MESH':
            keep.add(o)
    refs = bpy.data.collections.get('References — vehicle and scale guides')
    ref_objs = set(refs.all_objects) if refs else set()
    # The world root empty and zone-level groups stay so parents resolve like in Unity.
    for o in list(bpy.data.objects):
        if o in keep or o in ref_objs:
            continue
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name.startswith(('Zone_00', 'Zone_02', 'Zone_03', 'PREVIEW')):
            bpy.data.collections.remove(c)
    zone.name = ZONE_DST
    zone['tw_source_collection'] = ZONE_SRC
    zone['tw_note'] = 'Second zone (index 1) of RoadGame, reworked into the Toxic Wetlands biome. Unity IDs kept.'
    for c in zone.children:
        c.name = c.name.replace(ZONE_SRC, ZONE_DST)
    # single-user meshes / materials for the kept zone objects (no sharing with other zones' snapshots)
    mesh_map, mat_map = {}, {}
    for o in keep:
        if o.type != 'MESH':
            continue
        me = o.data
        if me not in mesh_map:
            new = me.copy()
            new.name = 'TW_' + me.name
            for k in ('unity_id',):
                if k in me:
                    new['tw_source_mesh_id'] = me[k]
            mesh_map[me] = new
        o.data = mesh_map[me]
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            if m not in mat_map:
                nm = m.copy()
                nm.name = 'TW_' + m.name
                nm['tw_source_material'] = m.name
                mat_map[m] = nm
            slot.link = 'OBJECT' if slot.link == 'OBJECT' else slot.link
            slot.material = mat_map[m]
    for o in keep:
        o['editing_zone'] = 1
        o['tw_stage'] = 'v10 snapshot (unchanged)'
    # purge everything no longer used (other zones' meshes, materials, images)
    for _ in range(4):
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.context.scene['tw_base_source'] = src_path
    print('TW_BASE kept objects', len(keep), 'meshes', len(mesh_map), 'materials', len(mat_map),
          'total objects', len(bpy.data.objects), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True, copy=False)


if __name__ == '__main__':
    main()
