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

Current steps performed by d0 `linux_load()` and `main()` (see `main.c`).
The user confirmed successful hardware boot with this PSRAM layout on
2026-10-19. The example transcripts above and below are from the previous layout.

| # | Action |
|---|---|
| 1 | Read kernel length from `*(uint32_t *)(0x580A0000-4)` |
| 2 | `unlz4(0x580A0000 → 0x50000000, len)` |
| 3 | `memcpy(0x58080000 → 0x51ff8000, 0x10000)` (DTB) |
| 4 | `memcpy(0x58800000 → 0x53f00000, 0x100000)` (OpenSBI slot) |
| 5 | Clean/invalidate D-cache, then `csrw mcor, 0x30013` |
| 6 | Install PMP table (8 entries) |
| 7 | `((void(*)(int,int))0x53f00000)(0, 0x51ff8000)` — jump to OpenSBI |

The DTB marks `0x53f00000..0x53ffffff` as reserved/no-map so Linux does not
allocate or directly map the OpenSBI firmware, BSS and scratch/stack area.

## 5. OpenSBI → Linux

Vendor `whole_img_linux.bin` flow shown below — the current U-Boot chain
(`whole_img_uboot.bin`) diverges after the OpenSBI jump, see section 6.

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

## 6. U-Boot chain (current, verified 2026-10-20)

`whole_img_uboot.bin` keeps the same slot geometry; the "kernel" slot holds
`u-boot.bin.lz4`, unpacked by the same `linux_load()` step to `0x50000000`.
OpenSBI (`fw_jump`, console-free) receives the DTB at `0x51ff8000` and jumps
to U-Boot instead of Linux.

From the U-Boot prompt (session driver `utils/linuxboot_console.py`; the
first run failed on a missing `mmc dev 0`, which the driver sends first now):

| # | Action | Verified result |
|---|---|---|
| 1 | `mmc dev 0`, `setenv bootargs earlycon` | card probed; console = `bflb,bl808-uart` earlycon (register-level; no mainline BL808 driver exists) |
| 2 | `load mmc 0:1 0x50200000 Image` | 27 506 176 B read in 2443 ms (10.7 MiB/s) |
| 3 | `load mmc 0:1 0x50080000 m1s.dtb` | 1 376 B bring-up DTB |
| 4 | `booti 0x50200000 - 0x50080000` | U-Boot relocated the DTB to `0x52a6b000`, "Starting kernel ..." |

Kernel evidence on ttyUSB0 (2026-10-20): early-init messages — boot banner,
SBI HSM extension available, ticket spinlock, zone/percpu/printk-buffer
init, SLUB and RCU setup, `riscv-intc: 64 local IRQs`, clocksource
registration, dummy console — heavily character-dropped, stopping at
`[    0.000803]` for the rest of the session. The drops come from the first
earlycon build writing the TX FIFO without checking `TX_FIFO_CNT`; a
FIFO-available rewrite was rebuilt (2026-10-20 05:36) but **not yet
boot-verified** — the stall cause stays unidentified until that run.
Transcript: `/tmp/opencode/linux_boot_transcript.log` (ephemeral). Kernel
side: branch `linux/bl808-m1s-bringup`, commits `83581e08` (DTS),
`81fc423c` (earlycon), `13ff5001` (dtb build fix).

## 7. Planned: kernel image from flash

Storage split decided 2026-10-20: the compressed kernel image moves into NOR
next to the chain, while the busybox/rootfs payload and modules stay on the
SD card. Slot placement, the required loader/merge changes and the
lz4-not-gz format decision are specified in
[Flash Layout](./flash-layout.md). Nothing here is implemented yet; the
section-6 SD path remains the iteration channel.

## 8. Summary of a "good boot"

| UART | Expected final lines |
|---|---|
| `ttyUSB1` | `psram clk init ok!` (m0, repeated after each reset) |
| `ttyUSB0` | `Linux login:` (vendor flow) — U-Boot chain currently ends at the U-Boot `=>` prompt until the kernel-in-flash slot lands (section 7) |
