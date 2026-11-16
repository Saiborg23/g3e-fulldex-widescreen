#!/usr/bin/env python3
"""Gen 3 Evolved widescreen v2 (any G3E release built like v1.0.8 - v1.0.22).

On top of v1 (the per-frame WIDECNT request and the BPRE->G3EV game code), v2 replaces the
overworld camera so the map layers are 64x32 tiles (as FireRed's own Fulldex patch does):

  - src/wide_camera.c, compiled freestanding to 0x09F00000 (build with src/build.sh), replaces
    field_camera.c's map drawing: a 32-metatile ring instead of 16, and a 512-pixel scroll;
  - 16-byte ARM long jumps at the start of the seven replaced functions;
  - sOverworldBgTemplates: BG1-3 moved to screen blocks 25/27/29 with screen size 1 (64x32);
  - the overworld tilemap buffers allocated at 0x1000 bytes instead of 0x800 (both copies
    of InitOverworldBgs).

Addresses: every constant below is the v1.0.22 address. g3e_locate.py finds the same functions
in the release being patched (relocatable signatures, g3e_sigs.json) and translates each one;
the C code is linked against a linker script generated the same way from src/g3e_v1.0.22.ld.
A release whose code differs where the patch works is refused, not patched.

usage: g3e_widescreen_v2.py IN.gba OUT.gba [--bps OUT.bps]
"""
import argparse, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g3e_widescreen as v1  # noqa: E402
import g3e_locate  # noqa: E402

CODE_ADDR = 0x09F00000

HOOKS = {                      # original function -> replacement symbol
    0x0813E8B8: "Wide_FieldUpdateBgTilemapScroll",
    0x0813E930: "Wide_DrawWholeMapView",
    0x0813E9CC: "Wide_CurrentMapDrawMetatileAt",
    0x0813EA2C: "Wide_DrawDoorMetatileAt",
    0x0813E72C: "Wide_RedrawMapSlicesForCameraUpdate",
    0x0813EADC: "Wide_CameraUpdateNoObjectRefresh",
    0x0813EDCC: "Wide_CameraUpdate",
    # weather: 6-column fog/ash/sandstorm, wider rain landing
    0x08156D18: "Wide_FogHorizontalSpriteCallback",
    0x08156D64: "Wide_UpdateAshSprite",
    0x08156E50: "Wide_UpdateFogDiagonalSprite",
    0x08156F00: "Wide_UpdateSandstormSprite",
    0x08157180: "Wide_StartRainSpriteFall",
}
VBLANK_CB_BATTLE = 0x0808AD34     # battle_main.c VBlankCB_Battle (6 pointers)
WIDECNT_BATTLE = 0xA53E           # BG1-3 + OBJ + bottom-48-line text band, as FireRed's patch
# NPC / field-effect offscreen limits: sprites were hidden 16 px past the 240-pixel edges.
# Now hidden only beyond -48 (left, -64 for the S.S. Anne) and 320 (right).
# Right test rewritten as  r = (x + 192) >> 9  (nonzero = offscreen: x >= 320 or x < -192).
OFFSCREEN_PATCHES = [
    # UpdateObjectEventOffscreen
    (0x081314FE,
     "01248018103bff2900dc0024",   # movs r4,#1; adds r0,r0,r2; subs r3,#16; cmp r1,#255; bgt; movs r4,#0
     "c0248018303b64186412c046"),  # movs r4,#192; adds r0,r0,r2; subs r3,#48; adds r4,r4,r1; asrs r4,r4,#9; nop
    # UpdateObjectEventSpriteInvisibility
    (0x0813AAD8,
     "170401213f14ff2f00dc0021",   # lsls r7,r2,#16; movs r1,#1; asrs r7,r7,#16; cmp r7,#255; bgt; movs r1,#0
     "17043f14c021c9194912c046"),  # lsls r7,r2,#16; asrs r7,r7,#16; movs r1,#192; adds r1,r1,r7; asrs r1,r1,#9; nop
    (0x0813AB04, "1032", "3032"),  # adds r2,#16 -> adds r2,#48   (x2 < -16 -> x2 < -48)
    # UpdateRainSprite: drawn for -8 <= x <= 248  ->  -32 <= x <= 288 (y unchanged, -16..176)
    (0x081573D4, "0125", "4125"),  # movs r5,#1 -> #65   (x limit 1+255 = 256 -> 320)
    (0x081573E0, "0832", "2032"),  # adds r2,#8 -> #32
    (0x081573F2, "403d", "803d"),  # subs r5,#64 -> #128 (y limit stays 192)
    # UpdateSnowflakeSprite: wraps at -3 / 242  ->  -28 / 250 (9-bit x: 255 is the most it can be)
    (0x08156CEA, "0333", "1c33"),  # adds r3,#3   -> #28
    (0x08156CEE, "f223", "fa23"),  # movs r3,#242 -> #250
    (0x08156CFC, "f229", "fa29"),  # cmp r1,#242  -> #250
    (0x08156D00, "0323", "1c23"),  # movs r3,#3   -> #28 (negated: -28)
]
ALLOC_SHIFTS = [0x0819FCBA, 0x0819FCC8, 0x0819FCD4, 0x081A37F4, 0x081A3802, 0x081A380E]


