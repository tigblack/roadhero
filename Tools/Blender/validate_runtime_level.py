"""Validate a runtime Blender mesh bundle without Blender or Unity dependencies."""
import argparse,array,hashlib,json,math,pathlib,struct


def validate(base):
    manifest=json.loads((base/'manifest.json').read_text())
    resource_base=base.as_posix().split('/Resources/')[-1]
    for descriptor in manifest['meshes']:
        relative=descriptor['resource'].removeprefix(resource_base+'/')+'.bytes'
        binary=(base/relative).read_bytes()
        vertex_count,submeshes=struct.unpack_from('<ii',binary)
        assert vertex_count==descriptor['vertexCount'] and submeshes==descriptor['submeshes']
        offset=8+vertex_count*56
        values=array.array('f');values.frombytes(binary[8:offset])
        assert all(map(math.isfinite,values)),descriptor['name']+' has nonfinite attributes'
        for corner in range(3,len(values),14):
            normal_squared=sum(float(values[k])**2 for k in range(corner,corner+3))
            assert .81<normal_squared<1.21,(descriptor['name'],corner,normal_squared)
        triangles=0
        for submesh in range(submeshes):
            count=struct.unpack_from('<i',binary,offset)[0];offset+=4
            indices=array.array('i');indices.frombytes(binary[offset:offset+count*4]);offset+=count*4
            assert count%3==0 and (not count or min(indices)>=0 and max(indices)<vertex_count)
            triangles+=count//3
        assert offset==len(binary) and triangles==descriptor['triangles']
        assert hashlib.sha256(binary).hexdigest()==descriptor['sha256']
    ids={n['id'] for n in manifest['nodes']}
    assert len(ids)==len(manifest['nodes']),'duplicate object ids'
    for node in manifest['nodes']:
        assert -1<=node['parent']<len(manifest['nodes']) and -1<=node['mesh']<len(manifest['meshes'])
        assert -1<=node['colliderMesh']<len(manifest['meshes'])
        if node['mesh']>=0:
            assert len(node['materials'])==manifest['meshes'][node['mesh']]['submeshes'],node['name']
            assert all(0<=index<len(manifest['materials']) for index in node['materials'])
        if node['lodLevel']>0:
            assert node['lodOf'] in ids
        assert all(map(math.isfinite,node['position']+node['rotation']+node['scale']))
    for material in manifest['materials']:
        if material['texture']:
            relative=material['texture'].removeprefix(resource_base+'/')+'.png'
            assert (base/relative).is_file(),relative
    result={'valid':True,'uniqueMeshes':len(manifest['meshes']),'nodes':len(manifest['nodes']),
            'spawnRoots':sum(n['spawnRoot'] for n in manifest['nodes']),
            'lodObjects':sum(n['lodLevel']>0 for n in manifest['nodes']),
            'roofs':sum(n['isRoof'] for n in manifest['nodes'])}
    (base/'validation_report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=pathlib.Path)
    validate(p.parse_args().bundle)
