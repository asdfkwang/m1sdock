#!/usr/bin/env python3
"""Validate OpenSBI 0.6 ELF, loaded bytes, BSS and per-hart scratch/stack."""
import argparse
from pathlib import Path
import struct
import subprocess

from merge_linux_image import OPENSBI_RAM, OPENSBI_SIZE


def validate(elf_path, bin_path, cross_prefix='riscv64-linux-gnu-'):
    firmware = bin_path.read_bytes()
    if not 0 < len(firmware) <= OPENSBI_SIZE:
        raise ValueError(f'Binary size {len(firmware)} exceeds the 1 MiB slot or is empty')
    elf = elf_path.read_bytes()
    if elf[:7] != b'\x7fELF\x02\x01\x01' or struct.unpack_from('<H', elf, 18)[0] != 243:
        raise ValueError('Expected a little-endian RISC-V ELF64')
    entry, phoff = struct.unpack_from('<QQ', elf, 24)
    phsize, phcount = struct.unpack_from('<HH', elf, 54)
    if entry != OPENSBI_RAM or phsize != 56:
        raise ValueError(f'Unexpected ELF entry {entry:#x} or program header size')
    ram_end = OPENSBI_RAM + OPENSBI_SIZE
    segments = []
    for index in range(phcount):
        kind, flags, offset, address, physical, filesz, memsz, align = struct.unpack_from(
            '<IIQQQQQQ', elf, phoff + index * phsize)
        if kind != 1 or not memsz:  # PT_LOAD
            continue
        if not OPENSBI_RAM <= address < address + memsz <= ram_end:
            raise ValueError('ELF load segment/BSS exceeds reserved OpenSBI RAM')
        if physical != address or filesz > memsz or offset + filesz > len(elf):
            raise ValueError('Invalid ELF load segment')
        relative = address - OPENSBI_RAM
        if firmware[relative:relative + filesz] != elf[offset:offset + filesz]:
            raise ValueError('Binary does not contain all ELF load bytes at the expected addresses')
        segments.append((address, offset, filesz, memsz))
    if not segments:
        raise ValueError('ELF has no load segments')

    result = subprocess.run([cross_prefix + 'nm', '--defined-only', str(elf_path)],
                            check=True, capture_output=True, text=True)
    symbols = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    if symbols.get('_fw_start') != OPENSBI_RAM or '_fw_end' not in symbols:
        raise ValueError('Missing or unexpected firmware boundary symbols')
    platform = symbols.get('platform')
    if platform is None:
        raise ValueError('Missing OpenSBI 0.6 platform descriptor')

    # Read the linked descriptor, rather than duplicating platform.h constants.
    # OpenSBI 0.6 packs hart_count and hart_stack_size at 0x50/0x54.
    for address, offset, filesz, _ in segments:
        relative = platform + 0x50 - address
        if 0 <= relative and relative + 8 <= filesz:
            harts, stack = struct.unpack_from('<II', elf, offset + relative)
            break
    else:
        raise ValueError('Platform descriptor is not backed by loaded ELF data')
    if not harts or stack < 4096 or stack % 16:
        raise ValueError('Invalid hart count or scratch/stack size')
    fw_end = symbols['_fw_end']
    if fw_end < max(address + memsz for address, _, _, memsz in segments):
        raise ValueError('_fw_end does not cover all ELF load segments/BSS')
    # This vendor release has no separately allocated firmware heap. Its
    # fw_base.S allocates scratch within each hart's stack above _fw_end.
    runtime_end = fw_end + harts * stack
    if runtime_end > ram_end:
        raise ValueError(f'BSS plus scratch/stack ends at {runtime_end:#x}, beyond {ram_end:#x}')
    return len(firmware), runtime_end - OPENSBI_RAM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--bin', type=Path, required=True)
    parser.add_argument('--cross-prefix', default='riscv64-linux-gnu-')
    args = parser.parse_args()
    try:
        size, runtime = validate(args.elf, args.bin, args.cross_prefix)
    except (OSError, ValueError, struct.error, subprocess.CalledProcessError) as error:
        parser.exit(1, f'OpenSBI validation failed: {error}\n')
    print(f'OpenSBI validated: entry={OPENSBI_RAM:#x}, binary={size} bytes, '
          f'runtime including BSS/scratch/stack={runtime}/{OPENSBI_SIZE} bytes (heap=0)')


if __name__ == '__main__':
    main()
