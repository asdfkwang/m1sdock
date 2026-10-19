# Hardware Interfaces

## USB CDC ports

| Port | Transceiver | Baud | Used for |
|---|---|---|---|
| `ttyUSB0` | CH552-side UART0 | 2,000,000 | C906 (d0): Linux console, earlyprintk, OpenSBI |
| `ttyUSB1` | CH552-side UART1 | 2,000,000 | E907 (m0) banner **and** bootrom flash protocol |

## Boot-mode pins

| Action | Result |
|---|---|
| RST only | Normal boot: bootrom → flash → m0 + d0 |
| Hold BOOT, press+release RST, release BOOT | ``flash mode`` (bootrom console = `ttyUSB1`, ready for flashers) |

## SPI NOR flash

| Item | Value |
|---|---|
| JEDEC ID | `EF 40 18` (XTX) — 16 MB |
| Capacity | `0x01000000` |
| XIP window, d0-mapped | `0x58000000` maps to D0 body at flash `0x052000` |
| XIP window, m0-mapped | `0x58000000` maps to M0 body at flash `0x002000` |
| Linux XIP sources | DTB@`0x58080000`, OpenSBI@`0x58800000`, kernel@`0x580A0000` in d0 `linux_load()` |
| OpenSBI runtime | `0x53f00000..0x53ffffff`: 1 MiB PSRAM, reserved/no-map in DTB |
| mtd physmap node | `0x58500000-0x588fffff`, starting at physical flash `0x552000`; rootfs partition size `0x280000` |
