# BL808 SDH interrupt and card-response experiments

## Verified on M1s Dock, 2026-10-20

The already-flashed U-Boot identified itself as
`2023.04-rc2-g15b4a6348b9-dirty`, built 2026-10-19 22:02:25 -0400.
Do not equate that dirty build string with the exact current U-Boot checkout.
OpenSBI was unchanged. No M0 code, Flash image or SD card data was written.

The complete observed path is:

```text
SDH event -> GLB M0IC source 17 -> PLIC source 81
          -> D0 supervisor external trap -> diagnostic handler
          -> source clear / PLIC completion -> return with sret
```

Two RAM executions obtained a real CMD8 response of `0x000001aa` with:

```text
scause = 0x8000000000000009  (supervisor external interrupt)
claim  = 0x00000051          (81 decimal)
SDH    = 0x00000001          (command complete, no error)
M0IC   = 0x00020000          (source 17)
```

The final execution repeated two forced-error interrupts, completed CMD0,
observed CMD8 timeout at the first settings, obtained CMD55/ACMD41 responses,
then completed CMD0/CMD8 successfully at the second settings. The final IRQ
count was eight. A stale response register was **not** treated as success:
CMD8 needed a fresh command-complete event without an error and the echo.

| Card profile | Clock register | Pad settings | Result |
|---|---|---|---|
| 0 | `0x7807` (nominal 400 kHz) | Existing U-Boot pin configuration | CMD8 timed out; CMD55 and ACMD41 responded |
| 1 | `0xE047` (nominal 100 kHz) | SDK-style SDH function, input, Schmitt, drive 1, pull-up on GPIO0..5 | CMD8 completed with R7 `0x1aa` and a real S-mode IRQ |
| 2 | `0xFFC7` (nominal 47 kHz) | Same SDK-style settings | Not reached after profile 1 succeeded |

Frequencies assume the configured 96 MHz controller source; no physical
clock waveform was measured. Speed, pin settings and prior card-command
history changed together. These runs do **not** isolate the cause of the
initial failure, prove a legacy card, or establish an upstream driver fix.

The final run independently read back 25 controller/pad/PLIC configuration
registers before and after execution. All writable configuration bits matched
(read-only clock-stable and GPIO input-level bits excluded). The application
restored supervisor CSRs and returned to the working U-Boot prompt. Transient
pending/status history and the card's protocol state are not restored.

## Evidence

- [Initial attempt](2026-10-20/00-baseline-attempt-transcript.txt): masking
  alone left previously latched M0IC status; stopped and restored settings.
- [Forced-event polling proof](2026-10-20/01-forced-event-transcript.txt):
  two SDH -> M0IC -> PLIC transitions, explicit S-context claim/complete.
- [First successful card + IRQ run](2026-10-20/ram-030834/transcript.txt).
- [Repeated card + IRQ run and restoration readback](2026-10-20/ram-030931/transcript.txt).
- [Machine-readable final result](2026-10-20/ram-030931/result.json),
  [before](2026-10-20/ram-030931/before.json),
  [after](2026-10-20/ram-030931/after.json).

Every RAM run retains its UART transcript and S-record image. The final run
also retains the exact target sources and image SHA-256 values. ELF build
artifacts are ignored. Earlier failed executions are retained as evidence:
an upload CRC mismatch stopped execution; an initial handler allowed another
notification to overwrite the first observation. The final handler masks CPU
delivery until main rearms and orders source acknowledgement before completion.

## Reproduce

Run from this repository root with the board already at the U-Boot prompt:

```sh
make -C experiments/sdh-irq
# Stop both loggers and release picocom before opening UART.
bash utils/uart_logger_stop.sh
fuser /dev/ttyUSB0 /dev/ttyUSB1
blflashcommand/venv/bin/python -B experiments/sdh-irq/run_ram_probe.py
```

`run_ram_probe.py` requires pyserial and the existing `loads`, `crc32`, `go`,
`md` and `mw` commands. It uses 2 Mbps D0 UART without toggling DTR/RTS.
It checks reported RAM reservations, initializes only the test region
`[0x50100000, 0x50110000)`, transfers S-records and verifies CRC before `go`.
The target uses the current U-Boot stack and UART, so this is a diagnostic
for this board state, not a general standalone application ABI or OS driver.

The program temporarily changes `stvec`, `sie`, `sstatus`, PLIC settings,
M0IC masks, GPIO0..5 and SDH configuration. It does not issue block writes,
change clocks/voltage outside the tested configuration or flash firmware.
Unexpected traps print cause/address and stop; a physical RESET is then
required. On normal success or a command failure it restores configuration
and returns. Log directories are created inside `2026-10-20/` for this study.

## Standard U-Boot MMC stack and file reads

