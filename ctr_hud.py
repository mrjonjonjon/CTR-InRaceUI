#!/usr/bin/env python3
"""Toggle the Crash Team Racing Nitro-Fueled HUD portrait mod.

  ctr_hud.py on       swap the racer portraits for the art in blobs/
  ctr_hud.py off      put the original portraits back (byte-for-byte)
  ctr_hud.py status   show whether the mod is on and which characters have art
  ctr_hud.py verify   read back every applied portrait and check its backup
  ctr_hud.py plan     validate full-roster coverage and slot sizes without writing

Only the few KB of each portrait inside the game's .pak files are rewritten; the originals are
saved in backup/ first. Close the game before toggling.
"""
import glob
import hashlib
import json
import lzma
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iga import IGA  # noqa: E402
from roster import CHARACTERS, character  # noqa: E402

BACKUP = os.path.join(HERE, 'backup')
BLOBS = os.path.join(HERE, 'blobs')
STATE = os.path.join(HERE, 'state.json')
SUFFIX_BYTES = {'': 16384, '_64': 4096, '_160': 25600}
SKIP = ('bg', 'contour')  # the portrait frame, not a character


def game_dir():
    if len(sys.argv) > 2 and not sys.argv[2].startswith('-'):
        return sys.argv[2]
    for p in glob.glob(os.path.expanduser('~/.config/sacredfire*/settings.json')):
        with open(p) as f:
            d = json.load(f).get('game_dir')
        if d:
            return d
    sys.exit('Cannot find the game folder; pass it as the second argument.')


def pak_files(arch):
    return sorted(fn for fn in os.listdir(arch) if fn.lower().endswith('.pak'))


def archives(arch, mode='rb'):
    """Visit outer and raw embedded archives; all offsets stay container-relative."""
    def visit(path, fn, base, length, containers):
        a = IGA(path, mode, base=base, length=length)
        try:
            yield fn, containers, a
            for e in a.entries:
                if not e['name'].lower().endswith('.pak'):
                    continue
                if e['mode'] != 0xffffffff:
                    raise ValueError('Compressed embedded archive requires explicit support: ' + e['name'])
                offset = e['off'] + ((e['size'] & 255) << 32)
                if offset + e['aux'] > a.length:
                    raise ValueError('Embedded archive outside its parent: ' + e['name'])
                yield from visit(path, fn, base + offset, e['aux'], containers + [e['name']])
        finally:
            a.f.close()
    for fn in pak_files(arch):
        path = os.path.join(arch, fn)
        yield from visit(path, fn, 0, os.path.getsize(path), [])


def game_running():
    out = subprocess.run(['pgrep', '-af', 'sacredfire|SacredFire'], capture_output=True, text=True).stdout
    return any(str(os.getpid()) != ln.split()[0] and 'ctr_hud' not in ln for ln in out.splitlines())


def load_state():
    if not os.path.exists(STATE):
        return {'applied': []}
    with open(STATE) as f:
        return json.load(f)


def save_state(st):
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(st, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)


def portraits(a):
    for e in a.entries:
        n = e['name'].lower()
        if not (n.lower().endswith('.igz') and e['mode'] >> 24 == 0x20):
            continue
        for marker in ('octane_ui_hud_racerportrait_', 'octane_ui_minimaps_portrait_',
                       'octane_ui_custo_ico_char_skin_'):
            if marker in n:
                token = n.rsplit(marker, 1)[1].split('`')[0]
                if token in SKIP:
                    break
                if 'custo_ico' in marker:
                    yield e, character(token), '_160'
                else:
                    yield e, character(token), '_64' if 'minimaps' in marker and e['aux'] < 10000 else ''
                break


