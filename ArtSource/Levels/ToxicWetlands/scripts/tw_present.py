"""Presentation lighting, cameras and renders for the Toxic Wetlands pass (Blender only, never exported).

Same recipe as the v13 Dust Flats presentation (rg_light.py): soft key sun at the Unity sun azimuth, a cool
counter fill and a warm-olive ground bounce, EEVEE ray-traced AO/GI, Khronos PBR Neutral tonemapping.
The game camera matches Unity's CameraRig: pitch 54 deg, vertical FOV 46 deg, 540 x 1170, distance from the
visible ground half-width 13.5 m. Unity (x, y, z) -> Blender (x, z, y).
"""
import math

import bpy
from mathutils import Euler, Vector

COL_NAME = 'PREVIEW — Toxic Wetlands cameras and lights (not exported)'
SUN_DIR = Vector((0.4936, -0.2625, -0.8290)).normalized()
PITCH, FOV_V, GW, GH, HALF_W = 54.0, 46.0, 540, 1170, 13.5


def coll():
    c = bpy.data.collections.get(COL_NAME)
    if c is None:
        c = bpy.data.collections.new(COL_NAME)
        bpy.context.scene.collection.children.link(c)
    return c


def sun(name, direction, energy, color, angle_deg, shadow=True, specular=1.0):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ld = bpy.data.lights.new(name, 'SUN')
        ob = bpy.data.objects.new(name, ld)
        coll().objects.link(ob)
    ld = ob.data
    ld.energy, ld.color, ld.angle = energy, color, math.radians(angle_deg)
    ld.use_shadow = shadow
    ld.specular_factor = specular
    ob.rotation_euler = Vector(direction).normalized().to_track_quat('-Z', 'Y').to_euler()
    ob['tw_note'] = 'presentation light (not exported)'
    return ob


def world(haze=(0.62, 0.66, 0.56)):
    w = bpy.data.worlds.get('Toxic Wetlands Presentation World') or bpy.data.worlds.new('Toxic Wetlands Presentation World')
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.40; cr.elements[0].color = (0.46, 0.44, 0.27, 1)    # olive mud bounce
    cr.elements[1].position = 0.62; cr.elements[1].color = (0.52, 0.60, 0.72, 1)    # cool grey-blue sky
    e = cr.elements.new(0.50); e.color = (0.70, 0.73, 0.64, 1)                       # pale green-grey horizon haze
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.55
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bgc = nt.nodes.new('ShaderNodeBackground')
    bgc.inputs['Color'].default_value = (haze[0], haze[1], haze[2], 1); bgc.inputs['Strength'].default_value = 1.0
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1]); nt.links.new(bgc.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    bpy.context.scene.world = w
    return w


def setup(samples=32, exposure=-0.25):
    sc = bpy.context.scene
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and not o.name.startswith('TW '):
            o.hide_render = True
    sun('TW Key Sun', SUN_DIR, 3.3, (1.0, 0.95, 0.84), 3.0, True)
    sun('TW Cool Fill', (-SUN_DIR.x, -SUN_DIR.y, -0.55), 0.45, (0.62, 0.68, 1.0), 30.0, False, 0.0)
    sun('TW Mud Bounce', (0.15, 0.2, 1.0), 0.28, (0.80, 0.78, 0.50), 60.0, False, 0.0)
    world()
    sc.render.engine = 'BLENDER_EEVEE'
    ee = sc.eevee
    ee.use_shadows = True
    ee.shadow_ray_count = 2; ee.shadow_step_count = 8
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN'
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    ee.fast_gi_distance = 2.5
    ee.fast_gi_quality = 0.6
    ee.taa_render_samples = samples
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'AgX'
    vs.look = 'None'; vs.exposure = exposure; vs.gamma = 1.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False
    return sc


def game_camera(name, car_xy, floor_z=0.0, zoom=1.0):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = 'PERSP'; cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(FOV_V)
    cd.clip_start = 1.0; cd.clip_end = 220.0
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, cd)
        coll().objects.link(cam)
    t = math.tan(math.radians(FOV_V * 0.5))
    d = max(HALF_W / (t * GW / GH), 15.0 / t) * zoom
    focus = Vector((car_xy[0], car_xy[1] + 2.5, floor_z))
    p = math.radians(PITCH)
    cam.location = focus + Vector((0, -math.cos(p) * d, math.sin(p) * d))
    cam.rotation_euler = Euler((math.radians(90 - PITCH), 0, 0), 'XYZ')
    return cam


def free_camera(name, loc, look, lens=35.0, ortho=None):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else:
        cd.type = 'PERSP'; cd.lens = lens
    cd.sensor_fit = 'AUTO'; cd.clip_start = 0.05; cd.clip_end = 3000
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, cd)
        coll().objects.link(cam)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return cam


def render(cam, path, res=(1200, 900), samples=None):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    if samples:
        sc.eevee.taa_render_samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def ground_plane(size=60.0, color=(0.20, 0.19, 0.13), z=0.0, name='TW_PreviewGround'):
    """Neutral mud-coloured studio floor for asset sheets."""
    me = bpy.data.meshes.get(name)
    if me is None:
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        m = bpy.data.materials.new(name + '_mat')
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1)
        b.inputs['Roughness'].default_value = 0.85
        me.materials.append(m)
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in coll().objects:
        coll().objects.link(ob)
    ob.location = (0, 0, z)
    return ob
