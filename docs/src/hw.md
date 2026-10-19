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
| XIP window, d0-mapped | `0x58000000` = flash offset `0x000000` |
| XIP window, m0-mapped | `0x58000000` as well (m0 identity = C906 XIP alias) |
| Linux XIP base | `0x58000000` (DTB@`0x58080000`, OpenSBI@`0x58090000`, kernel@`0x580A0000` in d0 `linux_load()`) |
| mtd physmap node | `0x58500000-0x588fffff` = flash offset `0x500000` (rootfs partition) |