def make_plan(arch):
    """Validate every portrait before any archive is modified."""
    plan = []
    covered = set()
    for fn, containers, a in archives(arch):
        for e, char, suffix in portraits(a):
            blob_path = os.path.join(BLOBS, char + suffix + '.bin')
            with open(blob_path, 'rb') as f:
                blob = f.read()
            if len(blob) != SUFFIX_BYTES[suffix]:
                raise ValueError('Incorrect replacement texture length: ' + blob_path)
            igz, off, used, room = a.read(e)
            if len(igz) < len(blob):
                raise ValueError('IGZ too small: ' + e['name'])
            enc = IGA.encode(igz[:-len(blob)] + blob, align=a.align)
            if len(enc) > room:
                raise ValueError('Replacement does not fit (%d > %d): %s' %
                                 (len(enc), room, e['name']))
            a.f.seek(off)
            original = a.f.read(len(enc))
            tag = '%s__%x__%d.bin' % (fn[:-4], a.base, e['i'])
            record = dict(pak=fn, off=a.base + off, len=len(enc), backup=tag,
                          name=e['name'], container=containers, char=char,
                          sha256=hashlib.sha256(original).hexdigest())
            plan.append((record, original, enc))
            covered.add((char, suffix))
    missing = {(c, sfx) for c in CHARACTERS for sfx in ('', '_64')} - covered
    if missing:
        raise ValueError('Roster coverage missing: ' + repr(sorted(missing)))
    # Check physical ranges, including portraits inside embedded archives.
    by_pak = {}
    for record, original, enc in plan:
        by_pak.setdefault(record['pak'], []).append(record)
    for fn, records in by_pak.items():
        ordered = sorted(records, key=lambda r: r['off'])
        for left, right in zip(ordered, ordered[1:]):
            if left['off'] + left['len'] > right['off']:
                raise ValueError('Overlapping portrait writes in ' + fn)
    return plan


def cmd_plan(arch):
    plan = make_plan(arch)
    print('READY: %d portraits across %d characters; every replacement fits. No files changed.' %
          (len(plan), len({r['char'] for r, _, _ in plan})))


def cmd_on(arch):
    st = load_state()
    if st['applied']:
        sys.exit('Already on (%d portraits). Run "off" first to rebuild.' % len(st['applied']))
    plan = make_plan(arch)
    os.makedirs(BACKUP, exist_ok=True)
    by_pak = {}
    for item in plan:
        by_pak.setdefault(item[0]['pak'], []).append(item)
    for fn, items in by_pak.items():
        with open(os.path.join(arch, fn), 'r+b') as f:
            for record, original, enc in items:
                f.seek(record['off'])
                if f.read(len(original)) != original:
                    raise ValueError('Archive changed after preflight: ' + fn)
                with open(os.path.join(BACKUP, record['backup']), 'wb') as backup:
                    backup.write(original)
                    backup.flush()
                    os.fsync(backup.fileno())
                # Persist the rollback record before writing to the archive.
                st['applied'].append(record)
                save_state(st)
                f.seek(record['off'])
                f.write(enc)
            f.flush()
            os.fsync(f.fileno())
        print('%s: %d portraits' % (fn, len(items)), flush=True)
    print('ON: %d portraits replaced for all %d characters; 0 skipped.' %
          (len(plan), len(CHARACTERS)))


def cmd_off(arch):
    st = load_state()
    if not st['applied']:
        print('Already off.')
        return
    # Validate every backup before restoring any archive. Old 19-character states
    # remain compatible; their records predate checksums and container paths.
    by_pak = {}
    for r in st['applied']:
        with open(os.path.join(BACKUP, r['backup']), 'rb') as f:
            original = f.read()
        if len(original) != r['len']:
            raise ValueError('Backup length mismatch: ' + r['backup'])
        if r.get('sha256') and hashlib.sha256(original).hexdigest() != r['sha256']:
            raise ValueError('Backup checksum mismatch: ' + r['backup'])
        if r['off'] < 0 or r['off'] + r['len'] > os.path.getsize(os.path.join(arch, r['pak'])):
            raise ValueError('Restore range outside archive: ' + r['pak'])
        by_pak.setdefault(r['pak'], []).append((r, original))
    for fn, items in by_pak.items():
        with open(os.path.join(arch, fn), 'r+b') as f:
            for r, original in items:
                f.seek(r['off'])
                f.write(original)
            f.flush()
            os.fsync(f.fileno())
    n = len(st['applied'])
    st['applied'] = []
    save_state(st)
    for items in by_pak.values():
        for r, _ in items:
            os.remove(os.path.join(BACKUP, r['backup']))
    print('OFF: %d original portraits restored.' % n)


