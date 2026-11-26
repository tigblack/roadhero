"""Build review contact sheets from existing, unmodified diagnostic captures."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "sheets"
OUT.mkdir(exist_ok=True)
FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
SCENARIOS = {
    "intro": ("intro", [1, 3, 5, 6.5, 10, 12.5, 13.5, 20, 30]),
    "flip": ("flip", [3, 6, 9, 14, 21, 27, 34, 40, 46, 54, 62, 64]),
    "terrain": ("terrain", [5, 10, 17, 23, 29, 35, 42, 49, 55, 62, 68, 75, 82, 86]),
    "core": ("start", [1, 15, 30, 45, 60, 90, 120, 180, 240, 300, 420, 600]),
}

for scenario, (prefix, times) in SCENARIOS.items():
    for first in range(0, len(times), 3):
        indices = list(range(first, min(first + 3, len(times))))
        sources = [ROOT / "evidence" / scenario / f"{prefix}_{i:02}.png" for i in indices]
        destination = OUT / f"{scenario}-{first // 3 + 1:02}.webp"
        if destination.exists() or not all(source.exists() for source in sources):
            continue
        canvas = Image.new("RGB", (360 * len(sources), 812), (28, 29, 31))
        draw = ImageDraw.Draw(canvas)
        for column, (index, source) in enumerate(zip(indices, sources)):
            with Image.open(source) as frame:
                frame = frame.convert("RGB")
                frame.thumbnail((360, 780))
                canvas.paste(frame, (column * 360, 32))
            draw.text((column * 360 + 8, 7), f"{scenario} {times[index]:g}s | {source.name}", font=FONT, fill="white")
        canvas.save(destination, quality=88)
        print(destination.relative_to(ROOT))
