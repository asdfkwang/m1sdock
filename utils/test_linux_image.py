#!/usr/bin/env python3
"""Hardware-free layout and vendor ELF checks; requires RISC-V binutils and dtc."""
import contextlib
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import merge_linux_image as layout
from validate_vendor_opensbi import validate

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o',
                        str(self.out / 'hw.dtb.5M'),
                        str(ROOT / 'M1s_BL808_Linux_SDK/bl808_dts/hw808c.dts')], check=True)
        for name, data in [('Image.lz4', b'kernel'), ('squashfs_test.img', b'rootfs'),
                           ('fw_jump.bin', b'firmware')]:
            (self.out / name).write_bytes(data)

    def build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return layout.build_image(self.out)

    def test_new_slot_and_unchanged_kernel_rootfs_header(self):
        image = self.build()
        self.assertEqual(len(image), 0x880000)
        self.assertLessEqual(0xD2000 + len(image), 0x1000000)
        self.assertEqual(image[0x780000:0x780008], b'firmware')
        self.assertEqual(image[0x20000:0x20006], b'kernel')
        self.assertEqual(image[0x480000:0x480006], b'rootfs')
        self.assertEqual(struct.unpack_from('<II', image, 0x1FFF8), (0x50000000, 6))
        self.assertEqual(image[0x10000:0x1FFF8], b'\xff' * 0xFFF8)
        # D0 maps physical flash 0x52000 to XIP 0x58000000.
        self.assertEqual(0x58000000 + 0xD2000 + layout.OPENSBI_OFFSET - 0x52000,
                         0x58800000)

    def test_firmware_flash_slot_boundary(self):
        (self.out / 'fw_jump.bin').write_bytes(b'F' * 0x100000)
        self.assertEqual(self.build()[0x780000:0x880000], b'F' * 0x100000)
        (self.out / 'fw_jump.bin').write_bytes(b'F' * 0x100001)
        with self.assertRaises(ValueError):
            self.build()

    def test_input_slot_boundaries(self):
        for name, limit in [('hw.dtb.5M', 0x10000), ('Image.lz4', 0x460000),
                            ('squashfs_test.img', 0x280000)]:
            with self.subTest(name=name):
                path = self.out / name
                original = path.read_bytes()
                # Pad the valid DTB rather than replacing it with arbitrary bytes.
                path.write_bytes(original + b'X' * (limit - len(original)))
                self.build()
                with path.open('ab') as stream:
                    stream.write(b'X')
                with self.assertRaises(ValueError):
                    self.build()
                path.write_bytes(original)

    def test_missing_ram_reservation_or_no_map(self):
        path = self.out / 'hw.dtb.5M'
        original = path.read_bytes()
        node = '/reserved-memory/opensbi@53f00000'
        for prop in ('no-map', 'reg'):
            path.write_bytes(original)
            subprocess.run(['fdtput', '-d', str(path), node, prop], check=True)
            with self.assertRaises(subprocess.CalledProcessError):
                self.build()

    def test_invalid_input_preserves_existing_whole(self):
        target = self.out / 'whole_img_linux.bin'
        target.write_bytes(b'previous image')
        (self.out / 'fw_jump.bin').write_bytes(b'X' * 0x100001)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'utils/merge_linux_image.py'),
                                 '--out-dir', str(self.out)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b'previous image')


class VendorElfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.elf = self.out / 'fw.elf'
        self.binary = self.out / 'fw.bin'

    def fixture(self, fw_end=0x53F01000, stack=8192, bss=16, base=0x53F00000):
        source = self.out / 'fw.S'
        source.write_text(f'''.section .text
.global _start
_start: nop
.section .rodata
.global platform
platform:
.long 6
.space 76
.long 1
.long {stack}
.section .bss
.space {bss}
''')
        script = self.out / 'fw.ld'
        script.write_text(f'''ENTRY(_start)
PHDRS {{ firmware PT_LOAD FLAGS(7); }}
SECTIONS {{
 . = {base}; _fw_start = .;
 .text : {{ *(.text) }} :firmware
 .rodata : {{ *(.rodata) }} :firmware
 .bss (NOLOAD) : {{ *(.bss) }} :firmware
 _fw_end = {fw_end};
}}
''')
        subprocess.run(['riscv64-linux-gnu-as', '-march=rv64gc', '-o',
                        str(self.out / 'fw.o'), str(source)], check=True)
        subprocess.run(['riscv64-linux-gnu-ld', '--no-warn-rwx-segments', '-T', str(script),
                        '-o', str(self.elf), str(self.out / 'fw.o')], check=True)
        subprocess.run(['riscv64-linux-gnu-objcopy', '-O', 'binary', str(self.elf),
                        str(self.binary)], check=True)

    def test_runtime_exactly_fits_and_stack_overflows(self):
        self.fixture(fw_end=0x53FFE000)
        self.assertEqual(validate(self.elf, self.binary)[1], 0x100000)
        self.fixture(fw_end=0x53FFE000, stack=8208)
        with self.assertRaisesRegex(ValueError, 'scratch/stack'):
            validate(self.elf, self.binary)

    def test_bss_cannot_extend_past_reservation(self):
        self.fixture(bss=0x100000)
        with self.assertRaisesRegex(ValueError, 'segment/BSS'):
            validate(self.elf, self.binary)

    def test_old_execution_address_is_rejected(self):
        self.fixture(base=0x3EFF0000)
        with self.assertRaisesRegex(ValueError, 'ELF entry'):
            validate(self.elf, self.binary)

    def test_truncated_or_corrupted_binary_is_rejected(self):
        self.fixture()
        original = self.binary.read_bytes()
        for data in (original[:-1], bytes([original[0] ^ 1]) + original[1:]):
            self.binary.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'ELF load bytes'):
                validate(self.elf, self.binary)


if __name__ == '__main__':
    unittest.main()
