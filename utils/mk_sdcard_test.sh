#!/usr/bin/env bash
# mk_sdcard_test.sh — prepare a microSD test card for the M1s Dock U-Boot MMC check.
#
# Usage:
#   bash utils/mk_sdcard_test.sh /dev/sdX [--yes] [--force]
#
# What it does:
#   1. Safety gates (WARNING: the WHOLE DEVICE is destroyed).
#   2. MBR partition table with a single FAT32 (type 0c) partition.
#   3. Copies two test files with mtools (NO mount needed).
#   4. Reads testfile back from the card and compares CRC-32
#      (the same CRC-32 algorithm U-Boot's `crc32` command prints).
#   5. Ejects cleanly (udisks power-off) or flushes buffers.
#   6. Saves a manifest for the console driver to /tmp/opencode/sdcard_manifest.txt.
#
# Requires: sfdisk, mkfs.vfat, mcopy/mtype/mdir (mtools), python3.
# Afterwards the card goes into the M1s Dock TF slot; the U-Boot-side check
# is `fatls mmc 0:1` / `load mmc 0:1 ...` / `crc32 ...` (see the script output).

set -euo pipefail

DEV=""
YES=0
FORCE=0

usage() {
    grep '^#' "$0" | sed -e 's/^# \{0,1\}//' | head -28
    exit 2
}

# crc_of FILE -> CRC32 hex (zlib.crc32 == U-Boot crc32 algorithm)
crc_of() {
    python3 -c 'import sys,zlib
data = open(sys.argv[1], "rb").read()
print("%08X" % (zlib.crc32(data) & 0xffffffff))' "$1"
}

hex_of() { printf '0x%X\n' "$1"; }

[[ $# -eq 0 ]] && usage
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes)   YES=1;   shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) usage ;;
        -*) echo "unknown option: $1" >&2; usage ;;
        *) [[ -z "$DEV" ]] && DEV="$1" || { echo "only one device allowed" >&2; usage; }; shift ;;
    esac
done
[[ -n "$DEV" ]] || usage

# sfdisk / mkfs.vfat live in /usr/sbin, which is absent from a plain user's PATH.
export PATH="$PATH:/usr/sbin:/sbin"

for tool in sfdisk mkfs.vfat mcopy mtype mdir python3; do
    command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: missing tool '$tool'" >&2; exit 1; }
done

SUDO="sudo"
[[ $(id -u) -eq 0 ]] && SUDO=""

# ---------------------------------------------------------------------------
# 1. safety gates
# ---------------------------------------------------------------------------
[[ -b "$DEV" ]] || { echo "ERROR: $DEV is not a block device" >&2; exit 1; }
BOX=$(basename "$DEV")
[[ "$BOX" =~ ^[a-z]+$ ]] || {
    echo "ERROR: pass the WHOLE device (e.g. /dev/sdd), not a partition ($DEV)" >&2
    exit 1
}

ROOT_SRC=$(findmnt -rn -o SOURCE / 2>/dev/null || true)
if [[ -n "$ROOT_SRC" && "$ROOT_SRC" == "$DEV"* ]]; then
    echo "ERROR: refusing to touch the running root filesystem on $DEV" >&2
    echo "this gate is not bypassable by --force" >&2
    exit 1
fi

REMOVABLE=$(cat "/sys/class/block/$BOX/removable" 2>/dev/null || echo 0)
if [[ "$REMOVABLE" != 1 && $FORCE -ne 1 ]]; then
    echo "ERROR: $DEV is not removable (removable=$REMOVABLE)" >&2
    echo "hint: pass --force only if you are 100% sure it is the USB SD reader" >&2
    exit 1
fi

TRAN=$(lsblk -dn -o TRAN "$DEV" 2>/dev/null || echo "?")
[[ "$TRAN" == "usb" ]] || echo "WARN: transport is '$TRAN' (expected usb for an SD reader)" >&2

# Unmount anything mounted from this device (udisks first, umount fallback).
for part in "$DEV" "$DEV"[0-9]*; do
    [[ -b "$part" ]] || continue
    while read -r tgt; do
        echo "unmounting $tgt ($part)"
        if command -v udisksctl >/dev/null 2>&1 && [[ $(id -u) -ne 0 ]]; then
            udisksctl unmount -b "$part" >/dev/null 2>&1 || $SUDO umount "$tgt" || true
        else
            $SUDO umount "$tgt" || true
        fi
    done < <(findmnt -rn -o TARGET,SOURCE 2>/dev/null | awk -v p="$part" '$2==p{print $1}')
done

SIZE=$(lsblk -dn -o SIZE "$DEV")
MODEL=$(lsblk -dn -o MODEL "$DEV")

# ---------------------------------------------------------------------------
# 2. confirm
# ---------------------------------------------------------------------------
if [[ $YES -ne 1 ]]; then
    echo "About to DESTROY the whole device:"
    echo "  device      : $DEV ($MODEL, $SIZE, removable=$REMOVABLE, transport=$TRAN)"
    echo "  layout      : MBR, one FAT32 partition, 2 test files"
    echo "Type YES to continue:" >&2
    read -r answer
    [[ "$answer" == "YES" ]] || { echo "aborted" >&2; exit 1; }
