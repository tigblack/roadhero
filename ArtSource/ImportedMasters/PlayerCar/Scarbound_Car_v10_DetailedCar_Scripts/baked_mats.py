"""Create the export materials M_<Set> from the baked textures (image -> Principled; vertex colour already baked in)."""
load("tsets.py")
import os
TEXREL = "//Scarbound_Car_v10_DetailedCar_Export/Textures/"
made = {}
for sname in SETS:
    m = bpy.data.materials.get("M_" + sname) or bpy.data.materials.new("M_" + sname)
    m.use_fake_user = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled"); p.location = (500, 0)
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"; uv.location = (-700, 0)

    def tex(key, noncolor, y):
        path = TEXREL + "T_%s_%s.png" % (sname, key)
        img = bpy.data.images.load(bpy.path.abspath(path), check_existing=True)
        img.filepath = path
        img.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = img; n.location = (-350, y); n.label = key
        nt.links.new(uv.outputs["UV"], n.inputs["Vector"])
        return n
    bc = tex("BaseColor", False, 400)
    nt.links.new(bc.outputs["Color"], p.inputs["Base Color"])
    ro = tex("Roughness", True, 150)
    nt.links.new(ro.outputs["Color"], p.inputs["Roughness"])
    me_ = tex("Metallic", True, -100)
    nt.links.new(me_.outputs["Color"], p.inputs["Metallic"])
    nm = tex("Normal", True, -350)
    nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.uv_map = "UVMap"; nmap.location = (150, -350)
    nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], p.inputs["Normal"])
    em = tex("Emission", False, -600)
    nt.links.new(em.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.0
    ao = tex("AO", True, -850)          # kept for engines (glTF occlusion / Unity AO); not used by Principled
    made[m.name] = len(nt.nodes)
print(made)
