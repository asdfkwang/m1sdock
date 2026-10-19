# bl808_linux

bl808 Linux

```bash
.
├── bl808_dts         # kernel dts file
├── bl_mcu_sdk_bl808  # bl_mcu_sdk for build low load bin
├── build.sh          # build script
├── linux-5.10.4-808  # linux kernel code
├── opensbi-0.6-808   # opensbi code
├── out               # bin file output dir
├── toolchain         # build need toolchain
└── README.md         # readme file
```

## Environment Setup

Ubuntu20.04 needs to use apt to install the package:

```bash
sudo apt install flex bison libncurses-dev device-tree-compiler lz4
```

Download toolchains

```bash
mkdir -p toolchain/cmake toolchain/elf_newlib_toolchain toolchain/linux_toolchain
curl https://cmake.org/files/v3.19/cmake-3.19.3-Linux-x86_64.tar.gz | tar xz -C toolchain/cmake/ --strip-components=1
curl https://occ-oss-prod.oss-cn-hangzhou.aliyuncs.com/resource//1663142243961/Xuantie-900-gcc-elf-newlib-x86_64-V2.6.1-20220906.tar.gz | tar xz -C toolchain/elf_newlib_toolchain/ --strip-components=1
curl https://occ-oss-prod.oss-cn-hangzhou.aliyuncs.com/resource//1663142514282/Xuantie-900-gcc-linux-5.10.4-glibc-x86_64-V2.6.1-20220906.tar.gz | tar xz -C toolchain/linux_toolchain/ --strip-components=1
```

## Compile

OpenSBI uses the system RISC-V GCC toolchain (`riscv64-linux-gnu-gcc`),
available on Debian via `sudo apt install gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu`.
It builds the vendor OpenSBI 0.6 with `rv64gc`, `lp64` and the default `-O2` into
`opensbi-0.6-808/build-system-gcc-1m`. OpenSBI runs at `0x53f00000` in a 1 MiB
PSRAM region reserved with `no-map` in the DTB. The build checks the binary,
ELF entry/load addresses, BSS and per-hart scratch/stack before updating
`out/fw_jump.bin`. This vendor version has no separate firmware heap.
The kernel and low_load continue to use the vendor toolchains above.

The whole image has a dedicated 1 MiB OpenSBI slot at relative offset
`0x780000` (D0 XIP `0x58800000`), outside the existing kernel and rootfs slots.
`utils/merge_linux_image.py` at the repository root validates the DT reservation
and all input sizes before producing the `0x880000`-byte whole image.
`out/merge_7_5Mbin.py` remains a compatibility entry point for this merger.
**Rebuild and update low_load (with regenerated boot headers), DTB and whole
image together. The old 48 KiB loader is incompatible with this layout.**

Step by step

```bash
./build.sh --help
./build.sh opensbi
./build.sh kernel_config
./build.sh kernel
./build.sh dtb
./build.sh low_load
./build.sh whole_bin
```

Or

```bash
./build.sh all
```

Then find the firmwares under out

```bash
├── fw_jump.bin
├── hw.dtb.5M
├── Image.lz4
├── squashfs_test.img 
├── low_load_bl808_d0.bin 
├── low_load_bl808_m0.bin 
├── merge_7_5Mbin.py
└── whole_img_linux.bin
```

## Download Firmware

- Get the latest version of DevCube from http://dev.bouffalolab.com/download
- Connect BL808 board with PC by USB cable
- Set BL808 board to programming mode
    + Press BOOT button
    + Press RESET button
    + Release RESET button
    + Release BOOT button
- Run DevCube, select [BL808], and switch to [MCU] page
- Select the uart port and set baudrate with 2000000
- M0 Group[Group0] Image Addr [0x58000000] [PATH to low_load_bl808_m0.bin]
- D0 Group[Group1] Image Addr [0x58000000] [PATH to low_load_bl808_d0.bin]
- Click 'Create & Download' and wait until it's done
- Switch to [IOT] page
- Enable 'Single Download', set Address with 0xD2000, choose [PATH to whole_image_linux.bin]
- Click 'Create & Download' again and wait until it's done

## Boot BL808 board

Press and release RESET button, E907 will output log by IO14(TX)/IO15(RX) and C906 by IO5(RX)/IO8(TX)
