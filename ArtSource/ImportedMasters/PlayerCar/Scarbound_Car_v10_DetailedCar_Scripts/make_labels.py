import bpy, sys, os
out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1600, 96
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("w")
bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 16.0; cam.location = (0, 0, 10)
for key, text, col in (("before", "ДО — Scarbound_Car_v10 (исходная)", (0.20, 0.21, 0.24)),
                       ("after", "ПОСЛЕ — Scarbound_Car_v10_DetailedCar", (0.10, 0.30, 0.27))):
    bg.inputs[0].default_value = (*col, 1)
    for o in list(sc.collection.objects):
        if o.type == "FONT":
            bpy.data.objects.remove(o)
    cu = bpy.data.curves.new("t", "FONT"); cu.body = text; cu.size = 0.55; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    try:
        cu.font = bpy.data.fonts.load("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    except Exception:
        pass
    t = bpy.data.objects.new("t", cu); sc.collection.objects.link(t)
    m = bpy.data.materials.new("em"); nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (1, 1, 1, 1); e.inputs[1].default_value = 1.0
    o_ = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o_.inputs[0])
    cu.materials.append(m)
    sc.render.filepath = os.path.join(out, "label_%s.png" % key)
    bpy.ops.render.render(write_still=True)
print("LABELS_DONE")
