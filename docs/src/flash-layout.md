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

## Storage split (decided 2026-10-20)

Flash carries the stable boot chain **and the compressed kernel image**; the
SD card carries everything bulky or iterative — busybox rootfs payload, kernel
modules, MMC check files. A flash update needs a full flash session; the SD
card is a plain FAT copy over the already-verified `load mmc` path, so the
split keeps NOR small and the payload swappable.

### Capacity check

The whole image (`{=0x880000}` at `0x0D2000`) ends at `0x952000` — same
geometry as the currently flashed `whole_img_uboot.bin`.

| Item | Size |
|---|---|
| Flash free after the whole image | `0x6AE000` ≈ 6.66 MiB |
| Max possible `WHOLE_SIZE` (`WHOLE_FLASH_OFFSET + WHOLE_SIZE ≤ 0x1000000`) | `0xF2E000` |
| New kernel slot at whole +`0x880000` (uses the free area) | `0x6AE000` ≈ 6.66 MiB |
| Alternative: repurpose the squashfs slot (whole +`0x480000`) | `0x280000` = 2.5 MiB |

Measured first boot kernel (upstream defconfig + embedded busybox initramfs,
2026-10-20):

| Format | Size |
|---|---|
| `Image` raw | 27 506 176 B (26.2 MB) |
| gzip -9 | 10 835 466 B (10.3 MB) |
| lz4 -9 | 12 057 342 B (11.5 MB) |

**The defconfig kernel does not fit** — even gzip exceeds all reclaimable
flash. A slim bring-up configuration is required: target raw ≤ ~6 MB, lz4
≤ ~3 MB. With that, the new slot at whole +`0x880000` holds the kernel with
room to grow; the 2.5 MiB squashfs slot is the tighter fallback.

### Format: lz4, not gz

The d0 loader's only decompressor is `unlz4` (`low_load/main.c`); it has no
gunzip. gz only helps a kernel that is already in RAM (U-Boot
`kernel_comp_addr_r` decompression), which does not apply to a flash-resident
image. Slot content is `Image.lz4` — or, for a small slim Image, raw bytes
through the loader's existing `memcpy` path.

### Required changes

1. `utils/merge_linux_image.py`: add the kernel slot with its 8-byte
   destination/length header (same convention as `KERNEL_HEADER_OFFSET =
   0x1FFF8` before the existing slot) and extend `WHOLE_SIZE`.
2. `bl_mcu_sdk_bl808/examples/low_load/main.c`: the loader unpacks the single
   kernel slot to the fixed `VM_LINUX_DST_ADDR = 0x50000000`, which is the
   U-Boot entry in this chain. Add a second unpack for the new slot to
   `0x51000000` — a verified-clear scratch address — reading the XIP source
   `0x58080000 + slot offset` and its length word.
3. `utils/prepare_blflash_low_load.py`: regenerate the d0 body and bootinfo
   headers for the changed loader. Loader, headers and whole image move as
   one set (see the warning above).
4. DTB slot content switches from the vendor `hw.dtb.5M` to the bring-up
   `bl808-d0-m1s.dtb`; it must keep the `reserved-memory/opensbi@53f00000`
   `no-map` node, which `merge_linux_image.py` validates.

U-Boot then boots with `booti 0x51000000 - 0x51ff8000`: the verified
`booti_setup` (u-boot `arch/riscv/lib/image.c`) relocates any in-RAM image to
`gd->ram_base + text_offset` = `0x50200000` and memmoves it there. A U-Boot
SPI-flash loader (`sf read`) is not needed and not available either:
`CONFIG_SPI_FLASH` is off and no BL808 SPI driver exists in the U-Boot tree;
it would require a port from the vendor SDK.

Status: **planned, not implemented.** Until the slot lands, the SD card boot
below is the verified kernel-iteration channel (SD copy, or UART `loady` —
`CONFIG_CMD_LOADB=y` is enabled in the U-Boot build).

### SD card role

Verified 2026-10-20 on the M1STEST FAT32 card (`load mmc 0:1` at
10.7 MiB/s):

| SD content | Consumer | Status |
|---|---|---|
| busybox rootfs / initrd cpio | U-Boot `booti <kernel> <initrd> <fdt>` | planned; embedded initramfs is the current bring-up default |
| kernel modules (`.ko`) | Linux, after mounting a rootfs | blocked on a BL808 MMC driver and a mountable root |
| MMC check files (`testfile`, `hello.txt`) | `utils/uboot_console.py` suite | verified |

Prep scripts: `utils/mk_sdcard_test.sh` (card), `utils/sdcard_add_linuxboot.sh`
(kernel phase), `utils/linuxboot_console.py` (boot session).

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
