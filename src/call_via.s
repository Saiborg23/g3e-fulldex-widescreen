@ Thumb interworking helpers that GCC calls for indirect / long calls on ARMv4T (normally libgcc's).
    .syntax unified
    .thumb
    .section .text.call_via, "ax"
    .macro CALL_VIA reg
    .global _call_via_\reg
    .thumb_func
_call_via_\reg:
    bx \reg
    nop
    .endm
    CALL_VIA r0
    CALL_VIA r1
    CALL_VIA r2
    CALL_VIA r3
    CALL_VIA r4
    CALL_VIA r5
    CALL_VIA r6
    CALL_VIA r7
