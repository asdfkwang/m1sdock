"""Single-pin pull-up isolation for GPIO0..3.

characterize-032621 established that enabling pad pull-up on GPIO0..5 makes
the standard U-Boot MMC driver work (GPIO4/5 already carry the pull-up bit in
the post-boot state, GPIO0..3 do not).  This study adds the pull-up bit to
each of GPIO0..3 individually, then successively to pairs, to find the
minimal pad set.  Profiles always start from the saved baseline so every run
is an independent A/B against the original configuration.
"""
from pathlib import Path
import json
import re
import time
from console import Console

root = Path(__file__).resolve().parent
run = root / '2026-10-20' / ('pins-' + time.strftime('%H%M%S'))
run.mkdir()
GPIO_BASE = 0x200008c4
SDH_CLOCK = 0x2006002c
PU_BIT = 0x10  # pull-up (established by characterize-032621)

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
    passing_single = None
    for pin in (0, 1, 2, 3):
        row = run_profile(f'pu-gpio{pin}', [pin])
        if row.get('crc_match') and passing_single is None:
            passing_single = pin
    if passing_single is not None:
        run_profile(f'single-green-gpio{passing_single}-repeat',
                    [passing_single])
    else:
        passing_pair = None
        for a in (0, 1, 2, 3):
            for b in range(a + 1, 4):
                row = run_profile(f'pu-gpio{a}+gpio{b}', [a, b])
                if row.get('crc_match'):
                    passing_pair = (a, b)
                    break
            if passing_pair:
                break
        if passing_pair:
            run_profile('pair-repeat-green',
                        [passing_pair[0], passing_pair[1]])
        else:
            run_profile('all-four', [0, 1, 2, 3])
    run_profile('baseline-repeat', [])
finally:
    for i, old in enumerate(saved):
        c.command(f'mw.l 0x{GPIO_BASE + 4 * i:x} 0x{old:x}')
    c.close()
    print('Results:', run, flush=True)
