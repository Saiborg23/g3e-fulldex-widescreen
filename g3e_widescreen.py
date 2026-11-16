#!/usr/bin/env python3
"""Gen 3 Evolved widescreen patcher (v1) for Pokemon Fulldex / Pokemon GBA Widescreen.

What it does to a Generation 3 Evolved ROM (any release, found by code shape, not address):
  1. Finds the overworld's per-frame callback (pokeemerald-expansion's VBlankCB_Field: push,
     exactly six calls, pop - two of those calls are made from nowhere else in the ROM).
  2. Writes a 24-byte stub into the free space at the end of the ROM. Every overworld frame it
     writes 0xA51E to 0x0400005E (Fulldex's WIDECNT: "draw BG1-3 and sprites into the sides")
     and then jumps to the original callback.
  3. Repoints every pointer to the callback at the stub.
  4. Changes the game code BPRE -> G3EV (and fixes the header checksum) so Fulldex no longer
     force-applies FireRed's widescreen patch, which would overwrite ~7 KB of the hack.

On real hardware and in ordinary emulators 0x0400005E is an unused register, so the patched
ROM plays exactly like the original there.

usage: g3e_widescreen.py IN.gba OUT.gba [--bps OUT.bps]
"""
import argparse, collections, struct, sys, zlib

WIDECNT_ADDR = 0x0400005E
WIDECNT_VALUE = 0xA51E          # 0xA500 | BG1 | BG2 | BG3 | OBJ, as FireRed's own wide patch writes
NEW_GAME_CODE = b"G3EV"
ROM_BASE = 0x08000000


def u16(r, o):
    return struct.unpack_from("<H", r, o)[0]


def bl_target(r, o):
    """Target of a Thumb BL pair at offset o, or None."""
    hi, lo = u16(r, o), u16(r, o + 2)
    if (hi & 0xF800) != 0xF000 or (lo & 0xF800) != 0xF800:
        return None
    off = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if off & 0x400000:
        off -= 0x800000
    return ROM_BASE + o + 4 + off


def free_space_start(rom):
    """Start of the 0xFF padding that runs to the end of the ROM."""
    i = len(rom)
    while i > 0 and rom[i - 1] == 0xFF:
        i -= 1
    return (i + 0xFFF) & ~0xFFF


def find_vblank_cb_field(rom, code_end):
    calls = collections.Counter()
    for o in range(0, code_end - 4, 2):
        t = bl_target(rom, o)
        if t is not None:
            calls[t] += 1
    found = []
    for o in range(0, code_end - 40, 2):
        if (u16(rom, o) & 0xFF00) != 0xB500:            # push {..., lr}
            continue
        p, targets = o + 2, []
        while (t := bl_target(rom, p)) is not None:
            targets.append(t)
            p += 4
        if len(targets) != 6 or (u16(rom, p) & 0xFF00) != 0xBC00:   # pop
            continue
        # VBlankCB_Field: FieldUpdateBgTilemapScroll (4th) and TransferTilesetAnimsBuffer (6th)
        # are called from this function only; LoadOam, ProcessSpriteCopyRequests and
        # TransferPlttBuffer (1st, 2nd, 5th) from dozens of screens.
        if calls[targets[3]] == 1 and calls[targets[5]] == 1 and min(calls[targets[0]], calls[targets[1]], calls[targets[4]]) >= 20:
            found.append(o)
    if len(found) != 1:
        sys.exit(f"expected exactly one VBlankCB_Field, found {len(found)}: {[hex(ROM_BASE + f) for f in found]}")
    return found[0]


def make_stub(callback_addr, value=WIDECNT_VALUE):
    # 0: ldr r0,[pc,#8] / 2: ldr r1,[pc,#12] / 4: strh r1,[r0] / 6: ldr r0,[pc,#12] / 8: bx r0 / 10: nop
    code = struct.pack("<6H", 0x4802, 0x4903, 0x8001, 0x4803, 0x4700, 0x46C0)
    return code + struct.pack("<3I", WIDECNT_ADDR, value, callback_addr | 1)


def bps(source, target):
    """A BPS patch (SourceRead / TargetRead only)."""
    def num(n):
        out = bytearray()
        while True:
            x = n & 0x7F
            n >>= 7
            if n == 0:
                out.append(0x80 | x)
                return bytes(out)
            out.append(x)
            n -= 1
    out = bytearray(b"BPS1") + num(len(source)) + num(len(target)) + num(0)
    i, n = 0, len(target)
    while i < n:
        same = i < len(source) and source[i] == target[i]
        j = i
        while j < n and (j < len(source) and source[j] == target[j]) == same:
            j += 1
        out += num(((j - i - 1) << 2) | (0 if same else 1))
        if not same:
            out += target[i:j]
        i = j
    out += struct.pack("<II", zlib.crc32(source), zlib.crc32(target))
    out += struct.pack("<I", zlib.crc32(bytes(out)))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--bps", help="also write a BPS patch from IN to OUT")
    a = ap.parse_args()
    src = open(a.inp, "rb").read()
    rom = bytearray(src)
    if rom[0xAC:0xB0] != b"BPRE" or b"RHHEXP" not in rom[:0x400]:
        sys.exit("not an unpatched Generation 3 Evolved ROM (expected game code BPRE and an RHHEXP header)")
    i = rom.find(b"RHHEXP")
    print(f"pokeemerald-expansion {rom[i + 6]}.{rom[i + 7]}.{rom[i + 8]}")

    free = free_space_start(rom)
    cb = find_vblank_cb_field(rom, free)
    cb_addr = ROM_BASE + cb
    print(f"VBlankCB_Field at 0x{cb_addr:08X}")

    ptr = struct.pack("<I", cb_addr | 1)
    refs = [o for o in range(0, free, 4) if rom[o:o + 4] == ptr]
    if not refs:
        sys.exit("no pointers to VBlankCB_Field found")
    stub_off = len(rom) - 0x1000                      # well inside the end padding
    if stub_off < free:
        sys.exit("no free space at the end of the ROM")
    stub = make_stub(cb_addr)
    rom[stub_off:stub_off + len(stub)] = stub
    for o in refs:
        rom[o:o + 4] = struct.pack("<I", (ROM_BASE + stub_off) | 1)
    print(f"stub at 0x{ROM_BASE + stub_off:08X}; repointed {len(refs)} pointers")

    rom[0xAC:0xB0] = NEW_GAME_CODE
    rom[0xBD] = (-sum(rom[0xA0:0xBD]) - 0x19) & 0xFF
    print(f"game code BPRE -> {NEW_GAME_CODE.decode()}, header checksum 0x{rom[0xBD]:02X}")

    open(a.out, "wb").write(rom)
    print(f"wrote {a.out}")
    if a.bps:
        p = bps(src, bytes(rom))
        open(a.bps, "wb").write(p)
        print(f"wrote {a.bps} ({len(p)} bytes)")


if __name__ == "__main__":
    main()
