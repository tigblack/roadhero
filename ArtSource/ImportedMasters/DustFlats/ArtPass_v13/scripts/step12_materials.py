"""v12 step: water material (Blender preview of a stylized shallow water shader) + wet-ground support."""
import bpy


def water_material():
    m = bpy.data.materials.get('River_Water') or bpy.data.materials.new('River_Water')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
    nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.14
    bsdf.inputs['Specular IOR Level'].default_value = 0.55
    bsdf.inputs['IOR'].default_value = 1.33
    # alpha: more see-through looking straight down, more reflective at grazing angles (soft fresnel)
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.0; mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.42; mr.inputs['To Max'].default_value = 0.85
    nt.links.new(lw.outputs['Facing'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], bsdf.inputs['Alpha'])
    # calm ripples: two noise layers in world space -> bump
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.9; n1.inputs['Detail'].default_value = 2.0
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 3.1; n2.inputs['Detail'].default_value = 1.0
    sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'MULTIPLY'; sc.inputs[1].default_value = (1.0, 2.6, 1.0)
    nt.links.new(tc.outputs['Object'], sc.inputs[0])
    nt.links.new(sc.outputs['Vector'], n1.inputs['Vector']); nt.links.new(tc.outputs['Object'], n2.inputs['Vector'])
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'ADD'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.35
    nt.links.new(n2.outputs['Fac'], mul.inputs[0])
    nt.links.new(n1.outputs['Fac'], add.inputs[0]); nt.links.new(mul.outputs[0], add.inputs[1])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.18; bump.inputs['Distance'].default_value = 0.05
    nt.links.new(add.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    try:
        m.use_transparency_overlap = False
    except Exception:
        pass
    m['unity_shader'] = 'NEW: RoadGame/Water (transparent, not in the project yet)'
    m['unity_notes'] = 'Colour = vertex RGB; alpha ~0.42 (top-down) .. 0.85 (grazing); gloss 0.85; ripple normal from 2 scrolling noises; depth tint optional'
    m['artpass_v12'] = 'new: stylized shallow water (Blender preview)'
    return m


def run(ctx):
    ctx['mats']['River_Water'] = water_material()
    print('STEP12 materials done', flush=True)
