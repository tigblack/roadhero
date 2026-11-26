"""Export the authored car to Unity-native mesh inputs without FBX axis/pivot loss.

Blender -b /path/Scarbound_Car_v10_DetailedCar.blend -noaudio --python \
  Tools/Blender/export_detailed_car.py -- --output Exports/Blender/2026-11-19/DetailedCar

The .blend is read only. Unity's ImportedCarSetup.Build turns these inputs into
serialized Mesh assets, materials and the runtime prefab. Each binary contains
int32 vertex/index counts, 14-float corner records (position, normal, linear
RGBA, UV0, UV1), then int32 triangle indices. Y/Z reflection and reversed
winding preserve Unity metres and all pivots. Unity computes Mikk tangents
from the final triangles, UV0 and authored corner normals.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

AXIS = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
NAMES = {
    'REFERENCE_PlayerCar_DoNotMerge': 'PlayerCar', 'Body.573': 'Body',
    'TurretBase.001': 'TurretBase', 'TurretYaw.001': 'TurretYaw',
    'Muzzle.018': 'Muzzle', 'Body.574': 'Body',
    'LegL.170': 'LegL', 'LegR.170': 'LegR', 'LegMesh.001': 'LegMesh',
    'WheelSteer.082': 'WheelSteer_FL', 'WheelSteer.083': 'WheelSteer_FR',
    'Wheel.084': 'Wheel_RL', 'Wheel.086': 'Wheel_RR',
    'Wheel.082': 'Wheel', 'Wheel.083': 'Wheel', 'Wheel.085': 'Wheel', 'Wheel.087': 'Wheel',
}
SETS = {
    'CarBody': ['Body.573'],
    'CarDetails': ['Details', 'Underbody', 'BrakeCaliper_FL', 'BrakeCaliper_FR', 'BrakeCaliper_RL', 'BrakeCaliper_RR'],
    'Wheels': ['Wheel.082', 'Wheel.083', 'Wheel.085', 'Wheel.087'],
    'HoodGun': ['HoodMount', 'Turntable', 'GunCradle', 'GunMesh'],
    'Harpoon': ['TurretBase.001', 'Column', 'LauncherMesh', 'HarpoonTip'],
    'Quasimodo': ['Cloak', 'HeadMesh', 'UpperArmR', 'UpperArmL', 'ForeArmR', 'ForeArmL', 'HandR', 'HandL', 'LegMesh', 'LegMesh.001'],
}


def array(items, field, width, dtype=np.float32):
    result = np.empty(len(items) * width, dtype=dtype)
    items.foreach_get(field, result)
    return result.reshape((-1, width))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def mesh_input(obj, path, deps):
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
    try:
        mesh.calc_loop_triangles()
        pos = array(mesh.vertices, 'co', 3)
        vi = array(mesh.loops, 'vertex_index', 1, np.int32).ravel()
        normal = array(mesh.corner_normals, 'vector', 3)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-20)
        color = mesh.color_attributes['Color']
        rgba = array(color.data, 'color', 4)
        if color.domain == 'POINT':
            rgba = rgba[vi]
        uv = [array(mesh.uv_layers[name].data, 'uv', 2) for name in ('UVMap', 'Unity_MaterialParams')]
        rows = np.concatenate((pos[vi][:, [0, 2, 1]], normal[:, [0, 2, 1]], rgba, *uv), axis=1).astype('<f4')
        triangles = array(mesh.loop_triangles, 'loops', 3, np.int32)
        tv = pos[vi[triangles]]
        cross = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
        keep = (cross * cross).sum(axis=1) > 1e-20
        triangles = triangles[keep][:, [0, 2, 1]]
        corners = rows[triangles.ravel()].copy()
        bad = (corners[:, 3:6] ** 2).sum(axis=1) < .5
        if bad.any():
            fn = cross[keep][:, [0, 2, 1]]
            fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
            corners[bad, 3:6] = np.repeat(fn, 3, axis=0)[bad]
        unique, inverse = np.unique(corners, axis=0, return_inverse=True)
        if not np.isfinite(unique).all():
            raise ValueError('Non-finite vertex data: ' + obj.name)
        with path.open('wb') as f:
            f.write(struct.pack('<ii', len(unique), len(inverse)))
            f.write(unique.astype('<f4').tobytes())
            f.write(inverse.astype('<i4').tobytes())
        return {'file': path.name, 'vertices': len(unique), 'triangles': len(inverse) // 3,
                'removedDegenerates': int((~keep).sum()), 'sha256': digest(path)}
    finally:
        evaluated.to_mesh_clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    opt = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    opt.output.mkdir(parents=True, exist_ok=True)
    source = Path(bpy.data.filepath)
    source_hash = digest(source)
    root = bpy.data.objects['REFERENCE_PlayerCar_DoNotMerge']
    nodes = [root] + [o for o in root.children_recursive if 'lod_level' not in o]
    index = {o: i for i, o in enumerate(nodes)}
    texture_sets = {name: group for group, names in SETS.items() for name in names}
    manifest = {'version': 1, 'source': str(source), 'sourceSha256': source_hash,
                'nodes': [], 'lodTriangles': [0, 0, 0]}
    deps = bpy.context.evaluated_depsgraph_get()
    for i, obj in enumerate(nodes):
        matrix = AXIS @ obj.matrix_local @ AXIS
        position, rotation, scale = matrix.decompose()
        node = {'name': NAMES.get(obj.name, obj.name), 'sourceName': obj.name,
                'parent': index.get(obj.parent, -1), 'position': list(position),
                'rotation': [rotation.x, rotation.y, rotation.z, rotation.w], 'scale': list(scale),
                'material': texture_sets.get(obj.name, ''), 'lods': []}
        if obj.name == 'HoodGun_Muzzle':
            # Blender's arrow empty points along its local Z; the runtime marker's
            # forward axis must instead follow the barrel (+Z in Unity).
            node['rotation'] = [0, 0, 0, 1]
        if obj.type == 'MESH':
            assert node['material'], obj.name
            for level in range(3):
                lod = obj if level == 0 else bpy.data.objects[f'{obj.name}_LOD{level}']
                record = mesh_input(lod, opt.output / f'mesh_{i:02d}_LOD{level}.bytes', deps)
                node['lods'].append(record)
                manifest['lodTriangles'][level] += record['triangles']
        manifest['nodes'].append(node)
    assert len(nodes) == 52
    assert sum(bool(n['lods']) for n in manifest['nodes']) == 29
    assert digest(source) == source_hash, 'Source changed during read-only export'
    (opt.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('DETAILED CAR EXPORT', len(nodes), 'nodes, LOD triangles:', manifest['lodTriangles'], flush=True)


main()
