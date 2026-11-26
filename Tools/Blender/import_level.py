"""Import a RoadGame runtime level snapshot into an editable Blender scene.

Run with Blender, not system Python::

    Blender --background --factory-startup --python Tools/Blender/import_level.py -- \
        --source scene.json --output RoadGame_Level.blend --fbx RoadGame_Level.fbx

The source is produced by RoadGame's Unity level exporter. All transforms use
meters. Unity (X right, Y up, Z forward) is converted to Blender (X, Y, Z up)
with (x, z, y); the reflection is compensated by reversing triangle winding.
Materials approximate RoadGame/Toon with its original vertex colors and UV1
gloss/metal values. Unity-specific lighting and gameplay are not baked here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


AXIS_CHANGE = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fbx", type=Path)
    parser.add_argument("--render-preview", type=Path)
    return parser.parse_args(argv)


def triples(values):
    return [(values[i], values[i + 2], values[i + 1]) for i in range(0, len(values), 3)]


def key(value):
    return str(value)


def local_matrix(node):
    position = node.get("position", (0, 0, 0))
    rotation = node.get("rotation", (0, 0, 0, 1))
    scale = node.get("scale", (1, 1, 1))
    quaternion = Quaternion((rotation[3], rotation[0], rotation[1], rotation[2]))
    if quaternion.magnitude < 1e-8:
        quaternion = Quaternion()
    else:
        quaternion.normalize()
    unity = Matrix.LocRotScale(Vector(position), quaternion, Vector(scale))
    return AXIS_CHANGE @ unity @ AXIS_CHANGE


def material_from_source(item, source_dir=None, warnings=None):
    material = bpy.data.materials.new(item.get("name") or f"Unity Material {item['id']}")
    color = list(item.get("color") or (1, 1, 1, 1))
    if len(color) == 3:
        color.append(1)
    material.diffuse_color = (*color[:3], 1.0)
    material.use_nodes = True
    material["unity_id"] = key(item["id"])
    material["unity_shader"] = item.get("shader", "")
    material["unity_base_color"] = [float(value) for value in color]
    material["preview_note"] = "RoadGame/Toon approximation: Color RGB × base color; alpha is self-light, not transparency."
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (730, 120)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (420, 120)
    principled.inputs["Roughness"].default_value = float(item.get("roughness", 0.8))
    principled.inputs["Metallic"].default_value = float(item.get("metallic", 0.0))
    vertex_color = nodes.new("ShaderNodeVertexColor")
    vertex_color.layer_name = "Color"
    vertex_color.label = "Original Unity vertex colors"
    vertex_color.location = (-600, 200)
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1
    multiply.inputs[2].default_value = (*color[:3], 1)
    multiply.label = "Unity Color × _BaseColor"
    multiply.location = (-330, 230)
    links.new(vertex_color.outputs["Color"], multiply.inputs[1])
    albedo = multiply.outputs["Color"]
    texture_path = item.get("baseMap")
    if texture_path and source_dir:
        texture_path = Path(texture_path)
        if not texture_path.is_absolute():
            texture_path = source_dir / texture_path
        if texture_path.is_file():
            image = bpy.data.images.load(str(texture_path), check_existing=True)
            image.colorspace_settings.name = "sRGB"
            texture = nodes.new("ShaderNodeTexImage")
            texture.image = image
            texture.extension = "REPEAT"
            texture.location = (-610, 530)
            world_uv = float(item.get("worldUV", 0))
            if world_uv > 0:
                geometry = nodes.new("ShaderNodeNewGeometry")
                geometry.location = (-1040, 530)
                world_scale = nodes.new("ShaderNodeVectorMath")
                world_scale.operation = "SCALE"
                world_scale.inputs[3].default_value = world_uv
                world_scale.label = "Unity world XZ → Blender world XY"
                world_scale.location = (-830, 530)
                links.new(geometry.outputs["Position"], world_scale.inputs[0])
                links.new(world_scale.outputs["Vector"], texture.inputs["Vector"])
            else:
                uv = nodes.new("ShaderNodeUVMap")
                uv.uv_map = "UVMap"
                uv.location = (-1250, 530)
                uv_scale = nodes.new("ShaderNodeVectorMath")
                uv_scale.operation = "MULTIPLY"
                scale = item.get("baseMapScale") or [1, 1]
                uv_scale.inputs[1].default_value = (scale[0], scale[1], 1)
                uv_scale.location = (-1050, 530)
                links.new(uv.outputs["UV"], uv_scale.inputs[0])
                uv_offset = nodes.new("ShaderNodeVectorMath")
                uv_offset.operation = "ADD"
                offset = item.get("baseMapOffset") or [0, 0]
                uv_offset.inputs[1].default_value = (offset[0], offset[1], 0)
                uv_offset.location = (-830, 530)
                links.new(uv_scale.outputs["Vector"], uv_offset.inputs[0])
                links.new(uv_offset.outputs["Vector"], texture.inputs["Vector"])
            tex_multiply = nodes.new("ShaderNodeMixRGB")
            tex_multiply.blend_type = "MULTIPLY"
            tex_multiply.inputs[0].default_value = 1
            tex_multiply.location = (0, 250)
            links.new(albedo, tex_multiply.inputs[1])
            links.new(texture.outputs["Color"], tex_multiply.inputs[2])
            albedo = tex_multiply.outputs["Color"]
        elif warnings is not None:
            warnings.append(f"Material {item['id']}: missing base map {texture_path}")
    links.new(albedo, principled.inputs["Base Color"])
    links.new(albedo, principled.inputs["Emission Color"])
    self_lit = nodes.new("ShaderNodeMath")
    self_lit.operation = "SUBTRACT"
    self_lit.inputs[0].default_value = 1
    self_lit.label = "Unity self-lit = 1 − vertex alpha"
    self_lit.location = (-280, -50)
    links.new(vertex_color.outputs["Alpha"], self_lit.inputs[1])
    links.new(self_lit.outputs[0], principled.inputs["Emission Strength"])
    # UV1 in RoadGame is a material parameter channel, not a second texture UV.
    params = nodes.new("ShaderNodeUVMap")
    params.uv_map = "Unity_MaterialParams"
    params.label = "Unity UV1: X gloss, Y metal"
    params.location = (-600, -270)
    split = nodes.new("ShaderNodeSeparateXYZ")
    split.location = (-360, -270)
    links.new(params.outputs["UV"], split.inputs[0])
    roughness = nodes.new("ShaderNodeMath")
    roughness.operation = "SUBTRACT"
    roughness.use_clamp = True
    roughness.inputs[0].default_value = 1
    roughness.location = (-100, -240)
    links.new(split.outputs["X"], roughness.inputs[1])
    links.new(roughness.outputs[0], principled.inputs["Roughness"])
    links.new(split.outputs["Y"], principled.inputs["Metallic"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def mesh_from_source(item, fallback_material, warnings):
    def trace(stage):
        if item["id"] == "mesh_000002":
            print(f"ROADGAME_MESH_TRACE {stage}", flush=True)

    vertices = item.get("vertices", [])
    if len(vertices) % 3:
        raise ValueError(f"Mesh {item['id']} has incomplete vertex coordinates")
    vertex_count = len(vertices) // 3
    faces = []
    slots = []
    max_slot = 0
    zero_area_triangles = 0
    for submesh in item.get("submeshes", []):
        triangles = submesh.get("triangles", [])
        if len(triangles) % 3:
            raise ValueError(f"Mesh {item['id']} has incomplete triangles")
        slot = int(submesh.get("materialSlot", len(slots)))
        max_slot = max(max_slot, slot)
        for i in range(0, len(triangles), 3):
            triangle = (triangles[i], triangles[i + 2], triangles[i + 1])
            if min(triangle) < 0 or max(triangle) >= vertex_count:
                raise ValueError(f"Mesh {item['id']} triangle points outside its vertex buffer")
            # MeshBuilder welds matching vertices after triangulation. This can
            # leave triangles with repeated indices. They have no visible area
            # in Unity, but Blender 5.2's custom-normal setter crashes on them.
            if len(set(triangle)) != 3:
                zero_area_triangles += 1
                continue
            a, b, c = (Vector(vertices[index * 3:index * 3 + 3]) for index in triangle)
            if (b - a).cross(c - a).length_squared <= 1e-24:
                zero_area_triangles += 1
                continue
            faces.append(triangle)
            slots.append(slot)
    mesh = bpy.data.meshes.new(item.get("name") or f"Unity Mesh {item['id']}")
    trace("from_pydata")
    mesh.from_pydata(triples(vertices), [], faces)
    trace("initial_update")
    mesh.update()
    mesh["unity_id"] = key(item["id"])
    mesh["unity_zero_area_triangles_removed"] = zero_area_triangles
    if zero_area_triangles:
        warnings.append(f"Mesh {item['id']}: omitted {zero_area_triangles} zero-area triangles from Unity's welded mesh")
    for _ in range(max_slot + 1):
        mesh.materials.append(fallback_material)
    if slots:
        mesh.polygons.foreach_set("material_index", slots)
    trace("colors")
    loop_vertices = [loop.vertex_index for loop in mesh.loops]
    colors = item.get("colors") or []
    if colors and len(colors) != vertex_count * 4:
        warnings.append(f"Mesh {item['id']}: invalid color buffer; using white")
        colors = []
    attribute = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
    corner_colors = []
    for vertex in loop_vertices:
        corner_colors.extend(colors[vertex * 4:vertex * 4 + 4] if colors else (1, 1, 1, 1))
    attribute.data.foreach_set("color", corner_colors)
    mesh.color_attributes.active_color = attribute
    mesh.color_attributes.render_color_index = 0
    trace("uv")
    for source_channel, layer_name in (("uv0", "UVMap"), ("uv1", "Unity_MaterialParams")):
        uv = item.get(source_channel) or []
        if uv and len(uv) != vertex_count * 2:
            warnings.append(f"Mesh {item['id']}: invalid {source_channel}; using zero")
            uv = []
        layer = mesh.uv_layers.new(name=layer_name)
        corner_uv = []
        for vertex in loop_vertices:
            corner_uv.extend(uv[vertex * 2:vertex * 2 + 2] if uv else (0, 0))
        layer.data.foreach_set("uv", corner_uv)
    # Unity already split vertices where a hard normal seam is required.
    normals = item.get("normals") or []
    trace("normals")
    if len(normals) == len(vertices) and len(mesh.polygons):
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        if hasattr(mesh, "normals_split_custom_set_from_vertices"):
            mesh.normals_split_custom_set_from_vertices(triples(normals))
        else:
            warnings.append(f"Mesh {item['id']}: Blender API has no custom vertex normal setter")
    trace("final_update")
    mesh.update()
    trace("done")
    return mesh


def bounds_of(objects):
    points = [obj.matrix_world @ Vector(corner)
              for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    if not points:
        return Vector((-10, -10, 0)), Vector((10, 10, 10))
    return (Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
            Vector(tuple(max(point[axis] for point in points) for axis in range(3))))


def focus_bounds(metadata, all_bounds):
    source = metadata.get("firstZoneBounds")
    if isinstance(source, dict) and source.get("min") and source.get("max"):
        a, b = source["min"], source["max"]
        return Vector((a[0], a[2], a[1])), Vector((b[0], b[2], b[1]))
    return all_bounds


def setup_presentation(scene, objects, metadata):
    all_bounds = bounds_of(objects)
    minimum, maximum = focus_bounds(metadata, all_bounds)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    span = max(size.x, size.y, size.z, 20)
    preview_collection = bpy.data.collections.new("PREVIEW — cameras and lights (not exported)")
    scene.collection.children.link(preview_collection)
    camera_data = bpy.data.cameras.new("Level Overview")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = span * 1.35
    camera_data.clip_end = max(10000, span * 10)
    camera = bpy.data.objects.new("Level Overview", camera_data)
    preview_collection.objects.link(camera)
    camera.location = center + Vector((0.65, -0.9, 1.15)).normalized() * span * 2
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    light_data = bpy.data.lights.new("Preview Sun", "SUN")
    light_data.energy = 2.0
    light_data.angle = math.radians(12)
    light = bpy.data.objects.new("Preview Sun", light_data)
    preview_collection.objects.link(light)
    light.rotation_euler = (math.radians(28), math.radians(-25), math.radians(-35))
    world = bpy.data.worlds.new("RoadGame Preview World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.39, 0.49, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.65
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "Medium High Contrast"
    except TypeError:
        scene.view_settings.look = "None"
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 32
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.unit_settings.length_unit = "METERS"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.clip_end = max(10000, span * 10)
            space.shading.type = "MATERIAL"
            space.shading.color_type = "MATERIAL"
            space.shading.studiolight_rotate_z = math.radians(30)
            space.overlay.show_floor = True
            region = space.region_3d
            region.view_perspective = "ORTHO"
            region.view_rotation = camera.rotation_euler.to_quaternion()
            region.view_location = center
            region.view_distance = span * 1.2
    return {
        "world_bounds_blender": {"min": list(all_bounds[0]), "max": list(all_bounds[1])},
        "focus_bounds_blender": {"min": list(minimum), "max": list(maximum)},
    }


def organize_geometry(scene, objects):
    names = ("Zone_00_DustFlats + Intro", "Zone_01_RustCanyon", "Zone_02_SaltFlats", "Zone_03_ToxicMarsh")
    collections = []
    roofs = []
    for name in names:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
        collections.append(collection)
        roof_collection = bpy.data.collections.new(name + " — Roofs (toggle to inspect interiors)")
        collection.children.link(roof_collection)
        roofs.append(roof_collection)
    references = bpy.data.collections.new("References — vehicle and scale guides")
    scene.collection.children.link(references)
    counts = {name: 0 for name in names}
    for obj in objects.values():
        if obj.type != "MESH":
            continue
        minimum, maximum = bounds_of([obj])
        midpoint = (minimum.y + maximum.y) * 0.5
        zone = max(0, min(3, int(math.floor((midpoint + 100) / 200))))
        is_roof = any(token in obj.name.lower() for token in ("roof", "tunnellid", "tunnel_lid"))
        target = references if obj.get("unity_category") == "reference" else roofs[zone] if is_roof else collections[zone]
        for existing in list(obj.users_collection):
            existing.objects.unlink(obj)
        target.objects.link(obj)
        obj["editing_zone"] = -1 if target == references else zone
        if target != references:
            counts[names[zone]] += 1
    return counts


def add_readme(scene, source_path):
    text = bpy.data.texts.new("START HERE — RoadGame level")
    text.write("""RoadGame — editable level snapshot
