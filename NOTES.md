# CTR HUD portrait mod — full roster

The mod supplies **56 character PNGs** and replaces **862 HUD and minimap texture
entries**, including default and alternate skins in this CUSA13795 installation.
The active art is now the generated Nitro Kart-style sprite sheet, split into
56 complete silhouettes with 128×128 transparent PNGs in `art/`. Each portrait
also supplies the 64×64 minimap texture. Nina Cortex is included (`art/nina.png`).
The previous full-roster placeholder set is saved in a snapshot.

## Toggle on the Steam Deck

Close SacredFire, then use **CTR-HUD-Mod-ON** or **CTR-HUD-Mod-OFF** on the Desktop.
The expanded mod is ON after installation. OFF restores the saved original bytes.
Keep `state.json` and `backup/` while ON.

```sh
cd ~/ctr-hud-mod
./ctr-hud.sh status
./ctr-hud.sh verify
./ctr-hud.sh plan
```

`plan` checks the full roster, compression and slot sizes without writing.
`verify` compares every portrait payload against its replacement blob, verifies
recorded absolute offsets, and checks backup lengths and SHA-256 checksums.
These checks validate archive data. Test a fresh game/race to confirm rendering.

ON preflights every replacement before changing any archive; missing art,
unknown characters, missing HUD/minimap coverage, overlapping writes or a blob
that cannot fit cause an error. It does not silently skip characters. Each
backup and its rollback record is persisted before its archive write. OFF
validates every backup before it restores any archive.

## Replace character art

1. Turn the mod OFF.
2. Replace the corresponding PNGs in `art/`, preserving their filenames.
3. On the Mac, build the texture blobs with Pillow and NumPy:

   ```sh
   cd ~/ctr-hud-mod
   python3 -m venv .venv
   .venv/bin/pip install pillow numpy
   .venv/bin/python build.py
   ```

   `build.py` flips each image vertically (the game samples these textures upside down), so
   keep `art/` upright. `blobs/` is generated and not committed; rebuild it after cloning.

4. Sync `art/`, `blobs/`, `build.py` and `texture-settings.json` to `deck@10.0.0.10:~/ctr-hud-mod/` and turn ON.

One image per character supplies every skin variant, at 128×128 for the HUD and
64×64 for the minimap. `make_placeholders.py` creates missing images and preserves
existing art. `roster.py` defines the canonical filenames and game-name aliases;
Baby Coco (`coco_baby`) is kept separate from Coco, and Tiny's aliases map to
`tinytiger`.

## Why the original scanner covered only 19 characters

Later driver and outfit archives are stored as raw nested `.pak` entries inside
`update.pak` and `update2.pak`. A search of outer indexes cannot see their texture
names. The scanner now visits all 405 outer archives and 945 embedded archives,
using bounded access and absolute physical write offsets. No large outer archive
is rebuilt. Portrait frames, unrelated customization icons and material files
are left alone. Extra Crash minimap copies are included.

The historical IGA entry field named `size` contains a packed ordinal and the
high offset byte, not compressed size. The reader decodes its 40-bit offset and
uses aligned LZMA chunks. All target portraits fit one decompressed chunk.

## Coverage and validation

`roster.py` lists all 56 characters, including Nina, Baby Coco, Baby Cortex,
Baby N. Tropy, Fixed Rilla Roo and the Iron Checkpoint Crate (`crate`). Every
portrait-name variant found in this installation is included: 862 replacements,
zero skipped; frames are excluded. In-game use still needs a fresh-race check
for newly added characters. The user previously confirmed Coco, Crash,
Komodo Joe, Zam and Zem with the original mod.

Run `python3 test_mod.py -v` for six regression checks: 40-bit offsets with a
valid decoy, rejection of an invalid real offset, Baby Coco and other aliases,
aligned multi-chunk encoding, nested archive bounds and byte-for-byte rollback,
corrupt backup rejection, and replacement-payload verification.

The pre-expansion Deck snapshot is stored in
`snapshots/before-full-roster-20261018.tar.gz`. It contains the previous code,
19 images, blobs, applied state and original backups. Current `backup/` remains
the normal OFF restore source; the snapshot is a historical fallback.

## Generated sprite-sheet installation

Source: `generated/cnk-spritesheet-v1/portraits.png`. `split_sheet.py` extracts
connected alpha silhouettes, preserving hair and ears that cross nominal grid
lines, and writes separate PNGs into the source folder's `extracted/` directory.
The source had exactly 56 large components; every opaque source pixel was assigned
to one portrait. `split-manifest.json` records their actual bounds.

`build.py` reads `texture-settings.json` to reproduce all 112 installed blobs.
The current art uses Pillow's DXT5 encoder, crisp transparent edges, and full
128×128/64×64 dimensions. The 18 HUD portraits with the tightest slots use reduced
color palettes; the remaining 38 HUD portraits and all 56 minimap portraits use
full color before BC3 compression. No portrait was downscaled below its target
resolution. `fit-report.json` records the per-character choices and slot margins.

`generated/cnk-spritesheet-v1/encoded-preview.png` shows decoded textures as the
game will receive them. The pre-install placeholder snapshot on both machines is
`snapshots/before-cnk-spritesheet-20261018.tar.gz`. On the Deck this also preserves
the applied state, original byte backups and Desktop shortcut files. The ordinary
OFF shortcut continues to restore original game art, rather than the placeholders.

## Character select icons

The select grid uses `octane_ui_custo_ico_char_skin_<char>_NN` (160×160 BC3, 25600 bytes,
the same tiled layout; 696 entries). Their compressed slots are only 6144 or 8192 bytes,
so `texture-settings.json` stores a palette size per character under `"160"`, chosen so the
encoded stream fits with a 200-byte margin. 25 characters appear as `racer32`..`racer56`;
`roster.py` maps these numbers to names by matching the icons against the original HUD
portraits (the baby characters are the least certain). `ctr-hud.sh plan` checks that
everything fits before writing.
