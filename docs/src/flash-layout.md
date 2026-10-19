# Flash Layout

16 MB NOR (`ef4018`). Regions on-die after a verified vendor low_load flash.

## Region table

| Flash offset | Name | Size (bytes) | Purpose |
|---|---|---|---|
| `0x000000` | bootinfo group0 (**BFNP**) | 1636 (`0x664`) | Describes *m0* image for the BootROM |
| `0x001000` | bootinfo group1 (**BFAP**) | 352 (`0x160`) | Describes *d0* image for the BootROM |
| `0x002000` | m0 binary | ~37 968–38 128 (`0x9450`) | XIP executes via `0x58002000` |
| `0x052000` | d0 binary | ~29 200–29 248 (`0x7240`) | XIP executes via `0x58052000` |
| `0x0D2000` | `whole_img.bin` | `0x72E000` | DTB + OpenSBI + kernel + rootfs payload |
| `0x500000` | Linux rootfs partition | `0x280000…0x2BF000` | squashfs (DTB-offset `mtd` node `xip-flash.0`) |
| `0x500000…0x7FFFFF` | whole-img payload zone | — | Consumed by the Linux mtd/squashfs |
| `0x080000` | DTB, inside whole-img | 64 K | Copied by d0 to `0x51ff8000` before jump |
| `0x090000` | OpenSBI v0.6, inside whole-img | `0xC000` | Copied by d0 to `0x3eff0000` |
| `0x0A0000` | kernel `Image.lz4`, inside whole-img | — | `unlz4` target `0x50000000` (RAM) |

## Alignment rule

`bootinfo @0x8C` = `img_len_cnt` field = **image length rounded up to 16 B**.

```
cjacker m0.bin = 37968 B = 0x9450  → bootinfo len @0x8C = 0x9450  (already 16-aligned)
our      d0.bin = 29200 B = 0x7210  → bootinfo len @0x8C = 0x7210  (already 16-aligned)
cjacker d0.bin = 29236 B = 0x7214  → bootinfo len @0x8C = 0x7240  (rounded up)
```

The dev-cube-generated images (`img_group0.bin 38128`, `img_group1.bin 29200`) follow the same rule but *prepend a 12-byte wrap* — the on-die result of that mode is discarded here in favor of *raw body at the slot offset*.

## Whole-img layout the d0 loader itself assumes

Defined in `bl_mcu_sdk_bl808/examples/low_load/main.c`:

| Macro | Value | Meaning |
|---|---|---|
| `VM_LINUX_SRC`  | `0x580A0000` | kernel Image.lz4 (length word at `0x5809FFFC`) |
| `VM_LINUX_DST`  | `0x50000000` | RAM unpack destination |
| `OPENSBI_SRC`   | `0x58090000` | `0xC000` bytes |
| `OPENSBI_DST`   | `0x3eff0000` | RAM destination |
| `DTB_SRC`       | `0x58080000` | 64 K device tree |
| `DTB_DST`       | `0x51ff8000` | RAM destination, passed as `hartid=0, fdt` to OpenSBI |
