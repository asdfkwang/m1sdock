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

build_uboot_generic()
{
    local source_dir="$SHELL_DIR/../opensbi"
    local build_dir="$source_dir/build/bl808-generic"
    local stage="$OUT_DIR/uboot_generic"
    make -C "$source_dir" O="$build_dir" PLATFORM=generic \
        PLATFORM_DEFCONFIG=bl808_defconfig CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" \
        PLATFORM_RISCV_ISA=rv64gc PLATFORM_RISCV_ABI=lp64 \
        FW_TEXT_START=0x53f00000 FW_JUMP_ADDR=0x50000000 \
        FW_JUMP_FDT_ADDR=0x51ff8000 FW_DYNAMIC=n FW_PAYLOAD=n -j"$(nproc)"
    local firmware="$build_dir/platform/generic/firmware/fw_jump.bin"
    local fw_end entry
    entry=$(LC_ALL=C "${OPENSBI_CROSS_PREFIX}readelf" -h "${firmware%.bin}.elf" | awk '/Entry point address:/ {print $NF}')
    fw_end=$("${OPENSBI_CROSS_PREFIX}nm" --defined-only "${firmware%.bin}.elf" | awk '$3 == "_fw_end" {print "0x" $1}')
    [[ "$entry" == 0x53f00000 && -n "$fw_end" ]]
    # The DT below specifies one hart and a 64 KiB heap; reserve its 8 KiB stack.
    (( fw_end >= 0x53f00000 && fw_end + 8192 + 65536 <= 0x54000000 ))
    (( $(stat -c %s "$firmware") > 0 && $(stat -c %s "$firmware") <= 0x100000 ))
    grep -qx '# CONFIG_FDT_SERIAL is not set' "$build_dir/platform/generic/kconfig/.config"
    grep -qx '# CONFIG_PLATFORM_BL808_UART_TEST is not set' "$build_dir/platform/generic/kconfig/.config"
    mkdir -p "$stage"
    cp "$OUT_DIR/uboot/hw.dtb.5M" "$stage/hw.dtb.5M"
    fdtput -p -t s "$stage/hw.dtb.5M" /chosen/opensbi-config compatible opensbi,config
    fdtput -t x "$stage/hw.dtb.5M" /chosen/opensbi-config heap-size 10000
    cp "$OUT_DIR/uboot/Image.lz4" "$OUT_DIR/uboot/squashfs_test.img" "$stage/"
    cp "$firmware" "$stage/fw_jump.bin"
    cp "$firmware" "$OUT_DIR/fw_jump_generic.bin"
    python3 -B "$SHELL_DIR/../utils/merge_linux_image.py" --out-dir "$stage"
    cp "$stage/whole_img_linux.bin" "$OUT_DIR/whole_img_uboot_generic.bin"
    echo "Generic OpenSBI (console disabled) -> S-mode U-Boot: $OUT_DIR/whole_img_uboot_generic.bin"
}

build_dtb()
{
    echo " "
    echo "==================== build dtb ====================="

    dtc -I dts -O dtb -o  $SHELL_DIR/bl808_dts/hw.dtb.5M $SHELL_DIR/bl808_dts/hw808c.dts
    cp $SHELL_DIR/bl808_dts/hw.dtb.5M $OUT_DIR

}

build_uboot()
{
    local source_dir="$SHELL_DIR/../u-boot"
    local build_dir="$source_dir/build/m1s-d0"
    local stage="$OUT_DIR/uboot"
    make -C "$source_dir" O="$build_dir" CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" m1s_d0_defconfig
    make -C "$source_dir" O="$build_dir" CROSS_COMPILE="$OPENSBI_CROSS_PREFIX" -j"$(nproc)"
    grep -qx 'CONFIG_RISCV_SMODE=y' "$build_dir/.config"
    # Use the proven vendor runtime first; keep the latest UART-only test intact.
    build_opensbi
    mkdir -p "$stage"
    cp "$build_dir/u-boot.bin" "$OUT_DIR/u-boot.bin"
    cp "$build_dir/arch/riscv/dts/bl808-d0-m1s.dtb" "$stage/hw.dtb.5M"
    cp "$OUT_DIR/fw_jump.bin" "$stage/fw_jump.bin"
    cp "$OUT_DIR/squashfs_test.img" "$stage/squashfs_test.img"
    # low_load already expands this slot at 0x50000000, the U-Boot entry.
    lz4 -9 -f "$build_dir/u-boot.bin" "$stage/Image.lz4"
    python3 -B "$SHELL_DIR/../utils/merge_linux_image.py" --out-dir "$stage"
    cp "$stage/whole_img_linux.bin" "$OUT_DIR/whole_img_uboot.bin"
    echo "S-mode U-Boot image: $OUT_DIR/whole_img_uboot.bin (flash at 0xD2000)"
    echo "Vendor Linux whole image and latest UART-only test are preserved."
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
    TARGET="kernel|kernel_config|opensbi|opensbi_uart|uboot|uboot_generic|dtb|low_load|clean_load|whole_bin|all"
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
uboot)
    build_uboot
    ;;
uboot_generic)
    build_uboot_generic
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
