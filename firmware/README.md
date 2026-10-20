# D0 Rust probe

Cargo builds a `no_std` static library for D0/C906. Vendor startup and hardware
initialization remain in C. Immediately after `C906 start...`, C calls
`d0_rust_probe()`, which prints `D0 Rust OK` through a vendor UART callback
and returns to the existing loader. Image decompression, DTB/OpenSBI copying,
PMP/cache setup and OpenSBI handoff are unchanged. M0 uses vendor firmware.

## Build

Requirements: Rust/Cargo, the existing vendor toolchain and
`riscv64-linux-gnu-objcopy` (`binutils-riscv64-linux-gnu` on Debian).

From the repository root:

```bash
rustup target add riscv64gc-unknown-none-elf
bash utils/build_rust_d0.sh
```

Outputs are isolated from SDK deployment binaries:

- `firmware/build-d0/out/firmware.elf`
- `firmware/build-d0/out/firmware.bin`
- `firmware/build-d0/out/firmware.map`
- `firmware/build-d0/out/firmware.asm`

The script enables `LOW_LOAD_RUST_D0`, which defaults to OFF in normal SDK
builds and rejects cores other than D0. It does not change SDK `out/`, copy
to the vendor flash-tool input, generate flash headers or flash hardware.

For the Rust archive alone, run `cargo build --release --locked --offline`
from `firmware/`. There are no external Cargo dependencies.

## ABI and linking

`riscv64gc-unknown-none-elf` uses RV64GC and the double-float `lp64d` ABI,
matching vendor D0's ABI. Rust uses the medium code model to match vendor
`medany`. No vector extension is enabled: C906's vendor vector 0.7 support
is not the modern RISC-V V extension.

The old vendor linker cannot parse modern Rust ISA attribute names. Modern
GNU objcopy removes only `.riscv.attributes` from a separate link-only archive;
machine code and ELF ABI flags are preserved. The Cargo archive is untouched.
Additional ISA extensions require a new hardware compatibility review.

## Verification and hardware test

On 2026-10-20, Rust 1.98.1 produced a 29,060-byte D0 body. ELF inspection
confirmed entry `0x58000000`, ELF64/double-float ABI, and the call from C to
the Rust probe, its UART callback and continuation at `mtimer_init()`.
Firmware format and shell syntax checks, `bdb` Cargo test/build and all
19 workflow tests passed.

Vendor M0 and the Rust D0 image were flashed on M1s Dock. Both boot headers
and both bodies passed full readback SHA-256 verification (transaction
`txn-6ad70503-0044`). The user confirmed `D0 Rust OK` output on the board.
This establishes execution of the Rust probe and UART callback; subsequent
return, OpenSBI, U-Boot, kernel/init and login were not established by that
output alone.

For a separately requested flash, use vendor M0 and stage this body as
`M1s_BL808_Linux_SDK/out/low_load_bl808_d0.bin`. Regenerate and validate
both low_load headers with `utils/prepare_blflash_low_load.py`, using
`blflashcommand/venv/bin/python`. Use the existing corrected `bdb` workflow;
do not rewrite the Linux/OpenSBI/U-Boot whole image.

The flash source M0 must be vendor firmware, not the earlier Rust M0 probe.
Git changes do not alter firmware already on the board. Hardware acceptance
requires `D0 Rust OK` followed by the existing OpenSBI-to-U-Boot prompt path.
Readback SHA-256 proves storage integrity; it does not prove boot success.
