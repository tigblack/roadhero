import parts_wheels as pw, carshape as cs
importlib.reload(pw)
O = bpy.data.objects
col = bpy.data.collections["Scarbound Car — EDITABLE"]
dg_objs = []


def temp(name, me):
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    return o


WHEELS = [("Wheel.082", "WheelSteer.082", cs.CarFrontWheelR, cs.CarFrontWheelW, -1, True, "FL"),
          ("Wheel.083", "WheelSteer.083", cs.CarFrontWheelR, cs.CarFrontWheelW, 1, True, "FR"),
          ("Wheel.085", "Wheel.084", cs.CarRearWheelR, cs.CarRearWheelW, -1, False, "RL"),
          ("Wheel.087", "Wheel.086", cs.CarRearWheelR, cs.CarRearWheelW, 1, False, "RR")]
report = {}
for wname, pivot, R, W, side, front, tag in WHEELS:
    t = temp("_tyre", pw.tyre(R, W, side).build("_tyre", sharp_deg=40))
    r = temp("_rim", pw.rim_parts(R, W, side).build("_rim", sharp_deg=35))
    d = temp("_dish", pw.dish(R, W, side).build("_dish", sharp_deg=40))
    c = temp("_cut", pw.dish_cutter(R, W, side).build("_cut", sharp_deg=40))
    c.hide_set(True); c.hide_render = True
    mod = d.modifiers.new("holes", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", c
    try:
        mod.material_mode = "TRANSFER"
    except Exception:
        pass
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cut_me = bpy.data.meshes.new_from_object(d.evaluated_get(dg))
    d.modifiers.clear()
    old_d = d.data
    d.data = cut_me
    bpy.data.meshes.remove(old_d)
    objs = [t, r, d]
    with bpy.context.temp_override(active_object=t, object=t, selected_objects=objs, selected_editable_objects=objs):
        res = bpy.ops.object.join()
    me = t.data
    me.name = "carwheel_detailed_%s" % tag
    me.set_sharp_from_angle(angle=math.radians(38))
    wob = O[wname]
    old = wob.data
    replace_mesh(wob, me)
    for o in (t, c):
        cm = o.data
        bpy.data.objects.remove(o)
        if cm.users == 0 and cm != me:
            bpy.data.meshes.remove(cm)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for m in bpy.data.meshes:
        if m.users == 0 and m.name.startswith(("_rim", "_dish", "_tyre", "_cut")):
            bpy.data.meshes.remove(m)
    # caliper / knuckle on the non-spinning pivot
    cname = "BrakeCaliper_" + tag
    cme = pw.caliper(R, W, side, front).build("brakecaliper_" + tag, sharp_deg=35)
    cob = O.get(cname)
    if cob is None:
        cob = bpy.data.objects.new(cname, cme)
        col.objects.link(cob)
    else:
        oldc = cob.data
        cob.data = cme
        if oldc.users == 0:
            bpy.data.meshes.remove(oldc)
    cob.parent = O[pivot]
    cob.matrix_parent_inverse.identity()
    cob.location = (0, 0, 0)
    report[wname] = (mesh_stats(me)["tris"], res, mesh_stats(cme)["tris"])
bpy.context.view_layer.update()
print(report)
for wname, *_ in WHEELS:
    print(wname, tuple(round(v, 3) for v in O[wname].dimensions), [m.name for m in O[wname].data.materials])
