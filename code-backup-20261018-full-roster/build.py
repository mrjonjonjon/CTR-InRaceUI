#!/usr/bin/env python3
"""Encode art/<character>.png (128x128) into the game's texture format: blobs/<character>.bin.

The game stores HUD portraits as 128x128 BC3 (DXT5) textures in PS4 1D-tiled order.
Needs Pillow and numpy:  pip install pillow numpy
"""
import glob
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 128


def morton8(i):
    x = (i & 1) | ((i >> 2) & 1) << 1 | ((i >> 4) & 1) << 2
    y = ((i >> 1) & 1) | ((i >> 3) & 1) << 1 | ((i >> 5) & 1) << 2
    return x, y


def tile(blocks, bw, bh):
    """Row-major list of 16-byte blocks -> PS4 thin 1D tiled order (8x8 block micro tiles)."""
    out = []
    for t in range((bw // 8) * (bh // 8)):
        tx, ty = t % (bw // 8), t // (bw // 8)
        for i in range(64):
            x, y = morton8(i)
            out.append(blocks[(ty * 8 + y) * bw + tx * 8 + x])
    return out


def rgb565(c):
    c = np.clip(np.round(c), 0, 255).astype(int)
    return int(((c[0] * 31 + 127) // 255) << 11 | ((c[1] * 63 + 127) // 255) << 5 | ((c[2] * 31 + 127) // 255))


def unpack565(v):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return np.array([r * 255 // 31, g * 255 // 63, b * 255 // 31], float)


def encode_block(px):
    """px: 4x4x4 RGBA uint8 -> 16 byte BC3 block."""
    a = px[:, :, 3].reshape(16).astype(int)
    a0, a1 = int(a.max()), int(a.min())
    pal = [a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
    if a0 == a1:
        abits = 0
    else:
        idx = [int(np.argmin([abs(v - p) for p in pal])) for v in a]
        abits = sum(i << (3 * n) for n, i in enumerate(idx))
    ablock = bytes([a0, a1]) + abits.to_bytes(6, 'little')

    rgb = px[:, :, :3].reshape(16, 3).astype(float)
    weight = a > 0
    src = rgb[weight] if weight.any() else rgb
    lo, hi = src.min(axis=0), src.max(axis=0)
    c0, c1 = rgb565(hi), rgb565(lo)
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:
        pal4 = [unpack565(c0)] * 4
    else:
        p0, p1 = unpack565(c0), unpack565(c1)
        pal4 = [p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3]
    bits = 0
    for n in range(16):
        d = [float(((rgb[n] - p) ** 2).sum()) for p in pal4]
        bits |= int(np.argmin(d)) << (2 * n)
    if c0 == c1:
        bits = 0
    return ablock + c0.to_bytes(2, 'little') + c1.to_bytes(2, 'little') + bits.to_bytes(4, 'little')


def encode(path, size=SIZE):
    im = Image.open(path).convert('RGBA')
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    arr = np.array(im)
    bw = bh = size // 4
    blocks = [encode_block(arr[y * 4:y * 4 + 4, x * 4:x * 4 + 4]) for y in range(bh) for x in range(bw)]
    return b''.join(tile(blocks, bw, bh))


if __name__ == '__main__':
    os.makedirs(os.path.join(HERE, 'blobs'), exist_ok=True)
    for p in sorted(glob.glob(os.path.join(HERE, 'art', '*.png'))):
        name = os.path.splitext(os.path.basename(p))[0]
        for size, suffix in ((SIZE, ''), (64, '_64')):
            data = encode(p, size)
            assert len(data) == size * size
            open(os.path.join(HERE, 'blobs', name + suffix + '.bin'), 'wb').write(data)
        print('encoded', name)
