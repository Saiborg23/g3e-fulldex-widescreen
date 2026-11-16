#!/usr/bin/env python3
"""Apply a BPS patch: bps_apply.py SOURCE PATCH OUT  (checks all three CRC32s)."""
import struct, sys, zlib


def apply(source, patch):
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS patch")
    i = 4

    def num():
        nonlocal i
        d, s = 0, 1
        while True:
            x = patch[i]
            i += 1
            d += (x & 0x7F) * s
            if x & 0x80:
                return d
            s <<= 7
            d += s

    src_size, tgt_size, meta = num(), num(), num()
    i += meta
    src_crc, tgt_crc, patch_crc = struct.unpack("<III", patch[-12:])
    if zlib.crc32(patch[:-4]) != patch_crc:
        raise ValueError("patch CRC mismatch")
    if len(source) != src_size or zlib.crc32(source) != src_crc:
        raise ValueError(f"wrong source ROM (needs size {src_size}, CRC32 {src_crc:08X})")
    out = bytearray(tgt_size)
    o = src_rel = tgt_rel = 0
    end = len(patch) - 12
    while i < end:
        d = num()
        action, n = d & 3, (d >> 2) + 1
        if action == 0:                      # SourceRead
            out[o:o + n] = source[o:o + n]
        elif action == 1:                    # TargetRead
            out[o:o + n] = patch[i:i + n]
            i += n
        elif action == 2:                    # SourceCopy
            x = num()
            src_rel += (-1 if x & 1 else 1) * (x >> 1)
            out[o:o + n] = source[src_rel:src_rel + n]
            src_rel += n
        else:                                # TargetCopy (may overlap: byte by byte)
            x = num()
            tgt_rel += (-1 if x & 1 else 1) * (x >> 1)
            for k in range(n):
                out[o + k] = out[tgt_rel + k]
            tgt_rel += n
        o += n
    if zlib.crc32(out) != tgt_crc:
        raise ValueError("output CRC mismatch")
    return bytes(out)


if __name__ == "__main__":
    src, pat, dst = sys.argv[1:4]
    open(dst, "wb").write(apply(open(src, "rb").read(), open(pat, "rb").read()))
    print(f"wrote {dst}")