==================================
One Blender unit = one meter. Z is up. Objects and their local hierarchy are
preserved from Unity. Meshes are shared when the original scene instanced them;
use Object > Relations > Make Single User > Object & Data before changing only
one instance. The original Unity IDs and local transforms are custom properties.

Use Material Preview to see the original vertex colors. The Color attribute
contains painted colors and self-light alpha; Unity_MaterialParams UV contains
gloss (X) and metal (Y). The node materials approximate Unity's custom shader;
lighting, shadows, ground dust and roof fading will not be identical in Blender.

This is geometry for visual editing, not a complete playable game. Colliders,
AI, terrain height queries, triggers, rewards, and save data do not run here.
Reimporting edits into gameplay needs a deliberate Unity integration step.
The PREVIEW collection contains an overview camera and sun; FBX excludes it.

Source JSON: """ + str(source_path) + "\n")
    scene["roadgame_editing_notes"] = "See text: START HERE — RoadGame level"


def main():
    args = arguments()
    args.source = args.source.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    print(f"ROADGAME_STAGE reading {args.source}", flush=True)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    if source.get("schema") != 1:
        raise ValueError(f"Unsupported scene schema: {source.get('schema')}")
    warnings = []
    print(f"ROADGAME_STAGE loaded: {len(source.get('nodes', []))} nodes, {len(source.get('meshes', []))} meshes", flush=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    collection = bpy.data.collections.new("RoadGame — EDITABLE LEVEL")
    scene.collection.children.link(collection)
    fallback = material_from_source({"id": "_fallback", "name": "Unassigned — white", "color": [1, 1, 1, 1]})
    materials = {}
    for item in source.get("materials", []):
        print(f"ROADGAME_STAGE material {item['id']} {item.get('name', '')}", flush=True)
        materials[key(item["id"])] = material_from_source(item, args.source.parent, warnings)
    meshes = {}
    for index, item in enumerate(source.get("meshes", [])):
        print(f"ROADGAME_STAGE mesh {index + 1}/{len(source['meshes'])} {item['id']} {item.get('name', '')}", flush=True)
        meshes[key(item["id"])] = mesh_from_source(item, fallback, warnings)
    print("ROADGAME_STAGE creating objects", flush=True)
    objects = {}
    source_nodes = source.get("nodes", [])
    print("ROADGAME_STAGE parenting objects", flush=True)
    for node in source_nodes:
        node_id = key(node["id"])
        if node_id in objects:
            raise ValueError(f"Duplicate node ID: {node_id}")
        mesh_id = node.get("meshId")
        mesh = meshes.get(key(mesh_id)) if mesh_id is not None else None
        if mesh_id is not None and mesh is None:
            warnings.append(f"Node {node_id}: missing mesh {mesh_id}; imported as empty")
        obj = bpy.data.objects.new(node.get("name") or f"Unity Object {node_id}", mesh)
        collection.objects.link(obj)
        obj["unity_id"] = node_id
        obj["unity_mesh_id"] = key(mesh_id) if mesh_id is not None else ""
        # FBX's custom-vector writer requires float arrays, including exact zero
        # and one values which the JSON reader otherwise represents as ints.
        obj["unity_local_position"] = [float(value) for value in node.get("position", [0, 0, 0])]
        obj["unity_local_rotation_xyzw"] = [float(value) for value in node.get("rotation", [0, 0, 0, 1])]
        obj["unity_local_scale"] = [float(value) for value in node.get("scale", [1, 1, 1])]
        obj["unity_category"] = node.get("category", "")
        obj["unity_active_self"] = bool(node.get("active", True))
        obj["unity_renderer_enabled"] = bool(node.get("renderer_enabled", True))
        if mesh:
            material_ids = node.get("materialIds") or []
            for slot_index, slot in enumerate(obj.material_slots):
                slot.link = "OBJECT"
                mat_id = material_ids[slot_index] if slot_index < len(material_ids) else None
                slot.material = materials.get(key(mat_id), fallback)
        else:
            obj.empty_display_type = "PLAIN_AXES"
            obj.empty_display_size = 1
        objects[node_id] = obj
    for node in source_nodes:
        obj = objects[key(node["id"])]
        parent_id = node.get("parentId")
        if parent_id is not None:
            if key(parent_id) not in objects:
                raise ValueError(f"Node {node['id']} has missing parent {parent_id}")
            seen = {key(node["id"])}
            parent = objects[key(parent_id)]
            ancestor = parent
            while ancestor:
                if ancestor["unity_id"] in seen:
                    raise ValueError(f"Cyclic parent hierarchy around node {node['id']}")
                seen.add(ancestor["unity_id"])
                ancestor = ancestor.parent
            obj.parent = parent
            obj.matrix_parent_inverse.identity()
        obj.matrix_basis = local_matrix(node)
    for obj in objects.values():
        enabled = bool(obj["unity_renderer_enabled"])
        ancestor = obj
        while ancestor is not None:
            enabled = enabled and bool(ancestor.get("unity_active_self", True))
            ancestor = ancestor.parent
        obj.hide_viewport = not enabled
        obj.hide_render = not enabled
    bpy.context.view_layer.update()
    print("ROADGAME_STAGE organizing and presentation", flush=True)
    metadata = source.get("metadata") or {}
    zone_counts = organize_geometry(scene, objects)
    bounds = setup_presentation(scene, list(objects.values()), metadata)
    scene["roadgame_source_json"] = str(args.source)
    scene["roadgame_source_metadata"] = json.dumps(metadata, ensure_ascii=False)
    scene["roadgame_coordinate_conversion"] = "Unity (x,y,z) -> Blender (x,z,y), meters; triangle winding reversed"
    add_readme(scene, args.source)
    bpy.ops.object.select_all(action="DESELECT")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print("ROADGAME_STAGE packing textures", flush=True)
    bpy.ops.file.pack_all()
    print(f"ROADGAME_STAGE saving {args.output}", flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    fbx_result = None
    if args.fbx:
        args.fbx = args.fbx.expanduser().resolve()
        args.fbx.parent.mkdir(parents=True, exist_ok=True)
        for obj in objects.values():
            obj.select_set(True)
        try:
            bpy.ops.export_scene.fbx(
                filepath=str(args.fbx), use_selection=True, object_types={"EMPTY", "MESH"},
                apply_unit_scale=True, global_scale=1.0, apply_scale_options="FBX_SCALE_UNITS",
                axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
                use_custom_props=True, mesh_smooth_type="FACE", add_leaf_bones=False,
                bake_anim=False, path_mode="AUTO", colors_type="LINEAR",
            )
            fbx_result = str(args.fbx)
        except Exception as exc:
            warnings.append(f"FBX export failed: {type(exc).__name__}: {exc}")
            print(f"ROADGAME_FBX_WARNING: {warnings[-1]}", flush=True)
        bpy.ops.object.select_all(action="DESELECT")
    if args.render_preview:
        args.render_preview = args.render_preview.expanduser().resolve()
        args.render_preview.parent.mkdir(parents=True, exist_ok=True)
        scene.render.resolution_x = 1200
        scene.render.resolution_y = 900
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(args.render_preview)
        bpy.ops.render.render(write_still=True)
    report = {
        "source": str(args.source), "blend": str(args.output), "fbx": fbx_result,
        "blender_version": bpy.app.version_string, "schema": 1,
        "meters_per_unit": 1, "coordinate_conversion": "(x,y,z) -> (x,z,y), reverse winding",
        "objects": len(objects), "mesh_objects": sum(obj.type == "MESH" for obj in objects.values()),
        "unique_meshes": len(meshes), "materials": len(materials),
        "unique_vertices": sum(len(mesh.vertices) for mesh in meshes.values()),
        "unique_triangles": sum(len(mesh.polygons) for mesh in meshes.values()),
        "zero_area_triangles_removed": sum(mesh.get("unity_zero_area_triangles_removed", 0) for mesh in meshes.values()),
        "instanced_triangles": sum(len(obj.data.polygons) for obj in objects.values() if obj.type == "MESH"),
        "zone_mesh_counts": zone_counts,
        "render_preview": str(args.render_preview) if args.render_preview else None,
        "warnings": warnings, **bounds,
    }
    report_path = args.output.with_suffix(".import-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ROADGAME_BLENDER_IMPORT " + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