def cmd_status(arch):
    st = load_state()
    print('HUD portrait mod is %s (%d portraits swapped).' % ('ON' if st['applied'] else 'OFF', len(st['applied'])))
    chars = sorted(os.path.splitext(os.path.basename(p))[0]
                   for p in glob.glob(os.path.join(HERE, 'art', '*.png')))
    print('Art supplied for %d characters: %s.' % (len(chars), ', '.join(chars)))
    print('Roster: %d playable characters, including Nina and every alternate skin.' % len(CHARACTERS))


def cmd_verify(arch):
    """Read-only payload and rollback-file check. This does not prove in-game use."""
    st = load_state()
    if not st['applied']:
        cmd_status(arch)
        return
    records = {(r['pak'], tuple(r.get('container', [])), r['name']): r for r in st['applied']}
    errors = []
    if len(records) != len(st['applied']):
        errors.append('Duplicate records in state.json')
    checked = 0
    covered = set()
    for fn, containers, a in archives(arch):
        for e, char, suffix in portraits(a):
            blob_path = os.path.join(BLOBS, char + suffix + '.bin')
            if not os.path.exists(blob_path):
                errors.append('Missing art blob: ' + blob_path)
                continue
            r = records.pop((fn, tuple(containers), e['name']), None)
            label = fn + ': ' + e['name'].split('!')[-1]
            if r is None:
                errors.append(label + ': no applied record')
                continue
            try:
                with open(blob_path, 'rb') as f:
                    blob = f.read()
                data, off, used, room = a.read(e)
                if not blob or not data.endswith(blob):
                    errors.append(label + ': replacement data mismatch')
                if a.base + off != r['off'] or not 0 < r['len'] <= room:
                    errors.append(label + ': recorded write range mismatch')
                with open(os.path.join(BACKUP, r['backup']), 'rb') as f:
                    backup = f.read()
                if len(backup) != r['len']:
                    errors.append(label + ': backup length mismatch')
                if r.get('sha256') and hashlib.sha256(backup).hexdigest() != r['sha256']:
                    errors.append(label + ': backup checksum mismatch')
                checked += 1
                covered.add(char)
            except (OSError, ValueError, EOFError, lzma.LZMAError) as exc:
                errors.append(label + ': ' + str(exc))
    for fn, containers, name in records:
        errors.append(fn + ': unmatched state record: ' + name)
    missing = set(CHARACTERS) - covered
    if missing:
        errors.append('Roster coverage missing: ' + ', '.join(sorted(missing)))
    for error in errors:
        print('FAIL: ' + error)
    print('Checked %d applied portraits for %d characters; %d errors.' %
          (checked, len(covered), len(errors)))
    print('Verified characters: ' + ', '.join(sorted(covered)))
    print('This checks archive bytes and backup lengths; test the HUD in a fresh race to confirm use.')
    if errors:
        raise SystemExit(1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('on', 'off', 'status', 'verify', 'plan'):
        sys.exit(__doc__)
    arch = os.path.join(game_dir(), 'archives')
    if sys.argv[1] in ('on', 'off') and '--force' not in sys.argv and game_running():
        sys.exit('The game looks like it is running. Close it first (or pass --force).')
    {'on': cmd_on, 'off': cmd_off, 'status': cmd_status, 'verify': cmd_verify, 'plan': cmd_plan}[sys.argv[1]](arch)


if __name__ == '__main__':
    main()
