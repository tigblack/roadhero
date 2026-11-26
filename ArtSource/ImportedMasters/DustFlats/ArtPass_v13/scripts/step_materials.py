"""Step: materials and BaseMaps (RoadGame/Toon compatible).

Blender node graph mirrors the v10 importer approximation of RoadToon:
  base = Color attribute RGB x BaseMap (UVMap or world XY / tile) ; emission strength = 1 - Color.A
  roughness = 1 - UV1.x (gloss) ; metallic = UV1.y (metal)
New materials carry unity_* custom properties describing the Unity material to create.
"""
import bpy, os
TEX_DIR_REL = '//ArtPass_v11/textures/basemap/'
TEX = {
    'ground': 'T_Ground_DustFlats_BaseMap_2K.png',
    'road':   'T_Road_Asphalt_BaseMap_1Kx2K.png',
    'rock':   'T_Rock_Strata_BaseMap_1K.png',
    'trim':   'T_Trim_Structures_BaseMap_2K.png',
}
GROUND_TILE_M = 40.0      # world metres per ground texture tile (v10: 26 m with a 512 px map)
ROAD_V_SCALE = 0.5        # road BaseMap tiling (1, 0.5): one 2048 px tile spans two v10 tiles (32 m)
ROCK_TILE_M = 6.0
TRIM_M_PER_U = 2.0


def load_image(key, abs_dir):
    fn = TEX[key]
    im = bpy.data.images.get(fn)
    path = os.path.join(abs_dir, fn)
    if im is None:
        im = bpy.data.images.load(path, check_existing=True)
    im.filepath = TEX_DIR_REL + fn
    im.colorspace_settings.name = 'sRGB'
    return im


