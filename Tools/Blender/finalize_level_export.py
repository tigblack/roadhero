"""Reopen and verify the full snapshot, then save a smaller first-zone editing file."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects
              if obj.type == 'MESH' for corner in obj.bound_box]
    return [[min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)]]


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    directory = args.directory.resolve()
    expected = json.loads((directory / 'expected-validation.json').read_text())
    full_path = directory / 'RoadGame_AllZones_v10.blend'
    bpy.ops.wm.open_mainfile(filepath=str(full_path))
    bpy.context.view_layer.update()
    objects = [o for o in bpy.context.scene.objects if 'unity_id' in o]
    geometry = [o for o in objects if o.type == 'MESH']
    assert len(objects) == expected['nodes'], (len(objects), expected['nodes'])
    assert len(geometry) == expected['meshInstances'], len(geometry)
    by_id = {m.get('unity_id'): m for m in bpy.data.meshes if m.get('unity_id')}
    assert len(by_id) == len(expected['meshes'])
    for mesh_id, source in expected['meshes'].items():
        mesh = by_id[mesh_id]
        assert len(mesh.vertices) == source['vertices'], mesh_id
        removed_faces = int(mesh.get('unity_zero_area_triangles_removed', 0))
        assert len(mesh.polygons) == source['triangles'] - removed_faces, mesh_id
        assert 'Color' in mesh.color_attributes, mesh_id
        assert 'UVMap' in mesh.uv_layers and 'Unity_MaterialParams' in mesh.uv_layers, mesh_id
        assert all(math.isfinite(v) for vertex in mesh.vertices for v in vertex.co), mesh_id
    full_bounds = bounds(geometry)
    source_bounds = expected['bounds']
    expected_bounds = [[part[0], part[2], part[1]] for part in (source_bounds['min'], source_bounds['max'])]
    assert max(abs(a-b) for left, right in zip(full_bounds, expected_bounds)
               for a, b in zip(left, right)) < 0.02, (full_bounds, expected_bounds)
    images = [image for image in bpy.data.images if image.type == 'IMAGE' and image.filepath]
    assert all(image.packed_file for image in images), 'External image was not packed into .blend'
    report = {'full_file_reopened': True, 'source_nodes': len(objects),
              'mesh_instances': len(geometry), 'unique_meshes': len(by_id),
              'unique_vertices': sum(len(m.vertices) for m in by_id.values()),
              'unique_triangles': sum(len(m.polygons) for m in by_id.values()),
              'original_triangles': sum(m['triangles'] for m in expected['meshes'].values()),
              'zero_area_triangles_removed': sum(int(m.get('unity_zero_area_triangles_removed', 0)) for m in by_id.values()),
              'all_vertices_match_source': True, 'all_faces_accounted_for_after_zero_area_cleanup': True,
              'color_and_uv_layers_preserved': True,
              'world_bounds_blender': full_bounds, 'packed_images': len(images)}

    # Keep all first-zone meshes, including the start canyon and scale-reference car.
    removed = [o for o in geometry if int(o.get('editing_zone', 0)) > 0]
    for obj in removed:
        for child in list(obj.children):
            transform = child.matrix_world.copy()
            child.parent = obj.parent
            child.matrix_world = transform
        bpy.data.objects.remove(obj, do_unlink=True)
    for _ in range(30):
        empty = [o for o in bpy.context.scene.objects
                 if o.type == 'EMPTY' and not o.children and 'unity_id' in o]
        if not empty:
            break
        for obj in empty:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.name.startswith(('Zone_01_', 'Zone_02_', 'Zone_03_')):
            bpy.data.collections.remove(collection)
    for mesh in list(bpy.data.meshes):
        if not mesh.users:
            bpy.data.meshes.remove(mesh)
    scene = bpy.context.scene
    scene['roadgame_subset'] = 'Dust Flats + Intro; extracted from the complete v10 snapshot'
    scene['roadgame_source_all_zones_blend'] = full_path.name
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.file.pack_all()
    first_path = directory / 'DustFlats_Level_v10.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(first_path), compress=True)
    first_geometry = [o for o in scene.objects if o.type == 'MESH']
    report['first_zone'] = {'file': first_path.name,
                            'mesh_objects': len(first_geometry),
                            'bounds_blender': bounds(first_geometry)}
    try:
        for obj in scene.objects:
            obj.select_set(obj.type in {'MESH', 'EMPTY'})
        fbx = directory / 'DustFlats_Level_v10.fbx'
        bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True,
                                object_types={'EMPTY', 'MESH'}, apply_unit_scale=True,
                                global_scale=1.0, apply_scale_options='FBX_SCALE_UNITS',
                                axis_forward='-Z', axis_up='Y', use_custom_props=True,
                                mesh_smooth_type='FACE', add_leaf_bones=False,
                                bake_anim=False, colors_type='LINEAR', path_mode='AUTO')
        report['first_zone']['fbx'] = fbx.name
    except Exception as error:
        report['first_zone']['fbx_warning'] = str(error)
    bpy.ops.object.select_all(action='DESELECT')
    # Reopening verifies that the delivered native first-zone file is readable too.
    bpy.ops.wm.open_mainfile(filepath=str(first_path))
    assert sum(o.type == 'MESH' for o in bpy.context.scene.objects) == report['first_zone']['mesh_objects']
    report['first_zone']['reopened'] = True
    (directory / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('ROADGAME_EXPORT_VALIDATED ' + json.dumps(report, ensure_ascii=False), flush=True)


main()
