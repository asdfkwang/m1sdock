"""Try the existing U-Boot MMC stack with SDK-style SDH pad settings."""
from pathlib import Path
import json
import time
from console import Console

root = Path(__file__).resolve().parent
run = root / '2026-10-20' / ('mmc-' + time.strftime('%H%M%S'))
run.mkdir()
c = Console(run / 'transcript.txt')
saved_gpio = []
saved_host = None
try:
    print(c.command('version'), flush=True)
    print(c.command('help mmc'), flush=True)
    for i in range(6):
        saved_gpio.append(c.read(0x200008c4 + 4 * i))
    saved_host = c.read(0x20060028, 'b')
    (run / 'original.json').write_text(json.dumps({'gpio': saved_gpio, 'host': saved_host}, indent=2))
    for i, old in enumerate(saved_gpio):
        c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{(old & ~0xc0001fff) | 0x17:x}')
    for mode in ('sdk-pads', 'sdk-pads-cd-test'):
        print('\nMODE: ' + mode, flush=True)
        c.log.write('\nMODE: ' + mode + '\n')
        if mode.endswith('cd-test'):
            host = c.read(0x20060028, 'b')
            c.command(f'mw.b 0x20060028 0x{host | 0xc0:x}')
        for command in ('mmc list', 'mmc dev 0', 'echo $?', 'mmc info', 'echo $?',
                        'md.l 0x20060024 7'):
            print(c.command(command, timeout=15), flush=True)
        info = c.command('mmc info', timeout=15)
        print(info, flush=True)
        if 'Capacity:' in info and 'Device:' in info:
            print('CARD IDENTIFIED', flush=True)
            print(c.command('mmc part'), flush=True)
            print(c.command('fatls mmc 0:1'), flush=True)
            break
finally:
    for i, old in enumerate(saved_gpio):
        c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{old:x}')
    if saved_host is not None:
        host = c.read(0x20060028, 'b')
        c.command(f'mw.b 0x20060028 0x{(host & ~0xc0) | (saved_host & 0xc0):x}')
    c.close()
    print('Transcript:', run / 'transcript.txt', flush=True)
