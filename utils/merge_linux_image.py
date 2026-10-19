#!/usr/bin/env python3
"""Build the BL808 Linux whole image with a separate 1 MiB OpenSBI slot."""
import argparse
from pathlib import Path
import struct
import subprocess

FLASH_SIZE = 0x1000000
WHOLE_FLASH_OFFSET = 0xD2000
WHOLE_SIZE = 0x880000
DTB_OFFSET = 0
DTB_SIZE = 0x10000
KERNEL_HEADER_OFFSET = 0x1FFF8
KERNEL_OFFSET = 0x20000
KERNEL_RAM = 0x50000000
ROOTFS_OFFSET = 0x480000
ROOTFS_SIZE = 0x280000  # Match the DT rootfs partition.
OPENSBI_OFFSET = 0x780000
OPENSBI_SIZE = 0x100000
OPENSBI_RAM = 0x53F00000


def validate_dtb(path):
    node = '/reserved-memory/opensbi@53f00000'
    result = subprocess.run(['fdtget', '-t', 'x', str(path), node, 'reg'],
                            check=True, capture_output=True, text=True)
    if [int(cell, 16) for cell in result.stdout.split()] != [0, OPENSBI_RAM, 0, OPENSBI_SIZE]:
        raise ValueError('DTB does not reserve the 1 MiB OpenSBI RAM region')
    subprocess.run(['fdtget', str(path), node, 'no-map'],
                   check=True, capture_output=True, text=True)


def build_image(out_dir):
    regions = [
        ('hw.dtb.5M', DTB_OFFSET, DTB_SIZE),
        ('Image.lz4', KERNEL_OFFSET, ROOTFS_OFFSET - KERNEL_OFFSET),
        ('squashfs_test.img', ROOTFS_OFFSET, ROOTFS_SIZE),
        ('fw_jump.bin', OPENSBI_OFFSET, OPENSBI_SIZE),
    ]
    if WHOLE_FLASH_OFFSET + WHOLE_SIZE > FLASH_SIZE:
        raise ValueError('Whole image exceeds the 16 MiB flash')
    validate_dtb(out_dir / 'hw.dtb.5M')

    # Validate every input and reserved range before touching the output file.
    occupied = [(KERNEL_HEADER_OFFSET, KERNEL_OFFSET, 'kernel header')]
    contents = []
    for name, offset, capacity in regions:
        data = (out_dir / name).read_bytes()
        if not 0 < len(data) <= capacity:
            raise ValueError(f'{name}: {len(data)} bytes; allowed 1..{capacity}')
        end = offset + capacity
        if offset < 0 or end > WHOLE_SIZE:
            raise ValueError(f'{name}: slot outside whole image')
        for start, stop, other in occupied:
            if offset < stop and start < end:
                raise ValueError(f'{name}: slot overlaps {other}')
        occupied.append((offset, end, name))
        contents.append((name, offset, data))

    image = bytearray(b'\xff') * WHOLE_SIZE
    for name, offset, data in contents:
        image[offset:offset + len(data)] = data
        print(f'{name}: {len(data)} bytes at whole +{offset:#x}')
    kernel_size = len(contents[1][2])
    struct.pack_into('<II', image, KERNEL_HEADER_OFFSET, KERNEL_RAM, kernel_size)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        image = build_image(args.out_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Whole image validation failed: {error}\n')
    target = args.out_dir / 'whole_img_linux.bin'
    target.write_bytes(image)
    print(f'{target}: {len(image)} bytes, flash at {WHOLE_FLASH_OFFSET:#x}')


if __name__ == '__main__':
    main()
