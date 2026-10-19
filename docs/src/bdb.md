# bdb dock companion (flash + logger, AI-facing)

`bdb` (repo: `bdb/`, Rust, zero dependencies) is the recommended driver for
flashing and log capture on the dock. It wraps the same underlying paths
documented in [Flashing](flashing.md) but adds the trust machinery an
autonomous agent needs: port locking, a crash-safe transaction journal,
on-chip readback verification as the only success criterion, and explicit
`NEED-USER` prompts whenever a human action is required (flash-mode entry,
USB replug, package installs).

See `bdb/README.md` for the full command reference. Summary:

```console
$ bdb state                     # classified device state + evidence + hints
$ bdb log start                 # tmux logger on /dev/ttyUSB0 and /dev/ttyUSB1
$ bdb flash low-load            # standard 4-region flash (flash-mode required)
$ bdb wait-for linux            # poll c0.log for the login prompt
$ bdb verify                    # re-read every region and compare SHA
$ bdb recover                   # replay an interrupted/failed transaction
```

Exit codes: `0` ok, `1` judged failure, `2` contention, `3` NEED-USER,
`4` usage error. Flash-mode entry (hold BOOT, tap RESET) and USB replugging
remain human steps; bdb prints the exact instruction instead of guessing.

## Field findings (2026-10-19 session)

### Cold-boot protocol is mandatory after any bflb session
After *any* flash or readback session (bdb, DevCube, or bare `bflb_mcu_tool`),
the BL808 is left in an eflash-loader state that **breaks the d0 branch on a
plain RESET**. The only reliable recovery is a **USB cold-cycle**:

1. Unplug USB cable, wait ≥ 3 s.
2. Plug back — the board re-enumerates both CDC ports (`ttyUSB0/1`).
3. Press **RESET only** (do not hold BOOT).
4. `bdb wait-for linux` → full d0 boot (OpenSBI → Linux login) appears on c0.

This behaviour was reproduced 4× in the session; it is **not** a bdb bug — it
is a property of the Bouffalo eflash loader leaving the chip in a state where
the m0 low_load skips the C906 start step unless the SoC is fully power-cycled.

### Flash map confirmed
| Region | Address | Size | Content |
|--------|---------|------|---------|
| bootinfo g0 (m0) | `0x0`   | 1636 B | BFNP header + m0 slot |
| bootinfo g1 (d0) | `0x1000`| 352 B  | BFAP header + d0 slot (flash `0x52000` → `0xD8000000`) |
| img g0 (m0 low_load) | `0x2000` | 38 128 B | wrapped `low_load_rep_bl808_m0.bin` |
| img g1 (d0 low_load) | `0x52000`| 29 200 B | wrapped `low_load_rep_bl808_d0.bin` |
| whole_img pack | `0xD2000` | ~7.5 MB | DTB @ `0xD2000`, OpenSBI @ `0xE2000`, kernel (Image.lz4) @ `0xF2000`, rootfs @ `0x500000` |

The whole_img pack is `M1s_BL808_Linux_SDK/out/whole_img_linux.bin` (7 528 448 B).
At 19:08 the chip held this pack at `0xD2000` and the region `0x80000..0xD2000`
was **all-FF**. A later tool session (20:48 DevCube mcu-tool run) wrote the same
pack mistakenly at `0x80000` (DTB at `0x80000`, OpenSBI at `0x90000`, kernel at
`0xA0000`), producing the "junk" that killed d0 until erased.

### Bootinfo tables
* Factory (19:08): 8 KB at `0x0` contains rich FCFG/GPIO pinmux blocks (marker
  `46 43 46 47` = "FCFG") used by the m0 firmware.
* DevCube / bflb tool output: same 8 KB but the FCFG region (`0x15C..0x663`)
  is **all-FF**; the rest of the header (BFNP/BFAP slots, lengths) is
  functionally equivalent — d0 boots fine either way.
* The tool-generated bootinfo (`img_create_mcu/bootinfo_group0.bin`) is only
  352 B (`0x160`), the minimal BFNP header without FCFG.

### bdb runtime patch
Embedded driver (`pyt.rs`) now patches the tool's runtime `.ini`
(`eflash_loader_cfg.ini`) at every session start:
```
cpu_reset_after_load = false  ->  true
```
This makes the tool emit the `reset cpu` (cmd 0x21) at session end. It fixes
the *flash session* cleanup, but **does not** eliminate the cold-boot
requirement — the wedge is deeper (PSRAM/clock/C906 start sequencing after
loader exit).

### Junk region `[0x80000..0xD2000)`
Not touched by bdb. Was written once by the 20:48 mcu-tool run (whole_img at
wrong base). Erased to FF by bdb; DevCube mcu flash does **not** rewrite it.
It is benign once cleared.
