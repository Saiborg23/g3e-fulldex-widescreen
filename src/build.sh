#!/bin/sh
# Builds the v2 code blob (wide.bin at 0x09F00000) and its symbols (wide.elf).
# usage: build.sh [LINKER_SCRIPT]   (default: the v1.0.22 addresses; the patcher passes a generated one)
set -e
cd "$(dirname "$0")"
LD="${1:-g3e_v1.0.22.ld}"
CFLAGS="-mcpu=arm7tdmi -mthumb -mthumb-interwork -mlong-calls -O2 -ffreestanding -fno-builtin -nostdlib -Wall -Wextra"
arm-none-eabi-gcc $CFLAGS -c wide_camera.c -o wide_camera.o
arm-none-eabi-gcc $CFLAGS -c wide_weather.c -o wide_weather.o
arm-none-eabi-as -mcpu=arm7tdmi call_via.s -o call_via.o
arm-none-eabi-ld -T "$LD" wide_camera.o wide_weather.o call_via.o -o wide.elf
test -z "$(arm-none-eabi-nm -u wide.elf)" || { echo "undefined symbols:"; arm-none-eabi-nm -u wide.elf; exit 1; }
arm-none-eabi-objcopy -O binary wide.elf wide.bin
