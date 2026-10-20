# M1s Dock workflow

- Use the local corrected `blflashcommand` checkout for flashing and readback.
  `bdb` is the Rust wrapper; do not restore the old `tools/bflb_*` backend.
- Stop both UART loggers and check that ports are released **before** asking
  the user to enter flash mode or opening a flash/readback session.
- USB replug is **not required** before or after flashing. Experiments showed
  direct BLFlashCommand succeeds without it; an active logger causes handshake
  failure, and stopping it alone permits a successful retry without RESET or
  replug. Do not restore mandatory replug gates or acknowledgements in bdb.
- After verified flashing, start loggers when requested and use RESET without
  BOOT to inspect boot logs. Flash-mode entry is a physical user action; do not
  assume it happened. Keep loggers off on a failed flash until retry is ready.
- Source binaries are in `M1s_BL808_Linux_SDK/out`. Follow that SDK's README:
  M0 = Group0, D0 = Group1, both image execution addresses `0x58000000`.
  Generated headers go at flash `0x0`/`0x1000`; bodies at `0x2000`/`0x52000`.
  Do not confuse execution addresses with flash offsets or rewrite Linux's
  whole image as part of a low-load-only update.
- Generate low-load images with `utils/prepare_blflash_low_load.py` using
  `blflashcommand/venv/bin/python`. Validate the entire flash configuration
  table, including board JEDEC ID `ef4018`, all pointers/CRCs and body hashes.
  The decompiled table builder previously skipped first occurrences of each
  config file, including `ef4018`, causing verified writes that did not boot.
- SHA verification proves storage integrity, not boot success. Report M0,
  OpenSBI, kernel/init, and login separately from the latest logger session.
- U-Boot SD/MMC status (verified 2026-10-20): upstream OpenSBI + S-mode
  U-Boot boot with `whole_img_uboot.bin` at flash `0xD2000`; the D0 console
  (`/dev/ttyUSB0`, 2 Mbps; `/dev/ttyUSB1` is the M0/blflash port) identifies
  the card and reads FAT test files with CRC matches. The fix was
  `bias-pull-up` on the SD pads in U-Boot's `bl808.dtsi`. Card scratch
  region is `0x51xxxxxx`; never use `0x5300xxxx` —
  it overlaps OpenSBI/U-Boot reservations. Evidence and limitations
  (writes, Linux, repeated boots) live in `experiments/sdh-irq/README.md`.
- `utils/uboot_console.py` runs the SD check suite over the D0 console with
  the blflashcommand venv (pyserial) and prints a PASS/FAIL verdict; run it
  while the loggers are stopped so the port is free. The UART loggers use
  `utils/uart_logger_start.sh` / `uart_logger_stop.sh`.
- Hardware-free checks: `cargo test --manifest-path bdb/Cargo.toml`,
  `cargo build --manifest-path bdb/Cargo.toml`, then
  `python3 -B bdb/tests/test_workflow.py`. Do not flash hardware to test code
  changes unless the user explicitly requests it.
