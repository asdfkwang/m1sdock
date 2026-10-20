"""Upload the freestanding diagnostic with S-records, then execute in RAM."""
from pathlib import Path
import hashlib
import json
import re
import time
import zlib
from console import Console

root = Path(__file__).resolve().parent
run = root / '2026-10-20' / ('ram-' + time.strftime('%H%M%S'))
run.mkdir()
console = Console(run / 'transcript.txt')

def snapshot():
    addresses = [(0x2006002c, 'w'), (0x20060029, 'b'), (0x20060028, 'b'),
                 (0x2006002e, 'b'), (0x2006000c, 'w'), (0x20060008, 'l'),
                 (0x20060034, 'l'), (0x20060038, 'l'),
                 (0x20000058, 'l'), (0x2000005c, 'l'), (0xe0000144, 'l'),
                 (0xe0200000, 'l'), (0xe0201000, 'l')]
    addresses += [(a, 'l') for a in (0xe0002000, 0xe0002004, 0xe0002008,
                                    0xe0002080, 0xe0002084, 0xe0002088)]
    addresses += [(0x200008c4 + 4 * i, 'l') for i in range(6)]
    return {hex(a): console.read(a, width) for a, width in addresses}

try:
    print(console.command('version'), flush=True)
    info = console.command('bdinfo')
    print(info, flush=True)
    print(console.command('md.l 0x200008c4 6'), flush=True)
    print(console.command('md.l 0x20060024 0x10'), flush=True)
    # Current U-Boot reserves RAM from 0x52a76000 upwards. Keep this test
    # in 0x50100000..0x50110000 and verify that the reservations still allow it.
    reservations = re.findall(r'reserved\[\d+\]\s*\[0x([0-9a-f]+)-0x([0-9a-f]+)\]', info)
    if not reservations or any(int(lo, 16) < 0x50110000 and int(hi, 16) >= 0x50100000 for lo, hi in reservations):
        raise RuntimeError('Cannot establish an unreserved upload region')
    before = snapshot()
    (run / 'before.json').write_text(json.dumps(before, indent=2))
    # S-records omit alignment gaps. Define their bytes before whole-image CRC.
    print(console.command('mw.b 0x50100000 0 0x10000'), flush=True)
    for name in ('build/irq_probe.srec', 'build/irq_probe.elf'):
        (run / Path(name).name).write_bytes((root / name).read_bytes())
    (run / 'source').mkdir()
    for name in ('irq_probe.c', 'irq_entry.S', 'ram.ld', 'Makefile'):
        (run / 'source' / name).write_bytes((root / name).read_bytes())
    (run / 'image-sha256.txt').write_text('\n'.join(
        hashlib.sha256((root / name).read_bytes()).hexdigest() + '  ' + Path(name).name
        for name in ('build/irq_probe.srec', 'build/irq_probe.elf')) + '\n')
    console.log.write('\n>>> loads\n')
    console.port.write(b'loads\r')
    print(console.receive(b'Ready for S-Record', timeout=5), flush=True)
    records = (root / 'build/irq_probe.srec').read_bytes().splitlines()
    for record in records:
        console.port.write(record + b'\r\n')
        console.port.flush()
        time.sleep(0.003)
    print(console.receive(timeout=10), flush=True)
    binary = bytearray()
    for record in records:
        if record.startswith(b'S3'):
            raw = bytes.fromhex(record[2:].decode())
            address = int.from_bytes(raw[1:5], 'big')
            payload = raw[5:-1]
            assert sum(raw) & 255 == 255
            offset = address - 0x50100000
            assert 0 <= offset and offset + len(payload) < 0x10000
            if len(binary) < offset + len(payload):
                binary.extend(b'\0' * (offset + len(payload) - len(binary)))
            binary[offset:offset + len(payload)] = payload
    expected = zlib.crc32(binary)
    result = console.command(f'crc32 0x50100000 0x{len(binary):x}')
    print(result, flush=True)
    observed = re.search(r'==>\s*([0-9a-fA-F]{8})', result)
    if not observed or int(observed[1], 16) != expected:
        raise RuntimeError(f'Upload CRC mismatch; expected {expected:08x}')
    result = console.command('go 0x50100000', timeout=15)
    print(result, flush=True)
    after = snapshot()
    (run / 'after.json').write_text(json.dumps(after, indent=2))
    changed = {}
    for addr, old in before.items():
        # Ignore read-only clock-stable and GPIO input-level bits.
        mask = 0xfffd if addr == '0x2006002c' else (0xefffffff if 0x200008c4 <= int(addr, 16) < 0x200008dc else 0xffffffff)
        if (old & mask) != (after[addr] & mask):
            changed[addr] = [old, after[addr]]
    summary = {
        'forced_irq_handler_pass': 'PASS: actual S-mode external trap' in result,
        'cmd8_card_and_irq_pass': 'PASS: real CMD8 R7=0x1aa' in result,
        'uboot_returned_zero': 'Application terminated, rc = 0x0' in result,
        'configuration_restored': not changed,
        'configuration_differences': changed,
    }
    (run / 'result.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    print(console.command('version'), flush=True)
    print('Transcript:', run / 'transcript.txt', flush=True)
    if not all(summary[k] for k in ('forced_irq_handler_pass', 'cmd8_card_and_irq_pass',
                                    'uboot_returned_zero', 'configuration_restored')):
        raise RuntimeError('Diagnostic failed; see result.json and transcript')
finally:
    console.close()
