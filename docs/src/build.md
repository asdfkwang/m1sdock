# Toolchain and Build

## Compiler

OpenSBI uses the system `riscv64-linux-gnu-gcc` and binutils from `PATH`.
Install them on Debian with `sudo apt install gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu`,
then run `./build.sh opensbi` from `M1s_BL808_Linux_SDK`.
The vendor OpenSBI 0.6 build uses `rv64gc`, the existing `lp64` ABI and the
Makefile's default `-O2`, without the previous size/unwind overrides.
Objects go into `opensbi-0.6-808/build-system-gcc-1m` to separate this layout
from previous builds. It links at `0x53f00000`, in the top 1 MiB of PSRAM.
The DTB reserves this region with `no-map`, leaving 63 MiB for Linux.
`utils/validate_vendor_opensbi.py` checks the binary size and ELF load bytes,
entry, BSS and per-hart scratch/stack against the reservation before copying
to `out/fw_jump.bin`. Hart count and stack size are read from the linked
platform descriptor. OpenSBI 0.6 has no separately allocated firmware heap.

`utils/merge_linux_image.py` reserves 1 MiB of flash for OpenSBI at whole-image
offset `0x780000`, preserving kernel/header/rootfs offsets. It validates the
DT reservation and rejects empty, oversized or overlapping inputs before
overwriting the existing whole image. The old `out/merge_7_5Mbin.py` command
forwards to this script. Install `device-tree-compiler` for `dtc` and `fdtget`.

The user confirmed successful hardware boot with the new 1 MiB PSRAM layout
and vendor OpenSBI built with system GCC at `-O2` on 2026-10-19.
**Update regenerated low_load headers/bodies and the new whole image together;
the old loader cannot boot firmware using the new addresses.**

The kernel and low_load still use the bundled vendor (Xuantie) toolchains.
For low_load:

```
$ tc=/…/M1s_BL808_Linux_SDK/toolchain/elf_newlib_toolchain/bin/riscv64-unknown-elf-gcc
$ $tc --version
riscv64-unknown-elf-gcc (Xuantie-900 elf newlib gcc Toolchain V2.6.1 B-20220906) 10.2.0
```

Evidence in the built ELF (macro dump):

```
__GNUC__ 10
__riscv_zvamo 7000
__WCHAR_T__ 4
```

CMake cache (`build/CMakeCache.txt`) confirms the toolchain file:

```
CMAKE_TOOLCHAIN_FILE=…/tools/cmake/riscv64-unknown-elf-gcc.cmake
CONFIG_TOOLCHAIN=…/toolchain/elf_newlib_toolchain/bin/riscv64-unknown-elf-
```

## Build output

`bl_mcu_sdk_bl808/build` runs the vendor build; the "out" directory holds the
flash-ready artifacts:

| File | Size | Notes |
|---|---|---|
| `out/low_load_bl808_m0.bin` | 38 116 | XIP body expected at flash 0x002000 |
| `out/low_load_bl808_d0.bin` | 29 196 | XIP body expected at flash 0x052000 |
| `out/low_load_bl808_{m0,d0}.elf` | ~2.5 MB | ELF32 (rv32) for m0, rv64-ish for d0 |
| `out/whole_img_linux.bin` | 0x880000 | DTB + Image.lz4 + rootfs + 1 MiB OpenSBI slot |

`out/examples/low_load/*` mirrors the same files (`.asm`, `.map` too).

## Rebuild

```bash
cd bl_mcu_sdk_bl808
make -j samples/low_load    # or your usual build invocation
```

For a matching set of artifacts from `M1s_BL808_Linux_SDK`:

```bash
./build.sh opensbi
./build.sh dtb
./build.sh low_load
./build.sh whole_bin
```

Before flashing rebuilt low_load, regenerate its headers with
`blflashcommand/venv/bin/python -B utils/prepare_blflash_low_load.py` from the
repository root. This validates lengths, hashes, header CRCs and the entire
flash configuration table, including JEDEC ID `ef4018`.

Hardware-free regression checks for the layout and ELF validator:

```bash
python3 -B utils/test_linux_image.py
```
