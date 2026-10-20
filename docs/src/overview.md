# Overview

Sipeed M1s Dock (BL808 SoC) running task-based Linux from SPI NOR flash.
Repo contains the SDK tree, the Bouffalo flash tools, loggers, and this book.

## What boots where

| ID | Core | ISA | Role | UART |
|---|---|---|---|---|
| m0 | E907 | \*rv32 | Loader stub; prints banner, then spins | `ttyUSB1` |
| d0 | C906 | rv64 linux cpu         | Boot ROM loads `bootinfo@0x1000`, XIP-executes `d0@0x52000`, loads OpenSBI → U-Boot → Linux | `ttyUSB0` |

Both banners and Linux console are on separate USB CDC channels of the dock:

- `ttyUSB0` = C906/Linux console (d0)
- `ttyUSB1` = E907/banner (m0) and the bootrom flashing port (same port!) — used by tools

## Storage split (2026-10-20)

Flash carries the boot chain and the compressed kernel image; the SD card
carries the iterative payload — busybox rootfs content, kernel modules, MMC
check files — over the verified `load mmc` path. See
[Flash Layout](./flash-layout.md) for the capacity math and the planned
kernel slot.

## Repository map

| Path | Contents |
|---|---|
| `M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/` | m0/d0 low_load sources, build system, drivers |
| `M1s_BL808_Linux_SDK/out/` | Flash-ready binaries (`low_load_bl808_m0.bin`, `low_load_bl808_d0.bin`, `whole_img_linux.bin`, `whole_img_uboot.bin`) |
| `tools/bflb_iot_tool/` | CLI flasher (`--single` raw-block flasher) |
| `tools/bflb_mcu_tool/` | Library used by our wrapper scripts |
| `chips/bl808/` | Vendor bootinfo/img artifacts (DevCube and iot tool outputs) |
| `linux/`, `u-boot/`, `opensbi/`, `busybox/` | Upstream checkouts; kernel branch `bl808-m1s-bringup` (DTS + `bflb,bl808-uart` earlycon) |
| `utils/build_linux.sh`, `utils/build_busybox.sh` | Cross builds: defconfig + SBI-console toggles, embedded busybox initramfs; static busybox |
| `utils/linuxboot_console.py`, `utils/sdcard_add_linuxboot.sh` | SD boot session driver and card prep |
| `utils/uart_logger_*.sh` | tmux-based serial loggers (c0, c1) |
| `logs/` | `c0.log`, `c1.log` raw UART captures |
