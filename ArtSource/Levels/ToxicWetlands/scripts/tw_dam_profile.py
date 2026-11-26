"""Height profile of the first-zone (Dust Flats v13) perimeter massifs at the second-zone cut line.

    python3 tw_dam_profile.py <fresh_export/scene.json> <out.npy>      (numpy only; Blender's python3.13 works)

The v13 massifs Cliff.014 / AP_Cliff_NorthEast (+ their scree and sand drift) reach into the south of the second zone.
ImportedLevel.ClipNorth drops their triangles north of z = 104.5 when the wetlands bundle is loaded; the south dam
(tw_borders.south_dam) hides that cut, so it has to stand taller than the massifs along the line. This script samples
the massif triangles in the band z = 102.5..104.5 and stores the maximum height per metre of x (-120..120, 240 values).

Input: a Unity -> Blender export of the running world WITH the v13 bundle applied (the v10 snapshot predates v13):

    Unity -batchmode -disableaudio -nographics -quit -projectPath <project copy> \
        -executeMethod RoadGame.EditorTools.LevelBlenderExport.Run -exportOut <dir>

Re-run only if the v13 massifs change; the result goes to data/ToxicWetlands_dam_profile.npy (read by tw_build.py).
"""
import json
import sys

import numpy as np

MASSIFS = ('Cliff', 'AP_Cliff_NorthEast', 'AP_Scree_Cliff.014', 'AP_Scree_AP_Cliff_NorthEast', 'AP_SandDrift_Cliff.014')
BAND = (102.5, 104.5)       # Unity z, just south of the cut line
X0, N = -120, 240           # one sample per metre of Unity x


def quat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main(scene_path, out_path):
    d = json.load(open(scene_path))
    nodes = d['nodes']
    byid = {n['id']: n for n in nodes}
    meshes = {m['id']: m for m in d['meshes']}

    def world(n):
        M = np.eye(4)
        chain = []
        while n:
            chain.append(n)
            n = byid.get(n['parentId'])
        for m in reversed(chain):
            T = np.eye(4)
            T[:3, :3] = quat(m['rotation']) * np.array(m['scale'])[None, :]
            T[:3, 3] = m['position']
            M = M @ T
        return M

    prof = np.full(N, -1.0)
    used = []
    for n in nodes:
        if not n.get('meshId') or n['name'] not in MASSIFS:
            continue
        m = meshes[n['meshId']]
        v = np.array(m['vertices'], float).reshape(-1, 3)
        W = world(n)
        p = v @ W[:3, :3].T + W[:3, 3]
        if not ((p[:, 2] > 100).any() and (p[:, 2] < 99).any()):
            continue                                    # does not cross into the second zone
        if p[:, 0].min() < -100 and p[:, 0].max() < -90:
            continue                                    # zone side walls
        subs = m.get('submeshes')
        if not subs:
            continue
        tris = np.array([i for s in subs for i in s.get('indices', s.get('triangles', []))], int).reshape(-1, 3)
        A, B, C = p[tris[:, 0]], p[tris[:, 1]], p[tris[:, 2]]
        for u in np.linspace(0, 1, 10):                 # dense barycentric sampling of every triangle
            for w_ in np.linspace(0, 1 - u, max(2, int(10 * (1 - u)))):
                P = A * (1 - u - w_) + B * u + C * w_
                sel = (P[:, 2] >= BAND[0]) & (P[:, 2] <= BAND[1])
                xi = np.floor(P[sel, 0] - X0).astype(int)
                ok = (xi >= 0) & (xi < N)
                np.maximum.at(prof, xi[ok], P[sel][ok, 1])
        used.append((n['name'], n['id']))
    np.save(out_path, prof)
    print('TW_DAM_PROFILE massifs', used, 'max height %.2f m' % prof.max(), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
