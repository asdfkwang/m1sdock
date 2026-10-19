# Boot Sequence

End-to-end order observed on silkscreen pins `RST` and bootrom messages.

## 1. Reset release

```
RST released
 └─ C906 (d0) bootrom runs from on-chip ROM @0x50000000
    bootrom build string: "Sep 29 2021 17:07:23 … romdriver version:%08x"
```

## 2. Flash scan

Bootrom scans flash @`0x000000`:

```
BFNP @0x000000  →  slot0 {flash=0x000000, dest=0x58000000}  → m0 path
BFAP @0x001000  →  slot1 {flash=0x052000, dest=0xD8000000} → d0 path
```

Both must decode (`magic`, `revision`, ok crc) — a mismatch in either
blocks that core silently (no banner on that UART at all).

## 3. m0 (E907) launch

```
E907 ← XIP @ 0x58002000 (flash 0x002000)
   runtime output (ttyUSB1):
     "dynamic memory init success,heap size = 156 Kbyte"
     "E907 start..."
     "mtimer clk:1000000"
     "psram clk init ok!"
```

The m0 firmware in `low_load` does nothing else but: banner, IPC sync word,
then spin. d0 startup is handled by the bootrom, not by m0.

## 4. d0 (C906) launch

```
C906 ← XIP @ 0x58052000 (flash 0x052000)
   runtime output (ttyUSB0):
     "C906 start..."
     "linux load start..."
     "len:0x00376c53"          ← 4-byte length header before Image.lz4
     "vm linux load done!"
     "dtb load done!"
     "opensbi load done!"
```

Steps performed by d0 `linux_load()` (see `main.c`):

| # | Action |
|---|---|
| 1 | Read kernel length from `*(uint32_t *)(0x580A0000-4)` |
| 2 | `unlz4(0x580A0000 → 0x50000000, len)` |
| 3 | `memcpy(0x58080000 → 0x51ff8000, 0x10000)` (DTB) |
| 4 | `memcpy(0x58090000 → 0x3eff0000, 0xC000)` (OpenSBI) |
| 5 | `csrw mcor, 0x30013` (invalid all DCACHE/ICACHE) |
| 6 | Install PMP table (8 entries) |
| 7 | `((void(*)(int,int))0x3eff0000)(0, 0x51ff8000)` — jump to OpenSBI |

## 5. OpenSBI → Linux

```
OpenSBI v0.6
...
[    0.000000] SBI specification v0.2 detected
...
[    0.095731] printk: console [ttyS0] enabled
...
[    0.154242] physmap-flash 58500000.xip_flash: [mem 0x58500000-0x588fffff]
[    0.155705] 1 fixed-partitions partitions found on MTD device xip-flash.0
[    0.156476] 0x000000000000-0x000000280000 : "rootfs"
...
[    0.191216] VFS: Mounted root (squashfs filesystem) readonly on device 31:0.
[    0.220950] Run /sbin/init as init process
...
Linux login:
```

## 6. Summary of a "good boot"

| UART | Expected final lines |
|---|---|
| `ttyUSB1` | `psram clk init ok!` (m0, repeated after each reset) |
| `ttyUSB0` | `Linux login:` |
