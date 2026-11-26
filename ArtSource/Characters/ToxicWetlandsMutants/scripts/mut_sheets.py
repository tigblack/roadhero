"""Presentation sheets for the mutants (Pillow; any Python 3).

    python3 mut_sheets.py <renders_dir> <out_dir> [<unity_capture_dir>]

mutants-sheet.png      the seven creatures (3/4 hero renders) with captions
turnarounds.png        front / side / back of every creature, one row each
unity-game-camera.png  Unity frames of the 'mutants' capture scenario from the normal game camera
unity-closeups.png     Unity close-ups of every creature: rest, wind-up, strike, death (boss: rest, stomp, rear-up, death)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
FONT_R = '/System/Library/Fonts/Supplemental/Arial.ttf'
BG = (236, 232, 226)
INK = (38, 34, 32)
SUB = (110, 100, 92)

CREATURES = [
    ('Mut_Leechling', '01 ПИЯВОЧНИК', 'Leechling · вместо Scav', 'низкое тело в ржавых бандажах, пасть-присоска; быстрый укус'),
    ('Mut_MireCrab', '02 КРАБ ТОПЕЙ', 'Mire Crab · вместо Raider', 'панцирь с бочкой, 4 ноги, большая и малая клешни; щипок'),
    ('Mut_ReedStalker', '03 КАМЫШОВЫЙ ПРОНЗАТЕЛЬ', 'Reed Stalker · вместо Spearman', 'длинные ноги, камыш на спине, костяной шип; выпад'),
    ('Mut_BileToad', '04 ЖАБА-ПЛЕВУН', 'Bile Toad · вместо Crossbow', 'железы, трубчатая пасть, горловой мешок; кислотный плевок'),
    ('Mut_SporeBrute', '05 ГРИБНОЙ ГРОМИЛА', 'Spore Brute · вместо Brute', 'корни и грибная ткань, рука-дубина; удар с замаха'),
    ('Mut_FleshEngine', '06 ЖИВОЙ ДВИГАТЕЛЬ', 'Flesh Engine · вместо Buggy', 'кузов сросся с плотью: глаз-фара, челюсть, живой мотор'),
    ('Mut_MireMother', '07 МАТКА ТРЯСИНЫ', 'Mire Mother · вместо BossBaron', 'корни-ноги, цистерна-сердце, корона; топот и удар с дыбов'),
]


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def centered(d, cx, y, text, f, col):
    w = d.textlength(text, font=f)
    d.text((cx - w / 2, y), text, fill=col, font=f)


def hero_sheet(renders, out):
    cell, pad, cap = 560, 20, 120
    cols = 4
    rows = 2
    W = pad + cols * (cell + pad)
    H = 120 + rows * (cell + cap + pad)
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 24), 'TOXIC WETLANDS — БОЛОТНЫЕ МУТАНТЫ', fill=INK, font=font(FONT, 42))
    d.text((pad + 6, 76), 'Вторая зона · Blender: ArtSource/Characters/ToxicWetlandsMutants/ToxicWetlands_Mutants_v2.blend',
           fill=SUB, font=font(FONT_R, 22))
    for i, (key, ru, en, note) in enumerate(CREATURES):
        r, c = divmod(i, cols)
        if r == 1:
            c += 0.5          # second row centred under the first
        x = int(pad + c * (cell + pad))
        y = 120 + r * (cell + cap + pad)
        shot = Image.open(os.path.join(renders, f'{key}_three.png')).convert('RGB').resize((cell, cell), Image.LANCZOS)
        img.paste(shot, (x, y))
        cx = x + cell // 2
        centered(d, cx, y + cell + 10, ru, font(FONT, 30), INK)
        centered(d, cx, y + cell + 48, en, font(FONT_R, 22), SUB)
        centered(d, cx, y + cell + 80, note, font(FONT_R, 17), SUB)
    img.save(os.path.join(out, 'mutants-sheet.png'))


def turnarounds(renders, out):
    cell, pad, lab = 420, 14, 380
    W = lab + 3 * (cell + pad) + pad
    H = 110 + len(CREATURES) * (cell + pad)
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 22), 'СПЕРЕДИ · СБОКУ · СЗАДИ', fill=INK, font=font(FONT, 38))
    d.text((pad + 6, 70), 'Ортогональные виды в позе покоя (Blender, EEVEE)', fill=SUB, font=font(FONT_R, 22))
    for i, (key, ru, en, note) in enumerate(CREATURES):
        y = 110 + i * (cell + pad)
        d.text((pad + 6, y + cell // 2 - 46), ru, fill=INK, font=font(FONT, 22))
        d.text((pad + 6, y + cell // 2 - 12), en.split(' · ')[0], fill=SUB, font=font(FONT_R, 20))
        d.text((pad + 6, y + cell // 2 + 16), en.split(' · ')[1], fill=SUB, font=font(FONT_R, 18))
        for j, v in enumerate(('front', 'side', 'back')):
            shot = Image.open(os.path.join(renders, f'{key}_{v}.png')).convert('RGB').resize((cell, cell), Image.LANCZOS)
            img.paste(shot, (lab + j * (cell + pad), y))
    img.save(os.path.join(out, 'turnarounds.png'))


GAME = [('01_Scav', 'Пиявочник'), ('02_Raider', 'Краб топей'), ('03_Spearman', 'Камышовый пронзатель'),
        ('04_Crossbow', 'Жаба-плевун'), ('05_Brute', 'Грибной громила'), ('06_Buggy', 'Живой двигатель'),
        ('07_BossBaron', 'Матка трясины')]


def unity_frames(cap, out):
    w, h, capw, pad = 300, 650, 52, 10
    cols = 7
    rows = 2
    img = Image.new('RGB', (pad + cols * (w + pad), 100 + rows * (h + capw + pad)), BG)
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 18), 'МУТАНТЫ В UNITY — ОБЫЧНАЯ ИГРОВАЯ КАМЕРА', fill=INK, font=font(FONT, 32))
    d.text((pad + 6, 60), 'Качество Mobile, 540×1170 · сценарий mutants · верхний ряд — подход, нижний — атака',
           fill=SUB, font=font(FONT_R, 20))
    for i, (key, ru) in enumerate(GAME):
        for r, suf in enumerate(('_a_approach', '_b_attack' if not key.startswith('07') else '_c_rearup_slam')):
            p = os.path.join(cap, f'mutants_{key}{suf}.png')
            if not os.path.exists(p):
                continue
            x = pad + i * (w + pad)
            y = 100 + r * (h + capw + pad)
            img.paste(Image.open(p).convert('RGB').resize((w, h), Image.LANCZOS), (x, y))
            centered(d, x + w / 2, y + h + 12, ru, font(FONT, 20), INK)
    img.save(os.path.join(out, 'unity-game-camera.png'))


def unity_close(cap, out):
    cell, pad, lab = 330, 10, 300
    poses = ['покой', 'подготовка', 'удар / выстрел', 'смерть']
    img = Image.new('RGB', (lab + 4 * (cell + pad) + pad, 150 + len(GAME) * (cell + pad)), BG)
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 18), 'АНИМАЦИИ В ИГРЕ — КРУПНЫЙ ПЛАН', fill=INK, font=font(FONT, 32))
    d.text((pad + 6, 60), 'Unity, вторая камера с тем же рендером; кадры сняты в реальном бою в тот кадр, когда игра наносит урон',
           fill=SUB, font=font(FONT_R, 19))
    for j, ptxt in enumerate(poses):
        centered(d, lab + j * (cell + pad) + cell / 2, 108, ptxt if j != 1 else 'подготовка удара', font(FONT, 22), INK)
    for i, (key, ru) in enumerate(GAME):
        y = 150 + i * (cell + pad)
        d.text((pad + 6, y + cell // 2 - 14), ru, fill=INK, font=font(FONT, 20))
        sufs = ['1_rest', '2_windup', '3_strike', '4_death'] if not key.startswith('07') else ['1_rest', '2_stomp', '3_rearup', '4_death']
        for j, sfx in enumerate(sufs):
            p = os.path.join(cap, f'mutants_close_{key}_{sfx}.png')
            if not os.path.exists(p):
                continue
            im = Image.open(p).convert('RGB')
            W_, H_ = im.size
            if H_ > W_:
                im = im.crop((0, (H_ - W_) // 2, W_, (H_ - W_) // 2 + W_))
            im = im.resize((cell, cell), Image.LANCZOS)
            img.paste(im, (lab + j * (cell + pad), y))
    img.save(os.path.join(out, 'unity-closeups.png'))


def silhouette_sheet(renders, out):
    cell, pad = 330, 10
    cols = len(CREATURES)
    img = Image.new('RGB', (pad + cols * (cell + pad), 150 + 2 * (cell + pad) + 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((pad + 6, 18), 'СИЛУЭТЫ БЕЗ ЦВЕТА', fill=INK, font=font(FONT, 32))
    d.text((pad + 6, 60), 'Верхний ряд — угол игровой камеры (54°), нижний — сбоку', fill=SUB, font=font(FONT_R, 20))
    for i, (key, ru, en, note) in enumerate(CREATURES):
        x = pad + i * (cell + pad)
        for r, v in enumerate(('game', 'side')):
            p = os.path.join(renders, f'sil_{key}_{v}.png')
            if os.path.exists(p):
                img.paste(Image.open(p).convert('RGB').resize((cell, cell), Image.LANCZOS), (x, 100 + r * (cell + pad)))
        centered(d, x + cell / 2, 100 + 2 * (cell + pad) + 6, ru.split(' ', 1)[1], font(FONT, 18), INK)
    img.save(os.path.join(out, 'silhouettes.png'))


if __name__ == '__main__':
    renders, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    hero_sheet(renders, out)
    turnarounds(renders, out)
    silhouette_sheet(renders, out)
    if len(sys.argv) > 3:
        unity_frames(sys.argv[3], out)
        unity_close(sys.argv[3], out)
    print('MUT_SHEETS', out)
