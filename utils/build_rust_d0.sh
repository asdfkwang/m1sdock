#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sdk_dir="$repo_dir/M1s_BL808_Linux_SDK"
cmake_bin="$sdk_dir/toolchain/cmake/bin/cmake"
build_dir="$repo_dir/firmware/build-d0"

"$cmake_bin" -S "$sdk_dir/bl_mcu_sdk_bl808" -B "$build_dir" \
    -DCHIP=bl808 -DCPU_ID=d0 -DBOARD=bl808_barebone \
    -DAPP_DIR=examples -DAPP=low_load -DBOOTROM=n \
    -DCONFIG_TOOLCHAIN="$sdk_dir/toolchain/elf_newlib_toolchain/bin/riscv64-unknown-elf-" \
    -DCONFIG_ROMAPI=n -DCONFIG_HALAPI=y -DCONFIG_DUALCORE=y \
    -DCONFIG_BUILD_TYPE=debug -DLOW_LOAD_RUST_D0=ON
"$cmake_bin" --build "$build_dir" --parallel "$(nproc)"
echo "D0 Rust probe: $build_dir/out/firmware.bin"
