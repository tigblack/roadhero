"""Surface materials for the DetailedCar pass (procedural, Cycles + EEVEE, bake-ready).

Every material reads the RoadGame service attributes:
  Color.rgb             palette albedo (linear)           Color.a < 1  -> self-lit (emission), like RoadToon
  Unity_MaterialParams  x = gloss -> roughness, y = metal -> metallic
and a per-vertex `Curvature` attribute (convex > 0.5 > concave) for edge wear / cavity grime, which works the
same in EEVEE and in the Cycles bakes (no Pointiness / AO shader tricks).
"""
import math

import bmesh
import bpy
import numpy as np

SURFACES = ["MAT_CarPaint", "MAT_Metal", "MAT_Rubber", "MAT_Glass", "MAT_Cloth", "MAT_Leather", "MAT_Skin", "MAT_Wood"]


class NT:
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.x = 0

    def n(self, typ, **props):
        node = self.nt.nodes.new(typ)
        for k, v in props.items():
            setattr(node, k, v)
        node.location = (self.x, 0)
        self.x += 180
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)

    def val(self, v):
        node = self.n("ShaderNodeValue")
        node.outputs[0].default_value = v
        return node.outputs[0]

    def math(self, op, a, b=None, clamp=False):
        node = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, s in enumerate((a, b)):
            if s is None:
                continue
            if isinstance(s, (int, float)):
                node.inputs[i].default_value = s
            else:
                self.link(s, node.inputs[i])
        return node.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True, interp="LINEAR"):
        node = self.n("ShaderNodeMapRange", clamp=clamp, interpolation_type=interp)
        self.link(v, node.inputs["Value"])
        node.inputs["From Min"].default_value = a
        node.inputs["From Max"].default_value = b
        node.inputs["To Min"].default_value = c
        node.inputs["To Max"].default_value = d
        return node.outputs["Result"]

    def mixf(self, f, a, b):
        node = self.n("ShaderNodeMix", data_type="FLOAT", clamp_factor=True)
        for sock, v in ((node.inputs[0], f), (node.inputs[2], a), (node.inputs[3], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return node.outputs[0]

    def mixc(self, f, a, b, blend="MIX"):
        node = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_factor=True)
        ins = [s for s in node.inputs if s.type == "RGBA"]
        if isinstance(f, (int, float)):
            node.inputs[0].default_value = f
        else:
            self.link(f, node.inputs[0])
        for sock, v in ((ins[0], a), (ins[1], b)):
            if isinstance(v, (tuple, list)):
                sock.default_value = tuple(v) + ((1.0,) if len(v) == 3 else ())
            else:
                self.link(v, sock)
        outs = [s for s in node.outputs if s.type == "RGBA"]
        return outs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dim="3D", w=None):
        node = self.n("ShaderNodeTexNoise", noise_dimensions=dim)
        self.link(vec, node.inputs["Vector"])
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = rough
        return node.outputs["Fac"]

    def voronoi(self, vec, scale, feature="F1", out="Distance"):
        node = self.n("ShaderNodeTexVoronoi", feature=feature)
        self.link(vec, node.inputs["Vector"])
        node.inputs["Scale"].default_value = scale
        return node.outputs[out]

    def wave(self, vec, scale, distortion=2.0, detail=3.0, wave_type="BANDS", direction="X", profile="SIN"):
        node = self.n("ShaderNodeTexWave", wave_type=wave_type, bands_direction=direction, wave_profile=profile)
        self.link(vec, node.inputs["Vector"])
        node.inputs["Scale"].default_value = scale
        node.inputs["Distortion"].default_value = distortion
        node.inputs["Detail"].default_value = detail
        return node.outputs["Fac"]

    def scale_vec(self, vec, s):
        node = self.n("ShaderNodeVectorMath", operation="MULTIPLY")
        self.link(vec, node.inputs[0])
        node.inputs[1].default_value = s
        return node.outputs[0]


