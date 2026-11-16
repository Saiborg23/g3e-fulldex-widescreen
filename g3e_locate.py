"""Finds the G3E functions and data the widescreen patch uses in any G3E release, from the
relocatable signatures in g3e_sigs.json (built from v1.0.22 by tools/make_sigs.py), and translates
v1.0.22 addresses to the release being patched.

Translation sources, in order:
  1. a call target or literal-pool word inside a matched signature (its v1.0.22 value is
     recorded in the signature);
  2. an address inside a matched signature's bytes (a function entry or a patch site):
     the same offset from the new match;
  3. DERIVED: struct fields at a fixed offset from a translated base.
"""
import json, os, struct

BASE = 0x08000000
HERE = os.path.dirname(os.path.abspath(__file__))

# struct fields / table halves used by the patch: old address -> (old base, offset)
DERIVED = {
    0x030013B4: (0x030013A8, 12),   # sHorizontalCameraPan (after sFieldCameraOffset)
    0x030013B6: (0x030013A8, 14),   # sVerticalCameraPan
    0x030025FC: (0x030025E4, 24),   # gTotalCameraPixelOffsetX (after gFieldCamera)
    0x030025FE: (0x030025E4, 26),   # gTotalCameraPixelOffsetY
    0x0860F004: (0x0860EFFC, 8),    # sRainSpriteMovement (after sRainSpriteFallingDurations)
}


class NotFound(Exception):
    pass


def _bl_target(r, o):
    hi, lo = struct.unpack_from("<HH", r, o)
    if (hi & 0xF800) != 0xF000 or (lo & 0xF800) != 0xF800:
        return None
    off = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if off & 0x400000:
        off -= 0x800000
    return BASE + o + 4 + off


def _parse(pattern):
    data = bytearray(); mask = bytearray()
    for i in range(0, len(pattern), 2):
        h = pattern[i:i + 2]
        if h == "??":
            data.append(0); mask.append(0)
        else:
            data.append(int(h, 16)); mask.append(1)
    return bytes(data), bytes(mask)


def _find(rom, data, mask, limit):
    # anchor on the longest unmasked run, then check the whole pattern
    best = (0, 0); run_start = None
    for i, m in enumerate(mask + b"\x00"):
        if m and run_start is None:
            run_start = i
        elif not m and run_start is not None:
            if i - run_start > best[1] - best[0]:
                best = (run_start, i)
            run_start = None
    a0, a1 = best
    anchor = data[a0:a1]
    hits = []
    i = rom.find(anchor, 0, limit)
    while i != -1:
        s = i - a0
        if s >= 0 and s % 2 == 0 and all(not m or rom[s + k] == b for k, (b, m) in enumerate(zip(data, mask))):
            hits.append(s)
        i = rom.find(anchor, i + 1, limit)
    return hits


class Locator:
    def __init__(self, rom, sigs_path=os.path.join(HERE, "g3e_sigs.json")):
        self.rom = rom
        sigs = json.load(open(sigs_path))["sigs"]
        limit = len(rom)
        while limit > 0 and rom[limit - 1] == 0xFF:
            limit -= 1
        self.match = {}       # name -> (old_start, new_start, size)
        self.table = {}       # old -> new
        missing = []
        for name, sig in sigs.items():
            data, mask = _parse(sig["pattern"])
            hits = _find(rom, data, mask, limit)
            if len(hits) != 1:
                missing.append(f"{name} ({len(hits)} matches)")
                continue
            old, new = int(sig["start"], 16), BASE + hits[0]
            self.match[name] = (old, new, sig["size"])
            for r in sig["relocs"]:
                ref = int(r["ref"], 16)
                if r["kind"] == "bl":
                    val = _bl_target(rom, hits[0] + r["at"])
                else:
                    val = struct.unpack_from("<I", rom, hits[0] + r["at"])[0]
                self._add(ref, val, name)
        if missing:
            raise NotFound("not found (changed in this release?): " + ", ".join(missing))

    def _add(self, old, new, where):
        prev = self.table.get(old)
        if prev is not None and prev != new:
            raise NotFound(f"inconsistent: 0x{old:08X} -> 0x{prev:08X} and 0x{new:08X} ({where})")
        self.table[old] = new

    def __call__(self, old):
        """Translate a v1.0.22 address (Thumb bit kept)."""
        thumb, a = old & 1, old & ~1
        if a in self.table:
            return self.table[a] | thumb
        for name, (o, n, size) in self.match.items():
            if o <= a < o + size:
                return (n + (a - o)) | thumb
        if a in DERIVED:
            base, off = DERIVED[a]
            return self(base) + off
        raise NotFound(f"no translation for 0x{old:08X}")
