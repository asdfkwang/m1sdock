#!/bin/bash
set -e

SHELL_DIR=$(cd "$(dirname "$0")"; pwd)
OUT_DIR=$SHELL_DIR/out

CMAKE=$SHELL_DIR/toolchain/cmake/bin/

LINUX_CROSS_PREFIX=$SHELL_DIR/toolchain/linux_toolchain/bin/riscv64-unknown-linux-gnu-
NEWLIB_ELF_CROSS_PREFIX=$SHELL_DIR/toolchain/elf_newlib_toolchain/bin/riscv64-unknown-elf-
OPENSBI_CROSS_PREFIX=riscv64-linux-gnu-
OPENSBI_BUILD_DIR=$SHELL_DIR/opensbi-0.6-808/build-system-gcc-1m

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
        -j"$(nproc)"

    local firmware="$OPENSBI_BUILD_DIR/platform/thead/c910/firmware/fw_jump.bin"
    python3 -B "$SHELL_DIR/../utils/validate_vendor_opensbi.py" \
        --elf "${firmware%.bin}.elf" --bin "$firmware" \
        --cross-prefix "$OPENSBI_CROSS_PREFIX"
    cp "$firmware" "$OUT_DIR/fw_jump.bin"
}

build_opensbi_uart()
{
    echo "================ OpenSBI UART-only test ================"
    local source_dir="$SHELL_DIR/../opensbi"
    local build_dir="$source_dir/build/bl808-uart-test"
    mkdir -p "$build_dir"
    make -C "$source_dir" O="$build_dir" PLATFORM=generic \
        PLATFORM_DEFCONFIG=bl808_uart_test_defconfig \
        CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" \
        PLATFORM_RISCV_ISA=rv64gc PLATFORM_RISCV_ABI=lp64 \
        FW_TEXT_START=0x53f00000 FW_JUMP_ADDR=0x50000000 \
        FW_JUMP_FDT_ADDR=0x51ff8000 FW_DYNAMIC=n FW_PAYLOAD=n \
        -j"$(nproc)"

    local firmware="$build_dir/platform/generic/firmware/fw_jump.bin"
    local elf="${firmware%.bin}.elf"
    local size entry fw_end
    size=$(stat -c %s "$firmware")
    entry=$(LC_ALL=C "${OPENSBI_CROSS_PREFIX}readelf" -h "$elf" | awk '/Entry point address:/ {print $NF}')
    fw_end=$("${OPENSBI_CROSS_PREFIX}nm" --defined-only "$elf" | awk '$3 == "_fw_end" {print "0x" $1}')
    if [[ "$entry" != 0x53f00000 || -z "$fw_end" ]]; then
        echo "UART test ELF has an unexpected entry or missing _fw_end" >&2
        return 1
    fi
    # This test stops inside fw_platform_init(). Only fw_base.S's temporary
    # stack (2 * SBI_SCRATCH_SIZE = 8192) is used; no heap/hart setup runs.
    if (( size == 0 || size > 0x100000 || fw_end < 0x53f00000 || fw_end + 8192 > 0x54000000 )); then
        echo "UART test image/temporary stack exceeds the 1 MiB reservation" >&2
        return 1
    fi
    cp "$firmware" "$OUT_DIR/fw_jump_uart.bin"
    echo "UART-only image: $OUT_DIR/fw_jump_uart.bin ($size bytes; entry=$entry)"
    echo "Expected: OpenSBI BL808 UART OK, then WFI. No Linux boot."
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
    python3 -B "$SHELL_DIR/../utils/merge_linux_image.py" --out-dir "$OUT_DIR"
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
    TARGET="kernel|kernel_config|opensbi|opensbi_uart|dtb|low_load|clean_load|whole_bin|all"
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
opensbi_uart)
    build_opensbi_uart
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
