"""Read existing SD test files through U-Boot; never write the card."""
from pathlib import Path
import json
import re
import time
from console import Console

root = Path(__file__).resolve().parent
run = root / '2026-10-20' / ('files-' + time.strftime('%H%M%S'))
run.mkdir()
manifest = Path('/tmp/opencode/sdcard_manifest.txt')
if not manifest.is_file():
    raise SystemExit('Original SD test manifest is required')
text = manifest.read_text()
(run / 'sdcard_manifest.txt').write_text(text)
expected = {}
for name in ('testfile', 'hello.txt'):
    size = re.search(rf'^\s*{re.escape(name)}\s*:\s*size=(\d+)', text, re.M)
    crc = re.search(rf'^\s*{re.escape(name)}\s*:\s*([0-9A-Fa-f]{{8}})\s*$', text, re.M)
    if not size or not crc:
        raise SystemExit('Incomplete manifest: ' + name)
    expected[name] = {'size': int(size[1]), 'crc': int(crc[1], 16)}

c = Console(run / 'transcript.txt')
saved_gpio = []
results = []
try:
    print(c.command('version'), flush=True)
    info = c.command('bdinfo')
    ranges = re.findall(r'reserved\[\d+\]\s*\[0x([0-9a-f]+)-0x([0-9a-f]+)\]', info)
    # Unlike the old manifest's 0x53000000, these buffers do not overlap U-Boot.
    if not ranges or any(int(lo, 16) < 0x51050000 and int(hi, 16) >= 0x51000000 for lo, hi in ranges):
        raise RuntimeError('Cannot establish safe file buffers')
    for i in range(6): saved_gpio.append(c.read(0x200008c4 + 4 * i))
    (run / 'original-gpio.json').write_text(json.dumps(saved_gpio))
    for i, old in enumerate(saved_gpio):
        c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{(old & ~0xc0001fff) | 0x17:x}')
    print(c.command('mmc rescan', timeout=20), flush=True)
    info = c.command('mmc info', timeout=20)
    print(info, flush=True)
    if 'Capacity: 59.7 GiB' not in info or 'Bus Width: 4-bit' not in info:
        raise RuntimeError('Expected test card was not identified')
    print(c.command('mmc part'), flush=True)
    print(c.command('fatls mmc 0:1'), flush=True)
    for iteration in (1, 2):
        for name, address in (('testfile', 0x51000000), ('hello.txt', 0x51040000)):
            exp = expected[name]
            c.command(f'mw.b 0x{address:x} 0xa5 0x{exp["size"]:x}')
            output = c.command(f'load mmc 0:1 0x{address:x} {name}', timeout=20)
            print(output, flush=True)
            if not re.search(rf'\b{exp["size"]} bytes read\b', output):
                raise RuntimeError('File load did not report exact expected size: ' + name)
            size_output = c.command('printenv filesize')
            print(size_output, flush=True)
            match = re.search(r'filesize=([0-9a-fA-F]+)', size_output)
            if not match or int(match[1], 16) != exp['size']:
                raise RuntimeError('U-Boot filesize mismatch')
            output = c.command(f'crc32 0x{address:x} 0x{exp["size"]:x}')
            print(output, flush=True)
            match = re.search(r'==>\s*([0-9a-fA-F]{8})', output)
            if not match or int(match[1], 16) != exp['crc']:
                raise RuntimeError('File CRC mismatch: ' + name)
            results.append({'iteration': iteration, 'file': name, 'size': exp['size'],
                            'crc32': f'{exp["crc"]:08X}', 'pass': True})
    print(c.command('md.b 0x51040000 0x37'), flush=True)
finally:
    for i, old in enumerate(saved_gpio):
        c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{old:x}')
    restored = all((c.read(0x200008c4 + 4*i) & 0xefffffff) == (old & 0xefffffff)
                   for i, old in enumerate(saved_gpio))
    summary = {'file_checks': results, 'all_four_reads_pass': len(results) == 4,
               'gpio_restored': restored}
    (run / 'result.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    c.close()
    print('Transcript:', run / 'transcript.txt', flush=True)
