# CTR HUD portrait mod

Desktop shortcuts on the Steam Deck: **CTR-HUD-Mod-ON** and **CTR-HUD-Mod-OFF**.
Close SacredFire before toggling. The mod is currently ON with 223 archive entries
patched for 19 characters. OFF restores the bytes saved in `backup/` using
`state.json`; keep both while the mod is ON.

## Supported art

Coco, Cortex, Crash, Crunch, Dingodile, Fake Crash, Komodo Joe, N. Gin,
Nitros Oxide, N. Tropy, Papu Papu, Penta Penguin, Pinstripe, Polar, Pura,
Ripper Roo, Tiny Tiger, Zam and Zem.

**Nina Cortex is not included.** Her original portrait is expected. Cortex and
Nina Cortex are separate characters. Adding a character outside this list also
requires locating and supporting its texture source, not just supplying a PNG.

## Commands on the Deck

```sh
cd ~/ctr-hud-mod
./ctr-hud.sh status
./ctr-hud.sh verify
```

`status` shows the toggle state and supplied art roster. `verify` reads every
supported portrait in the configured archives, compares it to its replacement
blob, and checks applied offsets and backup lengths. It is read-only. Passing
verification confirms the archive payloads; it does not prove which source the
renderer chooses in a race.

To replace an existing supported character's art: turn OFF, replace its PNG in
`art/`, run `python3 build.py` on the Mac with Pillow and NumPy installed, copy
`art/` and `blobs/` to the Deck, then turn ON. Keep the existing filenames.

## Investigation: October 18, 2026

- The reported remaining original portrait was Nina Cortex. No failure among
  the 19 supported characters has yet been confirmed.
- All 223 currently applied payloads matched their blobs, covering all 19
  supported characters. Every original compressed stream was also reconstructed
  from the saved prefix plus the untouched archive suffix and decompressed
  successfully in memory. All non-texture IGZ prefixes were unchanged.
- Every `driver*.pak` has exactly two portrait-name matches: HUD and minimap.
- `RacerPortraits_materials.igz` references numbered
  `octane_ui_custo_ico_char_racer_XX` textures. Skin portrait materials reference
  the named HUD/minimap textures. The numbered textures are not patched; they
  remain a candidate source to inspect if a supported character fails in-game.
- The unscanned `juicedomain_onlinemenus.pak` contains another Crash minimap
  portrait; it is not part of the current race-focused patch set.
- Fixed a reader bug: the descriptor's historical `size` key is a packed
  ordinal/offset field, not compressed byte length. Its low byte supplies
  offset bits 32..39. Guessing wrapped offsets from LZMA signatures can select
  unrelated data; update2 contains three ambiguous portrait-name entries, none
  of which belongs to the 19 supplied characters. All existing 223 recorded
  writes agree with the decoded descriptor offsets.
- No live game archive, applied state or backup was changed by this investigation.
  The mod remains ON. Test Coco or Cortex with the default skin in a newly
  started game/race to establish whether a supported portrait actually fails.

Regression checks (Mac and Deck): `python3 test_mod.py -v`. These cover a valid
low-offset decoy in a sparse >4 GiB archive, rejection of an invalid true offset,
verification of wrong art, and byte-for-byte ON/OFF restoration in a test archive.
