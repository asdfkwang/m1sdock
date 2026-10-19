# Toolchain and Build

## Compiler

The SDK is pinned to the vendor (Xuantie) toolchain that ships with the repo;
the system gcc on this host is *not* used for `out/`:

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
| `out/whole_img_linux.bin` | 0x72E000 | DTB + OpenSBI + Image.lz4 + rootfs |

`out/examples/low_load/*` mirrors the same files (`.asm`, `.map` too).

## Rebuild

```bash
cd bl_mcu_sdk_bl808
make -j samples/low_load    # or your usual build invocation
```

Because `make` handles `bootinfo` regeneration only inside the *iot/cube* path,
remember to re-run the flash pipeline (Flashing → Path B) after any low_load
rebuild — the bootinfo `img_len_cnt` is only recomputed by that path.
