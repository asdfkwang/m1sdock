"""Load a bounded diagnostic into unused RAM and retain complete evidence."""
from pathlib import Path
import hashlib
import json
import re
import sys
import time
import zlib

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent / 'sdh-irq'))
from console import Console

run = root / '2026-10-20' / ('probe-' + time.strftime('%H%M%S'))
run.mkdir(parents=True)
c = Console(run / 'transcript.txt')
try:
    print(c.command('version'), flush=True)
    info = c.command('bdinfo')
    print(info, flush=True)
    reservations = re.findall(r'reserved\[\d+\]\s*\[0x([0-9a-f]+)-0x([0-9a-f]+)\]', info)
    for start, end in ((0x50100000, 0x50110000), (0x51200000, 0x51280000)):
        if not reservations or any(int(lo, 16) < end and int(hi, 16) >= start for lo, hi in reservations):
            raise RuntimeError('Test area intersects a reservation or map unavailable')
    print(c.command('mw.b 0x50100000 0 0x10000'), flush=True)
    for name in ('soc_probe.c', 'probes.S', 'ram.ld', 'Makefile'):
        (run / name).write_bytes((root / name).read_bytes())
    (run / 'irq_entry.S').write_bytes((root.parent / 'sdh-irq/irq_entry.S').read_bytes())
    image = (root / 'build/soc_probe.srec').read_bytes()
    (run / 'soc_probe.srec').write_bytes(image)
    (run / 'image-sha256.txt').write_text(hashlib.sha256(image).hexdigest() + '  soc_probe.srec\n')
    c.log.write('\n>>> loads\n')
    c.port.write(b'loads\r')
    print(c.receive(b'Ready for S-Record'), flush=True)
    binary = bytearray()
    for line in image.splitlines():
        if line.startswith(b'S3'):
            raw = bytes.fromhex(line[2:].decode())
            assert sum(raw) & 255 == 255
            offset = int.from_bytes(raw[1:5], 'big') - 0x50100000
            payload = raw[5:-1]
            assert 0 <= offset and offset + len(payload) < 0x10000
            binary.extend(b'\0' * max(0, offset + len(payload) - len(binary)))
            binary[offset:offset + len(payload)] = payload
        c.port.write(line + b'\r\n')
        c.port.flush()
        time.sleep(0.003)
    print(c.receive(timeout=10), flush=True)
    output = c.command(f'crc32 0x50100000 0x{len(binary):x}')
    print(output, flush=True)
    match = re.search(r'==>\s*([0-9a-fA-F]{8})', output)
    if not match or int(match[1], 16) != zlib.crc32(binary):
        raise RuntimeError('RAM upload CRC mismatch; not executing')
    output = c.command('go 0x50100000', timeout=15)
    print(output, flush=True)
    (run / 'output.txt').write_text(output)
    print(c.command('version'), flush=True)
    print('Evidence:', run, flush=True)
finally:
    c.close()
