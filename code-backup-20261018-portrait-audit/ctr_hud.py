#!/usr/bin/env python3
"""Toggle the Crash Team Racing Nitro-Fueled HUD portrait mod.

  ctr_hud.py on       swap the racer portraits for the art in blobs/
  ctr_hud.py off      put the original portraits back (byte-for-byte)
  ctr_hud.py status   show whether the mod is on

Only the few KB of each portrait inside the game's .pak files are rewritten; the originals are
saved in backup/ first. Close the game before toggling.
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iga import IGA  # noqa: E402

BACKUP = os.path.join(HERE, 'backup')
BLOBS = os.path.join(HERE, 'blobs')
STATE = os.path.join(HERE, 'state.json')
PAKS = ('basedriver.pak', 'juicedomain_hub.pak', 'juicedomain_race.pak', 'juicedomain_race_flareday.pak',
        'juicedomain_race_flarenight.pak', 'juicedomain_startscreen.pak', 'update.pak', 'update2.pak')
SKIP = ('bg', 'contour')  # the portrait frame, not a character
ALIAS = {'nitrosoxide': 'nitrusoxide'}  # the game spells this character two ways


def game_dir():
    if len(sys.argv) > 2 and not sys.argv[2].startswith('-'):
        return sys.argv[2]
    for p in glob.glob(os.path.expanduser('~/.config/sacredfire*/settings.json')):
        d = json.load(open(p)).get('game_dir')
        if d:
            return d
    sys.exit('Cannot find the game folder; pass it as the second argument.')


def pak_files(arch):
    for fn in sorted(os.listdir(arch)):
        if fn in PAKS or (fn.startswith('driver') and fn.endswith('.pak')):
            yield fn


def game_running():
    out = subprocess.run(['pgrep', '-af', 'sacredfire|SacredFire'], capture_output=True, text=True).stdout
    return any(str(os.getpid()) != ln.split()[0] and 'ctr_hud' not in ln for ln in out.splitlines())


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {'applied': []}


def save_state(st):
    tmp = STATE + '.tmp'
    json.dump(st, open(tmp, 'w'), indent=1)
    os.replace(tmp, STATE)


def portraits(a):
    for e in a.entries:
        n = e['name']
        if not (n.lower().endswith('.igz') and e['mode'] >> 24 == 0x20):
            continue
        for marker in ('octane_ui_hud_racerportrait_', 'octane_ui_minimaps_portrait_'):
            if marker in n:
                token = n.rsplit(marker, 1)[1].split('`')[0]
                if token not in SKIP:
                    char = token.split('_')[0]
                    yield e, ALIAS.get(char, char), 'minimaps' in marker and e['aux'] < 10000
                break


def cmd_on(arch):
    st = load_state()
    if st['applied']:
        sys.exit('Already on (%d portraits). Run "off" first to rebuild.' % len(st['applied']))
    os.makedirs(BACKUP, exist_ok=True)
    done = []
    skipped = 0
    for fn in pak_files(arch):
        a = IGA(os.path.join(arch, fn), 'r+b')
        for e, char, small in portraits(a):
            blob_path = os.path.join(BLOBS, char + ('_64' if small else '') + '.bin')
            if not os.path.exists(blob_path):
                skipped += 1
                print('  no art for %s (%s), left alone' % (char, fn))
                continue
            blob = open(blob_path, 'rb').read()
            igz, off, used, room = a.read(e)
            if len(igz) < len(blob):
                skipped += 1
                print('  %s: unexpected size, left alone' % e['name'][-40:])
                continue
            enc = IGA.encode(igz[:-len(blob)] + blob)
            if len(enc) > room:
                skipped += 1
                print('  %s: new data too big (%d > %d), left alone' % (e['name'][-40:], len(enc), room))
                continue
            a.f.seek(off)
            orig = a.f.read(len(enc))
            tag = '%s__%d' % (fn[:-4], e['i'])
            open(os.path.join(BACKUP, tag + '.bin'), 'wb').write(orig)
            # Record before writing so an interruption can always be rolled back.
            st['applied'].append(dict(pak=fn, off=off, len=len(enc), backup=tag + '.bin', name=e['name']))
            save_state(st)
            a.f.seek(off)
            a.f.write(enc)
            done.append(tag)
        a.f.flush()
        os.fsync(a.f.fileno())
        a.f.close()
        print('%s: %d portraits so far' % (fn, len(done)))
    print('ON: %d portraits replaced, %d skipped.' % (len(done), skipped))


def cmd_off(arch):
    st = load_state()
    if not st['applied']:
        print('Already off.')
        return
    by_pak = {}
    for r in st['applied']:
        by_pak.setdefault(r['pak'], []).append(r)
    for fn, recs in by_pak.items():
        with open(os.path.join(arch, fn), 'r+b') as f:
            for r in recs:
                f.seek(r['off'])
                f.write(open(os.path.join(BACKUP, r['backup']), 'rb').read())
            f.flush()
            os.fsync(f.fileno())
    n = len(st['applied'])
    st['applied'] = []
    save_state(st)
    for fn in os.listdir(BACKUP):
        os.remove(os.path.join(BACKUP, fn))
    print('OFF: %d original portraits restored.' % n)


def cmd_status(arch):
    st = load_state()
    print('HUD portrait mod is %s (%d portraits swapped).' % ('ON' if st['applied'] else 'OFF', len(st['applied'])))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('on', 'off', 'status'):
        sys.exit(__doc__)
    arch = os.path.join(game_dir(), 'archives')
    if sys.argv[1] != 'status' and '--force' not in sys.argv and game_running():
        sys.exit('The game looks like it is running. Close it first (or pass --force).')
    {'on': cmd_on, 'off': cmd_off, 'status': cmd_status}[sys.argv[1]](arch)


if __name__ == '__main__':
    main()
