"""Pair-wise pull-up isolation for GPIO0..3.

characterize-041558 established that adding the pull-up bit to GPIO1 alone
made the standard U-Boot MMC driver identify the card and load+CRC the test
file, but repeating that profile right after other profiles failed with
'unable to select a mode' (ordering / card-state effects).  This study
therefore enumerates all GPIO0..3 pairs from a fresh baseline, repeats the
first passing pair twice, and closes with a baseline repeat.
"""
from pathlib import Path
import json
import re
import time
from console import Console

root = Path(__file__).resolve().parent
run = root / '2026-10-20' / ('pairs-' + time.strftime('%H%M%S'))
run.mkdir()
GPIO_BASE = 0x200008c4
SDH_CLOCK = 0x2006002c
PU_BIT = 0x10

c = Console(run / 'transcript.txt')
results = []
saved = []
try:
    print(c.command('version'), flush=True)
    for i in range(6):
        saved.append(c.read(GPIO_BASE + 4 * i))
    print('saved gpio:', [hex(v) for v in saved], flush=True)
    (run / 'original-gpio.json').write_text(json.dumps(saved))

    def run_profile(name, pins_added):
        print('\nPROFILE ' + name, flush=True)
        c.log.write('\nPROFILE ' + name + '\n')
        for i in range(6):
            value = saved[i] | (PU_BIT if i <= 3 and i in pins_added else 0)
            c.command(f'mw.l 0x{GPIO_BASE + 4 * i:x} 0x{value:x}')
        c.command('mmc rescan', timeout=25)
        info = c.command('mmc info', timeout=25)
        print(info, flush=True)
        row = {'profile': name, 'pins_added_pullup': pins_added,
               'card_identified': 'Capacity: 59.7 GiB' in info,
               'gpio': [c.read(GPIO_BASE + 4 * i) for i in range(6)],
               'sdh_clock_word': c.read(SDH_CLOCK, 'w')}
        if row['card_identified']:
            c.command('mw.b 0x51000000 0xa5 0x20000')
            output = c.command('load mmc 0:1 0x51000000 testfile', timeout=25)
            print(output, flush=True)
            row['loaded_131072_bytes'] = bool(
                re.search(r'\b131072 bytes read\b', output))
            if row['loaded_131072_bytes']:
                crc = c.command('crc32 0x51000000 0x20000')
                print(crc, flush=True)
                row['crc_match'] = bool(re.search(r'==>\s*7e8e43c2', crc, re.I))
        results.append(row)
        (run / 'results.json').write_text(json.dumps(results, indent=2))
        return row

    run_profile('baseline-original', [])
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    passing_pair = None
    for pair in pairs:
        row = run_profile('pu-gpio%d+gpio%d' % pair, list(pair))
        if row.get('crc_match'):
            passing_pair = pair
            break
    if passing_pair:
        run_profile('green-repeat-1', list(passing_pair))
        run_profile('green-repeat-2', list(passing_pair))
        run_profile('baseline-after-repeat', [])
    else:
        row_all = run_profile('all-four', [0, 1, 2, 3])
        if row_all.get('crc_match'):
            run_profile('all-four-repeat', [0, 1, 2, 3])
finally:
    for i, old in enumerate(saved):
        c.command(f'mw.l 0x{GPIO_BASE + 4 * i:x} 0x{old:x}')
    c.close()
    print('Results:', run, flush=True)
