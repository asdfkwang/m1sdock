import json
import re
import time
from pathlib import Path
import serial

ROOT = Path(__file__).resolve().parent / 'runs' / time.strftime('%Y%m%d-%H%M%S')
ROOT.mkdir(parents=True, exist_ok=False)
log = (ROOT / 'transcript.txt').open('w', buffering=1)
observations = []
saved = {}
mutated = False
restored = False
port = serial.Serial(port=None, baudrate=2000000, timeout=0.05,
                     write_timeout=2, exclusive=True)
port.port = '/dev/ttyUSB0'
port.dtr = False
port.rts = False

def note(message):
    print(message, flush=True)
    log.write(message + '\n')

def cmd(command):
    log.write('\n>>> ' + command + '\n')
    port.write((command + '\r').encode())
    port.flush()
    data = b''
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        data += port.read(4096)
        if data.rstrip().endswith(b'=>'):
            text = data.decode('utf-8', 'replace')
            log.write(text + '\n')
            if any(x in text for x in ['Unknown command', 'exception', 'Unhandled']):
                raise RuntimeError(text)
            return text
    log.write(data.decode('utf-8', 'replace') + '\n')
    raise RuntimeError('U-Boot prompt timeout: ' + command)

def read(addr, width='l'):
    text = cmd(f'md.{width} 0x{addr:08x} 1')
    match = re.search(rf'(?im)^{addr:08x}:\s+([0-9a-f]+)', text)
    if not match:
        raise RuntimeError('Unable to parse register: ' + text)
    return int(match[1], 16)

def write(addr, val, width='l'):
    cmd(f'mw.{width} 0x{addr:08x} 0x{val:x}')

def snapshot(stage):
    row = dict(stage=stage, sdh=read(0x20060030),
               m0ic0=read(0x20000050), m0ic1=read(0x20000054),
               plic=read(0xe0001008))
    observations.append(row)
    note(stage + ': ' + ' '.join(f'{k}=0x{v:08x}' for k, v in row.items() if k != 'stage'))
    return row

def claim_and_complete():
    irq = read(0xe0201004)
    note(f'CLAIM S-context: {irq}')
    if irq == 81:
        write(0xe0201004, irq)
    elif irq != 0:
        raise RuntimeError(f'Unexpected claim {irq}; stopping')
    return irq

registers = {
    'clock': (0x2006002c, 'w'),
    'status_enable': (0x20060034, 'l'),
    'signal_enable': (0x20060038, 'l'),
    'mask0': (0x20000058, 'l'),
    'mask1': (0x2000005c, 'l'),
    'priority81': (0xe0000144, 'l'),
    's_enable2': (0xe0002088, 'l'),
    'm_threshold': (0xe0200000, 'l'),
    's_threshold': (0xe0201000, 'l'),
}

try:
    port.open()
    # Synchronize without changing baud, reset lines, or firmware.
    cmd('version')
    for name, (addr, width) in registers.items():
        saved[name] = read(addr, width)
    for addr in (0xe0002000, 0xe0002004, 0xe0002008,
                 0xe0002080, 0xe0002084, 0xe0002088):
        if read(addr) != 0:
            raise RuntimeError('PLIC context already active; refuse to disturb it')
    initial = snapshot('initial')
    if initial['sdh'] != 0 or initial['m0ic0'] & (1 << 17):
        raise RuntimeError('Existing SDH event; need a clean baseline')
    (ROOT / 'saved.json').write_text(json.dumps(saved, indent=2))
    note('Saved original settings: ' + json.dumps(saved))
    mutated = True
    # Priority 1 is below threshold 7: allow explicit claim, never CPU delivery.
    write(0xe0200000, 7)
    write(0xe0201000, 7)
    write(0xe0000144, 1)
    write(0xe0002088, 1 << 17)
    write(0x20060038, 0)
    write(0x20000058, 0xffffffff)
    write(0x2000005c, 0xffffffff)
    # Mask alone does not deassert already-latched aggregate status.
    write(0x20000060, 0xffffffff)
    write(0x20000064, 0xffffffff)
    claim_and_complete()
    base = snapshot('isolated')
    if base['plic'] & (1 << 17):
        raise RuntimeError('PLIC 81 still pending after isolation')
    # Enable only the synthetic command-timeout status and signal.
    write(0x20060034, 1 << 16)
    write(0x20060038, 1 << 16)
    # Enable internal clock only; do not clock the card or issue commands.
    write(0x2006002c, (saved['clock'] & ~4) | 1, 'w')
    for _ in range(20):
        if read(0x2006002c, 'w') & 2:
            break
    else:
        raise RuntimeError('Internal clock not stable')

    for cycle in (1, 2):
        write(0x20000058, 0xffffffff & ~(1 << 17))
        before = snapshot(f'cycle{cycle}-before')
        if before['sdh'] & (1 << 16) or before['m0ic0'] & (1 << 17) or before['plic'] & (1 << 17):
            raise RuntimeError('Dirty pre-event baseline')
        write(0x20060052, 1, 'w')
        event = snapshot(f'cycle{cycle}-forced')
        if not event['sdh'] & (1 << 16):
            raise RuntimeError('Force event did not latch at SDH; downstream inconclusive')
        if not event['m0ic0'] & (1 << 17):
            raise RuntimeError('SDH event latched, but M0IC 17 not observed')
        if not event['plic'] & (1 << 17):
            raise RuntimeError('M0IC 17 latched, but PLIC 81 not observed')
        # Quiesce the source and mask/ack the edge-latched aggregator first.
        write(0x20060038, 0)
        write(0x20060030, 0x00018000)
        write(0x20000058, 0xffffffff)
        write(0x20000060, 1 << 17)
        if claim_and_complete() != 81:
            raise RuntimeError('Expected PLIC claim ID 81')
        cleared = snapshot(f'cycle{cycle}-cleared')
        if cleared['sdh'] & (1 << 16) or cleared['m0ic0'] & (1 << 17) or cleared['plic'] & (1 << 17):
            raise RuntimeError('Event did not clear')
        write(0x20060038, 1 << 16)
    note('PASS: two synthetic SDH events reached M0IC 17 and PLIC 81; claim/clear repeated')
except Exception as exc:
    note('STOP: ' + str(exc))
finally:
    if mutated:
        try:
            write(0x20060038, 0)
            write(0x20000058, 0xffffffff)
            write(0x2000005c, 0xffffffff)
            write(0x20060030, 0x00018000)
            write(0x20000060, 1 << 17)
            claim_and_complete()
            # Restore config, not transient status/claim history.
            for name in ('clock', 'status_enable', 's_enable2', 'priority81',
                         'm_threshold', 's_threshold', 'mask0', 'mask1', 'signal_enable'):
                addr, width = registers[name]
                write(addr, saved[name], width)
            mismatch = {}
            for name, (addr, width) in registers.items():
                got = read(addr, width)
                mask = 0xfffd if name == 'clock' else 0xffffffff
                if (got & mask) != (saved[name] & mask):
                    mismatch[name] = [saved[name], got]
            restored = not mismatch
            note('RESTORE: ' + ('all writable settings match original' if restored else json.dumps(mismatch)))
        except Exception as exc:
            note('RESTORE FAILED: ' + str(exc))
    if port.is_open:
        port.close()
    (ROOT / 'result.json').write_text(json.dumps(dict(saved=saved, observations=observations, restored=restored), indent=2))
    log.close()
