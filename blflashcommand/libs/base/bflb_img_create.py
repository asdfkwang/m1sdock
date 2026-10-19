# decompyle3 version 3.9.0
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.7.16 (default, Mar 30 2023, 01:25:49) 
# [GCC 12.2.1 20220924]
# Embedded file name: libs/base/bflb_img_create.py
import re, os, sys, time, shutil, zipfile
from libs import bflb_utils
from libs.bflb_utils import app_path, chip_path, set_error_code, convert_path
from libs.bflb_configobj import BFConfigParser
from libs.base import bflb_efuse_boothd_create

def take_second(elem):
    return elem[1]


def factory_mode_set(file, value):
    cfg = BFConfigParser()
    cfg.read(file)
    if cfg.has_option('EFUSE_CFG', 'factory_mode'):
        cfg.set('EFUSE_CFG', 'factory_mode', value)
        cfg.write(file, 'w')


def check_pt_file(file, addr):
    if len(file) > 0:
        i = 0
        L = []
        while i < len(file):
            L.append([convert_path(file[i]), int(addr[i], 16)])
            i += 1

        L.sort(key=take_second)
        i = 0
        try:
            while i < len(L) - 1:
                address = L[i][1]
                address_next = L[i + 1][1]
                file_size = os.path.getsize(os.path.join(app_path, L[i][0]))
                if address_next < address + file_size:
                    bflb_utils.printf('pt check fail, %s is overlayed with %s in flash layout, please check your partition table to fix this issue' % (
                     L[i][0], L[i + 1][0]))
                    return False
                else:
                    i += 1

        except Exception as e:
            try:
                bflb_utils.printf(e)
                return False
            finally:
                e = None
                del e

        return True


def compress_dir(chipname, zippath, efuse_load=False, address=None, flash_file=None, efuse_file=None, efuse_mask_file=None):
    zip_file = os.path.join(chip_path, chipname, zippath, 'whole_img.pack')
    dir_path = os.path.join(chip_path, chipname, chipname)
    cfg_file = os.path.join(chip_path, chipname, 'eflash_loader/eflash_loader_cfg.ini')
    cfg = BFConfigParser()
    cfg.read(cfg_file)
    if not address:
        address = []
    if not flash_file:
        flash_file = []
    if check_pt_file(flash_file, address) is not True:
        bflb_utils.printf('PT Check Fail')
        set_error_code('0082')
        return False
    flash_file.append(os.path.join(chip_path, chipname, 'eflash_loader/eflash_loader_cfg.ini'))
    if efuse_load:
        if efuse_file:
            flash_file.append(efuse_file)
        if efuse_mask_file:
            flash_file.append(efuse_mask_file)
    if len(flash_file) > 0:
        i = 0
        try:
            while i < len(flash_file):
                if chip_path in flash_file[i]:
                    relpath = os.path.relpath(os.path.join(app_path, convert_path(flash_file[i])), chip_path)
                    dir = os.path.join(chip_path, chipname, relpath)
                    if os.path.isdir(os.path.dirname(dir)) is False:
                        os.makedirs(os.path.dirname(dir))
                    shutil.copyfile(os.path.join(app_path, convert_path(flash_file[i])), dir)
                else:
                    relpath = os.path.relpath(os.path.join(chipname, 'img_create', os.path.basename(flash_file[i])))
                    dir = os.path.join(chip_path, chipname, relpath)
                    if os.path.isdir(os.path.dirname(dir)) is False:
                        os.makedirs(os.path.dirname(dir))
                    shutil.copyfile(flash_file[i], dir)
                i += 1

            verfile = os.path.join(chip_path, chipname, chipname, 'version.txt')
            with open(verfile, mode='w') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        except Exception as e:
            try:
                bflb_utils.printf(e)
                return False
            finally:
                e = None
                del e

        try:
            z = zipfile.ZipFile(zip_file, 'w')
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for file in filenames:
                    z.write(os.path.join(dirpath, file), os.path.relpath(os.path.join(dirpath, file), os.path.join(chip_path, chipname)))

            z.close()
            shutil.rmtree(dir_path)
        except Exception as e:
            try:
                bflb_utils.printf(e)
                return False
            finally:
                e = None
                del e

        return True


def img_create(args, chipname='bl60x', chiptype='bl60x', img_dir=None, config_file=None):
    sub_module = __import__(('libs.' + chiptype), fromlist=[chiptype])
    img_dir_path = os.path.join(chip_path, chipname, 'img_create')
    if img_dir is None:
        sub_module.img_create_do.img_create_do(args, img_dir_path, config_file)
    else:
        sub_module.img_create_do.img_create_do(args, img_dir, config_file)


def create_sp_media_image_file(config, chiptype='bl60x', cpu_type=None):
    sub_module = __import__(('libs.' + chiptype), fromlist=[chiptype])
    sub_module.img_create_do.create_sp_media_image(config, cpu_type)


def encrypt_loader_bin(chiptype, file, sign, encrypt, encrypt_key, encrypt_iv, publickey_file, privatekey_file):
    sub_module = __import__(('libs.base.' + chiptype), fromlist=[chiptype])
    return sub_module.img_create_do.encrypt_loader_bin_do(file, sign, encrypt, encrypt_key, encrypt_iv, publickey_file, privatekey_file)


def run():
    parser_image = bflb_utils.image_create_parser_init()
    args = parser_image.parse_args()
    bflb_utils.printf('Chipname: %s' % args.chipname)
    if args.chipname:
        chip_dict = { 'bl56x': 'bl60x',
          'bl60x': 'bl60x',
          'bl562': 'bl602',
          'bl602': 'bl602',
          'bl702': 'bl702',
          'bl702l': 'bl702l',
          'bl808': 'bl808',
          'bl606p': 'bl808',
          'bl616': 'bl616',
          'wb03': 'wb03'}
        chipname = args.chipname
        chiptype = chip_dict[chipname]
        img_create_path = os.path.join(chip_path, chipname, 'img_create_mcu')
        img_create_cfg = os.path.join(chip_path, chipname, 'img_create_mcu') + '/img_create_cfg.ini'
        bh_cfg_file = img_create_path + '/efuse_bootheader_cfg.ini'
        bh_file = img_create_path + '/bootheader.bin'
        if args.imgfile:
            imgbin = args.imgfile
            cfg = BFConfigParser()
            cfg.read(img_create_cfg)
            cfg.set('Img_Cfg', 'segdata_file', imgbin)
            cfg.write(img_create_cfg, 'w')
        bflb_efuse_boothd_create.bootheader_create_process(chipname, chiptype, bh_cfg_file, bh_file, img_create_path + '/bootheader_dummy.bin')
        img_create(args, chipname, chiptype, img_create_path, img_create_cfg)
    else:
        bflb_utils.printf('Please set chipname config, exit')


if __name__ == '__main__':
    run()
# okay decompiling ./libs/base/bflb_img_create.pyc
