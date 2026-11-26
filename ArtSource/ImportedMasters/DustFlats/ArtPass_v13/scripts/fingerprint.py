"""Dump a fingerprint of every object (transform, mesh hash, materials, visibility) to JSON."""
import bpy, sys, json, hashlib
import numpy as np
out = sys.argv[sys.argv.index('--') + 1]
res = {}
for o in bpy.context.scene.objects:
    d = dict(type=o.type, parent=o.parent.name if o.parent else None, mw=[round(x, 4) for r in o.matrix_world for x in r],
             hide_render=o.hide_render, hide_viewport=o.hide_viewport, colls=sorted(c.name for c in o.users_collection),
             mats=[s.material.name if s.material else None for s in o.material_slots],
             props={k: (o[k].to_list() if hasattr(o[k], 'to_list') else o[k]) for k in o.keys() if isinstance(o[k], (int, float, str)) or hasattr(o[k], 'to_list')})
    if o.type == 'MESH':
        me = o.data
        co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
        h = hashlib.md5(np.round(co, 4).tobytes()).hexdigest()
        col = me.color_attributes.get('Color')
        ch = ''
        if col:
            c = np.zeros(len(me.loops) * 4, np.float32); col.data.foreach_get('color', c); ch = hashlib.md5(np.round(c, 4).tobytes()).hexdigest()
        d.update(mesh=me.name, nv=len(me.vertices), nf=len(me.polygons), geo=h, colh=ch)
    elif o.type == 'LIGHT':
        d.update(energy=o.data.energy, color=list(o.data.color))
    elif o.type == 'CAMERA':
        d.update(lens=o.data.lens)
    res[o.name] = d
sc = bpy.context.scene
res['__scene__'] = dict(camera=sc.camera.name if sc.camera else None, vt=sc.view_settings.view_transform, exp=sc.view_settings.exposure,
                        world=sc.world.name if sc.world else None, res=[sc.render.resolution_x, sc.render.resolution_y],
                        mats={m.name: m.users for m in bpy.data.materials}, colls=sorted(c.name for c in bpy.data.collections))
json.dump(res, open(out, 'w'))
print("FP", len(res))
