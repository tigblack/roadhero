"""Capture the v12 baseline (run headless on ArtPass_v13/source/v12_live_snapshot.blend): fingerprint + triangles."""
import bpy, sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rg_check13 as C, step13_finalize as F
root = os.path.dirname(os.path.dirname(HERE))
fp = C.fingerprint()
json.dump(fp, open(os.path.join(root, 'ArtPass_v13', 'stats', 'baseline_v12_fingerprint.json'), 'w'), indent=0)
json.dump(F.tri_stats(), open(os.path.join(root, 'ArtPass_v13', 'stats', 'v12_triangles_by_category.json'), 'w'), indent=1)
print('BASELINE13', len(fp), F.tri_stats())
