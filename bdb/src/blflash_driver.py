"""bdb's blflashcommand adapter: write + readback over one UART connection."""
import configparser
import json
import os
from pathlib import Path
import re
import sys
import traceback
from types import SimpleNamespace


def main():
    sys.path.insert(0, os.environ['BDB_TOOL_ROOT'])
    from BLFlashCommand import MainClass
    from libs.bflb_utils import eflash_loader_parser_init
    from libs.bflb_eflash_loader import BL808EflashLoader

    regions = json.loads(Path(os.environ['BDB_REGIONS_JSON']).read_text())['regions']
    program = os.environ['BDB_PROGRAM'] == '1'
    out = Path(os.environ['BDB_RB_OUT_DIR'])
    config = configparser.ConfigParser()
    config['cfg'] = {'erase': '1', 'skip_mode': '0x0, 0x0', 'boot2_isp_mode': '0'}
    for region in regions:
        if not re.fullmatch(r'[A-Za-z0-9_]+', region['name']) or region['size'] <= 0:
            raise ValueError('Invalid readback region')
        if program:
            source = Path(region['src'])
            if source.stat().st_size != region['size']:
                raise ValueError('Source changed before programming')
            import hashlib
            if hashlib.sha256(source.read_bytes()).hexdigest() != region['src_sha256']:
                raise ValueError('Source hash changed before programming')
            config[region['name']] = {'filedir': str(source), 'address': region['addr']}
    path = out / 'flash.ini'
    with path.open('w') as stream:
        config.write(stream)
    args = SimpleNamespace(
        interface='uart', port=os.environ['BDB_PORT_C1'], chipname='bl808',
        baudrate=int(os.environ['BDB_BAUD']), config=str(path), cpu_id='',
        efuse='', key='', iv='', pk='', sk='')
    values = MainClass().get_value(args)
    if not values:
        raise RuntimeError('blflashcommand rejected the configuration')
    values['param']['chip_xtal'] = 'auto'
    loader_args = eflash_loader_parser_init().parse_args(
        ['--write' if program else '--none', '--flash'])
    loader = BL808EflashLoader('bl808', loader_args, values)
    try:
        result, detail = loader.run_step()
        if result is not True:
            raise RuntimeError(f'blflashcommand session failed: {detail}')
        if program:
            print('[bdb-driver] program-ok', flush=True)
        for region in regions:
            start = int(region['addr'], 0)
            remaining = region['size']
            with (out / f"rd_{region['name']}.bin").open('wb') as stream:
                while remaining:
                    # The decompiled multi-chunk reader stalls above tx_size-8.
                    # Request one packet at a time over this same connection.
                    size = min(remaining, loader._bflb_com_tx_size - 8, 4096)
                    if size <= 0:
                        raise RuntimeError('Invalid transport packet size')
                    ok, data = loader.flash_read_main_process(start, size, 0, None, None)
                    if ok is not True or data is None or len(data) != size:
                        raise RuntimeError(f"Short/failed readback: {region['name']}")
                    stream.write(data)
                    start += size
                    remaining -= size
            print(f"[bdb-driver] readback-ok region={region['name']} size={region['size']}", flush=True)
    finally:
        if loader.bflb_serial_object is not None:
            loader.close_serial()
    print('[bdb-driver] session-ok', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
