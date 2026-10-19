"""Regression checks for descriptor offsets, portrait matching and reversible writes."""
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from roster import character

from iga import IGA
import ctr_hud as mod

NAME = 'textures/octane_ui_hud_racerportrait_coco`tga,101.igz'


def archive(path, data, high=0, decoy=None, name=NAME):
    header = bytearray(0x38)
    header[:4] = b'IGA\x1a'
    for off, value in ((4, 13), (12, 1), (16, 2048)):
        struct.pack_into('<I', header, off, value)
    names = struct.pack('<I', 4) + name.encode() + b'\0'
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
        f.truncate((f.tell() + 2047) // 2048 * 2048)


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
            archive(arch / 'minimap.pak', b'prefix' + bytes(4096),
                    name='textures/octane_ui_minimaps_portrait_coco`tga,101.igz')
            (blobs / 'coco_64.bin').write_bytes(bytes([42]) * 4096)
            saved = mod.BACKUP, mod.BLOBS, mod.STATE, mod.CHARACTERS
            mod.BACKUP, mod.BLOBS, mod.STATE = map(str, (root / 'backup', blobs, root / 'state.json'))
            mod.CHARACTERS = ('coco',)
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
                mod.BACKUP, mod.BLOBS, mod.STATE, mod.CHARACTERS = saved


    def test_aliases_keep_baby_coco_separate(self):
        self.assertEqual(character('coco_baby_pj'), 'babycoco')
        self.assertEqual(character('coco_star'), 'coco')
        self.assertEqual(character('tiny_cheetah'), 'tinytiger')
        self.assertEqual(character('nitrosoxide_hotrod'), 'nitrusoxide')
        with self.assertRaises(ValueError):
            character('unknown')

    def test_multichunk_encoding_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'multi.pak'
            payload = bytes(range(256)) * 400
            archive(path, payload)
            a = IGA(path)
            try:
                self.assertEqual(a.read(a.entries[0])[0], payload)
            finally:
                a.f.close()

    def test_embedded_offsets_bounds_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arch = root / 'archives'
            arch.mkdir()
            blobs = root / 'blobs'
            blobs.mkdir()
            original_files = {}
            for small in (False, True):
                child = root / 'child.pak'
                marker = 'minimaps_portrait' if small else 'hud_racerportrait'
                size = 4096 if small else 16384
                archive(child, b'prefix' + bytes(size),
                        name='textures/octane_ui_%s_nina`tga,101.igz' % marker)
                data = child.read_bytes()
                # Build an outer raw container around the child archive.
                outer = arch / ('small.pak' if small else 'large.pak')
                archive(outer, b'x', name='install/archives/DriverNCX.pak')
                with open(outer, 'r+b') as f:
                    f.seek(60 + 8)
                    f.write(struct.pack('<2I', len(data), 0xffffffff))
                    f.seek(2048)
                    f.write(data)
                original_files[outer] = outer.read_bytes()
                (blobs / ('nina_64.bin' if small else 'nina.bin')).write_bytes(bytes([42]) * size)
            saved = mod.BACKUP, mod.BLOBS, mod.STATE
            mod.BACKUP, mod.BLOBS, mod.STATE = map(str, (root / 'backup', blobs, root / 'state.json'))
            try:
                with patch.object(mod, 'CHARACTERS', ('nina',)), contextlib.redirect_stdout(io.StringIO()):
                    mod.cmd_on(str(arch))
                    mod.cmd_verify(str(arch))
                    records = mod.load_state()['applied']
                    self.assertTrue(all(r['off'] == 4096 and len(r['container']) == 1 for r in records))
                    patched = {p: p.read_bytes() for p in original_files}
                    # A damaged backup must block OFF before any live file changes.
                    backup = Path(mod.BACKUP) / records[-1]['backup']
                    good = backup.read_bytes()
                    backup.write_bytes(bytes(len(good)))
                    with self.assertRaises(ValueError):
                        mod.cmd_off(str(arch))
                    self.assertEqual({p: p.read_bytes() for p in patched}, patched)
                    backup.write_bytes(good)
                    mod.cmd_off(str(arch))
                    self.assertEqual({p: p.read_bytes() for p in original_files}, original_files)
                a = IGA(arch / 'large.pak', base=2048, length=4096)
                try:
                    with self.assertRaises(ValueError):
                        a.f.seek(4097)
                finally:
                    a.f.close()
            finally:
                mod.BACKUP, mod.BLOBS, mod.STATE = saved


if __name__ == '__main__':
    unittest.main()
