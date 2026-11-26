"""Export the mutants as a runtime bundle for Unity (Scripts/World/Mutants.cs).

    Blender -b ToxicWetlands_Mutants_v2.blend --python mut_export.py -- --output Assets/RoadGame/Resources/Creatures/WetlandsMutants

Mesh buffers use the format of the level bundles (Tools/Blender/export_runtime_level.py): 14 float32 per vertex
(position, normal, linear colour RGBA, UV0, UV1 = gloss/metal), Unity axes (x, z, y) with reversed winding, int32
indices per submesh. manifest.json lists the creatures (Unity ModelId, root node, rest-pose height and footprint)
and every node with its parent, local transform (joint pivots, identity rest rotations), mesh, materials and LOD level.
The .blend is read only.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

AXIS = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
HERE = os.path.dirname(os.path.abspath(__file__))


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def arr(collection, prop, width, dtype=np.float32):
    a = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(prop, a)
    return a.reshape((-1, width))


def main():
    opt = args()
    t0 = time.time()
    out = opt.output
    mesh_dir = out / 'Meshes'
    tex_dir = out / 'Textures'
    for d in (mesh_dir, tex_dir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob('*'):
            if f.suffix in ('.bytes', '.png'):
                f.unlink()
    res_root = 'Creatures/' + out.name
    deps = bpy.context.evaluated_depsgraph_get()
    manifest = {'version': 1, 'sourceFile': os.path.basename(bpy.data.filepath),
                'sourceSha256': hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
                'creatures': [], 'nodes': [], 'meshes': [], 'materials': []}
    mats = {}
    cache = {}
    counts = {'triangles': 0, 'vertices': 0, 'lodTriangles': 0}

    def material_index(m):
        if m is None:
            m = bpy.data.materials.get('TW_Mutant')
        if m.name in mats:
            return mats[m.name]
        tex = m.get('unity_base_map', '')
        tex_res = ''
        if tex:
            src = Path(bpy.path.abspath(bpy.data.images[os.path.basename(tex)].filepath)) if os.path.basename(tex) in bpy.data.images else None
            if src is None or not src.exists():
                src = Path(HERE).parent / 'textures' / os.path.basename(tex)
            shutil.copy2(src, tex_dir / src.name)
            tex_res = res_root + '/Textures/' + src.stem
        mats[m.name] = len(manifest['materials'])
        manifest['materials'].append({'name': m.name, 'shader': 'RoadGame/Toon', 'texture': tex_res,
                                      'color': list(m.get('unity_base_color', [1, 1, 1, 1])),
                                      'baseKind': m.get('tw_unity_base', 'actor'), 'dust': 0.03})
        return mats[m.name]

    def mesh_index(o):
        key = o.data.name
        if key in cache:
            return cache[key]
        ev = o.evaluated_get(deps)
        me = ev.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
        try:
            me.calc_loop_triangles()
            pos = arr(me.vertices, 'co', 3)
            loop_v = arr(me.loops, 'vertex_index', 1, np.int32).ravel()
            normals = arr(me.corner_normals, 'vector', 3)
            normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-20)
            col = me.color_attributes.get('Color')
            rgba = arr(col.data, 'color', 4) if col else np.ones((len(me.loops), 4), np.float32)
            if col and col.domain == 'POINT':
                rgba = rgba[loop_v]
            uv = []
            for nm in ('UVMap', 'Unity_MaterialParams'):
                layer = me.uv_layers.get(nm)
                uv.append(arr(layer.data, 'uv', 2) if layer else np.zeros((len(me.loops), 2), np.float32))
            rows = np.concatenate((pos[loop_v][:, [0, 2, 1]], normals[:, [0, 2, 1]], rgba, *uv), axis=1).astype('<f4')
            tris = arr(me.loop_triangles, 'loops', 3, np.int32)
            slots = arr(me.loop_triangles, 'material_index', 1, np.int32).ravel()
            tv = pos[loop_v[tris]]
            area = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
            keep = (area * area).sum(axis=1) > 1e-20
            tris = tris[keep][:, [0, 2, 1]]
            slots = slots[keep]
            used = rows[tris.ravel()].copy()
            corners, inverse = np.unique(used, axis=0, return_inverse=True)
            indices = inverse.reshape((-1, 3)).astype('<i4')
            slot_count = max(len(o.material_slots), int(slots.max()) + 1 if len(slots) else 1, 1)
            mi = len(manifest['meshes'])
            path = mesh_dir / f'mesh_{mi:04d}.bytes'
            with path.open('wb') as f:
                f.write(np.array([len(corners), slot_count], '<i4').tobytes())
                f.write(corners.astype('<f4').tobytes())
                for s in range(slot_count):
                    buf = indices[slots == s].ravel()
                    f.write(np.array([len(buf)], '<i4').tobytes())
                    f.write(buf.tobytes())
            manifest['meshes'].append({'name': o.data.name, 'resource': res_root + '/Meshes/' + path.stem,
                                       'vertexCount': int(len(corners)), 'triangles': int(len(tris)), 'submeshes': slot_count})
            cache[key] = mi
            if o.get('unity_lod_level'):
                counts['lodTriangles'] += int(len(tris))
            else:
                counts['triangles'] += int(len(tris))
                counts['vertices'] += int(len(corners))
            return mi
        finally:
            ev.to_mesh_clear()

    roots = sorted([o for o in bpy.data.objects if o.get('mut_root')], key=lambda o: o.name)
    for root in roots:
        index = {}
        order = []

        def walk(o):
            order.append(o)
            for c in sorted(o.children, key=lambda c: c.name):
                walk(c)
        walk(root)
        lo = Vector((1e9, 1e9, 1e9))
        hi = Vector((-1e9, -1e9, -1e9))
        foot = 0.0
        rinv = root.matrix_world.inverted()
        for o in order:
            if o.type == 'MESH' and not o.get('unity_lod_level'):
                Mw = rinv @ o.matrix_world
                for v in o.data.vertices:
                    p = Mw @ v.co
                    lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
                    hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
                    foot = max(foot, math.hypot(p.x, p.y))
        first = len(manifest['nodes'])
        for o in order:
            index[o] = len(manifest['nodes'])
            if o is root:
                pos, rot, scl = Vector((0, 0, 0)), (0, 0, 0, 1), Vector((1, 1, 1))
            else:
                p_, q_, s_ = (AXIS @ o.matrix_local @ AXIS).decompose()
                pos, rot, scl = p_, (q_.x, q_.y, q_.z, q_.w), s_
            lod = int(o.get('unity_lod_level', 0))
            lod_of = bpy.data.objects.get(str(o.get('unity_lod_of', '')))
            node = {'name': str(o.get('mut_part', o.name)) if o is not root else o.name,
                    'parent': index.get(o.parent, -1) if o is not root else -1,
                    'mesh': mesh_index(o) if o.type == 'MESH' else -1,
                    'materials': [material_index(s.material) for s in o.material_slots] if o.type == 'MESH' else [],
                    'position': [round(x, 6) for x in pos], 'rotation': [round(x, 7) for x in rot],
                    'scale': [round(x, 6) for x in scl], 'lodLevel': lod,
                    'lodOf': index.get(lod_of, -1) if lod_of is not None else -1,
                    'castShadows': not bool(o.get('tw_no_shadow', False))}
            manifest['nodes'].append(node)
        manifest['creatures'].append({'model': root['mut_model'], 'name': root.name, 'root': first,
                                      'nodeCount': len(order), 'tris': int(root.get('mut_tris', 0)),
                                      'height': round(hi.z, 3), 'footprint': round(foot, 3),
                                      'size': [round(hi.x - lo.x, 3), round(hi.z - lo.z, 3), round(hi.y - lo.y, 3)]})
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
    for d in (mesh_dir, tex_dir):
        for f in d.iterdir():
            if f.suffix == '.meta' and not (d / f.stem).exists():
                f.unlink()
    report = {'creatures': [{k: c[k] for k in ('model', 'name', 'tris', 'height', 'footprint', 'size', 'nodeCount')}
                            for c in manifest['creatures']],
              'nodes': len(manifest['nodes']), 'meshes': len(manifest['meshes']), 'materials': len(manifest['materials']),
              'counts': counts, 'binaryBytes': sum(p.stat().st_size for p in mesh_dir.glob('*.bytes')),
              'elapsedSeconds': round(time.time() - t0, 2)}
    (out / 'export_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('MUT_EXPORT_COMPLETE', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
