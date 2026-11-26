"""Image utilities running inside Blender (numpy only): load/save PNG, contact sheets,
before/after comparisons with a tiny built-in pixel font for labels."""
import bpy, numpy as np, os

def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()  # top-down

def save(arr, path, colorspace='sRGB'):
    h, w = arr.shape[:2]
    if arr.shape[2] == 3: arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], 2)
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = colorspace
    im.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).astype(np.float32).ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)

def resize(a, w, h):
    H, W = a.shape[:2]
    ys = (np.arange(h) + 0.5) * H / h - 0.5; xs = (np.arange(w) + 0.5) * W / w - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, H - 1); x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
    y1 = np.clip(y0 + 1, 0, H - 1); x1 = np.clip(x0 + 1, 0, W - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None, None]; fx = np.clip(xs - x0, 0, 1)[None, :, None]
    if H > 2 * h or W > 2 * w:  # box prefilter
        k = max(1, int(min(H / h, W / w)))
        Hc, Wc = H // k * k, W // k * k
        a = a[:Hc, :Wc].reshape(Hc // k, k, Wc // k, k, -1).mean((1, 3))
        return resize(a, w, h)
    return (a[y0][:, x0] * (1 - fy) * (1 - fx) + a[y0][:, x1] * (1 - fy) * fx +
            a[y1][:, x0] * fy * (1 - fx) + a[y1][:, x1] * fy * fx)

# 5x7 pixel font
_F = {
 'A':"01110100011000111111100011000110001",'B':"11110100011111010001100011000111110",'C':"01110100011000010000100001000101110",
 'D':"11110100011000110001100011000111110",'E':"11111100001111010000100001000011111",'F':"11111100001111010000100001000010000",
 'G':"01110100011000010111100011000101111",'H':"10001100011111110001100011000110001",'I':"01110001000010000100001000010001110",
 'J':"00111000100001000010000101001001100",'K':"10001100101010011000101001001010001",'L':"10000100001000010000100001000011111",
 'M':"10001110111010110101100011000110001",'N':"10001110011010110011100011000110001",'O':"01110100011000110001100011000101110",
 'P':"11110100011000111110100001000010000",'Q':"01110100011000110001101011001001101",'R':"11110100011000111110101001001010001",
 'S':"01111100001000001110000010000111110",'T':"11111001000010000100001000010000100",'U':"10001100011000110001100011000101110",
 'V':"10001100011000110001100010101000100",'W':"10001100011000110101101011010101010",'X':"10001100010101000100010101000110001",
 'Y':"10001100010101000100001000010000100",'Z':"11111000010001000100010001000011111",
 '0':"01110100011001110101110011000101110",'1':"00100011000010000100001000010001110",'2':"01110100010000100010001000100011111",
 '3':"11111000100010000010000011000101110",'4':"00010001100101010010111110001000010",'5':"11111100001111000001000011000101110",
 '6':"00110010001000011110100011000101110",'7':"11111000010001000100010000100001000",'8':"01110100011000101110100011000101110",
 '9':"01110100011000101111000010001001100",' ':"0"*35,'-':"00000000000000011111000000000000000",'.':"00000000000000000000000000110001100",
 '/':"00001000010001000100010001000010000",':':"00000011000110000000011000110000000",'(':"00010001000100001000010000010000010",
 ')':"01000001000001000010000100010001000",'_':"00000000000000000000000000000011111",'+':"00000001000010011111001000010000000",
 '>':"10000010000010000010001000100010000",'=':"00000000001111100000111110000000000",',':"00000000000000000000001100010001000",
}
def text(img, s, x, y, scale=3, color=(1, 1, 1), shadow=True):
    s = s.upper()
    for pass_ in ((1, (0.05, 0.05, 0.05)), (0, color)) if shadow else ((0, color),):
        off, col = pass_
        cx = x
        for ch in s:
            g = _F.get(ch, _F[' '])
            for i in range(7):
                for j in range(5):
                    if g[i * 5 + j] == '1':
                        y0 = y + i * scale + off; x0 = cx + j * scale + off
                        img[y0:y0 + scale, x0:x0 + scale, :3] = col
            cx += 6 * scale
    return img

def sheet(paths, out, cols=4, cell_w=600, labels=None, bg=0.12, label_scale=2):
    ims = [load(p) for p in paths]
    cell_h = max(int(cell_w * im.shape[0] / im.shape[1]) for im in ims)
    rows = (len(ims) + cols - 1) // cols
    pad = 6; top = 22 if labels is not None else 0
    canvas = np.full((rows * (cell_h + pad + top) + pad, cols * (cell_w + pad) + pad, 4), bg, np.float32); canvas[..., 3] = 1
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        h = int(cell_w * im.shape[0] / im.shape[1])
        y = pad + r * (cell_h + pad + top) + top; x = pad + c * (cell_w + pad)
        canvas[y:y + h, x:x + cell_w] = resize(im, cell_w, h)
        if labels is not None: text(canvas, labels[k], x + 2, y - top + 4, label_scale)
    save(canvas, out)

def before_after(before, after, out, title='', cell_w=None, labels=('BEFORE  V10', 'AFTER  V11')):
    a = load(before); b = load(after)
    if cell_w: a = resize(a, cell_w, int(cell_w * a.shape[0] / a.shape[1])); b = resize(b, cell_w, int(cell_w * b.shape[0] / b.shape[1]))
    h, w = a.shape[:2]; pad = 8; top = 40
    canvas = np.full((h + top + pad, 2 * w + 3 * pad, 4), 0.1, np.float32); canvas[..., 3] = 1
    canvas[top:top + h, pad:pad + w] = a; canvas[top:top + h, 2 * pad + w:2 * pad + 2 * w] = b[:h, :w]
    text(canvas, labels[0], pad + 6, 10, 3, (0.9, 0.85, 0.75)); text(canvas, labels[1], 2 * pad + w + 6, 10, 3, (0.75, 0.95, 0.75))
    if title: text(canvas, title, 2 * pad + 2 * w - 6 * 3 * len(title) - 6, 10, 3, (0.95, 0.95, 0.95))
    save(canvas, out)
