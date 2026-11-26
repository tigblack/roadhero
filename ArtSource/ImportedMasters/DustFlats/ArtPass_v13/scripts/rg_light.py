"""Presentation lighting for DustFlats v11 (Blender only; not exported).
Key: soft warm sun = Unity Euler(56,118,0) -> Blender direction (0.494,-0.262,-0.829).
Fill: cool lavender sky dome from the world (top) + warm sand bounce (world bottom) + weak cool counter-sun.
Contact shadows: EEVEE ray-traced/horizon-scan AO. Tonemapping: Khronos PBR Neutral (Unity uses Neutral)."""
import bpy, math
from mathutils import Vector

COL_NAME = "PREVIEW — cameras and lights (not exported)"
SUN_DIR = Vector((0.4936, -0.2625, -0.8290)).normalized()

def _coll(sc):
    c = bpy.data.collections.get(COL_NAME)
    if c is None:
        c = bpy.data.collections.new(COL_NAME); sc.collection.children.link(c)
    return c

def _sun(sc, name, direction, energy, color, angle_deg, shadow=True, diffuse=1.0, specular=1.0):
    c = _coll(sc)
    ob = bpy.data.objects.get(name)
    if ob is None:
        ld = bpy.data.lights.new(name, 'SUN'); ob = bpy.data.objects.new(name, ld); c.objects.link(ob)
    ld = ob.data
    ld.energy = energy; ld.color = color; ld.angle = math.radians(angle_deg)
    ld.use_shadow = shadow
    ld.diffuse_factor = diffuse; ld.specular_factor = specular
    ob.rotation_euler = Vector(direction).normalized().to_track_quat('-Z', 'Y').to_euler()
    ob.location = (0, -80, 60)
    ob["artpass_v11"] = "presentation light (not exported)"
    return ob

def _world(sc):
    w = bpy.data.worlds.get("DustFlats v11 Presentation World") or bpy.data.worlds.new("DustFlats v11 Presentation World")
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    # Lighting dome: hemisphere gradient (cool lavender sky above, pale horizon, warm sand bounce below)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.40; cr.elements[0].color = (0.78, 0.55, 0.36, 1)   # warm sand bounce
    cr.elements[1].position = 0.62; cr.elements[1].color = (0.50, 0.50, 0.86, 1)   # cool lavender-blue sky
    e = cr.elements.new(0.50); e.color = (0.80, 0.74, 0.70, 1)                     # pale warm horizon
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.52
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    # Camera sees a soft dusty sky colour instead of the lighting dome
    bgc = nt.nodes.new('ShaderNodeBackground'); bgc.inputs['Color'].default_value = (0.70, 0.62, 0.58, 1); bgc.inputs['Strength'].default_value = 1.0
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1]); nt.links.new(bgc.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sc.world = w
    return w

def setup(sc=None):
    sc = sc or bpy.context.scene
    old = bpy.data.objects.get('Preview Sun')
    if old: old.hide_render = True; old.hide_viewport = True
    _sun(sc, 'V11 Key Sun', SUN_DIR, 3.4, (1.0, 0.92, 0.80), 3.0, True)
    # cool counter fill from the opposite side, no shadows, no highlights
    fill_dir = Vector((-SUN_DIR.x, -SUN_DIR.y, -0.55))
    _sun(sc, 'V11 Cool Fill', fill_dir, 0.42, (0.60, 0.62, 1.0), 30.0, False, 1.0, 0.0)
    # warm bounce from the sand (light travelling upward)
    _sun(sc, 'V11 Sand Bounce', (0.15, 0.2, 1.0), 0.30, (1.0, 0.68, 0.42), 60.0, False, 1.0, 0.0)
    _world(sc)
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
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'AgX'
    vs.look = 'None'; vs.exposure = -0.25; vs.gamma = 1.0
    sc.display_settings.display_device = 'sRGB'
    return sc
