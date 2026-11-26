import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imgtools
argv = sys.argv[sys.argv.index('--') + 1:]
out, cols, cw = argv[0], int(argv[1]), int(argv[2]); files = []
for g in argv[3:]: files += sorted(glob.glob(g))
imgtools.sheet(files, out, cols, cw, labels=[os.path.splitext(os.path.basename(f))[0] for f in files])
print("SHEET", out, len(files))
