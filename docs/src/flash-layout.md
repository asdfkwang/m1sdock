# Flash Layout

16 MB NOR (`ef4018`). Current build layout with a 1 MiB OpenSBI slot.
The user confirmed successful hardware boot with this layout on 2026-10-19.

## Region table

| Flash offset | Name | Size (bytes) | Purpose |
|---|---|---|---|
| `0x000000` | bootinfo group0 (**BFNP**) | 1636 (`0x664`) | Describes *m0* image for the BootROM |
| `0x001000` | bootinfo group1 (**BFAP**) | 352 (`0x160`) | Describes *d0* image for the BootROM |
| `0x002000` | m0 binary | ~37 968–38 128 (`0x9450`) | XIP executes via `0x58002000` |
| `0x052000` | d0 binary | ~29 200–29 248 (`0x7240`) | XIP executes via `0x58052000` |
| `0x0D2000` | `whole_img_linux.bin` | `0x880000` | DTB + kernel + rootfs + OpenSBI slot; ends at `0x952000` |
| `0x0D2000` | DTB slot (whole +`0x0`) | `0x10000` | Copied from D0 XIP `0x58080000` to `0x51ff8000` |
| `0x0F1FF8` | Kernel header (whole +`0x1FFF8`) | 8 | Little-endian destination address and compressed length |
| `0x0F2000` | Kernel slot (whole +`0x20000`) | `0x460000` | `Image.lz4`; unpacked at `0x50000000` |
| `0x552000` | Rootfs partition (whole +`0x480000`) | `0x280000` | DTB `xip-flash.0`, D0 XIP `0x58500000` |
| `0x852000` | OpenSBI slot (whole +`0x780000`) | `0x100000` | D0 XIP `0x58800000`; copied to PSRAM `0x53f00000` |

The legacy OpenSBI slot at whole +`0x10000` is unused and padded with `0xff`.
All flash offsets above are physical. D0's XIP base `0x58000000` maps to its
body at physical `0x52000`; do not treat XIP addresses as physical offsets.

The complete OpenSBI runtime (ELF load bytes, BSS, scratch and stack) must fit
`0x53f00000..0x53ffffff`. The DTB reserves that 1 MiB with `no-map`; Linux has
the remaining 63 MiB of PSRAM. The vendor 0.6 build has no separate heap.
The newer `opensbi/` checkout needs its own runtime-size validation when ported.

Update low_load, regenerated boot headers and the whole image/DTB as a set.
The old loader uses different firmware addresses and a 48 KiB copy limit.

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
| `OPENSBI_SRC`   | `0x58800000` | `0x100000` bytes |
| `OPENSBI_DST`   | `0x53f00000` | PSRAM destination, 1 MiB reserved/no-map |
| `DTB_SRC`       | `0x58080000` | 64 K device tree |
| `DTB_DST`       | `0x51ff8000` | RAM destination, passed as `hartid=0, fdt` to OpenSBI |
