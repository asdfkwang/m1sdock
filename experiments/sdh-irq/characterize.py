"""Clock register snapshot and read-only SD pin-configuration A/B trials."""
from pathlib import Path
import json
import re
import time
from console import Console

root = Path(__file__).resolve().parent
repo = root.parents[1]
run = root / '2026-10-20' / ('characterize-' + time.strftime('%H%M%S'))
run.mkdir()
c = Console(run / 'transcript.txt')
results = []
saved = []
try:
    print(c.command('version'), flush=True)
    print(c.command('clk dump'), flush=True)
    register_groups = {
        'GLB_SYS_CFG0': [0x20000090], 'HBN_GLB': [0x2000f030],
        'PDS_CPU_CORE_CFG': [0x2000e110, 0x2000e114],
        'MM_GLB_CLOCK': [0x30007000, 0x30007004, 0x30007010, 0x3000701c],
        'GLB_UART_SDH_PSRAM': [0x20000150, 0x20000430, 0x20000620],
        'GLB_GATES': [0x20000580, 0x20000584, 0x20000588],
        'WIFI_PLL': list(range(0x20000810, 0x2000083c, 4)),
        'UHS_PSRAM': list(range(0x3000f000, 0x3000f020, 4)),
        'UART3_CONFIG': [0x30002000, 0x30002004, 0x30002008],
        'SDH_CONFIG': [0x20060024, 0x20060028, 0x2006002c, 0x20060034, 0x20060038, 0x20060040, 0x20060044],
    }
    raw = {}
    for group, addresses in register_groups.items():
        raw[group] = {hex(a): c.read(a) for a in addresses}
        print(group, raw[group], flush=True)
    (run / 'registers.json').write_text(json.dumps(raw, indent=2))
    for i in range(6): saved.append(c.read(0x200008c4 + 4*i))
    (run / 'original-gpio.json').write_text(json.dumps(saved))
    # Factorial test: vary only pull configuration and drive-strength field.
    profiles = [
        ('original', lambda old: old),
        ('pull-up-only', lambda old: (old & ~0x20) | 0x10),
        ('drive1-only', lambda old: (old & ~0xc) | 4),
        ('pull-up-drive1', lambda old: (old & ~0x2c) | 0x14),
        ('original-repeat', lambda old: old),
        ('pull-up-drive1-repeat', lambda old: (old & ~0x2c) | 0x14),
    ]
    for name, transform in profiles:
        print('\nPROFILE ' + name, flush=True)
        c.log.write('\nPROFILE ' + name + '\n')
        for i, old in enumerate(saved):
            c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{transform(old):x}')
        print(c.command('mmc rescan', timeout=20), flush=True)
        info = c.command('mmc info', timeout=20)
        print(info, flush=True)
        row = {'profile': name, 'card_identified': 'Capacity: 59.7 GiB' in info,
               'gpio': [c.read(0x200008c4 + 4*i) for i in range(6)],
               'sdh_clock_word': c.read(0x2006002c, 'w')}
        if row['card_identified']:
            c.command('mw.b 0x51000000 0xa5 0x20000')
            output = c.command('load mmc 0:1 0x51000000 testfile', timeout=20)
            print(output, flush=True)
            row['loaded_131072_bytes'] = bool(re.search(r'\b131072 bytes read\b', output))
            if row['loaded_131072_bytes']:
                crc = c.command('crc32 0x51000000 0x20000')
                print(crc, flush=True)
                row['crc_match'] = bool(re.search(r'==>\s*7e8e43c2', crc, re.I))
        results.append(row)
        (run / 'results.json').write_text(json.dumps(results, indent=2))
finally:
    for i, old in enumerate(saved): c.command(f'mw.l 0x{0x200008c4 + 4*i:x} 0x{old:x}')
    c.close()
    print('Results:', run, flush=True)
