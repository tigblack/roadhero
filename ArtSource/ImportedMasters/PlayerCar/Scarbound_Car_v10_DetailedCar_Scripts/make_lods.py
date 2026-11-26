O = bpy.data.objects
scene_col = bpy.context.scene.collection
RATIOS = {  # name: (LOD1, LOD2, symmetric, hard_surface)
    "Body.573": (0.42, 0.14, True, True), "Details": (0.38, 0.11, True, True), "Underbody": (0.3, 0.06, True, True),
    "Wheel.082": (0.42, 0.13, False, True), "Wheel.083": (0.42, 0.13, False, True), "Wheel.085": (0.42, 0.13, False, True), "Wheel.087": (0.42, 0.13, False, True),
    "BrakeCaliper_FL": (0.5, 0.25, False, True), "BrakeCaliper_FR": (0.5, 0.25, False, True), "BrakeCaliper_RL": (0.5, 0.25, False, True), "BrakeCaliper_RR": (0.5, 0.25, False, True),
    "GunMesh": (0.55, 0.28, False, True), "GunCradle": (0.5, 0.22, False, True), "Turntable": (0.5, 0.22, False, True), "HoodMount": (0.5, 0.22, False, True),
    "TurretBase.001": (0.45, 0.16, False, True), "Column": (0.45, 0.16, False, True), "LauncherMesh": (0.45, 0.16, False, True), "HarpoonTip": (0.45, 0.2, False, True),
    "Cloak": (0.42, 0.14, False, False), "HeadMesh": (0.42, 0.14, False, False), "UpperArmR": (0.45, 0.18, False, False), "UpperArmL": (0.45, 0.18, False, False),
    "ForeArmR": (0.45, 0.16, False, False), "ForeArmL": (0.45, 0.16, False, False), "HandR": (0.45, 0.16, False, False), "HandL": (0.45, 0.16, False, False),
    "LegMesh": (0.45, 0.16, False, False), "LegMesh.001": (0.45, 0.16, False, False),
}


def lod_collection(level):
    name = "LOD%d — game" % level
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.data.collections["Scarbound Car — EDITABLE"].children.link(col)
    return col


def evaluated_copy(ob, name):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.name = name
    return me


report = {}
for level in (1, 2):
    col = lod_collection(level)
    for src_name, (r1, r2, sym, hard) in RATIOS.items():
        src = O[src_name]
        name = "%s_LOD%d" % (src_name, level)
        me = evaluated_copy(src, "%s_LOD%d" % (src.data.name, level))
        ob = O.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, me)
            col.objects.link(ob)
        else:
            old = ob.data
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
        ob.parent = src.parent
        ob.matrix_parent_inverse = src.matrix_parent_inverse.copy()
        ob.matrix_basis = src.matrix_basis.copy()
        ob.modifiers.clear()
        # protect palette boundaries (stripes, sill break, glass frames, lamp outlines): vertices whose corners carry
        # different Color values get weight 1 -> much higher collapse cost, so colour edges stay crisp
        ca = me.color_attributes.get("Color")
        if ca is not None and ca.domain == "CORNER" and hard:
            import numpy as _np
            nl = len(me.loops)
            cols = _np.empty(nl * 4, _np.float32); ca.data.foreach_get("color", cols)
            cols = cols.reshape(-1, 4)[:, :3]
            lv = _np.empty(nl, _np.int32); me.loops.foreach_get("vertex_index", lv)
            nv = len(me.vertices)
            vmin = _np.full((nv, 3), 9.0, _np.float32); vmax = _np.full((nv, 3), -9.0, _np.float32)
            _np.minimum.at(vmin, lv, cols); _np.maximum.at(vmax, lv, cols)
            bnd = set(_np.nonzero((vmax - vmin).max(1) > 0.12)[0].tolist())
            vg = ob.vertex_groups.get("LOD_protect") or ob.vertex_groups.new(name="LOD_protect")
            if bnd:
                vg.add(sorted(bnd), 1.0, "REPLACE")
        d = ob.modifiers.new("Decimate", "DECIMATE")
        if ob.vertex_groups.get("LOD_protect"):
            d.vertex_group = "LOD_protect"
            d.vertex_group_factor = 25.0
            d.invert_vertex_group = True      # group weight 1 = protected (Decimate decimates weighted verts freely)
        d.decimate_type = "COLLAPSE"
        d.ratio = r1 if level == 1 else r2
        d.use_symmetry = sym
        d.symmetry_axis = "X"
        d.use_collapse_triangulate = True
        dec = evaluated_copy(ob, me.name)
        ob.modifiers.clear()
        ob.data = dec
        bpy.data.meshes.remove(me)
        dec.set_sharp_from_angle(angle=math.radians(40 if hard else 65))
        if hard:
            wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"); wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
        for s in ob.material_slots:
            s.link = "DATA"
        ob["lod_of"] = src_name
        ob["lod_level"] = level
        ob.hide_set(True)
        ob.hide_render = True
        report.setdefault(level, 0)
        report[level] += len(dec.polygons)
    col.hide_render = True
for lv in (1, 2):
    lc = bpy.context.view_layer.layer_collection.children["Scarbound Car — EDITABLE"].children.get("LOD%d — game" % lv)
    if lc:
        lc.exclude = False
        lc.hide_viewport = True
bpy.context.view_layer.update()
print("LOD tris:", report)
bpy.ops.wm.save_mainfile()