fi

# ---------------------------------------------------------------------------
# 3. partition table: MBR, one FAT32 (0c), start 2048 (1 MiB aligned)
# ---------------------------------------------------------------------------
$SUDO wipefs -af "$DEV" >/dev/null
$SUDO sfdisk "$DEV" <<'EOF'
label: dos
start=2048, type=0c, bootable
EOF
if command -v partprobe >/dev/null 2>&1; then
    $SUDO partprobe "$DEV" || true
else
    $SUDO blockdev --rereadpt "$DEV" || true
fi
sleep 1

P1="${DEV}1"
[[ -b "$P1" ]] || { echo "ERROR: partition node $P1 did not appear" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 4. FAT32 filesystem
# ---------------------------------------------------------------------------
$SUDO mkfs.vfat -F 32 -n M1STEST "$P1" >/dev/null

# ---------------------------------------------------------------------------
# 5. stage the test files in the current dir and copy with mtools (no mount)
# ---------------------------------------------------------------------------
printf 'M1s Dock SDHC test card\nmarker: m1sdock-uboot-mmc-test\n' > hello.txt
head -c $((128 * 1024)) /dev/urandom > testfile
HELLO_SIZE=$(stat -c %s hello.txt)
TEST_SIZE=$(stat -c %s testfile)
HELLO_CRC=$(crc_of hello.txt)
TEST_CRC=$(crc_of testfile)

$SUDO mcopy -i "$P1" hello.txt testfile ::/ >/dev/null
echo "files copied with mtools (no mount)"

# ---------------------------------------------------------------------------
# 6. read testfile back from the card and compare CRC-32
# ---------------------------------------------------------------------------
BACK_CRC=$($SUDO mtype -i "$P1" ::testfile 2>/dev/null | \
    python3 -c 'import sys,zlib
print("%08X" % (zlib.crc32(sys.stdin.buffer.read()) & 0xffffffff))')
[[ "$BACK_CRC" == "$TEST_CRC" ]] || {
    echo "ERROR: card readback CRC mismatch (back=$BACK_CRC src=$TEST_CRC)" >&2
    exit 1
}
echo "readback verify: CRC match ($BACK_CRC)"
rm -f hello.txt testfile

# ---------------------------------------------------------------------------
# 8. manifest + U-Boot command block (written BEFORE eject so (Ctrl+C at the
#    optional power-off prompt) can never swallow the results)
# ---------------------------------------------------------------------------
MANIFEST=${MANIFEST:-/tmp/opencode/sdcard_manifest.txt}
mkdir -p "$(dirname "$MANIFEST")"

REPORT=$(cat <<EOF
=== SD card test manifest ===
device      : $DEV ($MODEL, $SIZE)
partition   : $P1 (MBR, FAT32, label M1STEST)
write path  : mtools (no mount)
verify      : readback CRC match ($BACK_CRC)
files
  hello.txt : size=$HELLO_SIZE ($(hex_of "$HELLO_SIZE") bytes)
  testfile  : size=$TEST_SIZE ($(hex_of "$TEST_SIZE") bytes)
CRC-32
  hello.txt : $HELLO_CRC
  testfile  : $TEST_CRC

=== U-Boot expected output (boot chain already on flash) ===
=> mmc list
=> mmc dev 0
=> mmc rescan
=> mmc info                     # shows detected card size/bus width
=> fatls mmc 0:1                # must list hello.txt and testfile
=> load mmc 0:1 0x53000000 testfile
=> crc32 0x53000000 $(hex_of "$TEST_SIZE")
   expected CRC: $TEST_CRC      # must match the crc32 output for testfile
=> load mmc 0:1 0x53000000 hello.txt
=> md.b 0x53000000 $(hex_of "$HELLO_SIZE")
   expected: "M1s Dock SDHC test card..." text
EOF
)

echo "$REPORT"
echo "$REPORT" > "$MANIFEST"
echo "manifest saved: $MANIFEST"

# ---------------------------------------------------------------------------
# 9. card listing for the record, then eject
#    (eject is optional; --no-user-interaction means it fails cleanly instead
#     of blocking on a polkit password, e.g. power-off-drive-other-seat)
# ---------------------------------------------------------------------------
echo "--- card listing (mdir) ---"
$SUDO mdir -i "$P1" :: 2>/dev/null || true

if [[ $(id -u) -ne 0 ]] && command -v udisksctl >/dev/null 2>&1; then
    udisksctl power-off --no-user-interaction -b "$DEV" >/dev/null 2>&1 || \
        echo "(optional power-off skipped — no authorization; data is already committed, just pull the card)"
else
    $SUDO blockdev --flushbufs "$DEV" >/dev/null 2>&1 || true
    echo "buffers flushed; card can now be pulled"
fi
