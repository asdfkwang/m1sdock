# bdb — dock companion for the Sipeed M1s (BL808)

`bdb` is a small, dependency-free Rust CLI designed for **AI agents that drive
the dock without a human babysitting every step**. It unifies the existing
flash + logger tooling under one interface whose first priority is *trust*:

- the tool always reports a truthful, classified **device state** with evidence;
- every flash runs as a **journalled transaction** that survives crashes;
- success is decided **only by on-chip readback SHA equality**, never by the
  flash tool claiming success;
- anything that requires human hands (holding BOOT, tapping RESET, replugging
  USB) is surfaced as a greppable `NEED-USER:` line — bdb never pretends a
  human step happened and never fakes results.

## Build

```console
$ cd bdb && cargo build --release     # binary: bdb/target/release/bdb
```

No crates.io dependencies; the tool shells out to the repo's existing
`bflb_mcu_tool`/`bflb_iot_tool` python stack (via `tools/venv`), util-linux
`flock`, `tmux`+`tio` for logging and `sha256sum`.

Run `bdb doctor` to self-check the environment; missing system packages are
reported as `NEED-USER: [exec] run: sudo apt install ...` and exit code 3.

## Commands

```console
devices                                # port inventory + holders (read-only)
state [--json]                         # classified state + evidence + hints
doctor                                 # dependency self-check
log start|stop|status|tail             # tmux logger (start/stop take the port lock)
wait-for linux|opensbi|d0|m0           # poll a log signature; long waits are fine
flash low-load | factory-bootinfo | file PATH --addr 0xX   # flash-mode required
readback --addr 0xX --len 0xN [--out]  # on-chip flash read (flash-mode required)
verify                                 # re-read and compare the last flash txn
recover                                # replay an unfinished/failed transaction
help
```

Global flags (any position): `--json`, `--timeout SECONDS` (lock wait + tool
soft cap, default 600), `--port-c0`, `--port-c1`, `--baud`, `--repo-root`.

## Cold-boot protocol (mandatory after any session)

After **any** flash or readback session (bdb, DevCube, bare `bflb_mcu_tool`),
the BL808 SoC is left in an eflash-loader state that **breaks the d0 branch
on a plain RESET**. The only reliable recovery is a **USB cold-cycle**:

1. Unplug USB cable, wait ≥ 3 s.
2. Plug back — the board re-enumerates both CDC ports (`ttyUSB0/1`).
3. Press **RESET only** (do not hold BOOT).
4. `bdb wait-for linux` → full d0 boot (OpenSBI → Linux login) appears on c0.

This is not a bdb bug — it is a property of the Bouffalo eflash loader leaving
the chip in a state where the m0 low_load skips the C906 start step unless the
SoC is fully power-cycled. bdb prints the exact instruction at the end of
every flash transaction.

## Flash recipes

- `flash low-load` — the standard flashing flow: programs the vendor
  `low_load_bl808_{m0,d0}.bin` with tool-generated bootinfos at
  `0x0 / 0x1000 / 0x2000 / 0x52000` (see `docs/bootinfo.md`).
- `flash factory-bootinfo` — rewrites `bdb/assets/factory_bootinfo.bin`
  (8 KiB factory bootinfo dump) to `0x0`. This is the proven **un-mute
  rescue recipe** for a silent d0: it was used to revive the dock after the
  ghost-write incident.
- `flash file PATH --addr 0xX` — any raw image at a fixed offset.
- `--no-verify` is accepted but ignored: on-chip readback verification is
  always enforced.

## How the crash-safety works

1. **Port lock**: exclusive commands re-exec themselves through
   `/usr/bin/flock` over `<run>/bdb/ttyUSB1.lock`. The kernel lock is held by
   the running process; a crash (SIGKILL/OOM) releases it automatically.
   No sudo, no daemon, no stale locks after a machine reboot.
2. **Transaction journal**: a manifest (`txn.json` in the run dir) is written
   *before* any flash step and updated after each verified region. The owner
   pid + its `/proc` start ticks are recorded, so a dead owner is detected
   even after pid reuse.
3. **Interrupted detection**: if the writing process died mid-flash the next
   `bdb state` reports `flash-interrupted` with the unverified regions, and
   `bdb recover` replays the recorded command — the board converges back to
   the intended state (flashing is idempotent).
4. **Ghost reaping**: an orphaned `bflb` python child (its bdb parent is
   gone) is reaped automatically at the next run before touching the port.
5. **Truth = on-chip readback**: after programming, every region is read
   back from the chip and compared against the source SHA; a mismatch ends
   with `NEED-USER: [replug]` because the known failure mode (repeated USB
   open/close polluting the port → ghost writes that claim success) requires
   a physical replug.

## Exit codes

| code | meaning |
|------|---------|
| 0 | success |
| 1 | judged failure (program failed, verify mismatch, wait timeout) |
| 2 | contention (port held, lock busy) |
| 3 | NEED-USER (manual step: buttons / replug / missing package) |
| 4 | usage error |

`NEED-USER: [tag]` lines are machine-greppable; tags: `buttons` (flash-mode
entry: hold BOOT, tap RESET, release after ~1 s), `replug` (unplug the USB
cable, wait 3 s, plug back), `exec` (run a command, e.g. `sudo apt install
tio`), `fix-repo` (restore a repo tree). `NEXT:` lines suggest what the AI
runs afterwards.

## Run-dir layout

`$XDG_RUNTIME_DIR/bdb/` (default `/run/user/<uid>/bdb/`, tmpfs-clean):

```
ttyUSB1.lock     # kernel-flock holder metadata (pid, pid_start, ts, cmd)
txn.json         # active transaction slot ("" when idle)
txn-hist/        # finished/failed transaction history
work/            # embedded python drivers + readback outputs
```
