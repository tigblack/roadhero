"""Before/after comparison images for v13 (same cameras). blender -b --python compare13.py"""
import bpy, sys, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import imgtools as I
root = os.path.dirname(HERE)
R = os.path.join(root, 'renders'); C = os.path.join(root, 'compare')
for mode in ('clay', 'color'):
    os.makedirs(os.path.join(C, mode), exist_ok=True)
    for f in sorted(glob.glob(os.path.join(R, f'before_{mode}', '*.png'))):
        n = os.path.basename(f); a = os.path.join(R, f'after_{mode}', n)
        if os.path.exists(a):
            I.before_after(f, a, os.path.join(C, mode, n), title=os.path.splitext(n)[0] + ('  (neutral grey)' if mode == 'clay' else ''),
                           labels=('BEFORE  v12', 'AFTER  v13 SmoothPass'))
    cu = []
    labels = []
    for f in sorted(glob.glob(os.path.join(R, f'before_{mode}_closeups', '*.png'))):
        n = os.path.basename(f); a = os.path.join(R, f'after_{mode}_closeups', n)
        if os.path.exists(a):
            cu += [f, a]; labels += [os.path.splitext(n)[0] + '  v12', os.path.splitext(n)[0] + '  v13']
    for k in range(0, len(cu), 16):
        I.sheet(cu[k:k + 16], os.path.join(C, f'closeups_{mode}_{k // 16 + 1}.png'), 4, 520, labels=labels[k:k + 16])
print('COMPARE13 done')