def bg_template(bg, char, map_, size, pal, prio, base):
    return bg | char << 2 | map_ << 4 | size << 9 | pal << 11 | prio << 12 | base << 14


def long_jump(target):
    # Thumb: bx pc; nop  -> ARM: ldr ip, [pc]; bx ip; .word target|1   (clobbers only ip)
    return struct.pack("<HHIII", 0x4778, 0x46C0, 0xE59FC000, 0xE12FFF1C, target | 1)


def generated_linker_script(tr):
    """src/g3e_v1.0.22.ld with every address translated to this release."""
    src = os.path.join(HERE, "src")
    out = []
    for line in open(os.path.join(src, "g3e_v1.0.22.ld")):
        m = re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)\s*;(.*)", line)
        if m:
            name, old = m.group(1), int(m.group(2), 16)
            line = f"{name:32s} = 0x{tr(old):08X};   /* v1.0.22: 0x{old:08X} */\n"
        out.append(line)
    path = os.path.join(src, "g3e_generated.ld")
    open(path, "w").write("".join(out))
    return path


def build(ld):
    src = os.path.join(HERE, "src")
    subprocess.run(["sh", os.path.join(src, "build.sh"), ld], check=True, cwd=src)
    code = open(os.path.join(src, "wide.bin"), "rb").read()
    syms = {}
    out = subprocess.run(["arm-none-eabi-nm", os.path.join(src, "wide.elf")], check=True, capture_output=True, text=True).stdout
    for line in out.splitlines():
        a, t, n = line.split()
        syms[n] = int(a, 16)
    return code, syms


