"""Export an edited RoadGame Blender snapshot as lossless runtime mesh resources.

Usage (Blender Python):
  Blender -b DustFlats_Level_v13_SmoothPass.blend --python Tools/Blender/export_runtime_level.py -- \
    --source-scene Exports/Blender/2026-11-17/scene.json \
    --output Assets/RoadGame/Resources/Levels/DustFlatsV13

The source .blend is read only. Positions/normals are transformed from Blender
(X,Y,Z up) to Unity (X,Y up,Z) by swapping Y/Z and reversing triangle winding.
Meshes share buffers only when their evaluated data and clipping agree. Corner
normals, float vertex colours, UV0, and UV1 gloss/metal are preserved exactly.
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, struct, sys, time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

AXIS = Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
ROCKS = ('MesaRock','Plateau','Ridge0.001','Cliff','Cliff.001','Cliff.002',
         'Cliff.003','Cliff.004','Cliff.011','Cliff.012','Cliff.014','AP_Cliff_NorthEast',
         'AP_River_GapBoulders')


def args():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-scene',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--clip-river-z',type=float,default=105)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:])


def get_array(collection,prop,width,dtype=np.float32):
    a=np.empty(len(collection)*width,dtype=dtype)
    collection.foreach_get(prop,a)
    return a.reshape((-1,width))


def excluded(o):
    return any(c.name.startswith(('PREVIEW','References','Zone_00 v12 — Backdrop')) for c in o.users_collection)


def source_path(n,lookup):
    names=[]; seen=set()
    while n and n['id'] not in seen:
        seen.add(n['id']); names.append(n['name']); n=lookup.get(n.get('parentId'))
    return '/'.join(reversed(names))


def export():
    opt=args(); started=time.time(); opt.output.mkdir(parents=True,exist_ok=True)
    mesh_dir=opt.output/'Meshes'; tex_dir=opt.output/'Textures'
    mesh_dir.mkdir(exist_ok=True);tex_dir.mkdir(exist_ok=True)
    resource_root=opt.output.as_posix().split('/Resources/')[-1]
    original=json.loads(opt.source_scene.read_text()); original_nodes={n['id']:n for n in original['nodes']}
    original_mats={m['id']:m for m in original['materials']}
    objects=[o for o in bpy.context.scene.objects if o.type in {'MESH','EMPTY'} and not excluded(o)]
    object_indices={o:i for i,o in enumerate(objects)}
    ids={o:str(o.get('unity_id') or 'blender_'+o.name) for o in objects}
    used_mats={s.material for o in objects if o.type=='MESH' for s in o.material_slots if s.material}
    mats=sorted(used_mats,key=lambda m:m.name)
    mat_indices={m:i for i,m in enumerate(mats)}
    manifest={'version':1,'sourceFile':Path(bpy.data.filepath).name,'coordinateSystem':'Unity: X right, Y up, Z forward; metres',
              'meshes':[],'materials':[],'nodes':[],'replacementNodeIds':[],
              'sourceHash':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()}
    textures={}; warnings=[]
    for i,m in enumerate(mats):
        mid=str(m.get('unity_id') or 'blender_material_'+m.name)
        src=original_mats.get(mid,{})
        color=list(m.get('unity_base_color',(1,1,1,1)))
        images=[n.image for n in m.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage' and n.image] if m.node_tree else []
        texture=''
        if images:
            image=images[0];filename=Path(image.name).stem+'.png'; texture=resource_root+'/Textures/'+Path(filename).stem
            if image.name not in textures:
                dest=tex_dir/filename; image_path=Path(bpy.path.abspath(image.filepath))
                if image.packed_file:
                    dest.write_bytes(bytes(image.packed_file.data))
                elif image_path.is_file():shutil.copy2(image_path,dest)
                else:
                    image.save_render(str(dest))
                textures[image.name]={'file':dest.name,'size':list(image.size),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
        world_uv=float(m.get('unity_world_uv',src.get('worldUV',0)))
        tiling=list(m.get('unity_base_map_tiling',src.get('baseMapScale',[1,1])))
        offset=list(src.get('baseMapOffset',[0,0]))
        shader=str(m.get('unity_shader','RoadGame/Toon'))
        manifest['materials'].append({'id':mid,'name':m.name,'shader':shader,'color':color,'texture':texture,'worldUV':world_uv,
                                      'tiling':tiling,'offset':offset,'unlit':'Unlit' in shader,'water':m.name=='River_Water',
                                      'roughness':0.14 if m.name=='River_Water' else float(src.get('roughness',0.8)),'metallic':float(src.get('metallic',0)),
                                      'alpha':0.56 if m.name=='River_Water' else float(color[3]),
                                      'additive':m.name in {'RepairGlow','LampPool'}})
    cache={};deps=bpy.context.evaluated_depsgraph_get();counts={'sourceCorners':0,'splitVertices':0,'triangles':0,'removedDegenerates':0,'clippedRiverTriangles':0,'repairedNormalCorners':0,'upwardWaterTriangles':0}
    def mesh_index(o):
        if o.type!='MESH':return -1
        # Modifiers are evaluated per object; unmofidied mesh datablocks retain instancing.
        clip=o.name.startswith('AP_River_')
        ck=(o.data.as_pointer(),o.name if len(o.modifiers) else None,tuple(v for row in o.matrix_world for v in row) if clip else None)
        if ck in cache:return cache[ck]
        evaluated=o.evaluated_get(deps);me=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=deps)
        try:
            me.calc_loop_triangles()
            if not len(me.loop_triangles):return -1
            pos=get_array(me.vertices,'co',3)
            loop_v=get_array(me.loops,'vertex_index',1,np.int32).ravel()
            normals=get_array(me.corner_normals,'vector',3)
            normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-20)
            colors=me.color_attributes.get('Color')
            rgba=get_array(colors.data,'color',4) if colors else np.ones((len(me.loops),4),dtype=np.float32)
            if colors and colors.domain=='POINT':rgba=rgba[loop_v]
            uv=[]
            for nm in ('UVMap','Unity_MaterialParams'):
                layer=me.uv_layers.get(nm)
                uv.append(get_array(layer.data,'uv',2) if layer else np.zeros((len(me.loops),2),dtype=np.float32))
            rows=np.concatenate((pos[loop_v][:,[0,2,1]],normals[:,[0,2,1]],rgba,*uv),axis=1).astype('<f4')
            tris=get_array(me.loop_triangles,'loops',3,np.int32)
            slots=get_array(me.loop_triangles,'material_index',1,np.int32).ravel()
            tv=pos[loop_v[tris]]
            area=np.cross(tv[:,1]-tv[:,0],tv[:,2]-tv[:,0])
            if o.name=='AP_River_Water':
                # Blender displayed this planar source double-sided; Unity culls backfaces.
                # Its winding is mostly downward, so orient water toward the sky.
                flip=area[:,2]<0
                tris[flip]=tris[flip][:,[0,2,1]]
                area[flip]*=-1
                rows[:,3:6]=(0,1,0)
                counts['upwardWaterTriangles']+=int(flip.sum())
            keep=(area*area).sum(axis=1)>1e-20
            degenerate=int((~keep).sum());counts['removedDegenerates']+=degenerate
            if clip:
                # These art meshes extend far beyond Dust Flats into later zones.
                # Drop triangles outside the sealed z=105 boundary, behind cliffs.
                mat=np.asarray(o.matrix_world,dtype=np.float32)
                world_z=tv[:,:,0]*mat[1,0]+tv[:,:,1]*mat[1,1]+tv[:,:,2]*mat[1,2]+mat[1,3]
                in_zone=np.max(world_z,axis=1)<=opt.clip_river_z
                counts['clippedRiverTriangles']+=int((keep&~in_zone).sum());keep&=in_zone
            tris=tris[keep][:,[0,2,1]];slots=slots[keep]
            if not len(tris):return -1
            # Only export used corners; unique rows preserve all normal/colour/UV seams.
            used_rows=rows[tris.ravel()].copy()
            invalid_normal=(used_rows[:,3:6]**2).sum(axis=1)<0.5
            if invalid_normal.any():
                face_normals=area[keep][:,[0,2,1]]
                face_normals/=np.maximum(np.linalg.norm(face_normals,axis=1,keepdims=True),1e-20)
                used_rows[invalid_normal,3:6]=np.repeat(face_normals,3,axis=0)[invalid_normal]
                counts['repairedNormalCorners']+=int(invalid_normal.sum())
            corners, inverse=np.unique(used_rows,axis=0,return_inverse=True)
            indices=inverse.reshape((-1,3)).astype('<i4')
            slot_count=max(len(o.material_slots),int(slots.max())+1,1)
            index=len(manifest['meshes']); filename=f'mesh_{index:04d}.bytes';path=mesh_dir/filename
            with path.open('wb') as f:
                f.write(struct.pack('<ii',len(corners),slot_count));f.write(corners.astype('<f4').tobytes())
                for slot in range(slot_count):
                    buf=indices[slots==slot].ravel();f.write(struct.pack('<i',len(buf)));f.write(buf.tobytes())
            desc={'name':o.data.name,'resource':resource_root+'/Meshes/'+Path(filename).stem,'vertexCount':len(corners),
                  'triangles':len(tris),'submeshes':slot_count,'sourceId':str(o.data.get('unity_id','')),
                  'sourceCorners':len(me.loops),'removedDegenerates':degenerate,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest['meshes'].append(desc);cache[ck]=index
            counts['sourceCorners']+=len(me.loops);counts['splitVertices']+=len(corners);counts['triangles']+=len(tris)
            if index%40==0:print('ROADGAME_EXPORT_MESH',index,o.name,len(corners),len(tris),flush=True)
            return index
        finally:evaluated.to_mesh_clear()
    for o in objects:
        source=original_nodes.get(str(o.get('unity_id')),{}); pos,rot,scale=(AXIS@o.matrix_local@AXIS).decompose()
        spawn_id=-1;spawn_root=False;ancestor=o
        while ancestor:
            match=re.match(r'Spawn_(\d+)_',ancestor.name)
            if match:
                spawn_id=int(match.group(1));spawn_root=ancestor==o;break
            ancestor=ancestor.parent
        is_lod=bool(o.get('unity_lod_level',0));lod_of=bpy.data.objects.get(str(o.get('unity_lod_of','')))
        is_roof=any('Roofs' in c.name for c in o.users_collection)
        mi=mesh_index(o)
        n={'id':ids[o],'name':o.name,'originalName':source.get('name',''),'originalParentId':source.get('parentId',''),
           'sourcePath':source_path(source,original_nodes) if source else '',
           'parent':object_indices.get(o.parent,-1),'mesh':mi,'materials':[mat_indices.get(s.material,-1) for s in o.material_slots] if o.type=='MESH' else [],
           'position':[0,0,0] if is_lod else list(pos),'rotation':[0,0,0,1] if is_lod else [rot.x,rot.y,rot.z,rot.w],'scale':[1,1,1] if is_lod else list(scale),'category':str(o.get('unity_category','environment')),
           'active':bool(o.get('unity_active_self',True)) and not is_lod,'rendererEnabled':bool(o.get('unity_renderer_enabled',True)) and not is_lod,
           'spawnId':spawn_id,'spawnRoot':spawn_root,'isRoof':is_roof,'castShadows':True,
           'lodOf':ids.get(lod_of,''),'lodLevel':int(o.get('unity_lod_level',0)),'lodScreenSize':float(o.get('unity_lod_screen_size',0)),
           'colliderMesh':-1}
        manifest['nodes'].append(n)
        if source.get('meshId') and source.get('category') not in ('spawn_visual','reference'):
            manifest['replacementNodeIds'].append(source['id'])
    by_name={o.name:i for i,o in enumerate(objects)}
    for name in ROCKS:
        if name not in by_name:continue
        node=manifest['nodes'][by_name[name]]
        lod=bpy.data.objects.get(name+'_LOD2')
        node['colliderMesh']=mesh_index(lod) if lod else node['mesh']
    (opt.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
    report={'sourceFile':bpy.data.filepath,'sourceSha256':manifest['sourceHash'],'sourceScene':str(opt.source_scene),
            'version':1,'nodes':len(manifest['nodes']),'meshObjects':sum(n['mesh']>=0 for n in manifest['nodes']),
            'uniqueMeshes':len(manifest['meshes']),'materials':len(mats),'textures':textures,
            'lodObjects':sum(n['lodLevel']>0 for n in manifest['nodes']),'collisionProxies':sum(n['colliderMesh']>=0 for n in manifest['nodes']),
            'counts':counts,'binaryBytes':sum(p.stat().st_size for p in mesh_dir.glob('*.bytes')),'elapsedSeconds':round(time.time()-started,2),
            'excluded':['References','PREVIEW','presentation horizon backdrop'],'clipRiverMaximumUnityZ':opt.clip_river_z,
            'waterOrientation':'Planar source displayed double-sided in Blender; runtime water winding and normals face upward. Source .blend unchanged.',
            'lodTransforms':'Hidden LOD mesh buffers use identity local transforms relative to source object.',
            'warnings':warnings}
    (opt.output/'export_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('ROADGAME_EXPORT_COMPLETE',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':export()
