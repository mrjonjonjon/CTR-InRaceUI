"""Regression checks for descriptor offsets, portrait matching and reversible writes."""
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from iga import IGA
import ctr_hud as mod

NAME = 'textures/octane_ui_hud_racerportrait_coco`tga,101.igz'


def archive(path, data, high=0, decoy=None):
    header = bytearray(0x38)
    header[:4] = b'IGA\x1a'
    for off, value in ((4, 13), (12, 1), (16, 2048)):
        struct.pack_into('<I', header, off, value)
    names = struct.pack('<I', 4) + NAME.encode() + b'\0'
    struct.pack_into('<Q', header, 40, 512)
    struct.pack_into('<I', header, 48, len(names))
    with open(path, 'wb') as f:
        f.write(header)
        f.write(bytes(4))
        f.write(struct.pack('<4I', 2048, (7 << 8) | high, len(data), 0x20000000))
        f.seek(512)
        f.write(names)
        if decoy is not None:
            f.seek(2048)
            f.write(IGA.encode(decoy))
        f.seek(2048 + (high << 32))
        f.write(IGA.encode(data))
        f.truncate(4096 + (high << 32))


class ModTests(unittest.TestCase):
    def test_high_offset_with_valid_low_offset_decoy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'large.pak'
            archive(p, b'correct high payload', high=1, decoy=b'unrelated low data!')
            a = IGA(p)
            try:
                data, off, used, room = a.read(a.entries[0])
                self.assertEqual(data, b'correct high payload')
                self.assertEqual(off, (1 << 32) + 2048)
            finally:
                a.f.close()

    def test_missing_high_payload_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'large.pak'
            archive(p, b'high', high=1, decoy=b'low')
            with open(p, 'r+b') as f:
                f.seek((1 << 32) + 2048)
                f.write(bytes(9))
            a = IGA(p)
            try:
                with self.assertRaises(ValueError):
                    a.read(a.entries[0])
            finally:
                a.f.close()

    def test_toggle_round_trip_and_verify_detects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arch = root / 'archives'
            arch.mkdir()
            blobs = root / 'blobs'
            blobs.mkdir()
            original = b'IGZ descriptor prefix' + bytes(range(256)) * 64
            replacement = bytes([42]) * 16384
            (blobs / 'coco.bin').write_bytes(replacement)
            p = arch / 'drivercoco.pak'
            archive(p, original)
            before = p.read_bytes()
            saved = mod.BACKUP, mod.BLOBS, mod.STATE
            mod.BACKUP, mod.BLOBS, mod.STATE = map(str, (root / 'backup', blobs, root / 'state.json'))
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    mod.cmd_on(str(arch))
                    mod.cmd_verify(str(arch))
                patched = p.read_bytes()
                self.assertNotEqual(before, patched)
                record = json.loads(Path(mod.STATE).read_text())['applied'][0]
                # A valid compressed stream containing the wrong art must fail verification.
                with open(p, 'r+b') as f:
                    f.seek(record['off'])
                    f.write(IGA.encode(b'IGZ descriptor prefix' + bytes([43]) * 16384))
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        mod.cmd_verify(str(arch))
                self.assertEqual(exc.exception.code, 1)
                with contextlib.redirect_stdout(io.StringIO()):
                    mod.cmd_off(str(arch))
                self.assertEqual(p.read_bytes(), before)
                self.assertEqual(json.loads(Path(mod.STATE).read_text())['applied'], [])
            finally:
                mod.BACKUP, mod.BLOBS, mod.STATE = saved


if __name__ == '__main__':
    unittest.main()
