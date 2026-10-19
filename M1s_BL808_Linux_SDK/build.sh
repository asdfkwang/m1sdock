#!/bin/bash
set -e

SHELL_DIR=$(cd "$(dirname "$0")"; pwd)
OUT_DIR=$SHELL_DIR/out

CMAKE=$SHELL_DIR/toolchain/cmake/bin/

LINUX_CROSS_PREFIX=$SHELL_DIR/toolchain/linux_toolchain/bin/riscv64-unknown-linux-gnu-
NEWLIB_ELF_CROSS_PREFIX=$SHELL_DIR/toolchain/elf_newlib_toolchain/bin/riscv64-unknown-elf-
OPENSBI_CROSS_PREFIX=riscv64-linux-gnu-
OPENSBI_BUILD_DIR=$SHELL_DIR/opensbi-0.6-808/build-system-gcc

BUILD_TARGET=$1

if [[ ! -e $OUT_DIR ]]; then
    mkdir $OUT_DIR
fi

build_linux()
{
    echo " "
    echo "================ build linux kernel ================"
    cd $SHELL_DIR/linux-5.10.4-808
    if [ ! -f .config ]; then
        cp c906.config .config
    fi
    make ARCH=riscv CROSS_COMPILE=$LINUX_CROSS_PREFIX Image -j$(nproc)
    echo " "
    echo "=========== high compression kernel image =========="
    lz4 -9 -f $SHELL_DIR/linux-5.10.4-808/arch/riscv/boot/Image $SHELL_DIR/linux-5.10.4-808/arch/riscv/boot/Image.lz4
    cp $SHELL_DIR/linux-5.10.4-808/arch/riscv/boot/Image.lz4 $OUT_DIR
}

build_linux_config()
{
    echo " "
    echo "============ build linux kernel config ============="
    cd $SHELL_DIR/linux-5.10.4-808
    make ARCH=riscv CROSS_COMPILE=$LINUX_CROSS_PREFIX menuconfig -j$(nproc)
}

build_opensbi(){
    echo " "
    echo "================== build opensbi ==================="
    cd $SHELL_DIR/opensbi-0.6-808
    make O="$OPENSBI_BUILD_DIR" PLATFORM=thead/c910 \
        CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" PLATFORM_RISCV_ISA=rv64gc \
        'platform-cflags-y=-Os -fno-asynchronous-unwind-tables -fno-unwind-tables' \
        -j"$(nproc)"

    local firmware="$OPENSBI_BUILD_DIR/platform/thead/c910/firmware/fw_jump.bin"
    local firmware_size
    firmware_size=$(stat -c %s "$firmware")
    # low_load/main.c copies only 0xC000 bytes of OpenSBI into RAM.
    if (( firmware_size > 49152 )); then
        echo "OpenSBI is $firmware_size bytes; the loader limit is 49152 bytes (48 KiB)." >&2
        return 1
    fi
    cp "$firmware" "$OUT_DIR/fw_jump.bin"
}

build_dtb()
{
    echo " "
    echo "==================== build dtb ====================="

    dtc -I dts -O dtb -o  $SHELL_DIR/bl808_dts/hw.dtb.5M $SHELL_DIR/bl808_dts/hw808c.dts
    cp $SHELL_DIR/bl808_dts/hw.dtb.5M $OUT_DIR

}

build_low_load()
{
    echo " "
    echo "============== build kernel low load ==============="
    cd $SHELL_DIR/bl_mcu_sdk_bl808/
    make CHIP=bl808 CPU_ID=m0 CMAKE_DIR=$CMAKE CROSS_COMPILE=$NEWLIB_ELF_CROSS_PREFIX SUPPORT_DUALCORE=y APP=low_load
    make CHIP=bl808 CPU_ID=d0 CMAKE_DIR=$CMAKE CROSS_COMPILE=$NEWLIB_ELF_CROSS_PREFIX SUPPORT_DUALCORE=y APP=low_load

    cp -f $SHELL_DIR/bl_mcu_sdk_bl808/out/examples/low_load/low_load_bl808_m0.bin  $OUT_DIR
    cp -f $SHELL_DIR/bl_mcu_sdk_bl808/out/examples/low_load/low_load_bl808_d0.bin  $OUT_DIR

}

build_clean_load()
{
    echo " "
    echo "============== build clean low load ==============="
    rm -rf $SHELL_DIR/bl_mcu_sdk_bl808/out/
    rm -rf $SHELL_DIR/bl_mcu_sdk_bl808/build/
}

build_whole_bin()
{
    echo " "
    echo "================ build whole bin =================="
    cd $OUT_DIR
    python3 merge_7_5Mbin.py
}

build_all()
{
    build_opensbi
    build_linux
    build_dtb
    build_low_load
    build_whole_bin
}

clean_all()
{
    echo " "
    echo "================ clean out ================"
    find ./out ! -name 'squashfs_test.img' ! -name 'merge_7_5Mbin.py' -type f -exec rm -f {} +
    echo " "
    echo "================ clean kernel ================"
    cd $SHELL_DIR/linux-5.10.4-808
    make ARCH=riscv CROSS_COMPILE=$LINUX_CROSS_PREFIX mrproper
    echo " "
    echo "================== clean opensbi ==================="
    cd $SHELL_DIR/opensbi-0.6-808
    make O="$OPENSBI_BUILD_DIR" PLATFORM=thead/c910 CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" distclean

}

case "$BUILD_TARGET" in
--help)
    TARGET="kernel|kernel_config|opensbi|dtb|low_load|clean_load|whole_bin|all"
    USAGE="usage $0 [$TARGET]"
    echo $USAGE
    exit 0
    ;;

kernel)
    build_linux
    ;;
kernel_config)
    build_linux_config
    ;;
opensbi)
    build_opensbi
    ;;
dtb)
    build_dtb
    ;;
low_load)
    build_low_load
    ;;
clean_load)
    build_clean_load
    ;;
whole_bin)
    build_whole_bin
    ;;
clean_all)
    clean_all
    ;;
all)
    build_all
    ;;
*)
    echo $USAGE
    exit 255
    ;;

esac

echo " "
echo "===================== build done ======================="
