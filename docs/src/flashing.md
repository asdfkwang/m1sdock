# Flashing

Use the corrected local `blflashcommand` checkout, directly or through
[bdb](bdb.md). The legacy `tools/bflb_*` paths are no longer the active backend.

## Required sequence

1. Stop both UART loggers: `bash utils/uart_logger_stop.sh`.
2. Confirm no other process holds either UART.
3. Enter flash mode: hold BOOT, press/release RESET, release BOOT.
4. Program and verify.
5. Start loggers, press RESET without BOOT, and inspect the new logs.

Never ask for flash mode while loggers still hold UART ports. USB replug is not
required: direct-command experiments succeeded before and after flashing without
it, and a logger-induced handshake failure recovered by stopping loggers alone.

## bdb

```bash
cargo build --release --manifest-path bdb/Cargo.toml
bdb/target/release/bdb log stop
# Enter flash mode
bdb/target/release/bdb flash low-load
bdb/target/release/bdb log start
# Press RESET without BOOT
bdb/target/release/bdb log tail --lines 100
```

Flash commands stop any active loggers, check both ports, and proceed directly
when the ports are free. On handshake failure, keep loggers off, check port
holders and flash mode, then retry. No replug acknowledgement is required.
Program and independent readback SHA verification share one UART connection.
Loggers are restarted only when requested.

## Direct blflashcommand

From the repo root, prepare images without touching UART:

```bash
blflashcommand/venv/bin/python -B utils/prepare_blflash_low_load.py
bash utils/uart_logger_stop.sh
```

After flash-mode entry:

```bash
cd blflashcommand
venv/bin/python -u -B BLFlashCommand.py \
  --interface=uart --port=/dev/ttyUSB1 --baudrate=2000000 --chipname=bl808 \
  --config="$PWD/chips/bl808/img_create/flash_low_load.ini"
```

Check four `Verify success` lines and final `[All Success]`. Start loggers and
press RESET without BOOT. This command updates only low-load images:

| Group | CPU | Execution address | Bootinfo flash offset | Body flash offset |
|---|---|---|---|---|
| Group0 | M0 | `0x58000000` | `0x0` | `0x2000` |
| Group1 | D0 | `0x58000000` | `0x1000` | `0x52000` |

Inputs are `M1s_BL808_Linux_SDK/out/low_load_bl808_{m0,d0}.bin`, as prescribed
by that SDK README. The Linux whole image is not included in this operation.
The preparer checks all flash-table IDs, including the board's **ef4018**.
The original decompiled table generator skipped first occurrences and produced
images that passed write verification but did not boot.

## Boot verification

Read only the newest logger session in `logs/c0.log` and `logs/c1.log`.
M0's `E907 start` / PSRAM message confirms M0 startup. OpenSBI, Linux kernel,
rootfs mount, and init on c0 confirm D0 boot progress. Report `Linux login:` only
when that prompt actually appears. Stored-byte verification alone does not
prove a working boot.
