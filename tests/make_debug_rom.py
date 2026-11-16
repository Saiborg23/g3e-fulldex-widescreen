# TEST-ONLY: v2 ROM + G3E's debug menu on the start menu's Option slot.
import sys, struct, subprocess
src, blob, elf, out = sys.argv[1:5]
rom = bytearray(open(src,'rb').read()); code = open(blob,'rb').read()
sym = int([l for l in subprocess.run(['arm-none-eabi-nm', elf], capture_output=True, text=True).stdout.splitlines() if 'Test_StartMenuDebug' in l][0].split()[0], 16)
rom[0x01F80000:0x01F80000+len(code)] = code
o = 0x08DA3D84 - 0x08000000; assert struct.unpack_from('<I', rom, o)[0] == 0x0821AE75
struct.pack_into('<I', rom, o, sym | 1); open(out, 'wb').write(rom)
