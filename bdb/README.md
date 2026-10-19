# bdb — M1s Dock companion

Dependency-free Rust CLI wrapping the local corrected `blflashcommand` checkout.
The old `tools/bflb_mcu_tool`, `tools/bflb_iot_tool`, and CPU-reset runtime patch
are no longer used. Flash and readback use `blflashcommand/venv/bin/python`.

## Build and check

```bash
cargo build --release --manifest-path bdb/Cargo.toml
bdb/target/release/bdb doctor
```

Runtime requirements: `blflashcommand` with its Python dependencies (including
`setuptools<81` for CryptoPlus), `tmux`, `tio`, `flock`, and `sha256sum`.
`doctor` checks files and Python imports without opening a UART.

## Flash procedure

1. Stop loggers with `bdb log stop` before entering flash mode. Every flash,
   readback, verify, or recover session also stops active loggers and checks
   both UARTs for residual holders before opening the device.
2. Enter flash mode: hold BOOT, press/release RESET, release BOOT.
3. Run `bdb flash low-load`. A free port proceeds directly; no replug or
   acknowledgement flag is required. An external port holder blocks flashing.
4. After verified flashing, run `bdb log start`, press RESET **without BOOT**,
   and inspect the newest session with `bdb log tail`.

```bash
bdb/target/release/bdb log stop
# Enter flash mode
bdb/target/release/bdb flash low-load
bdb/target/release/bdb log start
# Press RESET without BOOT
bdb/target/release/bdb log tail --lines 100
```

USB replug is not part of the normal procedure, including retries. The former
`--usb-replugged` option is accepted as a no-op for old commands, but is no
longer advertised or needed. Old `usb-replug-required` marker files are ignored.
Loggers are not automatically restarted after a session.

### Observed experiments (2026-10-19)

| Sequence | Result |
|---|---|
| Loggers off → replug → flash mode → flash → RESET | PASS |
| Loggers off → no replug → flash → RESET | PASS |
| Loggers on → flash | Handshake failure, code 0050 |
| Handshake failure → loggers off → RESET → flash | PASS, no replug |
| Loggers on → flash failure → loggers off → flash | PASS, no RESET/replug |

These direct BLFlashCommand experiments support releasing UARTs as the normal
precondition. They supersede the earlier claim that a USB cold-cycle is always
mandatory; they do not establish every possible cause of a communication error.
Storage verification and the subsequent boot check remain separate.

## Images and verification

`flash low-load` generates and validates artifacts with
`utils/prepare_blflash_low_load.py`, using binaries from
`M1s_BL808_Linux_SDK/out/low_load_bl808_{m0,d0}.bin`.
It follows the SDK README: M0 **Group0**, D0 **Group1**, both execution addresses
**0x58000000**. Physical flash offsets are:

| Artifact | Offset |
|---|---|
| Group0 bootinfo | `0x0` |
| Group1 bootinfo | `0x1000` |
| M0 body | `0x2000` |
| D0 body | `0x52000` |

The Linux whole image is not rewritten by this recipe. Image generation checks
body SHA-256, header CRC, core selection, entry addresses, all 56 JEDEC table
entries (including this board's **ef4018**), and table pointers/CRCs. The corrected
table builder includes the first occurrence of each config file; the original
decompiled code omitted those rows and produced nonbooting images.

bdb hashes sources and saves the transaction **before** opening UART. It uses
`blflashcommand`'s BL808 loader to program and read back all regions over **one
connection**, then independently compares exact-size readback SHA-256 hashes.
It never trusts a tool success banner alone. Reads are packet-sized to avoid
the decompiled reader's multi-packet loop bug. No efuses are programmed.

Verification proves stored bytes match; confirm actual boot from the newest
logger session. OpenSBI/kernel/init output proves progress even if the low-load
banner or `Linux login:` prompt is absent.

## Commands

```text
devices
state [--json]
doctor
log start|stop|status
log tail [--lines N] [--which c0|c1|all]
wait-for linux|opensbi|d0|m0
flash low-load
flash file PATH --addr 0xX
flash factory-bootinfo
readback --addr 0xX --len 0xN [--out PATH]
verify
recover
```

`factory-bootinfo` writes the historical 8 KiB asset; it is not a general replacement
for regenerating headers matching current binaries. `readback` and `verify` never
write firmware. `recover` replays failed/interrupted operations; readback recovery
remains read-only. `--no-verify` is accepted but cannot disable verification.

Global flags, in any position: `--json`, `--timeout SECONDS`
(default 600), `--port-c0`, `--port-c1`, `--baud`, `--repo-root`.
Exclusive operations retain a kernel `flock`; global options survive the lock
re-exec. Journals and work files live under `$XDG_RUNTIME_DIR/bdb`, or
`/tmp/bdb-<uid>/bdb` if unset. A timed-out/interrupted run remains recoverable;
source records are available even if the writer died mid-program.

Exit codes: **0** verified success, **1** failure/timeout, **2** busy,
**3** physical step or missing dependency, **4** usage error.
`NEED-USER: [buttons]` and `NEXT:` lines describe flash-mode entry and next steps.

## Hardware-free tests

```bash
cargo test --manifest-path bdb/Cargo.toml
cargo build --manifest-path bdb/Cargo.toml
python3 -B bdb/tests/test_workflow.py
```

The workflow tests use an isolated fake tool, fake ports, and fake tmux. They
exercise automatic logger shutdown, port-holder blocking, flag forwarding, a single write/read connection,
journaling, short reads, SHA mismatch, timeout, recovery, and paths with spaces.
