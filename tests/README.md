# Test tools

Not part of the patch. These run a test build of Fulldex's GBA player with scripted button presses and screenshots.

**Test player:** Fulldex's `gba/` at commit `4607874` plus `fulldex-gba-player-test-harness.patch`, and mGBA at
`6493149` plus Fulldex's `mgba-wide.patch` and `mgba-wide-test-switches.patch`. Build with CMake, then set
`GBAW_PLAYER` to the built `pokemon-gba-wide`.

| File | What it does |
|---|---|
| `run.sh NAME ROM WxH ASPECT "moves"` | Runs one test session |
| `walk.py` | Turns moves like `R3 U4 A1 shot:name` into a player script |
| `fulldex_identify_test.cpp` | Checks which patch Fulldex picks for a ROM |
| `make_debug_rom.py`, `test_debug.c`, `test.ld` | Test-only ROM that opens G3E's hidden debug menu |
| `bps_apply.py` | Applies G3E's release patches to make test ROMs |
