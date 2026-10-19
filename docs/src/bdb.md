# bdb Dock Companion

`bdb` uses the local corrected **blflashcommand** backend for programming and
readback. See [the CLI README](../../bdb/README.md) for commands and build steps.

## Flash procedure

1. Run `bdb log stop` before asking the user to enter flash mode.
2. Enter flash mode: hold BOOT, press/release RESET, release BOOT.
3. Run `bdb flash low-load`. It also stops any active loggers and checks both
   UARTs for other holders before opening the port.
4. Run `bdb log start`, then press RESET without BOOT and read the latest
   session with `bdb log tail`.

**USB replug is not required before/after flashing or on a normal retry.**
The old acknowledgement gate and persistent replug-state checks are removed.
Old marker files are ignored; `--usb-replugged` is a compatibility no-op.
Readback, verify, and recover follow the same free-port requirement.

Controlled direct-BLFlashCommand experiments found that flashing succeeded
without pre/post replug, failed with loggers active (0050 handshake failure),
and succeeded after stopping the loggers alone, without RESET or replug.
The previous mandatory cold-cycle claim is superseded by these observations.

## Confirmed configuration

- Inputs: `M1s_BL808_Linux_SDK/out/low_load_bl808_{m0,d0}.bin`.
- M0 = Group0, D0 = Group1, execution address **0x58000000** for each, as in the
  SDK README. Header offsets `0x0`/`0x1000`; body offsets `0x2000`/`0x52000`.
- Low-load flashing leaves the Linux whole image alone.
- `utils/prepare_blflash_low_load.py` validates CRCs, hashes, core assignment,
  addresses, and the entire flash config table, including actual board ID **ef4018**.
- The decompiled table builder originally omitted the first row for each unique
  config file, including ef4018. Fixing it restored the table from 47 to 56 IDs
  and Group0 bootinfo from 1564 to 1636 bytes. Subsequent logs reached OpenSBI,
  Linux, rootfs mount, and init; that is boot progress, not proof of a login prompt.

Sources are journaled before writing. Program and readback share one UART
connection; success requires matching readback SHA-256 for every region. Exit 0
means bytes verified, followed by a separate RESET and boot-log check.
Do not infer boot success solely from `[All Success]` or a hash match.

The old `tools/bflb_*` backend and CPU-reset runtime patch are removed. UART ownership must be exclusive during flashing.