def build_toon(mat, image=None, mapping='UV', scale=(1.0, 1.0), world_scale=None):
    """(Re)build a RoadToon-approximation node tree on 'mat'."""
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (600, 0)
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'; vc.location = (-400, 200)
    base = vc.outputs['Color']
    if image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = image; tex.location = (-200, -100)
        tex.interpolation = 'Linear'
        if mapping == 'WORLD':
            geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.location = (-800, -100)
            vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'SCALE'; vm.inputs['Scale'].default_value = world_scale
            vm.location = (-500, -100)
            nt.links.new(geo.outputs['Position'], vm.inputs[0]); nt.links.new(vm.outputs['Vector'], tex.inputs['Vector'])
        else:
            uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'; uv.location = (-800, -100)
            vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'; vm.location = (-500, -100)
            vm.inputs[1].default_value = (scale[0], scale[1], 1.0)
            nt.links.new(uv.outputs['UV'], vm.inputs[0]); nt.links.new(vm.outputs['Vector'], tex.inputs['Vector'])
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.location = (200, 150)
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(vc.outputs['Color'], mul.inputs['A']); nt.links.new(tex.outputs['Color'], mul.inputs['B'])
        base = mul.outputs['Result']
    nt.links.new(base, bsdf.inputs['Base Color'])
    nt.links.new(base, bsdf.inputs['Emission Color'])
    em = nt.nodes.new('ShaderNodeMath'); em.operation = 'SUBTRACT'; em.inputs[0].default_value = 1.0; em.location = (200, -150)
    nt.links.new(vc.outputs['Alpha'], em.inputs[1]); nt.links.new(em.outputs[0], bsdf.inputs['Emission Strength'])
    prm = nt.nodes.new('ShaderNodeUVMap'); prm.uv_map = 'Unity_MaterialParams'; prm.location = (-400, -400)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-200, -400)
    nt.links.new(prm.outputs['UV'], sep.inputs[0])
    rough = nt.nodes.new('ShaderNodeMath'); rough.operation = 'SUBTRACT'; rough.inputs[0].default_value = 1.0; rough.location = (200, -350)
    nt.links.new(sep.outputs['X'], rough.inputs[1]); nt.links.new(rough.outputs[0], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs['Y'], bsdf.inputs['Metallic'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.4
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def new_toon(name, image=None, mapping='UV', scale=(1, 1), world_scale=None, unity=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    build_toon(m, image, mapping, scale, world_scale)
    m['unity_shader'] = 'RoadGame/Toon'
    m['unity_base_color'] = [1.0, 1.0, 1.0, 1.0]
    m['preview_note'] = 'RoadGame/Toon approximation: Color RGB × BaseMap; alpha is self-light, not transparency.'
    for k, v in (unity or {}).items():
        m[k] = v
    return m


def fix_glow_preview(mat):
    """Blender-only preview: Unity draws these quads additively; render them as glowing transparent decals."""
    nt = mat.node_tree
    tex = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexImage'), None)
    if tex is None:
        return
    col = mat.get('unity_base_color', [1, 1, 1, 1])
    keep = tex.name
    for nm in [n.name for n in nt.nodes]:
        n = nt.nodes[nm]
        if nm != keep and n.bl_idname not in ('ShaderNodeUVMap', 'ShaderNodeVectorMath'):
            nt.nodes.remove(n)
    tex = nt.nodes[keep]
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (col[0], col[1], col[2], 1)
    em.inputs['Strength'].default_value = 1.2
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    mix = nt.nodes.new('ShaderNodeMixShader')
    gray = nt.nodes.new('ShaderNodeRGBToBW')
    mulf = nt.nodes.new('ShaderNodeMath'); mulf.operation = 'MULTIPLY'; mulf.inputs[1].default_value = float(col[3]) * 1.4
    nt.links.new(tex.outputs['Color'], gray.inputs[0]); nt.links.new(gray.outputs[0], mulf.inputs[0])
    nt.links.new(mulf.outputs[0], em.inputs['Strength'])
    nt.links.new(tr.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat['preview_note'] = 'Blender preview only: additive glow approximation of RoadGame/Unlit (Unity material unchanged).'


def run(ctx):
    abs_dir = os.path.join(ctx['root'], 'ArtPass_v11', 'textures', 'basemap')
    ground = bpy.data.materials['Ground']
    build_toon(ground, load_image('ground', abs_dir), 'WORLD', world_scale=1.0 / GROUND_TILE_M)
    ground['unity_world_uv'] = 1.0 / GROUND_TILE_M
    ground['unity_base_map'] = 'ArtPass_v11/textures/basemap/' + TEX['ground']
    ground['artpass_v11'] = f'new 2K ground BaseMap, world tile {GROUND_TILE_M} m (_WorldUV = 1/{GROUND_TILE_M:g})'
    road = bpy.data.materials['Road0']
    build_toon(road, load_image('road', abs_dir), 'UV', scale=(1.0, ROAD_V_SCALE))
    road['unity_base_map'] = 'ArtPass_v11/textures/basemap/' + TEX['road']
    road['unity_base_map_tiling'] = [1.0, ROAD_V_SCALE]
    road['artpass_v11'] = 'new 1Kx2K asphalt BaseMap; tiling (1, 0.5) -> one tile = 32 m of road'
    new_toon('Rock_Strata', load_image('rock', abs_dir), 'UV', unity={
        'unity_base_map': 'ArtPass_v11/textures/basemap/' + TEX['rock'],
        'artpass_v11': f'new: terracotta rock, box-projected UV0 ({ROCK_TILE_M} m tile), colour from vertex colours'})
    new_toon('Trim_Structures', load_image('trim', abs_dir), 'UV', unity={
        'unity_base_map': 'ArtPass_v11/textures/basemap/' + TEX['trim'],
        'artpass_v11': 'new: 2K trim sheet for wood/metal/concrete structures; UV0 strips, tint by vertex colours'})
    for m in bpy.data.materials:
        if m.name.startswith(('LampPool', 'RepairGlow')):
            fix_glow_preview(m)
    # keep v10 materials untouched otherwise
    ctx['mats'] = {k: bpy.data.materials[k] for k in ('Toon', 'Ground', 'Road0', 'Rock_Strata', 'Trim_Structures')}
    print('STEP materials done', flush=True)
