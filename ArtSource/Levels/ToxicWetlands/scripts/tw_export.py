"""Export the Toxic Wetlands zone (second zone, index 1) as a runtime bundle for ImportedLevel.cs.

    Blender -b ToxicWetlands_Zone01.blend --python tw_export.py -- \
        --source-scene Exports/Blender/2026-11-17/scene.json --output Assets/RoadGame/Resources/Levels/ToxicWetlandsZ1

Same binary format and manifest as Tools/Blender/export_runtime_level.py (Dust Flats v13): one .bytes buffer per
unique evaluated mesh (14 float32 per vertex: position, normal, linear colour RGBA, UV0, UV1; int32 indices per
submesh), Unity axes (Y up) with reversed winding, IDs from the 2026-11-17 snapshot (unity_id), new objects
'blender_<name>'. Additions for this zone: 'zone' = 1, per-material baseKind / dust / AO / water shader,
spawn roots of every zone-1 target (props, enemies, buggies, boss) so ImportedLevel can swap live targets.
The .blend is read only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

AXIS = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
ZONE_COLLECTION = 'Zone_01_ToxicWetlands'


def args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--art-root', type=Path, default=None)
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def get_array(collection, prop, width, dtype=np.float32):
    a = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(prop, a)
    return a.reshape((-1, width))


def source_path(n, lookup):
    names, seen = [], set()
    while n and n['id'] not in seen:
        seen.add(n['id']); names.append(n['name']); n = lookup.get(n.get('parentId'))
    return '/'.join(reversed(names))


def export():
    opt = args()
    started = time.time()
    art_root = opt.art_root or Path(bpy.data.filepath).parent
    out = opt.output
    out.mkdir(parents=True, exist_ok=True)
    mesh_dir = out / 'Meshes'
    tex_dir = out / 'Textures'
    for d in (mesh_dir, tex_dir):
        if d.exists():
            for f in d.iterdir():
                if f.suffix in ('.bytes', '.png'):
                    f.unlink()
        d.mkdir(exist_ok=True)
    resource_root = out.as_posix().split('/Resources/')[-1]
    original = json.loads(opt.source_scene.read_text())
    original_nodes = {n['id']: n for n in original['nodes']}

    zone = bpy.data.collections[ZONE_COLLECTION]
    zone_objs = set(zone.all_objects)
    objects = set()
    for o in zone_objs:
        if o.get('tw_no_export'):
            continue
        objects.add(o)
        p = o.parent
        while p is not None:
            objects.add(p)
            p = p.parent
    objects = sorted(objects, key=lambda o: o.name)
    index = {o: i for i, o in enumerate(objects)}
    ids = {o: str(o.get('unity_id') or 'blender_' + o.name) for o in objects}
    mats = sorted({s.material for o in objects if o.type == 'MESH' for s in o.material_slots if s.material}, key=lambda m: m.name)
    mat_index = {m: i for i, m in enumerate(mats)}
    manifest = {'version': 1, 'zone': 1, 'sourceFile': Path(bpy.data.filepath).name,
                'coordinateSystem': 'Unity: X right, Y up, Z forward; metres',
                'meshes': [], 'materials': [], 'nodes': [], 'replacementNodeIds': [],
                'clipZone0': ['Cliff.014', 'AP_Cliff_NorthEast', 'AP_Scree_Cliff.014', 'AP_Scree_AP_Cliff_NorthEast',
                              'AP_SandDrift_Cliff.014'],
                'clipZone0MaxZ': 104.5,
                'sourceHash': hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()}
    textures = {}
    for m in mats:
        mid = str(m.get('unity_id') or 'tw_material_' + m.name)
        base = str(m.get('tw_unity_base', ''))
        if not base:
            srcm = str(m.get('tw_source_material', m.name))
            base = ('ground' if srcm == 'Ground' else 'flat' if srcm == 'ToonFlat' else 'road' if srcm.startswith('Road')
                    else '' if srcm.startswith(('LampPool', 'RepairGlow')) else 'toon')
        color = list(m.get('unity_base_color', (1, 1, 1, 1)))
        tex_rel = str(m.get('unity_base_map', ''))
        texture = ''
        img = None
        if m.node_tree:
            imgs = [n.image for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image]
            img = imgs[0] if imgs else None
        if img is not None:
            name = Path(img.name).stem
            dest = tex_dir / (name + '.png')
            if name not in textures:
                src = art_root / tex_rel if tex_rel and (art_root / tex_rel).is_file() else Path(bpy.path.abspath(img.filepath))
                if src.is_file():
                    shutil.copy2(src, dest)
                elif img.packed_file:
                    dest.write_bytes(bytes(img.packed_file.data))
                else:
                    img.save_render(str(dest))
                textures[name] = {'file': dest.name, 'size': list(img.size), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
            texture = resource_root + '/Textures/' + name
        shader = str(m.get('unity_shader', 'RoadGame/Toon'))
        manifest['materials'].append({
            'id': mid, 'name': m.name, 'shader': shader, 'color': color, 'texture': texture,
            'worldUV': float(m.get('unity_world_uv', 0.0)), 'tiling': list(m.get('unity_base_map_tiling', [1, 1])), 'offset': [0, 0],
            'unlit': 'Unlit' in shader, 'water': base == 'water', 'additive': m.name in {'TW_RepairGlow.001', 'TW_LampPool'},
            'roughness': 0.8, 'metallic': 0.0, 'alpha': float(m.get('tw_alpha', color[3] if len(color) > 3 else 1.0)),
            'baseKind': base, 'dust': float(m.get('tw_dust', -1.0)), 'aoFloor': float(m.get('tw_ao_floor', -1.0)),
            'zone': 1})
    cache = {}
    deps = bpy.context.evaluated_depsgraph_get()
    counts = {'sourceCorners': 0, 'splitVertices': 0, 'triangles': 0, 'removedDegenerates': 0, 'repairedNormalCorners': 0}

    def mesh_index(o):
        if o.type != 'MESH':
            return -1
        ck = (o.data.as_pointer(), o.name if len(o.modifiers) else None)
        if ck in cache:
            return cache[ck]
        ev = o.evaluated_get(deps)
        me = ev.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
        try:
            me.calc_loop_triangles()
            if not len(me.loop_triangles):
                cache[ck] = -1
                return -1
            pos = get_array(me.vertices, 'co', 3)
            loop_v = get_array(me.loops, 'vertex_index', 1, np.int32).ravel()
            normals = get_array(me.corner_normals, 'vector', 3)
            normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-20)
            colors = me.color_attributes.get('Color')
            rgba = get_array(colors.data, 'color', 4) if colors else np.ones((len(me.loops), 4), np.float32)
            if colors and colors.domain == 'POINT':
                rgba = rgba[loop_v]
            uv = []
            for nm in ('UVMap', 'Unity_MaterialParams'):
                layer = me.uv_layers.get(nm)
                uv.append(get_array(layer.data, 'uv', 2) if layer else np.zeros((len(me.loops), 2), np.float32))
            rows = np.concatenate((pos[loop_v][:, [0, 2, 1]], normals[:, [0, 2, 1]], rgba, *uv), axis=1).astype('<f4')
            tris = get_array(me.loop_triangles, 'loops', 3, np.int32)
            slots = get_array(me.loop_triangles, 'material_index', 1, np.int32).ravel()
            tv = pos[loop_v[tris]]
            area = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
            keep = (area * area).sum(axis=1) > 1e-20
            counts['removedDegenerates'] += int((~keep).sum())
            tris = tris[keep][:, [0, 2, 1]]
            slots = slots[keep]
            if not len(tris):
                cache[ck] = -1
                return -1
            used = rows[tris.ravel()].copy()
            bad = (used[:, 3:6] ** 2).sum(axis=1) < 0.5
            if bad.any():
                fn = area[keep][:, [0, 2, 1]]
                fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
                used[bad, 3:6] = np.repeat(fn, 3, axis=0)[bad]
                counts['repairedNormalCorners'] += int(bad.sum())
            corners, inverse = np.unique(used, axis=0, return_inverse=True)
            indices = inverse.reshape((-1, 3)).astype('<i4')
            slot_count = max(len(o.material_slots), int(slots.max()) + 1, 1)
            mi = len(manifest['meshes'])
            path = mesh_dir / f'mesh_{mi:04d}.bytes'
            with path.open('wb') as f:
                f.write(np.array([len(corners), slot_count], '<i4').tobytes())
                f.write(corners.astype('<f4').tobytes())
                for slot in range(slot_count):
                    buf = indices[slots == slot].ravel()
                    f.write(np.array([len(buf)], '<i4').tobytes())
                    f.write(buf.tobytes())
            manifest['meshes'].append({'name': o.data.name, 'resource': resource_root + '/Meshes/' + path.stem,
                                       'vertexCount': int(len(corners)), 'triangles': int(len(tris)), 'submeshes': slot_count,
                                       'sourceId': str(o.data.get('tw_source_mesh_id', '')),
                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            cache[ck] = mi
            counts['sourceCorners'] += len(me.loops)
            counts['splitVertices'] += int(len(corners))
            counts['triangles'] += int(len(tris))
            return mi
        finally:
            ev.to_mesh_clear()

    for o in objects:
        src = original_nodes.get(str(o.get('unity_id')), {})
        pos, rot, scale = (AXIS @ o.matrix_local @ AXIS).decompose()
        spawn_id, spawn_root, anc = -1, False, o
        while anc is not None:
            m = re.match(r'Spawn_(\d+)_', anc.name)
            if m:
                spawn_id = int(m.group(1)); spawn_root = anc is o
                break
            anc = anc.parent
        is_lod = bool(o.get('unity_lod_level', 0))
        lod_of = bpy.data.objects.get(str(o.get('unity_lod_of', '')))
        # hidden originals (replaced ground, desert decor, rock walls): no buffer, the node only switches them off
        mi = -1 if o.get('tw_hidden') else mesh_index(o)
        node = {'id': ids[o], 'name': o.name, 'originalName': src.get('name', '') or str(o.get('tw_original_name', '')),
                'originalParentId': src.get('parentId', ''), 'sourcePath': source_path(src, original_nodes) if src else '',
                'parent': index.get(o.parent, -1), 'mesh': mi,
                'materials': [mat_index.get(s.material, -1) for s in o.material_slots] if o.type == 'MESH' else [],
                'position': [0, 0, 0] if is_lod else list(pos), 'rotation': [0, 0, 0, 1] if is_lod else [rot.x, rot.y, rot.z, rot.w],
                'scale': [1, 1, 1] if is_lod else list(scale), 'category': str(o.get('unity_category', 'environment')),
                'active': bool(o.get('unity_active_self', True)) and not is_lod,
                'rendererEnabled': bool(o.get('unity_renderer_enabled', True)) and not is_lod and not o.get('tw_hidden', False),
                'spawnId': spawn_id, 'spawnRoot': spawn_root, 'isRoof': bool(o.get('tw_roof', False)),
                'castShadows': not bool(o.get('tw_no_shadow', False)),
                'lodOf': ids.get(lod_of, ''), 'lodLevel': int(o.get('unity_lod_level', 0)),
                'lodScreenSize': float(o.get('unity_lod_screen_size', 0.0)), 'colliderMesh': -1,
                'colliderConvex': bool(o.get('tw_collider_convex', False))}
        manifest['nodes'].append(node)
        if src.get('meshId') and src.get('category') not in ('spawn_visual', 'reference') and o.get('tw_replaced', True):
            manifest['replacementNodeIds'].append(src['id'])
    # collision proxies: tw_collider = name of a proxy object (exported only as a buffer) or 'self'
    by_name = {o.name: i for i, o in enumerate(objects)}
    proxies = 0
    for o in objects:
        c = o.get('tw_collider')
        if not c:
            continue
        proxy = o if c == 'self' else bpy.data.objects.get(str(c))
        if proxy is None:
            continue
        manifest['nodes'][by_name[o.name]]['colliderMesh'] = mesh_index(proxy)
        proxies += 1
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
    for d in (mesh_dir, tex_dir):
        for f in d.iterdir():
            if f.suffix == '.meta' and not (d / f.stem).exists():
                f.unlink()
    report = {'sourceFile': bpy.data.filepath, 'sourceSha256': manifest['sourceHash'], 'nodes': len(manifest['nodes']),
              'meshObjects': sum(n['mesh'] >= 0 for n in manifest['nodes']), 'uniqueMeshes': len(manifest['meshes']),
              'materials': len(mats), 'textures': textures, 'collisionProxies': proxies,
              'spawnRoots': sum(1 for n in manifest['nodes'] if n['spawnRoot']),
              'lodObjects': sum(n['lodLevel'] > 0 for n in manifest['nodes']), 'counts': counts,
              'binaryBytes': sum(p.stat().st_size for p in mesh_dir.glob('*.bytes')),
              'elapsedSeconds': round(time.time() - started, 2)}
    (out / 'export_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('TW_EXPORT_COMPLETE', json.dumps({k: v for k, v in report.items() if k != 'textures'}), flush=True)


if __name__ == '__main__':
    export()
