G3E_StartMenuDebugCallback = 0x0821ACD5;
G3E_Debug_ShowMainMenu     = 0x08112DE5;
SECTIONS { . = 0x09F80000; .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.data*) *(.bss*) *(COMMON) *(.comment) *(.ARM.*) } }