def apply_v2(src, game_code=True):
    """Returns (patched ROM, translator, info). game_code=False keeps BPRE (for Fulldex's own patch
    list, which picks the patch by its .safety lines instead)."""
    info = {"code": None, "stubs": None, "hooks": {}}
    if src[0xAC:0xB0] != b"BPRE" or b"RHHEXP" not in src[:0x400]:
        sys.exit("not an unpatched Generation 3 Evolved ROM (expected game code BPRE and an RHHEXP header)")
    h = src.find(b"RHHEXP")
    print(f"pokeemerald-expansion {src[h + 6]}.{src[h + 7]}.{src[h + 8]}")
    try:
        tr = g3e_locate.Locator(src)
    except g3e_locate.NotFound as e:
        sys.exit(f"this G3E release differs from the ones v2 knows: {e}")
    print(f"found all {len(tr.match)} signatures")
    rom = bytearray(src)

    # --- v1: per-frame WIDECNT + game code ---
    free = v1.free_space_start(rom)
    cb = v1.find_vblank_cb_field(rom, free)
    if v1.bl_target(rom, cb + 2 + 3 * 4) != tr(0x0813E8B8) & ~1:   # its 4th call: FieldUpdateBgTilemapScroll
        sys.exit("VBlankCB_Field's 4th call is not FieldUpdateBgTilemapScroll")
    ptr = struct.pack("<I", (v1.ROM_BASE + cb) | 1)
    refs = [o for o in range(0, free, 4) if rom[o:o + 4] == ptr]
    stub_off = len(rom) - 0x1000
    rom[stub_off:stub_off + 24] = v1.make_stub(v1.ROM_BASE + cb)
    for o in refs:
        rom[o:o + 4] = struct.pack("<I", (v1.ROM_BASE + stub_off) | 1)
    if game_code:
        rom[0xAC:0xB0] = v1.NEW_GAME_CODE
    print(f"v1: WIDECNT stub, {len(refs)} VBlankCB_Field pointers" + (", game code G3EV" if game_code else ""))

    # --- v2: battles ask for wide frames too ---
    battle_cb = tr(VBLANK_CB_BATTLE)
    bptr = struct.pack("<I", battle_cb | 1)
    brefs = [o for o in range(0, free, 4) if rom[o:o + 4] == bptr]
    if not brefs:
        sys.exit("no pointers to VBlankCB_Battle")
    bstub = stub_off + 0x20
    rom[bstub:bstub + 24] = v1.make_stub(battle_cb, WIDECNT_BATTLE)
    for o in brefs:
        rom[o:o + 4] = struct.pack("<I", (v1.ROM_BASE + bstub) | 1)
    print(f"v2: battle WIDECNT 0x{WIDECNT_BATTLE:04X} stub, {len(brefs)} VBlankCB_Battle pointers")

    # --- v2: wide camera ---
    code, syms = build(generated_linker_script(tr))
    off = CODE_ADDR - v1.ROM_BASE
    if off < free or off + len(code) > stub_off:
        sys.exit("code does not fit in the free space")
    rom[off:off + len(code)] = code
    info["code"] = (CODE_ADDR, len(code)); info["stubs"] = (v1.ROM_BASE + stub_off, 0x40); info["syms"] = syms
    for old, name in HOOKS.items():
        orig = tr(old)
        if orig & 3:
            sys.exit(f"0x{orig:08X} ({name}) is not word-aligned")
        o = orig - v1.ROM_BASE
        rom[o:o + 16] = long_jump(syms[name])
        info["hooks"][orig] = name
        print(f"v2: 0x{orig:08X} -> {name} 0x{syms[name]:08X}")

    expect = struct.pack("<4I", bg_template(0, 2, 31, 0, 0, 0, 0), bg_template(1, 0, 29, 0, 0, 1, 0),
                         bg_template(2, 0, 28, 0, 0, 2, 0), bg_template(3, 0, 30, 0, 0, 3, 0))
    hits = [i for i in range(0, free, 4) if rom[i:i + 16] == expect]
    if len(hits) != 1:
        sys.exit(f"expected one sOverworldBgTemplates, found {len(hits)}")
    t = hits[0]
    struct.pack_into("<3I", rom, t + 4, bg_template(1, 0, 25, 1, 0, 1, 0),
                     bg_template(2, 0, 27, 1, 0, 2, 0), bg_template(3, 0, 29, 1, 0, 3, 0))
    print("v2: BG1-3 -> screen blocks 25/27/29, 64x32")

    for a_ in ALLOC_SHIFTS:
        o = tr(a_) - v1.ROM_BASE
        if v1.u16(rom, o) != 0x0100:          # lsls r0, r0, #4
            sys.exit(f"unexpected instruction at 0x{a_:08X}")
        struct.pack_into("<H", rom, o, 0x0140)  # lsls r0, r0, #5
    print("v2: overworld tilemap buffers 0x800 -> 0x1000 (x6)")

    for addr, old_hex, new_hex in OFFSCREEN_PATCHES:
        addr = tr(addr)
        o = addr - v1.ROM_BASE
        old_b, new_b = bytes.fromhex(old_hex), bytes.fromhex(new_hex)
        if rom[o:o + len(old_b)] != old_b:
            sys.exit(f"unexpected bytes at 0x{addr:08X}: {rom[o:o+len(old_b)].hex()}")
        rom[o:o + len(new_b)] = new_b
    print("v2: NPC/field-effect offscreen limits widened (-48 / 320); rain and snow limits widened")

    if game_code:
        rom[0xBD] = (-sum(rom[0xA0:0xBD]) - 0x19) & 0xFF
    return rom, tr, info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--bps")
    a = ap.parse_args()
    src = open(a.inp, "rb").read()
    rom, _, _ = apply_v2(src)
    open(a.out, "wb").write(rom)
    print(f"wrote {a.out}")
    if a.bps:
        p = v1.bps(src, bytes(rom))
        open(a.bps, "wb").write(p)
        print(f"wrote {a.bps} ({len(p)} bytes)")


if __name__ == "__main__":
    main()
