#!/usr/bin/env python3
"""Makes Fulldex's own widescreen patch for a Generation 3 Evolved release: gen3evolved-wide.ips
(IPS32: the patch writes past 16 MB) and gen3evolved-wide.safety, in the format of Fulldex's
gba/wide-patches (as Radical Red's and Unbound's).

The patch is exactly v2's changes (g3e_widescreen_v2.apply_v2) minus the game-code change: Fulldex
picks a widescreen patch by its .safety lines, so the ROM keeps BPRE.

.safety lines (Fulldex's PatchFits / PatchCantTry):
  same OFF SIZE CRC NAME   bytes that must be as in this release: every range the patch
                           overwrites, and every function it was located by (pins the release)
  call OFF 2 CRC NAME      the first halfword of each G3E function the patch's code calls
  free OFF SIZE            space the patch writes into, which must be empty (0xFF)

usage: make_fulldex_patch.py G3E.gba OUTDIR
"""
import os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import g3e_widescreen_v2 as v2  # noqa: E402

BASE = 0x08000000
MERGE_GAP = 8          # changed runs closer than this become one IPS record


def changed_runs(a, b):
    runs, i, n = [], 0, len(a)
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and (a[j] != b[j] or (j + MERGE_GAP < n and a[j:j + MERGE_GAP] != b[j:j + MERGE_GAP])):
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs


def ips32(rom, runs):
    out = bytearray(b"IPS32")
    for off, size in runs:
        for k in range(0, size, 0xFFFF):
            n = min(0xFFFF, size - k)
            out += struct.pack(">IH", off + k, n) + rom[off + k:off + k + n]
    return bytes(out + b"EEOF")


def main():
    inp, outdir = sys.argv[1:3]
    src = open(inp, "rb").read()
    rom, tr, info = v2.apply_v2(src, game_code=False)
    runs = changed_runs(src, rom)
    lines, seen = [], set()

    def same(off, size, name):
        key = (off, size)
        if key not in seen:
            seen.add(key)
            lines.append(f"same {off:07X} {size:X} {zlib.crc32(src[off:off + size]):08X} {name}")

    # Pin the release: every signature region the patch was located by.
    for name, (old, new, size) in sorted(tr.match.items(), key=lambda kv: kv[1][1]):
        same(new - BASE, size, name)
    # Every range the patch overwrites outside empty space.
    free = []
    for off, size in runs:
        if all(b == 0xFF for b in src[off:off + size]):
            free.append((off, size))
        else:
            same(off, size, f"patched_{BASE + off:08X}")
    # The G3E functions the patch's C code calls (from the generated linker script).
    ld = open(os.path.join(os.path.dirname(HERE), "src", "g3e_generated.ld")).read().splitlines()
    for l in ld:
        p = l.split()
        if len(p) >= 3 and p[0].startswith("G3E_") and p[1] == "=":
            addr = int(p[2].rstrip(";"), 16) & ~1
            o = addr - BASE
            if "Rain" in p[0]:     # data tables the code reads, not functions
                same(o, 8, p[0][4:])
            else:
                lines.append(f"call {o:07X} 2 {zlib.crc32(src[o:o + 2]):08X} {p[0][4:]}")
    for off, size in free:
        lines.append(f"free {off:07X} {size:X}")

    os.makedirs(outdir, exist_ok=True)
    ips = ips32(rom, runs)
    open(os.path.join(outdir, "gen3evolved-wide.ips"), "wb").write(ips)
    open(os.path.join(outdir, "gen3evolved-wide.safety"), "w").write("\n".join(lines) + "\n")
    print(f"gen3evolved-wide.ips: {len(ips)} bytes, {len(runs)} records; .safety: {len(lines)} lines "
          f"({sum(l.startswith('same') for l in lines)} same, {sum(l.startswith('call') for l in lines)} call, {len(free)} free)")
    # Self-check: applying the IPS to the original gives the patched ROM.
    chk = bytearray(src)
    i = 5
    while ips[i:i + 4] != b"EEOF":
        off, n = struct.unpack(">IH", ips[i:i + 6]); i += 6
        chk[off:off + n] = ips[i:i + n]; i += n
    assert chk == rom, "IPS self-check failed"
    print("self-check: IPS applied to the release == v2 output (game code kept)")


if __name__ == "__main__":
    main()
