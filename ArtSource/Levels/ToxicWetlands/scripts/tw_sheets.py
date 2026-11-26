"""Presentation sheets from the renders (needs Pillow; any Python 3).

    python3 tw_sheets.py <renders_dir> <out_dir> [<unity_frames_dir> [<before_dir>]]

enemies-toxic-wetlands.png: the six enemies with captions (same layout as the Rust Canyon review sheet).
unity-game-camera.png: Unity frames of the `wetlands` capture scenario (normal game camera), with captions.
before-after.png: Rust Canyon review shots (Docs/screenshots/rust-canyon-review-2026-11-20) next to the new renders.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
FONT_R = '/System/Library/Fonts/Supplemental/Arial.ttf'

ENEMIES = [
    ('Scav', 'Мусорщик', 'Scavenger', 'капюшон, респиратор, рюкзак, самодельное ружьё'),
    ('Raider', 'Рейдер', 'Raider', 'броня из бочки, маска, гребень, булава-вентиль'),
    ('Spearman', 'Копейщик', 'Lancer', 'щит-крышка, вейдерсы, копьё с ампулой'),
    ('Crossbow', 'Арбалетчик', 'Bolter', 'фильтр-маска, ржавый арбалет, колчан-огнетушитель'),
    ('Brute', 'Громила', 'Brute', 'костюм химзащиты, крупные фильтры, бак, раструб'),
    ('Buggy', 'Багги', 'Buggy', 'грязевые шины, шноркель, решётка, канистры'),
]


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def enemies(renders, out):
    cell, pad, cap = 512, 18, 118
    W = pad + 3 * (cell + pad)
    H = 110 + 2 * (cell + cap + pad)
    img = Image.new('RGB', (W, H), (242, 238, 232))
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 22), 'ВРАГИ TOXIC WETLANDS', fill=(40, 36, 32), font=font(FONT, 38))
    d.text((pad + 6, 70), 'Новые модели из Blender (ArtSource/Levels/ToxicWetlands) · вторая зона', fill=(110, 100, 90), font=font(FONT_R, 22))
    for i, (key, ru, en, note) in enumerate(ENEMIES):
        x = pad + (i % 3) * (cell + pad)
        y = 110 + (i // 3) * (cell + cap + pad)
        shot = Image.open(os.path.join(renders, 'enemy_%s.png' % key)).convert('RGB').resize((cell, cell), Image.LANCZOS)
        img.paste(shot, (x, y))
        cx = x + cell // 2
        for text, f, col, dy in ((ru, font(FONT, 30), (34, 30, 28), 12), (en, font(FONT_R, 22), (100, 92, 84), 50),
                                 (note, font(FONT_R, 18), (120, 112, 104), 82)):
            w = d.textlength(text, font=f)
            d.text((cx - w / 2, y + cell + dy), text, fill=col, font=f)
    img.save(os.path.join(out, 'enemies-toxic-wetlands.png'))


# stops of the `wetlands` capture scenario (Editor/AutoCaptureWetlands.cs), in capture order
STOPS = ['Въезд: ворота у дамбы', 'Западный лагерь', 'Эстакада над тоннелем', 'Путепровод', 'Восточный лагерь',
         'Подъезд к арене', 'Бой с Sludge Baron', 'Северо-восток, вал', 'Северо-запад', 'Юго-запад арены',
         'Брод через заводь', 'Брод: в воде', 'Брод: у южной дамбы']


def frames(frames_dir, out):
    fs = sorted(f for f in os.listdir(frames_dir) if f.startswith('wetlands_') and f.endswith('.png'))
    w, h, cap, pad = 360, 780, 46, 10
    cols = 5
    rows = (len(fs) + cols - 1) // cols
    img = Image.new('RGB', (pad + cols * (w + pad), 96 + rows * (h + cap + pad)), (242, 238, 232))
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 18), 'TOXIC WETLANDS В UNITY', fill=(40, 36, 32), font=font(FONT, 34))
    d.text((pad + 6, 60), 'Обычная игровая камера, качество Mobile, 540×1170 · сценарий wetlands', fill=(110, 100, 90),
           font=font(FONT_R, 20))
    f = font(FONT, 20)
    for i, name in enumerate(fs):
        x = pad + (i % cols) * (w + pad)
        y = 96 + (i // cols) * (h + cap + pad)
        img.paste(Image.open(os.path.join(frames_dir, name)).convert('RGB').resize((w, h), Image.LANCZOS), (x, y))
        text = '%d. %s' % (i + 1, STOPS[i] if i < len(STOPS) else name)
        d.text((x + w / 2 - d.textlength(text, font=f) / 2, y + h + 10), text, fill=(34, 30, 28), font=f)
    img.save(os.path.join(out, 'unity-game-camera.png'))


def before_after(before_dir, renders, out):
    pairs = [('arena-wide.png', 'arena_overview.png', 'Арена'), ('boss-close.png', 'boss_close.png', 'Босс'),
             ('enemies-rust-canyon.png', 'enemies-toxic-wetlands.png', 'Противники')]
    w, h, pad, head, band = 900, 640, 16, 120, 44
    img = Image.new('RGB', (pad + 2 * (w + pad), head + len(pairs) * (band + h + pad)), (242, 238, 232))
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 18), 'ВТОРАЯ ЗОНА: БЫЛО И СТАЛО', fill=(40, 36, 32), font=font(FONT, 34))
    for j, t in enumerate(('Было: Rust Canyon (обзор 2026-11-20)', 'Стало: Toxic Wetlands (Blender, ArtSource)')):
        d.text((pad + j * (w + pad) + 6, 74), t, fill=(110, 100, 90), font=font(FONT, 24))
    for i, (a, b, label) in enumerate(pairs):
        y0 = head + i * (band + h + pad)
        d.text((pad + 6, y0 + 6), label, fill=(40, 36, 32), font=font(FONT, 28))
        y = y0 + band
        for j, path in enumerate((os.path.join(before_dir, a), os.path.join(renders, b))):
            im = Image.open(path).convert('RGB')
            s = min(w / im.width, h / im.height)
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            cell = Image.new('RGB', (w, h), (28, 28, 26))
            cell.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
            img.paste(cell, (pad + j * (w + pad), y))
    img.save(os.path.join(out, 'before-after.png'))


if __name__ == '__main__':
    os.makedirs(sys.argv[2], exist_ok=True)
    enemies(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 3:
        frames(sys.argv[3], sys.argv[2])
    if len(sys.argv) > 4:
        before_after(sys.argv[4], sys.argv[1], sys.argv[2])
