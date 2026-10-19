#!/usr/bin/env python3
"""Prepare SDK README's M0/group0 and D0/group1 images; never open UART."""
import configparser
import csv
import hashlib
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'blflashcommand'
OUT = TOOL / 'chips/bl808/img_create'
sys.path.insert(0, str(TOOL))

from libs.base import bflb_efuse_boothd_create as headers
from libs.base.bl808 import bootheader_cfg_keys as keys
from libs.base.bl808.img_create_do import img_creat_process
from libs.bflb_configobj import BFConfigParser


def save(cfg, path):
    with path.open('w') as stream:
        cfg.write(stream)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = configparser.ConfigParser()
    cfg.read(TOOL / 'chips/bl808/efuse_bootheader/efuse_bootheader_cfg.conf')
    images = configparser.ConfigParser()
    flash = configparser.ConfigParser()
    flash['cfg'] = {'erase': '1', 'skip_mode': '0x0, 0x0', 'boot2_isp_mode': '0'}
    sources = []
    for group, cpu, offset in ((0, 'm0', 0x2000), (1, 'd0', 0x52000)):
        section = f'BOOTHEADER_GROUP{group}_CFG'
        for core in ('m0', 'd0', 'lp'):
            cfg[section][f'{core}_config_enable'] = str(int(core == cpu))
        cfg[section][f'{cpu}_boot_entry'] = '0x58000000'
        cfg[section][f'{cpu}_image_address_offset'] = '0'
        cfg[section]['group_image_offset'] = hex(offset)
        cfg[section]['sign'] = '0'
        cfg[section]['encrypt_type'] = '0'
        cfg[section]['crc_ignore'] = '0'
        cfg[section]['hash_ignore'] = '0'
        source = ROOT / f'M1s_BL808_Linux_SDK/out/low_load_bl808_{cpu}.bin'
        if not source.is_file():
            raise FileNotFoundError(source)
        sources.append((group, cpu, offset, source))
        files = ['UNUSED'] * 3
        files[('m0', 'd0', 'lp').index(cpu)] = str(source)
        images[f'Img_Group{group}_Cfg'] = {
            'boot_header_file': str(OUT / f'bootheader_group{group}.bin'),
            'segdata_file': '|'.join(files),
            'bootinfo_file': str(OUT / f'bootinfo_group{group}.bin'),
            'img_file': str(OUT / f'img_group{group}.bin'),
            'efuse_file': str(OUT / 'efusedata.bin'),
            'efuse_mask_file': str(OUT / 'efusedata_mask.bin'),
        }
        for kind, addr in (('bootinfo', group * 0x1000), ('img', offset)):
            flash[f'{kind}_group{group}'] = {
                'filedir': f'{kind}_group{group}.bin', 'address': hex(addr)}
    bh_cfg = OUT / 'low_load_bootheader.ini'
    img_cfg = OUT / 'low_load_images.ini'
    save(cfg, bh_cfg)
    save(images, img_cfg)
    # Local scratch files required by the image generator, never burned to efuse.
    for name in ('efusedata.bin', 'efusedata_mask.bin'):
        (OUT / name).write_bytes(bytes(256))
    for group, cpu, offset, source in sources:
        data, _ = headers.update_data_from_cfg(
            keys.bootheader_cfg_keys, str(bh_cfg), f'BOOTHEADER_GROUP{group}_CFG')
        data = headers.bootheader_update_flash_pll_crc(data, 'bl808')
        (OUT / f'bootheader_group{group}.bin').write_bytes(data)
        if group == 0:
            (TOOL / 'chips/bl808/efuse_bootheader/clock_para.bin').write_bytes(data[100:128])
        result, _ = img_creat_process(f'group{group}', 1, BFConfigParser(str(img_cfg)))
        assert result == 'OK', result
        boot = (OUT / f'bootinfo_group{group}.bin').read_bytes()
        body = (OUT / f'img_group{group}.bin').read_bytes()
        raw = source.read_bytes()
        assert body == raw + bytes((-len(raw)) % 16)
        assert struct.unpack_from('<I', boot, 132)[0] == offset
        assert struct.unpack_from('<I', boot, 140)[0] == len(body)
        assert boot[144:176] == hashlib.sha256(body).digest()
        assert struct.unpack_from('<I', boot, keys.bootheader_len - 4)[0] == zlib.crc32(boot[:keys.bootheader_len - 4])
        if group == 0:
            table_start, table_len = struct.unpack_from('<II', boot, 0x100)
            table = boot[table_start:table_start + table_len]
            assert table[:4] == b'FCTG'
            assert struct.unpack_from('<I', table, len(table) - 4)[0] == zlib.crc32(table[4:-4])
            with (TOOL / 'utils/flash/bl808/flashcfg_list.csv').open() as stream:
                expected = {row['flashJedecID'] for row in csv.DictReader(stream)}
            actual = set()
            for pos in range(4, len(table) - 4, 8):
                actual.add(table[pos:pos + 3].hex())
                address = struct.unpack_from('<I', table, pos + 4)[0]
                entry = boot[address:address + 92]
                assert len(entry) == 92 and entry[:4] == b'FCFG'
                assert struct.unpack_from('<I', entry, 88)[0] == zlib.crc32(entry[4:88])
            assert actual == expected, (expected - actual, actual - expected)
            assert 'ef4018' in actual, 'Board JEDEC ID missing from boot flash table'
            print(f'VALIDATED flash table: all {len(actual)} JEDEC IDs, including ef4018')
        for i, core in enumerate(('m0', 'd0', 'lp')):
            base = keys.bootcpucfg_start_pos + i * keys.bootcpucfg_len
            assert (boot[base] & 1) == int(core == cpu)
            if core == cpu:
                assert struct.unpack_from('<II', boot, base + 12) == (0, 0x58000000)
        print(f'VALIDATED Group{group} {cpu}: entry=0x58000000, flash={offset:#x}, size={len(body)}')
    save(flash, OUT / 'flash_low_load.ini')
    print('Flash configuration:', OUT / 'flash_low_load.ini')


if __name__ == '__main__':
    main()