Subsequent tests used the existing U-Boot MMC driver, without the RAM IRQ
application or any driver patch. With SDK-style pad settings, `mmc dev 0`
and `mmc rescan` identified a 59.7 GiB SD 3.0 high-capacity card, manufacturer
`1b`, OEM `534d`, name `EC1S5`, using a 4-bit bus and the requested SD High
Speed 50 MHz mode. The controller source is nominally 96 MHz and its divided
clock register was `0x0107`, corresponding to 48 MHz, not a measured 50 MHz.

The DOS/FAT32 partition started at sector 2048. Both test files were loaded
twice into unreserved RAM, with exact load length and U-Boot `filesize`
checked before CRC. The independent, previously generated manifest matched:

| File | Bytes | CRC32 | Repetitions |
|---|---:|---|---:|
| `testfile` | 131072 | `7E8E43C2` | 2 |
| `hello.txt` | 55 | `BDB1A907` | 2 |

[Original transcript](2026-10-20/files-031656/transcript.txt),
[results](2026-10-20/files-031656/result.json), and
[original card manifest](2026-10-20/files-031656/sdcard_manifest.txt).
Buffers were `0x51000000` and `0x51040000`: the old manifest's proposed
`0x53000000` overlaps current U-Boot reservations and was not used.

### Pull-up versus drive-strength A/B results

The next experiment varied only pull-up and drive-strength on GPIO0..5;
each profile ran a fresh `mmc rescan`. Successful profiles also loaded the
128 KiB test file and matched its CRC. No SD or SoC clock source was changed.

| Profile | Card initialization | File CRC |
|---|---|---|
| Original pin settings | Fail | Not attempted |
| Add pull-up only | Pass | Match |
| Set drive-strength 1 only | Fail | Not attempted |
| Pull-up + drive-strength 1 | Pass | Match |
| Original settings again | Fail | Not attempted |
| Pull-up + drive-strength 1 again | Pass | Match |

[A/B transcript and clock dump](2026-10-20/characterize-032621/transcript.txt),
[results](2026-10-20/characterize-032621/results.json), and
[clock registers](2026-10-20/characterize-032621/registers.json).

For this board/card/session, enabling pad pull-up is sufficient to make the
standard driver work; increasing drive-strength alone is insufficient. This
is stronger evidence than the earlier mixed clock/pad trial.

## Pull-up pin narrowing (characterize-041558, pairs-041750)

Two follow-up studies added the pull-up bit (GPIO_CFG bit4) to subsets of
GPIO0..3 only (GPIO4/5 already carry the pull-up bit in every observed
post-boot state), always recomputed from the saved baseline:

- [pins run](2026-10-20/pins-041558/results.json): pull-up on GPIO1 alone
  identified the card and matched the test-file CRC once, but repeating the
  profile directly afterwards failed with `unable to select a mode`
  (card-state/ordering effects). GPIO0, GPIO2, GPIO3 singles failed.
- [pairs run](2026-10-20/pairs-041750/results.json): pull-up on
  **GPIO0+GPIO1** passed three consecutive runs (card identification,
  131072-byte load, CRC `7e8e43c2`), and the no-pull-up baseline failed both
  before and after. The remaining pairs were not needed and not tested.

The minimal reliable pad set for this board/card is therefore
**GPIO0+GPIO1 pull-up**; the robust board-wide setting mirrors the vendor
SDK style: pull-up on all six SD pads.

## Cold-boot verification with the DT fix (whole_img_uboot.bin)

`u-boot/arch/riscv/dts/bl808.dtsi` now sets `bias-pull-up;` on the
`sdh-pins` group (all six pads). The rebuilt `whole_img_uboot.bin`
(8,912,896 B) flashed at `0xD2000`):
read-back SHA-256 matched `f4e04352…d85491`. After RESET without BOOT,
`utils/uboot_console.py --repeat 2` produced a full pass on the D0 console
([transcript](2026-10-20/coldboot-transcript.txt)):

| Check | Result |
|---|---|
| `mmc list` | `mmc@20060000: 0` |
| Card identity | manuf `1b`, OEM `SM`, name `EC1S5`, SD 3.0 HC, 59.7 GiB, 4-bit, HS 50 MHz |
| Partition/files | DOS part 1 (FAT32): `hello.txt` 55 B, `testfile` 131072 B |
| testfile load + CRC @0x51000000 | 131072 B read, CRC `7e8e43c2` = manifest |
| hello.txt @0x51040000 | byte dump matches "M1s Dock SDHC test card" |
| Repeat round | buffer scrambled with `mw.b 0xa5`, fresh load, same CRC |

Load addresses use the 0x51xxxxxx scratch region; 0x5300xxxx overlaps
OpenSBI/U-Boot reservations and must not be used for card data.

## Remaining work

Repeated cold boots (more than one), SD writes and Linux IRQ handling are
not established. No OpenSBI patch was needed for the IRQ,
card-identification or file-read tests above. Original pad settings are
restored after each experiment.
