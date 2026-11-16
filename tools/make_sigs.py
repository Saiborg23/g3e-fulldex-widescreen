#!/usr/bin/env python3
"""Builds g3e_sigs.json from the reference ROM (G3E v1.0.22): one relocatable signature per G3E
function the widescreen patch touches or calls.

A signature is the function's bytes (code and literal pool, up to the next function) with the
parts that move between builds masked out: each Thumb BL pair (recorded as a 'bl' relocation, so
its target can be read back) and each literal-pool word an LDR reads (a 'pool' relocation).
Everything else must match exactly, so a function the author changed is not found, rather than
being patched wrongly.

usage: make_sigs.py REFERENCE.gba OUT.json
"""
import json, struct, sys, zlib

REF_CRC = 0x98E1DF5A
BASE = 0x08000000

# name: entry address in v1.0.22. Sizes run to the next function entry (call or pointer target).
FUNCS = {
    "FieldUpdateBgTilemapScroll":        0x0813E8B8,
    "DrawWholeMapView":                  0x0813E930,
    "CurrentMapDrawMetatileAt":          0x0813E9CC,
    "DrawDoorMetatileAt":                0x0813EA2C,
    "RedrawMapSlicesForCameraUpdate":    0x0813E72C,
    "CameraUpdateNoObjectRefresh":       0x0813EADC,
    "CameraUpdate":                      0x0813EDCC,
    "MapGridGetMetatileIdAt":            0x08159E60,
    "VBlankCB_Battle":                   0x0808AD34,
    "UpdateObjectEventOffscreen_tail":   0x081314C0,   # window, see WINDOWS
    "UpdateObjectEventSpriteInvisibility_mid": 0x0813AA96,
    "FogHorizontalSpriteCallback":       0x08156D18,
    "UpdateAshSprite":                   0x08156D64,
    "UpdateFogDiagonalSprite":           0x08156E50,
    "UpdateSandstormSprite":             0x08156F00,
    "UpdateSnowflakeSprite":             0x08156C9C,
    "StartRainSpriteFall":               0x08157180,
    "UpdateRainSprite":                  0x08157398,
    "CreateSprite":                      0x0821963C,
    "DestroySprite":                     0x08218548,
    "InitOverworldBgs_allocs":           0x0819FC8C,   # window
    "InitOverworldBgs_inlined_allocs":   0x081A37B0,   # window
}
# Fixed-size windows for patch sites inside large functions (start in FUNCS, size here).
WINDOWS = {
    "CameraUpdate": 0x354,
    "DrawMetatileAt": 0x80,                    # the next function is G3E's own and changes per release                     # a stray pointer value inside it fooled the size scan
    "UpdateObjectEventOffscreen_tail": 0x70,
    "UpdateObjectEventSpriteInvisibility_mid": 0x70,
    "InitOverworldBgs_allocs": 0x50,
    "InitOverworldBgs_inlined_allocs": 0x68,
}


def u16(r, o): return struct.unpack_from("<H", r, o)[0]


def bl_target(r, o):
    hi, lo = u16(r, o), u16(r, o + 2)
    if (hi & 0xF800) != 0xF000 or (lo & 0xF800) != 0xF800:
        return None
    off = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if off & 0x400000:
        off -= 0x800000
    return BASE + o + 4 + off


def entry_points(rom, lo, hi):
    """Call and Thumb-pointer targets in [lo, hi): function entries."""
    pts = set()
    code_end = len(rom)
    while code_end > 0 and rom[code_end - 1] == 0xFF:
        code_end -= 1
    for o in range(0, code_end - 4, 2):
        t = bl_target(rom, o)
        if t and lo <= t < hi:
            pts.add(t)
    for o in range(0, code_end - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if v & 1 and lo <= (v & ~1) < hi:
            pts.add(v & ~1)
    return sorted(pts)


def make_sig(rom, start, size):
    o0 = start - BASE
    data = rom[o0:o0 + size]
    mask = bytearray(b"\x01" * size)
    relocs = []
    pool = set()
    for k in range(0, size - 1, 2):                       # LDR rd, [pc, #imm]
        h = u16(data, k)
        if (h & 0xF800) == 0x4800:
            p = ((start + k + 4) & ~3) + (h & 0xFF) * 4 - start
            if 0 <= p <= size - 4 and p not in pool:
                pool.add(p)
    skip = set()
    for p in pool:
        skip.update(range(p, p + 4))
    k = 0
    while k < size - 3:
        if k in skip:
            k += 2
            continue
        t = bl_target(rom, o0 + k)
        if t is not None and (k + 2) not in skip:
            relocs.append({"kind": "bl", "at": k, "ref": hex(t)})
            mask[k:k + 4] = b"\x00\x00\x00\x00"
            k += 4
            continue
        k += 2
    for p in sorted(pool):
        relocs.append({"kind": "pool", "at": p, "ref": hex(struct.unpack_from("<I", data, p)[0])})
        mask[p:p + 4] = b"\x00\x00\x00\x00"
    pattern = "".join(f"{b:02x}" if m else "??" for b, m in zip(data, mask))
    return {"start": hex(start), "size": size, "pattern": pattern, "relocs": relocs}


def main():
    ref, out = sys.argv[1:3]
    rom = open(ref, "rb").read()
    if zlib.crc32(rom) != REF_CRC:
        sys.exit("reference must be G3E v1.0.22")
    sigs = {}
    for name, start in FUNCS.items():
        if name in WINDOWS:
            size = WINDOWS[name]
        else:
            nxt = [e for e in entry_points(rom, start + 2, start + 0x800)]
            size = (nxt[0] if nxt else start + 0x200) - start
        sigs[name] = make_sig(rom, start, size)
        print(f"{name:42s} 0x{start:08X} {size:4d} bytes, {len(sigs[name]['relocs'])} relocations")
    json.dump({"reference": "G3E v1.0.22 (CRC32 98E1DF5A)", "sigs": sigs}, open(out, "w"), indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
