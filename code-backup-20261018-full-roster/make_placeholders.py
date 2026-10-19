#!/usr/bin/env python3
"""Generate simple placeholder portraits: art/<character>.png (128x128). Replace them with real art later."""
import colorsys
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
# Names exactly as the game spells them in its texture files.
CHARACTERS = ['coco', 'cortex', 'crash', 'crunch', 'dingodile', 'fakecrash', 'komodojoe', 'ngin',
              'nitrusoxide', 'ntrophy', 'papupapu', 'pentapenguin', 'pinstripe', 'polar', 'pura',
              'ripperroo', 'tinytiger', 'zam', 'zem']
FONTS = ['/System/Library/Fonts/Helvetica.ttc', '/System/Library/Fonts/Supplemental/Arial Bold.ttf']


def font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make(name, hue):
    r, g, b = (int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.6, 0.85))
    im = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 3, 124, 124], 18, fill=(r, g, b, 255), outline=(255, 255, 255, 255), width=4)
    d.ellipse([44, 20, 84, 60], fill=(255, 255, 255, 235))
    d.rounded_rectangle([32, 66, 96, 100], 12, fill=(255, 255, 255, 235))
    size = 20
    while size > 8 and d.textlength(name.upper(), font=font(size)) > 112:
        size -= 1
    f = font(size)
    w = d.textlength(name.upper(), font=f)
    d.text(((128 - w) / 2, 104), name.upper(), fill=(0, 0, 0, 255), font=f)
    return im


if __name__ == '__main__':
    os.makedirs(os.path.join(HERE, 'art'), exist_ok=True)
    for i, c in enumerate(CHARACTERS):
        make(c, i / len(CHARACTERS)).save(os.path.join(HERE, 'art', c + '.png'))
    print('wrote', len(CHARACTERS), 'placeholders')
