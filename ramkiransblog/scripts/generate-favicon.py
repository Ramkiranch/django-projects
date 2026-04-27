#!/usr/bin/env python3
"""Generate favicon.ico + apple-touch-icon.png for ramkiransblog.

Pillow is already a project dep (used by Post.image), so no extra install.
Run from the repo root:

    .venv/bin/python scripts/generate-favicon.py

Outputs land in ramkiransblog/static/img/. Re-run if the brand color
or letter changes.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / 'ramkiransblog' / 'static' / 'img'
ACCENT = (13, 110, 253)  # #0d6efd — same accent as main.css's --rk-accent
LETTER = 'R'

FONT_CANDIDATES = [
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/Library/Fonts/Arial Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Linux fallback
]


def find_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, int(size * 0.72))
        except OSError:
            continue
    return ImageFont.load_default()


def render_letter(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), ACCENT + (255,))
    draw = ImageDraw.Draw(img)
    font = find_font(size)
    bbox = draw.textbbox((0, 0), LETTER, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), LETTER, fill='white', font=font)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Multi-size .ico for crisp display in browser tabs and tab-overflow menus
    favicon = render_letter(64)
    favicon.save(OUT_DIR / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print(f'wrote {OUT_DIR / "favicon.ico"}')

    # 180x180 PNG for iOS home-screen pin
    apple = render_letter(180)
    apple.save(OUT_DIR / 'apple-touch-icon.png', 'PNG', optimize=True)
    print(f'wrote {OUT_DIR / "apple-touch-icon.png"}')


if __name__ == '__main__':
    main()