def _common(t, ao_dist=0.06, bevel_r=0.005):
    attr = t.n("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="Color")
    uvp = t.n("ShaderNodeUVMap", uv_map="Unity_MaterialParams")
    sep = t.n("ShaderNodeSeparateXYZ")
    t.link(uvp.outputs["UV"], sep.inputs[0])
    tc = t.n("ShaderNodeTexCoord")
    geo = t.n("ShaderNodeNewGeometry")
    sepw = t.n("ShaderNodeSeparateXYZ")
    t.link(geo.outputs["Position"], sepw.inputs[0])
    sepn = t.n("ShaderNodeSeparateXYZ")
    t.link(geo.outputs["Normal"], sepn.inputs[0])
    # cavities: self-occlusion only (parts move, so no contact AO from other objects); EEVEE + Cycles
    ao = t.n("ShaderNodeAmbientOcclusion", samples=16, only_local=True)
    ao.inputs["Distance"].default_value = ao_dist
    concave = t.maprange(ao.outputs["AO"], 0.85, 0.35)
    # convex edges: Bevel-node normal vs true normal (Cycles: previews clean in EEVEE, wear shows in the bakes)
    bev = t.n("ShaderNodeBevel", samples=8)
    bev.inputs["Radius"].default_value = bevel_r
    dot = t.n("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    t.link(bev.outputs["Normal"], dot.inputs[0])
    t.link(geo.outputs["Normal"], dot.inputs[1])
    edge = t.maprange(dot.outputs["Value"], 0.995, 0.94)
    convex = t.math("MULTIPLY", edge, t.maprange(ao.outputs["AO"], 0.7, 0.95), clamp=True)
    gloss = sep.outputs["X"]
    metal = sep.outputs["Y"]
    rough = t.maprange(gloss, 0.0, 1.0, 0.92, 0.14)
    return dict(col=attr.outputs["Color"], alpha=attr.outputs["Alpha"], gloss=gloss, metal=metal, rough=rough,
                convex=convex, concave=concave, obj=tc.outputs["Object"], z=sepw.outputs["Z"], nz=sepn.outputs["Z"])


def _bsdf(t, base, rough, metal, normal=None, alpha=None, extra=None):
    p = t.n("ShaderNodeBsdfPrincipled")
    t.link(base, p.inputs["Base Color"])
    for sock, v in (("Roughness", rough), ("Metallic", metal)):
        if isinstance(v, (int, float)):
            p.inputs[sock].default_value = v
        else:
            t.link(v, p.inputs[sock])
    if normal is not None:
        t.link(normal, p.inputs["Normal"])
    if alpha is not None:
        # self-lit like RoadToon: emission = albedo * (1 - a)
        e = t.math("SUBTRACT", 1.0, alpha, clamp=True)
        e = t.math("MULTIPLY", e, 1.15)
        t.link(base, p.inputs["Emission Color"])
        t.link(e, p.inputs["Emission Strength"])
    for k, v in (extra or {}).items():
        if isinstance(v, (int, float)):
            p.inputs[k].default_value = v
        elif isinstance(v, tuple):
            p.inputs[k].default_value = v
        else:
            t.link(v, p.inputs[k])
    out = t.n("ShaderNodeOutputMaterial")
    t.link(p.outputs["BSDF"], out.inputs["Surface"])
    return p


def _bump(t, height, strength, dist=0.002, normal=None):
    b = t.n("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    t.link(height, b.inputs["Height"])
    if normal is not None:
        t.link(normal, b.inputs["Normal"])
    return b.outputs["Normal"]


def _fresh(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.node_tree.nodes.clear()
    m.diffuse_color = (0.5, 0.5, 0.5, 1)
    return m


def build_carpaint():
    m = _fresh("MAT_CarPaint")
    t = NT(m)
    c = _common(t, 0.14, 0.008)
    obj = c["obj"]
    chips_n = t.noise(obj, 22.0, 6.0, 0.62)
    chips = t.math("MULTIPLY", t.maprange(chips_n, 0.52, 0.62), c["convex"], clamp=True)
    scratch = t.noise(t.scale_vec(obj, (1.0, 6.0, 1.0)), 30.0, 3.0, 0.5)
    chips = t.math("MAXIMUM", chips, t.math("MULTIPLY", t.maprange(scratch, 0.72, 0.76), 0.25))
    steel = (0.30, 0.31, 0.32)
    base = t.mixc(chips, c["col"], steel)
    # dust settles low on the body and in cavities; a dusty film on up-facing panels
    low = t.maprange(c["z"], 0.75, 0.25)
    patch = t.maprange(t.noise(obj, 3.0, 3.0, 0.5), 0.45, 0.75)
    dust_amt = t.math("MULTIPLY", t.math("MAXIMUM", low, t.math("MULTIPLY", c["concave"], 0.8)), patch, clamp=True)
    dust_amt = t.math("MULTIPLY", dust_amt, 0.3)
    up = t.maprange(c["nz"], 0.6, 0.95)
    dust_amt = t.math("MAXIMUM", dust_amt, t.math("MULTIPLY", t.math("MULTIPLY", up, patch), 0.035))
    base = t.mixc(dust_amt, base, (0.56, 0.45, 0.32))
    grime = t.math("MULTIPLY", c["concave"], 0.55)
    base = t.mixc(grime, base, (0.03, 0.028, 0.025))
    rough = t.math("ADD", c["rough"], t.math("MULTIPLY", t.math("SUBTRACT", t.noise(obj, 40.0, 3.0, 0.5), 0.5), 0.16))
    rough = t.mixf(chips, rough, 0.38)
    rough = t.mixf(dust_amt, rough, 0.9)
    metal = t.mixf(chips, c["metal"], 0.9)
    orange_peel = t.noise(obj, 260.0, 2.0, 0.5)
    nrm = _bump(t, orange_peel, 0.035, 0.001)
    chip_h = t.math("SUBTRACT", 1.0, chips)
    nrm = _bump(t, chip_h, 0.25, 0.0015, nrm)
    _bsdf(t, base, rough, metal, nrm, c["alpha"], {"Coat Weight": 0.35, "Coat Roughness": 0.18})
    return m


def build_metal():
    m = _fresh("MAT_Metal")
    t = NT(m)
    c = _common(t)
    obj = c["obj"]
    edge = t.math("MULTIPLY", c["convex"], t.maprange(t.noise(obj, 18.0, 4.0, 0.6), 0.3, 0.55), clamp=True)
    base = t.mixc(t.math("MULTIPLY", edge, 0.5), c["col"], (0.62, 0.63, 0.64), "MIX")
    soot = t.math("MULTIPLY", c["concave"], t.maprange(t.noise(obj, 7.0, 3.0, 0.5), 0.3, 0.7))
    base = t.mixc(t.math("MULTIPLY", soot, 0.7), base, (0.02, 0.018, 0.016))
    tarnish = t.maprange(t.noise(obj, 2.5, 4.0, 0.55), 0.45, 0.75)
    base = t.mixc(t.math("MULTIPLY", tarnish, 0.35), base, (0.72, 0.68, 0.62), "MULTIPLY")
    scratch = t.noise(t.scale_vec(obj, (1.0, 1.0, 14.0)), 55.0, 2.0, 0.4)
    rough = t.math("ADD", c["rough"], t.math("MULTIPLY", t.math("SUBTRACT", scratch, 0.5), 0.22))
    rough = t.mixf(edge, rough, 0.22)
    rough = t.mixf(soot, rough, 0.8)
    nrm = _bump(t, scratch, 0.05, 0.0006)
    _bsdf(t, base, rough, c["metal"], nrm, c["alpha"])
    return m


def build_rubber():
    m = _fresh("MAT_Rubber")
    t = NT(m)
    c = _common(t, 0.06, 0.006)
    obj = c["obj"]
    dust = t.math("MULTIPLY", t.math("MAXIMUM", c["concave"], t.maprange(c["z"], 0.35, 0.05)),
                  t.maprange(t.noise(obj, 6.0, 3.0, 0.5), 0.35, 0.7), clamp=True)
    base = t.mixc(t.math("MULTIPLY", dust, 0.45), c["col"], (0.32, 0.26, 0.19))
    wear = t.math("MULTIPLY", c["convex"], 0.35)
    base = t.mixc(wear, base, (0.08, 0.075, 0.07))
    rough = t.math("ADD", t.math("MAXIMUM", c["rough"], 0.72), t.math("MULTIPLY", t.noise(obj, 80.0, 2.0, 0.5), 0.1))
    grain = t.noise(obj, 320.0, 2.0, 0.6)
    nrm = _bump(t, grain, 0.06, 0.0005)
    _bsdf(t, base, rough, 0.0, nrm, c["alpha"])
    return m


def build_glass():
    m = _fresh("MAT_Glass")
    t = NT(m)
    c = _common(t)
    obj = c["obj"]
    smudge = t.maprange(t.noise(obj, 9.0, 4.0, 0.6), 0.45, 0.75)
    dirt = t.math("MAXIMUM", t.math("MULTIPLY", smudge, 0.25), t.math("MULTIPLY", c["concave"], 0.6))
    base = t.mixc(dirt, c["col"], (0.32, 0.27, 0.2))
    rough = t.mixf(dirt, 0.04, 0.5)
    _bsdf(t, base, rough, 0.0, None, c["alpha"], {"Specular IOR Level": 0.75, "Coat Weight": 0.5, "Coat Roughness": 0.03})
    return m


def build_cloth():
    m = _fresh("MAT_Cloth")
    t = NT(m)
    c = _common(t, 0.08, 0.006)
    obj = c["obj"]
    weave = t.noise(t.scale_vec(obj, (1.0, 1.0, 2.5)), 260.0, 2.0, 0.6)
    mottled = t.noise(obj, 9.0, 5.0, 0.6)
    base = t.mixc(t.math("MULTIPLY", t.maprange(mottled, 0.3, 0.7), 0.35), c["col"], (0.03, 0.022, 0.016), "MULTIPLY")
    dirt_low = t.maprange(c["z"], 1.05, 0.62)
    dirt = t.math("MULTIPLY", t.math("MAXIMUM", dirt_low, c["concave"]), t.maprange(t.noise(obj, 4.0, 3.0, 0.5), 0.3, 0.7), clamp=True)
    base = t.mixc(t.math("MULTIPLY", dirt, 0.5), base, (0.2, 0.15, 0.1))
    fray = t.math("MULTIPLY", c["convex"], 0.45)
    base = t.mixc(fray, base, (0.25, 0.19, 0.13))
    rough = t.math("MAXIMUM", c["rough"], 0.85)
    nrm = _bump(t, weave, 0.05, 0.0006)
    nrm = _bump(t, mottled, 0.06, 0.002, nrm)
    _bsdf(t, base, rough, 0.0, nrm, c["alpha"], {"Sheen Weight": 0.18, "Sheen Roughness": 0.5})
    return m


def build_leather():
    m = _fresh("MAT_Leather")
    t = NT(m)
    c = _common(t)
    obj = c["obj"]
    grain = t.voronoi(obj, 260.0)
    crease = t.noise(t.scale_vec(obj, (1.0, 1.0, 3.0)), 25.0, 4.0, 0.6)
    edge = t.math("MULTIPLY", c["convex"], 0.6)
    base = t.mixc(edge, c["col"], (0.36, 0.26, 0.17))
    base = t.mixc(t.math("MULTIPLY", c["concave"], 0.5), base, (0.03, 0.02, 0.015))
    rough = t.math("ADD", c["rough"], t.math("MULTIPLY", t.math("SUBTRACT", crease, 0.5), 0.2))
    rough = t.mixf(edge, rough, 0.45)
    nrm = _bump(t, grain, 0.08, 0.0005)
    nrm = _bump(t, crease, 0.15, 0.0015, nrm)
    _bsdf(t, base, rough, 0.0, nrm, c["alpha"])
    return m


def build_skin():
    m = _fresh("MAT_Skin")
    t = NT(m)
    c = _common(t)
    obj = c["obj"]
    blotch = t.noise(obj, 30.0, 5.0, 0.6)
    base = t.mixc(t.math("MULTIPLY", t.maprange(blotch, 0.4, 0.75), 0.25), c["col"], (0.42, 0.16, 0.11))
    base = t.mixc(t.math("MULTIPLY", c["concave"], 0.45), base, (0.15, 0.07, 0.045))
    pores = t.voronoi(obj, 900.0)
    wrinkle = t.noise(t.scale_vec(obj, (1.0, 1.0, 4.0)), 60.0, 3.0, 0.55)
    nrm = _bump(t, pores, 0.05, 0.0003)
    nrm = _bump(t, wrinkle, 0.12, 0.0008, nrm)
    rough = t.math("ADD", t.math("MAXIMUM", c["rough"], 0.5), t.math("MULTIPLY", t.math("SUBTRACT", blotch, 0.5), 0.15))
    _bsdf(t, base, rough, 0.0, nrm, c["alpha"], {"Subsurface Weight": 0.18, "Subsurface Scale": 0.008,
                                                  "Subsurface Radius": (1.0, 0.45, 0.28)})
    return m


def build_wood():
    m = _fresh("MAT_Wood")
    t = NT(m)
    c = _common(t, 0.08, 0.004)
    obj = c["obj"]
    grain = t.wave(t.scale_vec(obj, (1.0, 0.08, 1.0)), 9.0, 6.0, 4.0, "BANDS", "X", "SIN")
    streak = t.noise(t.scale_vec(obj, (10.0, 0.5, 10.0)), 6.0, 4.0, 0.6)
    gtone = t.math("MULTIPLY", t.math("ADD", grain, streak), 0.5)
    base = t.mixc(t.math("MULTIPLY", t.maprange(gtone, 0.3, 0.8), 0.4), c["col"], (0.06, 0.05, 0.04), "MULTIPLY")
    base = t.mixc(t.math("MULTIPLY", c["concave"], 0.6), base, (0.02, 0.017, 0.014))
    dust = t.math("MULTIPLY", t.maprange(t.noise(obj, 3.0, 3.0, 0.5), 0.45, 0.7), 0.3)
    base = t.mixc(dust, base, (0.5, 0.42, 0.31))
    rough = t.math("ADD", t.math("MAXIMUM", c["rough"], 0.78), t.math("MULTIPLY", gtone, 0.12))
    nrm = _bump(t, gtone, 0.3, 0.002)
    _bsdf(t, base, rough, 0.0, nrm, c["alpha"])
    return m


BUILDERS = {"MAT_CarPaint": build_carpaint, "MAT_Metal": build_metal, "MAT_Rubber": build_rubber,
            "MAT_Glass": build_glass, "MAT_Cloth": build_cloth, "MAT_Leather": build_leather,
            "MAT_Skin": build_skin, "MAT_Wood": build_wood}


def build_all():
    return [BUILDERS[n]() for n in SURFACES]


def compute_curvature(me, name="Curvature", gain=2.2):
    """Per-vertex convexity from edge neighbours: 0.5 flat, -> 1 convex edges, -> 0 creases."""
    me.update()
    nv = len(me.vertices)
    if nv == 0:
        return
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    nrm = np.empty(nv * 3, np.float32)
    me.vertex_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(-1, 3)
    ed = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    a, b = ed[:, 0], ed[:, 1]
    d = co[b] - co[a]
    ln = np.linalg.norm(d, axis=1) + 1e-9
    ca = -(nrm[a] * d).sum(1) / ln        # neighbour below a's tangent plane -> convex at a
    cb = (nrm[b] * d).sum(1) / ln
    acc = np.zeros(nv, np.float64)
    cnt = np.zeros(nv, np.float64)
    np.add.at(acc, a, ca)
    np.add.at(acc, b, cb)
    np.add.at(cnt, a, 1)
    np.add.at(cnt, b, 1)
    k = acc / np.maximum(cnt, 1)
    val = np.clip(0.5 + k * gain, 0.0, 1.0).astype(np.float32)
    at = me.attributes.get(name)
    if at is None or at.domain != "POINT":
        if at is not None:
            me.attributes.remove(at)
        at = me.attributes.new(name, "FLOAT", "POINT")
    at.data.foreach_set("value", val)
    return float(val.mean())
