"""Extract the untouched player-car reference into a standalone Blender file.

Blender --background --factory-startup -noaudio --python Tools/Blender/export_car.py -- \
  --source Exports/Blender/2026-11-17/RoadGame_AllZones_v10.blend \
  --output Exports/Blender/2026-11-18/Scarbound_Car_v10.blend

The source is opened for reading and never saved. The output is reopened and
checked before this script exits. An FBX, PNG preview and JSON check accompany it.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT_NAME = "REFERENCE_PlayerCar_DoNotMerge"


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner)
              for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    return (Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
            Vector(tuple(max(point[axis] for point in points) for axis in range(3))))


def summary(root):
    objects = [root] + list(root.children_recursive)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    minimum, maximum = bounds(objects)
    return {
        "root": root.name,
        "root_position": list(root.matrix_world.translation),
        "objects": len(objects),
        "mesh_objects": len(meshes),
        "vertices": sum(len(obj.data.vertices) for obj in meshes),
        "triangles": sum(len(obj.data.polygons) for obj in meshes),
        "bounds_min": list(minimum),
        "bounds_max": list(maximum),
        "dimensions_meters": list(maximum - minimum),
        "object_names": sorted(obj.name for obj in objects),
    }


def presentation(scene, objects):
    minimum, maximum = bounds(objects)
    center = (minimum + maximum) * 0.5
    span = max(maximum - minimum)
    collection = bpy.data.collections.new("PREVIEW — camera and lights")
    scene.collection.children.link(collection)
    data = bpy.data.cameras.new("Car Overview")
    data.type = "ORTHO"
    data.ortho_scale = span * 1.35
    data.clip_start = 0.01
    data.clip_end = 200
    camera = bpy.data.objects.new("Car Overview", data)
    collection.objects.link(camera)
    camera.location = center + Vector((1.05, 1.5, 0.95)) * span
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    for name, position, power, size in (
        ("Key — softbox", (4, 5, 7), 1100, 6),
        ("Fill — softbox", (-4, 2, 4), 650, 5),
        ("Rim — softbox", (1, -5, 6), 900, 4),
    ):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = power
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        collection.objects.link(light)
        light.location = center + Vector(position)
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    world = bpy.data.worlds.new("Car Preview World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.17, 0.20, 0.25, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.unit_settings.length_unit = "METERS"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.clip_start = 0.01
            space.clip_end = 1000
            space.shading.type = "MATERIAL"
            space.overlay.show_floor = True
            space.overlay.show_extras = False
            region = space.region_3d
            region.view_perspective = "ORTHO"
            region.view_location = center
            region.view_rotation = camera.rotation_euler.to_quaternion()
            region.view_distance = span * 1.5


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if source == output:
        raise ValueError("Output must be separate from the read-only source")
    if output.exists():
        raise FileExistsError(f"Will not overwrite an existing edited file: {output}")
    source_hash = file_hash(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise ValueError(f"Car root missing: {ROOT_NAME}")
    source_summary = summary(root)
    if source_summary["mesh_objects"] != 23:
        raise AssertionError(f"Unexpected car geometry: {source_summary['mesh_objects']} mesh objects")
    keep = set([root] + list(root.children_recursive))
    original_matrix = root.matrix_world.copy()
    root.parent = None
    original_matrix.translation = Vector((0, 0, 0))
    root.matrix_world = original_matrix
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    collection = bpy.data.collections.new("Scarbound Car — EDITABLE")
    scene.collection.children.link(collection)
    for obj in keep:
        for previous in list(obj.users_collection):
            previous.objects.unlink(obj)
        collection.objects.link(obj)
    for previous in list(bpy.data.collections):
        if previous != collection:
            bpy.data.collections.remove(previous)
    scene.camera = None
    for text in list(bpy.data.texts):
        bpy.data.texts.remove(text)
    text = bpy.data.texts.new("START HERE — Scarbound Car")
    text.write("""Scarbound Car v10 — модель машины для редактирования
===================================================
Машина, небольшой M249 на правой стороне капота, гарпунная турель и
Квазимодо сохранены отдельными объектами с исходной иерархией.
Корень REFERENCE_PlayerCar_DoNotMerge находится в (0, 0, 0).
Одна единица Blender = один метр; Z направлена вверх.

Материалы используют атрибут цвета Color. Для просмотра цветов включите
Material Preview. Unity_MaterialParams UV хранит gloss/metal, а не текстурную
развёртку. Свет и shader — приближение игрового отображения.

Редактируйте объекты в коллекции Scarbound Car — EDITABLE.
PREVIEW содержит только камеру и свет, в FBX они не входят.
Эта копия не связана с проектом Unity автоматически: игровые изменения
потребуют отдельного переноса и настройки. Исходные файлы уровней сохранены.
""")
    bpy.context.view_layer.update()
    presentation(scene, list(keep))
    scene["car_source_read_only"] = str(source)
    scene["car_source_sha256"] = source_hash
    scene["car_export_note"] = "Standalone car subtree, centered at origin, meters; no game code or source blend edited."
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    fbx = output.with_suffix(".fbx")
    for obj in keep:
        obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=str(fbx), use_selection=True, object_types={"EMPTY", "MESH"},
        apply_unit_scale=True, global_scale=1.0, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
        use_custom_props=True, mesh_smooth_type="FACE", add_leaf_bones=False,
        bake_anim=False, path_mode="AUTO", colors_type="LINEAR",
    )
    preview = output.with_name(output.stem + "_preview.png")
    scene.render.filepath = str(preview)
    bpy.ops.render.render(write_still=True)
    # Reopen the actual saved artifact, not just the in-memory working scene.
    bpy.ops.wm.open_mainfile(filepath=str(output))
    actual_root = bpy.data.objects.get(ROOT_NAME)
    actual = summary(actual_root)
    expected = {**source_summary, "root_position": [0.0, 0.0, 0.0]}
    for field in ("objects", "mesh_objects", "vertices", "triangles", "object_names"):
        if actual[field] != expected[field]:
            raise AssertionError(f"Reopened output changed {field}: {actual[field]} vs {expected[field]}")
    if max(abs(value) for value in actual["root_position"]) > 1e-6:
        raise AssertionError("Car is not centered at the origin")
    if max(abs(a - b) for a, b in zip(actual["dimensions_meters"], source_summary["dimensions_meters"])) > 1e-4:
        raise AssertionError("Car size changed during extraction")
    if file_hash(source) != source_hash:
        raise AssertionError("Read-only source file unexpectedly changed")
    report = {
        "verified": True,
        "source": str(source), "source_sha256": source_hash, "source_unchanged": True,
        "blend": str(output), "fbx": str(fbx), "preview": str(preview),
        "blender_version": bpy.app.version_string, "meters_per_unit": 1,
        **actual,
    }
    output.with_suffix(".validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SCARBOUND_CAR_EXPORT " + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
