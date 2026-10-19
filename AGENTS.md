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
- Hardware-free checks: `cargo test --manifest-path bdb/Cargo.toml`,
  `cargo build --manifest-path bdb/Cargo.toml`, then
  `python3 -B bdb/tests/test_workflow.py`. Do not flash hardware to test code
  changes unless the user explicitly requests it.
