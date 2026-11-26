"""Verify AutoCapture's conservative gun envelopes against the authored Blender source.

Run with Blender's Python (bpy/mathutils are required), without changing a .blend:
  Blender --background --factory-startup --python-exit-code 1 \
    --python Tools/Blender/validate_detailed_gun_proxies.py -- \
    --source-dir /path/to/Scarbound_Car_v10_DetailedCar_Scripts

--source-dir accepts the source scripts directory or its lib directory.
--project-dir defaults to this script's Unity project. --out writes a JSON report.
Every polygon must fit wholly in one convex proxy; this proves surface enclosure,
including each polygon's interior, rather than checking only its vertices.
Recoil is enclosed analytically by sweeping these primitives along local -Z.
This checks proxy coverage, not collisions with the car or angular table margins.
"""
from pathlib import Path
import argparse
import importlib
import json
import re
import sys


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--project-dir', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--out', type=Path)
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def vector(text):
    return tuple(float(n.strip().removesuffix('f')) for n in text.split(','))


def proxies(source, name, kind):
    array = re.search(r'\b' + re.escape(name) + r'\s*=\s*\{(.*?)\n\s*\};', source, re.S)
    if not array:
        raise ValueError('Missing C# proxy array: ' + name)
    if kind == 'capsule':
        parts = re.findall(r'new GunCapsule\(new Vector3\(([^)]*)\), new Vector3\(([^)]*)\), ([^)]+)\)', array.group(1))
        result = [(vector(a), vector(b), float(r.strip().removesuffix('f'))) for a, b, r in parts]
    else:
        parts = re.findall(r'new GunBox\(new Vector3\(([^)]*)\), new Vector3\(([^)]*)\)\)', array.group(1))
        result = [(vector(c), vector(h)) for c, h in parts]
    if not result:
        raise ValueError('No recognised primitives in C# array: ' + name)
    return result


def inside_box(v, part):
    centre, half = part
    return all(abs(v[i] - centre[i]) <= half[i] + 1e-7 for i in range(3))


def inside_capsule(v, part):
    a, b, radius = part
    direction = tuple(b[i] - a[i] for i in range(3))
    along = max(0, min(1, sum((v[i] - a[i]) * direction[i] for i in range(3)) / sum(x*x for x in direction)))
    return sum((v[i] - a[i] - along * direction[i])**2 for i in range(3)) <= (radius + 1e-7)**2


def coverage(mesh, capsules, boxes):
    vertices = [(v[0], v[2], v[1]) for v in mesh.co]  # Blender X,Y,Z -> Unity X,Z,Y
    tests = [lambda v, p=p: inside_capsule(v, p) for p in capsules] + [lambda v, p=p: inside_box(v, p) for p in boxes]
    uncovered = [v for v in vertices if not any(test(v) for test in tests)]
    faces = [i for i, face in enumerate(mesh.faces) if not any(all(test(vertices[vi]) for vi in face) for test in tests)]
    return {
        'vertices': len(vertices),
        'polygons': len(mesh.faces),
        'capsules': len(capsules),
        'boxes': len(boxes),
        'uncovered_vertices': len(uncovered),
        'polygons_not_wholly_in_one_convex_proxy': len(faces),
        'first_uncovered_vertices': uncovered[:10],
        'first_unenclosed_polygon_indices': faces[:10],
    }


def main():
    args = arguments()
    lib = args.source_dir if (args.source_dir / 'parts_gun.py').is_file() else args.source_dir / 'lib'
    if not (lib / 'parts_gun.py').is_file():
        raise FileNotFoundError('parts_gun.py not found in source-dir or source-dir/lib')
    sys.path.insert(0, str(lib.resolve()))
    parts_gun = importlib.import_module('parts_gun')
    source = (args.project_dir / 'Assets/RoadGame/Editor/AutoCapture.cs').read_text()
    gun_capsules = proxies(source, 'GunFront', 'capsule')
    gun_boxes = proxies(source, 'GunFrontBoxes', 'box') + proxies(source, 'GunRearBoxes', 'box')
    cradle_capsules = proxies(source, 'GunCradleCapsules', 'capsule')
    cradle_boxes = proxies(source, 'GunCradleBoxes', 'box')
    recoil = float(re.search(r'CheckGunRecoil\s*=\s*([\d.]+)f', source).group(1))
    assert recoil >= parts_gun.RECOIL, 'CheckGunRecoil does not enclose the authored recoil stroke'
    assert all(a[:2] == b[:2] for a, b, _ in gun_capsules), 'Recoiling capsules must parallel the local Z axis'
    result = {
        'source_dir': str(lib.resolve()),
        'project_dir': str(args.project_dir.resolve()),
        'recoil_sweep_m': recoil,
        'GunMesh': coverage(parts_gun.gun_mesh(), gun_capsules, gun_boxes),
        'GunCradle': coverage(parts_gun.cradle_mesh(), cradle_capsules, cradle_boxes),
    }
    result['passed'] = all(result[name]['uncovered_vertices'] == 0 and result[name]['polygons_not_wholly_in_one_convex_proxy'] == 0 for name in ('GunMesh', 'GunCradle'))
    print('DETAILED_GUN_PROXY_COVERAGE=' + json.dumps(result))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    if not result['passed']:
        raise AssertionError('Detailed gun surface escapes the clearance proxies; see report above')


if __name__ == '__main__':
    main()
