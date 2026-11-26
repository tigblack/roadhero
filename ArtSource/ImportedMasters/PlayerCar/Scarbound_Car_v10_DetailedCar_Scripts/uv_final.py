load("tsets.py"); load("uv_fill.py")
O = bpy.data.objects; vl = bpy.context.view_layer
if bpy.context.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
for sname, names in SETS.items():
    objs = [O[n] for n in names]
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    vl.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(52), margin_method="FRACTION", island_margin=0.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="FRACTION", margin=0.002, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    area = sum(p.area for o in objs for p in o.data.polygons)
    f = fill(objs)
    print(sname, "fill", f, "px/m@2K", round(2048 * math.sqrt(f / area), 1), "bounds", bounds(objs), flush=True)
for o in vl.objects:
    o.select_set(False)
bpy.ops.wm.save_mainfile()
print("saved")
