# CTR-InRaceUI

Replaces the in-race HUD and minimap character portraits in **Crash Team Racing
Nitro-Fueled** (PC/Linux port via SacredFire, tested on Steam Deck) with custom art.
It covers 56 characters and every skin (1558 textures: HUD portraits, minimap portraits
and the 160×160 skin icons used in the character select grid). The game's original bytes
are backed up, so the mod can be switched off at any time.

Technical details are in [NOTES.md](NOTES.md).

## Requirements

- Steam Deck (or Linux box) running the game through SacredFire, reachable over SSH
  as `deck@10.0.0.10` (edit the address if yours differs).
- Mac/Linux with Python 3 for building the art.
- The game closed whenever you toggle the mod.

## Install

1. Copy this folder to the Deck at `~/ctr-hud-mod/`:

   ```sh
   rsync -a --exclude .git --exclude .venv ./ deck@10.0.0.10:ctr-hud-mod/
   ```

2. Build the texture blobs (they are generated, not committed):

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python build.py
   rsync -a blobs deck@10.0.0.10:ctr-hud-mod/
   ```

3. Optional: copy `CTR-HUD-Mod-ON.desktop` and `CTR-HUD-Mod-OFF.desktop` to the
   Deck's Desktop and mark them executable and trusted.

## Use

Close the game, then on the Deck either double-click **CTR-HUD-Mod-ON** /
**CTR-HUD-Mod-OFF** on the Desktop, or run:

```sh
cd ~/ctr-hud-mod
./ctr-hud.sh on       # apply the portraits
./ctr-hud.sh off      # restore the original game data, byte for byte
./ctr-hud.sh status
./ctr-hud.sh plan     # dry run: check every slot fits, write nothing
./ctr-hud.sh verify   # check what is installed against the blobs and backups
```

Keep `backup/` and `state.json` on the Deck while the mod is ON; OFF needs them.
Game updates or a Steam "verify files" can overwrite the patched data. Run OFF
then ON again if portraits revert.

## Change the art

1. Turn the mod OFF.
2. Replace the PNGs in `art/`, keeping the filenames. Use upright images, ideally
   128×128 with transparency. One image per character is used for all skins and
   is also resized for the minimap.
3. Rebuild and sync the blobs (step 2 of Install), then turn the mod ON.

The 160×160 skin icons are scaled up from the 128×128 art and use reduced colour palettes
(set per character in `texture-settings.json`) so they fit the game's small slots.

`build.py` flips images vertically because the game reads these textures upside
down, so do not pre-flip your art.

## Tests

```sh
python3 test_mod.py -v
```
