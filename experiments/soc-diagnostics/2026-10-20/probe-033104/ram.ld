OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
    . = 0x50100000;
    .text : { KEEP(*(.text.entry)) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.* .sdata .sdata.*) }
    . = ALIGN(8);
    __bss_start = .;
    .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) }
    . = ALIGN(8);
    __bss_end = .;
    ASSERT(. < 0x50110000, "Diagnostic exceeds RAM test region")
    /DISCARD/ : { *(.eh_frame*) *(.comment) }
}
