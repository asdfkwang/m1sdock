# decompyle3 version 3.9.0
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.7.16 (default, Mar 30 2023, 01:25:49) 
# [GCC 12.2.1 20220924]
# Embedded file name: libs/base/bflb_base_eflash_loader.py
__doc__ = '\nCreated on 20220908\n\n@author: Dillon\n'
import os, lzma, ecdsa, config as gol
from libs.bflb_utils import *
from libs.bflb_configobj import BFConfigParser
from libs import bflb_ecdh
from libs import bflb_interface_jlink
from libs import bflb_interface_cklink
from libs import bflb_interface_openocd
from libs.base import bflb_img_loader
from libs.base import bflb_flash_select
from libs.base import bflb_efuse_boothd_create
from libs.base import bflb_img_create as img_create
from pickle import NONE
FLASH_LOAD_SHAKE_HAND = 'Flash load shake hand'
FLASH_ERASE_SHAKE_HAND = 'Flash erase shake hand'

class BaseEflashLoader(object):
    __doc__ = '\n    Load the flash base execution file.\n    '

    def __init__(self, chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num):
        self.chip_type = chip_type
        self.chip_name = ''
        self.args = args
        self.config = config
        self.callback = callback
        self.macaddr_callback = macaddr_callback
        self.create_simple_callback = create_simple_callback
        self.create_img_callback = create_img_callback
        self.temp_task_num = task_num
        self.task_num = None
        self.device = ''
        self.speed = 0
        self.boot_speed = 0
        self.bflb_serial_object = None
        self.start = ''
        self.end = ''
        self.file = ''
        self.address = ''
        self.macaddr = ''
        self.bootinfo = None
        self.flash_set = 0
        self.read_flash_id = 0
        self.id_valid_flag = '80'
        self.read_flash2_id = 0
        self.id2_valid_flag = '80'
        self.do_reset = True
        self.reset_hold_time = 100
        self.shake_hand_delay = 100
        self.reset_revert = True
        self.cutoff_time = 0
        self.shake_hand_retry = 2
        self.flash_burn_retry = 1
        self.ram_load = False
        self.load_function = 1
        self.macaddr_check = False
        self.NUM_ERR = 5
        self.cfg = ''
        self.eflash_loader_file = ''
        self.cpu_reset = False
        self.retry_delay_after_cpu_reset = 0
        self.input_macaddr = ''
        self.isp_mode_sign = False
        self.create_cfg = None
        self._skip_addr = []
        self._skip_len = []
        self.address_list = []
        self.flash_file_list = []
        self.encrypt_key = None
        self.encrypt_iv = None
        self.public_key = None
        self.private_key = None
        self.load_file = ''
        self._mac_addr = bytearray(0)
        self._need_shake_hand = True
        self._isp_shakehand_timeout = 0
        self._macaddr_check = bytearray(0)
        self._default_time_out = 2.0
        self._flash2_en = False
        self._flash1_size = 0
        self._flash2_size = 0
        self._flash2_select = False
        self._efuse_bootheader_file = ''
        self._img_create_file = ''
        self._com_cmds = {'change_rate':{'cmd_id':'20', 
          'data_len':'0008', 
          'callback':None}, 
         'reset':{'cmd_id':'21', 
          'data_len':'0000', 
          'callback':None}, 
         'clk_set':{'cmd_id':'22', 
          'data_len':'0000', 
          'callback':None}, 
         'opt_finish':{'cmd_id':'23', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_erase':{'cmd_id':'30', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_write':{'cmd_id':'31', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_read':{'cmd_id':'32', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_boot':{'cmd_id':'33', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_xip_read':{'cmd_id':'34', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_switch_bank':{'cmd_id':'35', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_read_jid':{'cmd_id':'36', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_read_status_reg':{'cmd_id':'37', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_write_status_reg':{'cmd_id':'38', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_write_check':{'cmd_id':'3a', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_set_para':{'cmd_id':'3b', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_chiperase':{'cmd_id':'3c', 
          'data_len':'0000', 
          'callback':None}, 
         'flash_readSha':{'cmd_id':'3d', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_xip_readSha':{'cmd_id':'3e', 
          'data_len':'0100', 
          'callback':None}, 
         'flash_decompress_write':{'cmd_id':'3f', 
          'data_len':'0100', 
          'callback':None}, 
         'efuse_write':{'cmd_id':'40', 
          'data_len':'0080', 
          'callback':None}, 
         'efuse_read':{'cmd_id':'41', 
          'data_len':'0000', 
          'callback':None}, 
         'efuse_read_mac':{'cmd_id':'42', 
          'data_len':'0000', 
          'callback':None}, 
         'efuse_write_mac':{'cmd_id':'43', 
          'data_len':'0006', 
          'callback':None}, 
         'flash_xip_read_start':{'cmd_id':'60', 
          'data_len':'0080', 
          'callback':None}, 
         'flash_xip_read_finish':{'cmd_id':'61', 
          'data_len':'0000', 
          'callback':None}, 
         'log_read':{'cmd_id':'71', 
          'data_len':'0000', 
          'callback':None}, 
         'efuse_security_write':{'cmd_id':'80', 
          'data_len':'0080', 
          'callback':None}, 
         'efuse_security_read':{'cmd_id':'81', 
          'data_len':'0000', 
          'callback':None}, 
         'ecdh_get_pk':{'cmd_id':'90', 
          'data_len':'0000', 
          'callback':None}, 
         'ecdh_chanllenge':{'cmd_id':'91', 
          'data_len':'0000', 
          'callback':None}}
        self._resp_cmds = [
         'flash_read','flash_xip_read','efuse_read','efuse_read_mac','flash_readSha','flash_xip_readSha','flash_read_jid',
         'flash_read_status_reg','log_read','ecdh_get_pk','ecdh_chanllenge','efuse_security_read']

    def first_run_step_load_parameter(self):
        """
        First step: init.
        """
        if self.temp_task_num == None:
            local_log_enable(True)
        if self.temp_task_num != None:
            if self.temp_task_num > 256:
                self.task_num = self.temp_task_num - 256
            else:
                self.task_num = self.temp_task_num
        else:
            self.task_num = None
        printf('========= eflash loader cmd arguments =========')
        self.interface = self.config['param']['interface_type'].lower()
        self.chip_name = self.config['param']['chip_name']
        self.config_file = os.path.join(app_path, 'chips', self.chip_name.lower(), 'eflash_loader', 'eflash_loader_cfg.ini')
        if not os.path.exists(self.config_file):
            conf_file = self.config_file.replace('.ini', '.conf')
            if os.path.exists(conf_file):
                shutil.copy(conf_file, self.config_file)
        if os.path.exists(self.config_file):
            self.cfg = BFConfigParser()
            self.cfg.read(self.config_file)
        else:
            printf('Config file "' + self.config_file + '" not found')
            self.error_code_print('000B')
            return (False, 0)
        if self.interface == 'openocd':
            self.device = self.cfg.get('LOAD_CFG', 'openocd_config')
            self._bflb_sn_device = self.config['param']['comport_uart']
        else:
            if self.interface == 'cklink':
                self.device = self.cfg.get('LOAD_CFG', 'cklink_vidpid')
                self._bflb_sn_device = self.cfg.get('LOAD_CFG', 'cklink_type') + ' ' + self.config['param']['comport_uart']
            else:
                self.device = self.config['param']['comport_uart']
        if 'aes_key' in self.config['param']:
            if self.config['check_box']['encrypt']:
                self.encrypt_key = self.config['param']['aes_key']
        if 'aes_iv' in self.config['param']:
            if self.config['check_box']['sign']:
                self.encrypt_iv = self.config['param']['aes_iv']
        if 'input_path' in self.config:
            if 'publickey' in self.config['input_path']['publickey']:
                self.public_key = self.config['input_path']['publickey']
        if 'input_path' in self.config:
            if 'privatekey' in self.config['input_path']['privatekey']:
                self.private_key = self.config['input_path']['privatekey']
        xtal_type = self.config['param']['chip_xtal']
        if self.interface == 'uart':
            temp_speed = int(self.config['param']['speed_uart'])
        else:
            temp_speed = int(self.config['param']['speed_jlink'])
        printf('serial port is ', self.device)
        printf('chiptype: ', self.chip_type)
        try:
            if self.args.start:
                self.start = self.args.start
            if self.args.end:
                self.end = self.args.end
            if self.args.file:
                self.file = self.args.file
            if self.args.addr:
                self.address = self.args.addr
            if self.args.mac:
                self.macaddr = self.args.mac
            if self.args.createcfg:
                self.create_cfg = self.args.createcfg
            if self.args.loadfile:
                self.load_file = self.args.loadfile
            if self.args.usage:
                printf('-e --start=00000000 --end=0000FFFF -c config.ini')
                printf('-w --flash -c config.ini')
                printf('-w --flash --file=1.bin,2.bin --addr=00000000,00001000 -c config.ini')
                printf('-r --flash --start=00000000 --end=0000FFFF --file=flash.bin -c config.ini')
        except Exception as e:
            try:
                printf(e)
                self.error_code_print('0002')
                return (False, 0)
            finally:
                e = None
                del e

        if self.cfg.has_option('LOAD_CFG', 'verify'):
            if self.cfg.get('LOAD_CFG', 'verify') == '1':
                self.verify = 1
            else:
                self.verify = 0
        else:
            self.verify = 0
        try:
            self.erase = int(self.config['param']['erase'])
        except:
            self.erase = 1

        try:
            boot2_isp_mode = int(self.config['param']['boot2_isp_mode'])
            if int(boot2_isp_mode) == 1:
                self.isp_mode_sign = True
        except:
            pass

        if not 'skip_mode' in self.config['param'] or self.config['param']['skip_mode']:
            skip_para = self.config['param']['skip_mode'].replace(' ', '')
            if skip_para[-1] == ';':
                skip_para = skip_para[:-1]
            skip_para_list = skip_para.split(';')
            for temp_value in skip_para_list:
                temp_list = temp_value.split(',')
                if temp_list[0][0:2] == '0x':
                    self._skip_addr.append(int(temp_list[0][2:], 16))
                else:
                    self._skip_addr.append(int(temp_list[0], 10))
                if temp_list[1][0:2] == '0x':
                    self._skip_len.append(int(temp_list[1][2:], 16))
                else:
                    self._skip_len.append(int(temp_list[1], 10))

            if len(self._skip_len) > 1 or len(self._skip_len) == 1 and self._skip_len[0] > 0:
                if self.erase == 2:
                    printf('Error: skip mode can not set flash chiperase!')
                    self.error_code_print('0044')
                    return (False, 0)
            if self.cfg.has_option('LOAD_CFG', 'local_log'):
                if self.cfg.get('LOAD_CFG', 'local_log') == 'true':
                    printf('local log enable')
                    local_log_enable(True)
                    self.input_macaddr = self.macaddr
                else:
                    local_log_enable(False)
                    self.input_macaddr = ''
            if self.interface == 'cklink':
                self._bflb_com_tx_size = 14344
            else:
                self._bflb_com_tx_size = int(self.cfg.get('LOAD_CFG', 'tx_size'))
            if self.cfg.has_option('LOAD_CFG', 'erase_time_out'):
                self._erase_time_out = int(self.cfg.get('LOAD_CFG', 'erase_time_out'))
            if self.cfg.has_option('LOAD_CFG', 'shake_hand_retry'):
                self.shake_hand_retry = int(self.cfg.get('LOAD_CFG', 'shake_hand_retry'))
            if self.cfg.has_option('LOAD_CFG', 'flash_burn_retry'):
                self.flash_burn_retry = int(self.cfg.get('LOAD_CFG', 'flash_burn_retry'))
            if self.cfg.has_option('LOAD_CFG', 'checksum_err_retry'):
                self._checksum_err_retry_limit = int(self.cfg.get('LOAD_CFG', 'checksum_err_retry'))
            if self.cfg.has_option('LOAD_CFG', 'cpu_reset_after_load'):
                self.cpu_reset = self.cfg.get('LOAD_CFG', 'cpu_reset_after_load') == 'true'
            if self.cfg.has_option('LOAD_CFG', 'retry_delay_after_cpu_reset'):
                self.retry_delay_after_cpu_reset = int(self.cfg.get('LOAD_CFG', 'retry_delay_after_cpu_reset'))
                printf('retry delay: ', self.retry_delay_after_cpu_reset)
            if self.cfg.has_option('LOAD_CFG', 'eflash_loader_file'):
                if self.eflash_loader_file is None:
                    self.eflash_loader_file = self.cfg.get('LOAD_CFG', 'eflash_loader_file')
            printf('cpu_reset=', self.cpu_reset)
            if xtal_type != '':
                self.eflash_loader_file = 'chips/' + self.chip_name.lower() + '/eflash_loader/eflash_loader_' + xtal_type.replace('.', 'p').lower() + '.bin'
            if self.load_file and not self.eflash_loader_file:
                self.eflash_loader_file = self.load_file
            else:
                if self.eflash_loader_file is not None:
                    self.eflash_loader_file = os.path.join(app_path, self.eflash_loader_file)
            self.load_function = 1
            if self.cfg.has_option('LOAD_CFG', 'isp_shakehand_timeout'):
                self._isp_shakehand_timeout = int(self.cfg.get('LOAD_CFG', 'isp_shakehand_timeout'))
            result, address, flash_file = self.get_flash_file_and_address()
            if not result:
                return (False, self.flash_burn_retry)
            temp_file_list = []
            for one in flash_file:
                if os.path.join(chip_path, self.chip_name) in one:
                    temp_file_list.append(one.replace(app_path, '')[1:])
                else:
                    temp_file_list.append(os.path.join('chips', self.chip_name, 'img_create', os.path.basename(one)))

            if 'erase' in self.config['param']:
                if self.config['param']['erase']:
                    update_cfg(self.cfg, 'LOAD_CFG', 'erase', str(self.erase))
            if 'skip_mode' in self.config['param']:
                if self.config['param']['skip_mode']:
                    update_cfg(self.cfg, 'LOAD_CFG', 'skip_mode', self.config['param']['skip_mode'])
            if 'boot2_isp_mode' in self.config['param']:
                if self.config['param']['boot2_isp_mode']:
                    update_cfg(self.cfg, 'LOAD_CFG', 'boot2_isp_mode', self.config['param']['boot2_isp_mode'])
            update_cfg(self.cfg, 'FLASH_CFG', 'file', ' '.join(temp_file_list))
            update_cfg(self.cfg, 'FLASH_CFG', 'address', ' '.join(address))
            self.cfg.write(self.config_file, 'w+')
            with open((self.config_file), 'r', encoding='utf-8') as cf_file:
                cf_context = cf_file.read().replace('"', '')
            with open((self.config_file), 'w', encoding='utf-8') as cf_file:
                cf_file.write(cf_context)
            self.bl_write_flash_img(address, flash_file)
            self.address_list = address[:]
            self.flash_file_list = flash_file[:]
            if self.args.efuse:
                try:
                    if self.config['input_path']['efuse']:
                        if self.config['check_box']['efuse']:
                            efusefile = self.config['input_path']['efuse']
                except:
                    efusefile = ''

                if efusefile:
                    efuse_file = efusefile
                    mask_file = efuse_file.replace('.bin', '_mask.bin')
                    relpath_efuse_file = os.path.relpath(os.path.join('chips', self.chip_name, 'img_create', os.path.basename(efuse_file)))
                    relpath_mask_file = os.path.relpath(os.path.join('chips', self.chip_name, 'img_create', os.path.basename(mask_file)))
                    if self.cfg.has_option('EFUSE_CFG', 'file'):
                        update_cfg(self.cfg, 'EFUSE_CFG', 'file', relpath_efuse_file)
                        update_cfg(self.cfg, 'EFUSE_CFG', 'maskfile', relpath_mask_file)
                        self.cfg.write(self.config_file, 'w+')
                        with open((self.config_file), 'r', encoding='utf-8') as cf_file:
                            cf_context = cf_file.read().replace('"', '')
                        with open((self.config_file), 'w', encoding='utf-8') as cf_file:
                            cf_file.write(cf_context)
                else:
                    efuse_file = self.cfg.get('EFUSE_CFG', 'file')
                    mask_file = self.cfg.get('EFUSE_CFG', 'maskfile')
                if self.temp_task_num != None:
                    efuse_file = 'task' + str(self.temp_task_num) + '/' + efuse_file
                ret = img_create.compress_dir(self.chip_name, 'img_create', self.args.efuse, address, flash_file, efuse_file, mask_file)
                if ret is not True:
                    return errorcode_msg()
            else:
                ret = img_create.compress_dir(self.chip_name, 'img_create', False, address, flash_file)
                if ret is not True:
                    return errorcode_msg()
            if self.interface == 'uart' or self.interface == 'sdio':
                if temp_speed:
                    self.speed = temp_speed
                self.boot_speed = int(self.cfg.get('LOAD_CFG', 'speed_uart_boot'))
                self.set_boot_speed()
                if self.cfg.has_option('LOAD_CFG', 'reset_hold_time'):
                    self.reset_hold_time = int(self.cfg.get('LOAD_CFG', 'reset_hold_time'))
                if self.cfg.has_option('LOAD_CFG', 'shake_hand_delay'):
                    self.shake_hand_delay = int(self.cfg.get('LOAD_CFG', 'shake_hand_delay'))
                if self.cfg.has_option('LOAD_CFG', 'do_reset'):
                    self.do_reset = self.cfg.get('LOAD_CFG', 'do_reset') == 'true'
                if self.cfg.has_option('LOAD_CFG', 'reset_revert'):
                    self.reset_revert = self.cfg.get('LOAD_CFG', 'reset_revert') == 'true'
                if self.cfg.has_option('LOAD_CFG', 'cutoff_time'):
                    self.cutoff_time = int(self.cfg.get('LOAD_CFG', 'cutoff_time'))
                printf('========= Interface is %s =========' % self.interface)
                self._bflb_com_img_loader = bflb_img_loader.BflbImgLoader(self.device, self.speed, self.boot_speed, self.interface, self.chip_type, self.chip_name, self.eflash_loader_file, '', self.callback, self.do_reset, self.reset_hold_time, self.shake_hand_delay, self.reset_revert, self.cutoff_time, self.shake_hand_retry, self.isp_mode_sign, self._isp_shakehand_timeout, self.encrypt_key, self.encrypt_iv, self.public_key, self.private_key)
                self.bflb_serial_object = self._bflb_com_img_loader.bflb_serial_object
                if not self.cfg.has_option('LOAD_CFG', 'isp_mode_speed') or self.isp_mode_sign is True:
                    isp_mode_speed = int(self.cfg.get('LOAD_CFG', 'isp_mode_speed'))
                    self._bflb_com_img_loader.set_isp_baudrate(isp_mode_speed)
            else:
                if self.interface == 'jlink':
                    printf('========= Interface is JLink =========')
                    self.bflb_serial_object = bflb_interface_jlink.BflbJLinkPort()
                    if temp_speed:
                        self.speed = temp_speed
                        printf('com speed: %dk' % self.speed)
                    else:
                        self.speed = int(self.cfg.get('LOAD_CFG', 'speed_jlink'))
                    self.boot_speed = self.speed
                else:
                    if self.interface == 'openocd':
                        printf('========= Interface is Openocd =========')
                        self.bflb_serial_object = bflb_interface_openocd.BflbOpenocdPort()
                        if temp_speed:
                            self.speed = temp_speed
                            printf('com speed: %dk' % self.speed)
                        else:
                            self.speed = int(self.cfg.get('LOAD_CFG', 'speed_jlink'))
                        self.boot_speed = self.speed
                    else:
                        if self.interface == 'cklink':
                            printf('========= Interface is CKLink =========')
                            self.bflb_serial_object = bflb_interface_cklink.BflbCKLinkPort()
                            if temp_speed:
                                self.speed = temp_speed
                                printf('com speed: %dk' % self.speed)
                            else:
                                self.speed = int(self.cfg.get('LOAD_CFG', 'speed_jlink'))
                            self.boot_speed = self.speed
                        else:
                            printf(self.interface + ' is not supported ')
                            return (
                             False, self.flash_burn_retry)
            if self.args.chipid:
                ret, self.bootinfo, res = self.get_boot_info()
                if ret is False:
                    self.error_code_print('0003')
                    return (
                     False, self.flash_burn_retry)
                return (
                 True, self.flash_burn_retry)
            if self.cfg.has_option('LOAD_CFG', 'load_function'):
                self.load_function = int(self.cfg.get('LOAD_CFG', 'load_function'))
            if self.isp_mode_sign is True:
                if self._isp_shakehand_timeout == 0:
                    self._isp_shakehand_timeout = 5
                self.set_load_function()
            return (True, 'continue')

    def second_run_step_shake_hand(self):
        """
        Second step: shake hand and load eflash_loader.bin.
        """
        try:
            if self.load_function == 0:
                printf('No need load eflash_loader.bin')
            else:
                if self.load_function == 1:
                    load_bin_pass = False
                    printf('Eflash load bin file: ', self.eflash_loader_file)
                    ret, self.bootinfo, res = self.load_eflash_loader_bin()
                    if res == 'shake hand fail':
                        self.error_code_print('0050')
                    if res.startswith('repeat_burn') is True:
                        return ('repeat_burn', self.flash_burn_retry)
                    if res.startswith('error_shakehand') is True:
                        if self.cpu_reset is True:
                            self.error_code_print('0003')
                            return (
                             False, self.flash_burn_retry)
                        load_bin_pass = True
                        time.sleep(4.5)
                    if ret is False:
                        if load_bin_pass == False:
                            self.error_code_print('0003')
                            return (
                             False, self.flash_burn_retry)
                    if self.ram_load:
                        return (True, self.flash_burn_retry)
                else:
                    if self.load_function == 2:
                        load_bin_pass = False
                        printf('Bootrom load')
                        ret, self.bootinfo, res = self.get_boot_info()
                        if res == 'shake hand fail':
                            self.error_code_print('0050')
                        if res.startswith('repeat_burn') is True:
                            self.error_code_print('000A')
                            return (
                             'repeat_burn', self.flash_burn_retry)
                        if res.startswith('error_shakehand') is True:
                            if self.cpu_reset is True:
                                self.error_code_print('0003')
                                return (
                                 False, self.flash_burn_retry)
                            load_bin_pass = True
                            time.sleep(4.5)
                        if ret is False:
                            if load_bin_pass == False:
                                self.error_code_print('0050')
                                return (
                                 False, self.flash_burn_retry)
                        self._need_shake_hand = False
                        clock_para = bytearray(0)
                        if self.cfg.has_option('LOAD_CFG', 'clock_para'):
                            clock_para_str = self.cfg.get('LOAD_CFG', 'clock_para')
                            if clock_para_str != '':
                                clock_para_file = os.path.join(app_path, clock_para_str)
                                printf('clock para file: ', clock_para_file)
                                clock_para = self.clock_para_update(clock_para_file)
                        printf('change bdrate: ', self.speed)
                        ret = self.clock_pll_set(self._need_shake_hand, True, clock_para)
                        if ret is False:
                            printf('pll set fail!!')
                            return (
                             False, self.flash_burn_retry)
            return (True, 'continue')
        except Exception as e:
            try:
                printf(e)
                self.error_code_print('0003')
                return (
                 False, self.flash_burn_retry)
            finally:
                e = None
                del e

    def third_run_step_read_mac_address(self):
        """
        Third step: read mac address.
        """
        time.sleep(0.1)
        if self.isp_mode_sign is True:
            if self.cpu_reset is True:
                self.set_clear_boot_status(self._need_shake_hand)
        if self.cfg.has_option('LOAD_CFG', 'check_mac'):
            self.macaddr_check = self.cfg.get('LOAD_CFG', 'check_mac') == 'true'
        if self.macaddr_check:
            if self.isp_mode_sign is False:
                ret, self._mac_addr = self.efuse_read_mac_addr_process()
                if ret is False:
                    printf('read mac addr fail!!')
                    return (
                     False, self.flash_burn_retry)
                if self._mac_addr == self._macaddr_check:
                    self.error_code_print('000A')
                    return (
                     False, self.flash_burn_retry)
                self._need_shake_hand = False
                self._macaddr_check_status = True
        if self.macaddr_callback is not None:
            ret, self._efuse_data, self._efuse_mask_data, macaddr = self.macaddr_callback(binascii.hexlify(self._mac_addr).decode('utf-8'))
            if ret is False:
                return (False, self.flash_burn_retry)
            if self._efuse_data != bytearray(0) and self._efuse_mask_data != bytearray(0) or macaddr != '':
                self.args.efuse = True
        if self.callback:
            self.callback(0, 100, 'running', 'blue')
        return (True, 'continue')

    def fourth_run_step_interact_chip(self):
        """
        Fourth step: Interact with chip, read chip ID and update flash parameter.
        """
        if self.args.flash:
            flash_pin = 0
            flash_clock_cfg = 0
            flash_io_mode = 0
            flash_clk_delay = 0
            if self.cfg.has_option('FLASH_CFG', 'decompress_write'):
                self.decompress_write = self.cfg.get('FLASH_CFG', 'decompress_write') == 'true'
            self.set_decompress_write()
            printf('flash set para')
            if self.cfg.get('FLASH_CFG', 'flash_pin'):
                flash_pin_cfg = self.cfg.get('FLASH_CFG', 'flash_pin')
                if flash_pin_cfg.startswith('0x'):
                    flash_pin = int(flash_pin_cfg, 16)
                else:
                    flash_pin = int(flash_pin_cfg, 10)
                if flash_pin == 128:
                    flash_pin = self.get_flash_pin_from_bootinfo(self.chip_type, self.bootinfo)
                    printf('get flash pin cfg from bootinfo: 0x%02X' % flash_pin)
            else:
                flash_pin = self.get_flash_pin()
            if self.cfg.has_option('FLASH_CFG', 'flash_clock_cfg'):
                clock_div_cfg = self.cfg.get('FLASH_CFG', 'flash_clock_cfg')
                if clock_div_cfg.startswith('0x'):
                    flash_clock_cfg = int(clock_div_cfg, 16)
                else:
                    flash_clock_cfg = int(clock_div_cfg, 10)
            if self.cfg.has_option('FLASH_CFG', 'flash_io_mode'):
                io_mode_cfg = self.cfg.get('FLASH_CFG', 'flash_io_mode')
                if io_mode_cfg.startswith('0x'):
                    flash_io_mode = int(io_mode_cfg, 16)
                else:
                    flash_io_mode = int(io_mode_cfg, 10)
            if self.cfg.has_option('FLASH_CFG', 'flash_clock_delay'):
                clk_delay_cfg = self.cfg.get('FLASH_CFG', 'flash_clock_delay')
                if clk_delay_cfg.startswith('0x'):
                    flash_clk_delay = int(clk_delay_cfg, 16)
                else:
                    flash_clk_delay = int(clk_delay_cfg, 10)
            self.flash_set = (flash_pin << 0) + (flash_clock_cfg << 8) + (flash_io_mode << 16) + (flash_clk_delay << 24)
            if self.flash_set != 66047 or self.load_function == 2:
                printf('set flash cfg: %X' % self.flash_set)
                ret = self.flash_set_para_main_process(self.flash_set, bytearray(0))
                self._need_shake_hand = False
                if ret is False:
                    return (False, self.flash_burn_retry)
            ret, data = self.flash_read_jedec_id_process()
            if ret:
                self._need_shake_hand = False
                data = binascii.hexlify(data).decode('utf-8')
                self.id_valid_flag = data[6:]
                read_id = data[0:6]
                self.read_flash_id = read_id
                if self.cfg.has_option('FLASH_CFG', 'flash_para'):
                    flash_para_file = os.path.join(app_path, self.cfg.get('FLASH_CFG', 'flash_para'))
                    self.flash_para_update(flash_para_file, read_id)
                if self.id_valid_flag != '80':
                    if not self.show_identify_fail():
                        return (False, self.flash_burn_retry)
                if self.is_conf_exist(self.read_flash_id) is False:
                    self.error_code_print('003D')
                    return (
                     False, self.flash_burn_retry)
            else:
                self.error_code_print('0030')
                return (
                 False, self.flash_burn_retry)
            result, content = self.run_flash2()
            return (
             result, content)
        return (True, 'continue')

    def fifth_run_step_write_flash_and_check(self):
        """
        Fifth step: write flash and check.
        """
        if self.args.none:
            return (True, self.flash_burn_retry)
        if self.args.write:
            if not self.args.flash:
                if not self.args.efuse:
                    printf('No target select')
                    return (
                     False, self.flash_burn_retry)
            printf('Program operation')
            if self.args.flash:
                flash_para_file = ''
                flash2_para_file = ''
                if self.cfg.has_option('FLASH_CFG', 'flash_para'):
                    flash_para_file = os.path.join(app_path, self.cfg.get('FLASH_CFG', 'flash_para'))
                if self.cfg.has_option('FLASH2_CFG', 'flash2_para'):
                    flash2_para_file = os.path.join(app_path, self.cfg.get('FLASH2_CFG', 'flash2_para'))
                address = self.address_list
                flash_file = self.flash_file_list
                if self.erase == 2:
                    ret = self.flash_chiperase_main_process()
                    if ret is False:
                        return (False, self.flash_burn_retry)
                    self._need_shake_hand = False
                    self.erase = 0
                if len(flash_file) > 0:
                    size_before = 0
                    size_all = 0
                    i = 0
                    for item in flash_file:
                        if self.temp_task_num != None:
                            size_all += os.path.getsize(os.path.join(app_path, convert_path('task' + str(self.temp_task_num) + '/' + item)))
                        else:
                            size_all += os.path.getsize(os.path.join(app_path, convert_path(item)))

                    try:
                        ret = False
                        while i < len(flash_file):
                            if self.temp_task_num != None:
                                flash_file[i] = 'task' + str(self.temp_task_num) + '/' + flash_file[i]
                                size_current = os.path.getsize(os.path.join(app_path, convert_path(flash_file[i])))
                            else:
                                size_current = os.path.getsize(os.path.join(app_path, convert_path(flash_file[i])))
                            if self.callback:
                                self.callback(size_before, size_all, 'program1')
                            else:
                                if self.callback:
                                    self.callback(size_current, size_all, 'program2')
                                printf('Dealing Index ', i)
                                if self.isp_mode_sign is True:
                                    printf('========= programming ', convert_path(flash_file[i]))
                                else:
                                    printf('========= programming ', convert_path(flash_file[i]), ' to 0x', address[i])
                                flash1_bin = ''
                                flash1_bin_len = 0
                                flash2_bin = ''
                                flash2_bin_len = 0
                                flash1_bin, flash1_bin_len, flash2_bin, flash2_bin_len = self.get_flash1_and_flash2(flash_file, address, size_current, i)
                                if flash1_bin != '' and flash2_bin != '':
                                    ret = self.flash_cfg_option(self.read_flash_id, flash_para_file, self.flash_set, self.id_valid_flag, flash1_bin, self.config_file, self.cfg, self.create_img_callback, self.create_simple_callback)
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                    printf('========= programming ', convert_path(flash1_bin), ' to 0x', address[i])
                                    ret = self.flash_load_specified(convert_path(flash1_bin), int(address[i], 16), self.callback)
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                    ret = self.flash_switch_bank_process(1)
                                    self._need_shake_hand = False
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                    ret = self.flash_cfg_option(self.read_flash2_id, flash2_para_file, self.flash2_set, self.id2_valid_flag, flash_file[i], self.config_file, self.cfg, self.create_img_callback, self.create_simple_callback)
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                    printf('========= programming ', convert_path(flash2_bin), ' to 0x%08X' % (int(address[i], 16) + flash1_bin_len))
                                    ret = self.flash_load_specified(convert_path(flash2_bin), int(address[i], 16) + flash1_bin_len, self.callback)
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                else:
                                    if not (self._flash2_en is False or self._flash2_select) is False or int(address[i], 16) < self._flash1_size:
                                        ret = self.flash_cfg_option(self.read_flash_id, flash_para_file, self.flash_set, self.id_valid_flag, flash_file[i], self.config_file, self.cfg, self.create_img_callback, self.create_simple_callback)
                                        if ret is False:
                                            return (False, self.flash_burn_retry)
                                    else:
                                        if self._flash2_select is False:
                                            if int(address[i], 16) >= self._flash1_size:
                                                ret = self.flash_switch_bank_process(1)
                                                self._need_shake_hand = False
                                                if ret is False:
                                                    return (False, self.flash_burn_retry)
                                        ret = self.flash_cfg_option(self.read_flash2_id, flash2_para_file, self.flash2_set, self.id2_valid_flag, flash_file[i], self.config_file, self.cfg, self.create_img_callback, self.create_simple_callback)
                                        if ret is False:
                                            return (False, self.flash_burn_retry)
                                    if 'eflash_loader_cfg.ini' in flash_file[i]:
                                        print('11111')
                                    ret = self.flash_load_specified(convert_path(flash_file[i]), int(address[i], 16), self.callback)
                                    if ret is False:
                                        return (False, self.flash_burn_retry)
                                size_before += os.path.getsize(os.path.join(app_path, convert_path(flash_file[i])))
                                i += 1
                                if self.callback:
                                    self.callback(i, len(flash_file), 'program')
                                self._need_shake_hand = False

                        if self._flash2_select is True:
                            ret = self.flash_switch_bank_process(0)
                            self._need_shake_hand = False
                            if ret is False:
                                return (False, self.flash_burn_retry)
                        printf('Program Finished')
                    except Exception as e:
                        try:
                            printf(e)
                            traceback.print_exc(limit=(self.NUM_ERR), file=(sys.stdout))
                            return (
                             False, self.flash_burn_retry)
                        finally:
                            e = None
                            del e

                else:
                    printf('Warning: No input file to program to flash')
        return (True, 'continue')

    def sixth_run_step_write_efuse(self):
        """
        Sixth step: write efuse.
        """
        if self.args.efuse:
            try:
                if self.config['input_path']['efuse']:
                    efusefile = self.config['input_path']['efuse']
            except:
                efusefile = ''

            if efusefile:
                efuse_file = efusefile
                mask_file = efuse_file.replace('.bin', '_mask.bin')
            else:
                efuse_file = self.cfg.get('EFUSE_CFG', 'file')
                mask_file = self.cfg.get('EFUSE_CFG', 'maskfile')
            if self.temp_task_num != None:
                efuse_file = 'task' + str(self.temp_task_num) + '/' + efuse_file
            efuse_load = True
            efuse_verify = 0
            if self.cfg.has_option('EFUSE_CFG', 'burn_en'):
                efuse_load = self.cfg.get('EFUSE_CFG', 'burn_en') == 'true'
            if self.cfg.has_option('EFUSE_CFG', 'factory_mode'):
                if self.cfg.get('EFUSE_CFG', 'factory_mode') == 'true':
                    efuse_verify = 1
            security_write = self.cfg.get('EFUSE_CFG', 'security_write') == 'true'
            if efuse_load and self.isp_mode_sign is False:
                ret = self.efuse_load_specified(efuse_file, mask_file, bytearray(0), bytearray(0), efuse_verify, security_write)
                if self.callback:
                    self.callback(1, 1, 'APP_WR')
                if ret is False:
                    return (False, self.flash_burn_retry)
            else:
                printf('efuse load disalbe')
            self._need_shake_hand = False
        return (True, 'continue')

    def seventh_run_step_erase(self):
        """
        Seventh step: erase.
        """
        if self.args.erase:
            printf('Erase flash operation')
            if self.end == '0':
                ret = self.flash_chiperase_main_process()
                if ret is False:
                    return (False, self.flash_burn_retry)
            else:
                ret = self.flash_erase_main_process(int(self.start, 16), int(self.end, 16), self._need_shake_hand)
                if ret is False:
                    return (False, self.flash_burn_retry)
            printf('Erase flash OK')
        return (True, 'continue')

    def eighth_run_step_read(self):
        """
        Eighth step: read.
        """
        if self.args.read:
            printf('Read operation')
            if not self.args.flash:
                if not self.args.efuse:
                    printf('No target select')
                    return (
                     False, self.flash_burn_retry)
            if not (self.args.flash and self.start and self.end):
                self.flash_read_jedec_id_process(self.callback)
            else:
                start_addr = int(self.start, 16)
                end_addr = int(self.end, 16)
                ret, readdata = self.flash_read_main_process(start_addr, end_addr - start_addr + 1, self._need_shake_hand, self.file, self.callback)
                if ret is False:
                    return (False, self.flash_burn_retry)
            if self.args.efuse:
                start_addr = int(self.start, 16)
                end_addr = int(self.end, 16)
                if self.efuse_read_main_process(start_addr, end_addr - start_addr + 1, self._need_shake_hand, self.file) is False:
                    return (False, self.flash_burn_retry)
        return (True, 'continue')

    def ninth_run_step_end(self):
        """
        Ninth step: run end.
        """
        self.run_reset_cpu()
        if self.macaddr_check is True:
            self._bootinfo = self.bootinfo
        self._macaddr_check = self._mac_addr
        self._macaddr_check_status = False
        return (
         True, self.flash_burn_retry)

    def set_clear_boot_status(self, shakehand=0):
        pass

    def set_boot_speed(self):
        pass

    def set_load_function(self):
        self.load_function = 2

    def set_decompress_write(self):
        pass

    def get_flash_pin(self):
        return 0

    def show_identify_fail(self):
        return True

    def run_flash2(self):
        return (True, 'continue')

    def get_flash1_and_flash2(self, flash_file, address, size_current, i):
        return ('', 0, '', 0)

    def run_reset_cpu(self):
        pass

    def get_mac_len(self):
        return 6

    def get_isp_sh_time(self):
        return 0

    def write_flash_data(self, file, start_addr, callback):
        pass

    def clear_boot_status(self, shakehand=0):
        printf('Clear boot status at hbn rsvd register')
        if shakehand != 0:
            printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        data = bytearray(12)
        data[0] = 80
        data[1] = 0
        data[2] = 8
        data[3] = 0
        data[4] = 8
        data[5] = 241
        data[6] = 0
        data[7] = 32
        data[8] = 0
        data[9] = 0
        data[10] = 0
        data[11] = 0
        self.bflb_serial_object.write(data)
        self.bflb_serial_object.deal_ack(dmy_data=False)
        return True

    def set_config_file(self, bootheaderFile, imgCreateFile):
        self._efuse_bootheader_file = bootheaderFile
        self._img_create_file = imgCreateFile

    def load_eflash_loader_bin(self):
        """
        This function is used to load eflash loader bin file.
        """
        printf('========= load eflash_loader.bin =========')
        bootinfo = None
        if self.interface == 'jlink':
            printf('Load eflash_loader.bin via jlink')
            self.bflb_serial_object.if_init(self.device, self.speed, self.chip_type, self.chip_name)
            self.bflb_serial_object.reset_cpu()
            imge_fp = open_file(self.eflash_loader_file, 'rb')
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__(('libs.base.' + self.chip_type), fromlist=[self.chip_type])
            load_addr = sub_module.jlink_load_cfg.jlink_load_addr
            self.bflb_serial_object.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            self.bflb_serial_object.set_pc_msp(binascii.hexlify(pc), binascii.hexlify(msp).decode('utf-8'))
            time.sleep(0.01)
            self.bflb_serial_object.if_close()
            return (
             True, bootinfo, '')
        if self.interface == 'openocd':
            printf('Load eflash_loader.bin via openocd')
            self.bflb_serial_object.if_init(self.device, self._bflb_sn_device, self.speed, self.chip_type, self.chip_name)
            self.bflb_serial_object.halt_cpu()
            imge_fp = open_file(self.eflash_loader_file, 'rb')
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__(('libs.base.' + self.chip_type), fromlist=[self.chip_type])
            load_addr = sub_module.openocd_load_cfg.openocd_load_addr
            self.bflb_serial_object.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            self.bflb_serial_object.set_pc_msp(binascii.hexlify(pc), binascii.hexlify(msp).decode('utf-8'))
            return (
             True, bootinfo, '')
        if self.interface == 'cklink':
            printf('Load eflash_loader.bin via cklink')
            self.bflb_serial_object.if_init(self.device, self._bflb_sn_device, self.speed, self.chip_type, self.chip_name)
            self.bflb_serial_object.halt_cpu()
            imge_fp = open_file(self.eflash_loader_file, 'rb')
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__(('libs.base.' + self.chip_type), fromlist=[self.chip_type])
            load_addr = sub_module.openocd_load_cfg.openocd_load_addr
            self.bflb_serial_object.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            self.bflb_serial_object.set_pc_msp(binascii.hexlify(pc), binascii.hexlify(msp).decode('utf-8'))
            self.bflb_serial_object.resume_cpu()
            return (
             True, bootinfo, '')
        if self.interface.lower() == 'uart' or self.interface == 'sdio':
            ret = True
            printf('Load eflash_loader.bin via %s' % self.interface)
            start_time = time.time() * 1000
            ret, bootinfo, res = self._bflb_com_img_loader.img_load_process(self.boot_speed, self.boot_speed, None, self.do_reset, self.reset_hold_time, self.shake_hand_delay, self.reset_revert, self.cutoff_time, self.shake_hand_retry, self.isp_mode_sign, self._isp_shakehand_timeout, True, bootinfo)
            printf('Load helper bin time cost(ms): ', time.time() * 1000 - start_time)
            return (
             ret, bootinfo, res)

    def set_temp_timeout(self):
        self.bflb_serial_object.set_timeout(self._erase_time_out / 1000)

    def get_new_bh_data(self, section, bh_data, fp):
        return b''

    def get_chip_id(self, bootinfo):
        chip_id = bootinfo[34:36] + bootinfo[32:34] + bootinfo[30:32] + bootinfo[28:30] + bootinfo[26:28] + bootinfo[24:26]
        return chip_id

    def get_flash_file_and_address(self):
        result = True
        temp_files = []
        temp_addrs = []
        temp_dict = {}
        temp_set_addrs = []
        for key, value_dict in self.config.items():
            if isinstance(value_dict, dict):
                if 'addr' in value_dict:
                    if value_dict['addr'] in temp_set_addrs:
                        printf('Error: %s has duplicate addresse %s!' % (key, value_dict['addr']))
                        return (
                         False, temp_addrs, temp_files)
                    else:
                        temp_dict[value_dict['addr']] = value_dict['path']
                        temp_set_addrs.append(value_dict['addr'])

        if temp_dict:
            temp_list = sorted((temp_dict.items()), key=(lambda x: int(x[0], 16)
), reverse=False)
            for i in range(len(temp_list)):
                temp_addrs.append(temp_list[i][0].replace('0x', ''))
                temp_files.append(temp_list[i][1])
                if i != 0:
                    temp_length = int(temp_list[i][0], 16) - int(temp_list[i - 1][0], 16)
                    file_length = os.path.getsize(temp_list[i - 1][1])
                    if temp_length < file_length:
                        result = False
                        printf('Error: path: %s  size: %s  range: %s' % (temp_list[i - 1][1], str(file_length), str(temp_length)))
                        printf('Error: The file size exceeds the address space size!')

        return (
         result, temp_addrs, temp_files)

    def get_boot_info(self):
        """
        This function is used to get boot information from chips. At the same time, it can get chip ID.
        """
        printf('========= get_boot_info =========')
        bootinfo = None
        if self.interface == 'uart':
            ret = True
            start_time = time.time() * 1000
            ret, bootinfo = self._bflb_com_img_loader.img_get_bootinfo(self.boot_speed, self.boot_speed, None, self.do_reset, self.reset_hold_time, self.shake_hand_delay, self.reset_revert, self.cutoff_time, self.shake_hand_retry, self.isp_mode_sign, self._isp_shakehand_timeout)
            bootinfo = bootinfo.decode('utf-8')
            chipid = ''
            chipid = self.get_chip_id(bootinfo)
            printf('========= ChipID: ', chipid, ' =========')
            printf('Get bootinfo time cost(ms): ', time.time() * 1000 - start_time)
            return (
             ret, bootinfo, 'OK')
        printf('interface not fit')
        return (
         False, bootinfo, '')

    def error_code_print(self, code):
        set_error_code(code, self.task_num)
        printf('{"ErrorCode": "' + code + '","ErrorMsg":"' + eflash_loader_error_code[code] + '"}')

    def clock_para_update(self, file):
        if os.path.isfile(file) is False:
            efuse_bootheader_path = os.path.join(chip_path, self.chip_name, 'efuse_bootheader')
            efuse_bh_cfg = efuse_bootheader_path + '/efuse_bootheader_cfg.conf'
            sub_module = __import__(('libs.base.' + self.chip_type), fromlist=[self.chip_type])
            section = 'BOOTHEADER_GROUP0_CFG'
            fp = open(efuse_bh_cfg, 'r')
            data = fp.read()
            fp.close()
            if 'BOOTHEADER_CFG' in data:
                section = 'BOOTHEADER_CFG'
            else:
                if 'BOOTHEADER_CPU0_CFG' in data:
                    section = 'BOOTHEADER_CPU0_CFG'
                else:
                    if 'BOOTHEADER_GROUP0_CFG' in data:
                        section = 'BOOTHEADER_GROUP0_CFG'
            bh_data, tmp = bflb_efuse_boothd_create.update_data_from_cfg(sub_module.bootheader_cfg_keys.bootheader_cfg_keys, efuse_bh_cfg, section)
            bh_data = bflb_efuse_boothd_create.bootheader_update_flash_pll_crc(bh_data, self.chip_type)
            fp = open(file, 'wb+')
            self.get_new_bh_data(section, bh_data, fp)
            fp.close()
        fp = open_file(file, 'rb')
        clock_para = bytearray(fp.read())
        fp.close()
        return clock_para

    def clock_pll_set(self, shakehand, irq_en, clk_para):
        printf('Clock PLL set')
        if shakehand != 0:
            printf('clock set shake hand')
            if self.img_load_shake_hand() is False:
                return False
        start_time = time.time() * 1000
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('clk_set')['cmd_id'])
        irq_enable = bytearray(4)
        load_speed = bytearray(4)
        if irq_en:
            irq_enable = b'\x01\x00\x00\x00'
        load_speed = int_to_4bytearray_l(int(self.speed))
        data_send = irq_enable + load_speed + clk_para
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd('clk_set', cmd_id, data_send)
            if ret.startswith('OK'):
                break
            if try_cnt < self._checksum_err_retry_limit:
                printf('Retry')
                try_cnt += 1
            else:
                self.error_code_print('000C')
                return False

        printf('Set clock time cost(ms): ', time.time() * 1000 - start_time)
        self.bflb_serial_object.repeat_init(self.device, self.speed, self.chip_type, self.chip_name)
        self.bflb_serial_object.clear_buf()
        time.sleep(0.01)
        return True

    def efuse_read_mac_addr_process(self, callback=None):
        readdata = bytearray(0)
        macLen = self.get_mac_len()
        if self._need_shake_hand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('efuse_read_mac')['cmd_id'])
        printf('Read mac addr ')
        ret, data_read = self.com_process_one_cmd('efuse_read_mac', cmd_id, bytearray(0))
        if ret.startswith('OK') is False:
            self.error_code_print('0023')
            return (False, None)
        readdata += data_read
        crcarray = get_crc32_bytearray(readdata[:macLen])
        if crcarray != readdata[macLen:macLen + 4]:
            printf(binascii.hexlify(crcarray))
            printf(binascii.hexlify(readdata[macLen:macLen + 4]))
            self.error_code_print('0025')
            return (False, None)
        return (True, readdata[:macLen])

    def flash_set_para_main_process(self, flash_pin, flash_para):
        printf('Set flash config ')
        if flash_para != bytearray(0):
            if flash_para[13:14] == b'\xff':
                printf('Skip set flash para due to flash id is 0xFF')
                return True
        if self._need_shake_hand != 0:
            printf('Flash set para shake hand')
            if self.img_load_shake_hand() is False:
                return False
        start_time = time.time() * 1000
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_set_para')['cmd_id'])
        data_send = int_to_4bytearray_l(flash_pin) + flash_para
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd('flash_set_para', cmd_id, data_send)
            if ret.startswith('OK'):
                break
            if try_cnt < self._checksum_err_retry_limit:
                printf('Retry')
                try_cnt += 1
            else:
                self.error_code_print('003B')
                return False

        printf('Set para time cost(ms): ', time.time() * 1000 - start_time)
        return True

    def flash_read_jedec_id_process(self, callback=None):
        printf('========= flash read jedec ID =========')
        readdata = bytearray(0)
        if self._need_shake_hand is not False:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_read_jid')['cmd_id'])
        ret, data_read = self.com_process_one_cmd('flash_read_jid', cmd_id, bytearray(0))
        printf('Read flash jedec ID ')
        if ret.startswith('OK') is False:
            self.error_code_print('0030')
            return (False, None)
        readdata += data_read
        printf('readdata: ')
        printf(binascii.hexlify(readdata))
        printf('Finished')
        return (
         True, readdata[:4])

    def flash_para_update(self, file, jedec_id):
        flash_para = bytearray(0)
        if self.is_conf_exist(jedec_id) is True:
            sub_module = __import__(('libs.base.' + self.chip_type), fromlist=[self.chip_type])
            cfg_dir = app_path + '/utils/flash/' + self.chip_type + '/'
            conf_name = sub_module.flash_select_do.get_suitable_file_name(cfg_dir, jedec_id)
            offset, flashCfgLen, flash_para, flashCrcOffset, crcOffset = bflb_flash_select.update_flash_para_from_cfg(sub_module.bootheader_cfg_keys.bootheader_cfg_keys, cfg_dir + conf_name)
            fp = open(os.path.join(app_path, file), 'wb+')
            fp.write(flash_para)
            fp.close()
        return flash_para

    def is_conf_exist(self, flash_id):
        cfg_dir = app_path + '/utils/flash/' + self.chip_type + '/'
        conf_name = self.get_suitable_conf_name(cfg_dir, flash_id)
        if os.path.isfile(cfg_dir + conf_name) is False:
            printf('ERROR: Could not find flash configuration for chip')
            printf('File must be at: %s' % cfg_dir + conf_name)
            return False
        return True

    def flash_chiperase_main_process(self):
        printf('Flash Chip Erase All')
        if self._need_shake_hand != 0:
            printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                printf('Shake hand fail')
                return False
        start_time = time.time() * 1000
        self.set_temp_timeout()
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_chiperase')['cmd_id'])
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd('flash_chiperase', cmd_id, bytearray(0))
            if ret.startswith('OK'):
                break
            else:
                if ret.startswith('PD'):
                    printf('erase pending')
                    while True:
                        ret = self.bflb_serial_object.deal_ack()
                        if ret.startswith('PD'):
                            printf('erase pending')
                        else:
                            self.bflb_serial_object.set_timeout(0.02)
                            self.bflb_serial_object.read(1000)
                            break
                        if time.time() * 1000 - start_time > self._erase_time_out:
                            printf('erase timeout')
                            break

                    if ret.startswith('OK'):
                        break
                    if try_cnt < self._checksum_err_retry_limit:
                        printf('Retry')
                        try_cnt += 1
                    else:
                        printf('Erase Fail')
                        self.bflb_serial_object.set_timeout(self._default_time_out)
                        self.error_code_print('0033')
                        return False

        printf('Chip erase time cost(ms): ', time.time() * 1000 - start_time)
        self.bflb_serial_object.set_timeout(self._default_time_out)
        return True

    def flash_cfg_option(self, read_flash_id, flash_para_file, flash_set, id_valid_flag, binfile, cfgfile, cfg, create_img_callback=None, create_simple_callback=None):
        ret = bflb_flash_select.flash_bootheader_config_check(self.chip_type, read_flash_id, convert_path(binfile), flash_para_file)
        if ret is False:
            printf('flashcfg not match first')
            if self.is_conf_exist(read_flash_id) is True:
                update_cfg(cfg, 'FLASH_CFG', 'flash_id', read_flash_id)
                if isinstance(cfgfile, BFConfigParser) == False:
                    cfg.write(cfgfile, 'w+')
                if create_img_callback is not None:
                    create_img_callback()
                else:
                    if create_simple_callback is not None:
                        create_simple_callback()
            else:
                self.error_code_print('003D')
                return False
            ret = bflb_flash_select.flash_bootheader_config_check(self.chip_name, read_flash_id, convert_path(binfile), flash_para_file)
            if ret is False:
                printf('flashcfg not match again')
                self.error_code_print('0040')
                return False
        if flash_para_file:
            if id_valid_flag != '80':
                printf('flash para file: ', flash_para_file)
                fp = open_file(flash_para_file, 'rb')
                flash_para = bytearray(fp.read())
                fp.close()
                ret = self.flash_set_para_main_process(flash_set, flash_para)
                self._need_shake_hand = False
                if ret is False:
                    return False

    def flash_switch_bank_process(self, bank):
        """When the chip has two flashes, switch the flashes according to bank."""
        printf('Flash Switch Bank')
        if self._need_shake_hand != 0:
            printf('Flash switch bank shake hand')
            if self.img_load_shake_hand() is False:
                printf('Shake hand fail')
                return False
        start_time = time.time() * 1000
        self.bflb_serial_object.set_timeout(self._erase_time_out / 1000)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_switch_bank')['cmd_id'])
        data_send = int_to_4bytearray_l(bank)
        ret, dmy = self.com_process_one_cmd('flash_switch_bank', cmd_id, data_send)
        if ret.startswith('OK') is False:
            printf('Switch Fail')
            self.bflb_serial_object.set_timeout(self._default_time_out)
            self.error_code_print('0042')
            return False
        printf('Switch bank time cost(ms): ', time.time() * 1000 - start_time)
        self.bflb_serial_object.set_timeout(self._default_time_out)
        if bank == 0:
            self._flash2_select = False
        else:
            self._flash2_select = True
        return True

    def flash_load_opt(self, file, start_addr, callback=None):
        printf('========= flash load =========')
        if self._need_shake_hand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        if self._flash2_select is True:
            start_addr -= self._flash1_size
        self.write_flash_data(file, start_addr, callback)
        ret = self.flash_load_main_process(file, start_addr, callback)
        if ret is False:
            printf('Flash load fail')
            return ret
        fw_sha256 = ''
        fp = open_file(file, 'rb')
        flash_data = fp.read()
        fp.close()
        flash_data_len = len(flash_data)
        if flash_data_len > 2097152:
            self.bflb_serial_object.set_timeout(2.0 * (flash_data_len / 2097152 + 1))
        sh = hashlib.sha256()
        sh.update(flash_data)
        fw_sha256 = sh.hexdigest()
        fw_sha256 = hexstr_to_bytearray(fw_sha256)
        printf('Sha caled by host: ', binascii.hexlify(fw_sha256).decode('utf-8'))
        del sh
        printf('xip mode Verify')
        ret, read_data = self.flash_xip_read_sha_main_process(start_addr, flash_data_len, 0, None, callback)
        try:
            printf('Sha caled by dev: ', binascii.hexlify(read_data).decode('utf-8'))
        except:
            printf('Sha caled by dev: ', binascii.hexlify(read_data))

        if ret is True and read_data == fw_sha256:
            printf('Verify success')
        else:
            printf('Verify fail')
            self.flash_load_tips()
            self.error_code_print('003E')
            ret = False
        if self.verify > 0:
            fp = open_file(file, 'rb')
            flash_data = bytearray(fp.read())
            fp.close()
            flash_data_len = len(flash_data)
            ret, read_data = self.flash_read_main_process(start_addr, flash_data_len, 0, None, callback)
            if ret is True and read_data == flash_data:
                printf('Verify success')
            else:
                printf('Verify fail')
                self.flash_load_tips()
                self.error_code_print('003E')
                ret = False
            printf('sbus mode Verify')
            ret, read_data = self.flash_read_sha_main_process(start_addr, flash_data_len, 0, None, callback)
            printf('Sha caled by dev: ', binascii.hexlify(read_data).decode('utf-8'))
            if ret is True and read_data == fw_sha256:
                printf('Verify success')
            else:
                printf('Verify fail')
                self.flash_load_tips()
                self.error_code_print('003E')
                ret = False
        self.bflb_serial_object.set_timeout(self._default_time_out)
        return ret

    def flash_load_specified(self, file, start_addr, callback=None):
        ret = False
        run_state = 0
        temp_start_addr = start_addr
        if len(self._skip_len) > 0 and self._skip_len[0] > 0:
            fp = open_file(file, 'rb')
            flash_data = fp.read()
            fp.close()
            flash_data_len = len(flash_data)
            if self._skip_addr[0] > temp_start_addr + flash_data_len or self._skip_addr[-1] + self._skip_len[-1] < temp_start_addr:
                ret = self.flash_load_opt(file, start_addr, callback)
                return ret
            for i in range(len(self._skip_addr)):
                if self._skip_addr[i] <= start_addr:
                    if self._skip_addr[i] + self._skip_len[i] > start_addr and self._skip_addr[i] + self._skip_len[i] < temp_start_addr + flash_data_len:
                        addr = self._skip_addr[i] + self._skip_len[i]
                        start_addr = self._skip_addr[i] + self._skip_len[i]
                    else:
                        if self._skip_addr[i] > start_addr and self._skip_addr[i] + self._skip_len[i] < temp_start_addr + flash_data_len:
                            printf('skip flash file, skip addr 0x%08X, skip len 0x%08X' % (
                             self._skip_addr[i], self._skip_len[i]))
                            addr = start_addr
                            data = flash_data[start_addr - temp_start_addr:self._skip_addr[i] - temp_start_addr]
                            filename, ext = os.path.splitext(file)
                            file_temp = os.path.join(app_path, filename + '_skip' + str(i) + ext)
                            fp = open(file_temp, 'wb')
                            fp.write(data)
                            fp.close()
                            ret = self.flash_load_opt(file_temp, addr, callback)
                            start_addr = self._skip_addr[i] + self._skip_len[i]
                        else:
                            if self._skip_addr[i] > start_addr:
                                if self._skip_addr[i] < temp_start_addr + flash_data_len and self._skip_addr[i] + self._skip_len[i] >= temp_start_addr + flash_data_len:
                                    printf('skip flash file, skip addr 0x%08X, skip len 0x%08X' % (
                                     self._skip_addr[i], self._skip_len[i]))
                                    addr = start_addr
                                    data = flash_data[start_addr - temp_start_addr:self._skip_addr[i] - temp_start_addr]
                                    filename, ext = os.path.splitext(file)
                                    file_temp = os.path.join(app_path, filename + '_skip' + str(i) + ext)
                                    fp = open(file_temp, 'wb')
                                    fp.write(data)
                                    fp.close()
                                    ret = self.flash_load_opt(file_temp, addr, callback)
                                    start_addr = temp_start_addr + flash_data_len
                                else:
                                    if self._skip_addr[i] <= start_addr:
                                        if self._skip_addr[i] + self._skip_len[i] >= temp_start_addr + flash_data_len:
                                            printf('skip flash file, skip addr 0x%08X, skip len 0x%08X' % (
                                             self._skip_addr[i], self._skip_len[i]))
                                            start_addr = temp_start_addr + flash_data_len
                                            return True

            if start_addr < temp_start_addr + flash_data_len:
                addr = start_addr
                data = flash_data[start_addr - temp_start_addr:]
                filename, ext = os.path.splitext(file)
                file_temp = os.path.join(app_path, filename + '_skip' + str(i + 1) + ext)
                fp = open(file_temp, 'wb')
                fp.write(data)
                fp.close()
                ret = self.flash_load_opt(file_temp, addr, callback)
        else:
            ret = self.flash_load_opt(file, start_addr, callback)
        return ret

    def flash_load_main_process(self, file, start_addr, callback=None):
        fp = open_file(file, 'rb')
        flash_data = bytearray(fp.read())
        fp.close()
        flash_data_len = len(flash_data)
        i = 0
        cur_len = 0
        if self.erase == 1:
            ret = self.flash_erase_main_process(start_addr, start_addr + flash_data_len - 1)
            if ret is False:
                return False
        start_time = time.time() * 1000
        log = ''
        if self.decompress_write and flash_data_len > 4096:
            self.bflb_serial_object.set_timeout(30.0)
            start_addr |= 2147483648
            cmd_name = 'flash_decompress_write'
            ret, flash_data, flash_data_len = self.flash_load_xz_compress(file)
            if ret is False:
                printf('Flash write data xz fail')
                self.bflb_serial_object.set_timeout(self._default_time_out)
                return False
            if time.time() * 1000 - start_time > 2200:
                printf(FLASH_LOAD_SHAKE_HAND)
                if self.img_load_shake_hand() is False:
                    return False
            else:
                if time.time() * 1000 - start_time > 1800:
                    time.sleep(0.5)
                    printf(FLASH_LOAD_SHAKE_HAND)
                    if self.img_load_shake_hand() is False:
                        return False
            printf('decompress flash load ', flash_data_len)
        else:
            cmd_name = 'flash_write'
        while i < flash_data_len:
            cur_len = flash_data_len - i
            if cur_len > self._bflb_com_tx_size - 8:
                cur_len = self._bflb_com_tx_size - 8
            cmd_id = hexstr_to_bytearray(self._com_cmds.get(cmd_name)['cmd_id'])
            data_send = int_to_4bytearray_l(i + start_addr) + flash_data[i:i + cur_len]
            start_addr &= 2147483647
            try_cnt = 0
            while True:
                ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
                if ret.startswith('OK'):
                    break
                if try_cnt < self._checksum_err_retry_limit:
                    printf('Retry')
                    try_cnt += 1
                else:
                    self.error_code_print('0036')
                    self.bflb_serial_object.set_timeout(self._default_time_out)
                    return False

            i += cur_len
            log = 'Load ' + str(i) + '/' + str(flash_data_len) + ' {"progress":' + str(i * 100 // flash_data_len) + '}'
            printf(log)
            if callback is not None:
                if flash_data_len > 200:
                    callback(i, flash_data_len, 'APP_WR')

        printf(log)
        if self.flash_write_check_main_process() is False:
            printf('Flash write check fail')
            self.bflb_serial_object.set_timeout(self._default_time_out)
            return False
        self.bflb_serial_object.set_timeout(self._default_time_out)
        printf('Flash load time cost(ms): ', time.time() * 1000 - start_time)
        printf('Finished')
        return True

    def flash_xip_read_sha_main_process(self, start_addr, flash_data_len, shakehand=0, file=None, callback=None):
        readdata = bytearray(0)
        if shakehand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_xip_read_start')['cmd_id'])
        ret, dmy = self.com_process_one_cmd('flash_xip_read_start', cmd_id, bytearray(0))
        if ret.startswith('OK') is False:
            self.error_code_print('0039')
            return (False, None)
        start_time = time.time() * 1000
        log = ''
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_xip_readSha')['cmd_id'])
        data_send = int_to_4bytearray_l(start_addr) + int_to_4bytearray_l(flash_data_len)
        try_cnt = 0
        while True:
            ret, data_read = self.com_process_one_cmd('flash_xip_readSha', cmd_id, data_send)
            if ret.startswith('OK'):
                break
            if try_cnt < self._checksum_err_retry_limit:
                printf('Retry')
                try_cnt += 1
            else:
                printf('Read Fail')
                cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_xip_read_finish')['cmd_id'])
                ret, dmy = self.com_process_one_cmd('flash_xip_read_finish', cmd_id, bytearray(0))
                if ret.startswith('OK') is False:
                    self.error_code_print('0039')
                    return (False, None)
                return (False, None)

        log += 'Read Sha256/' + str(flash_data_len)
        if callback is not None:
            callback(flash_data_len, flash_data_len, 'APP_VR')
        readdata += data_read
        printf(log)
        printf('Flash xip readsha time cost(ms): ', time.time() * 1000 - start_time)
        printf('Finished')
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_xip_read_finish')['cmd_id'])
        ret, dmy = self.com_process_one_cmd('flash_xip_read_finish', cmd_id, bytearray(0))
        if ret.startswith('OK') is False:
            self.error_code_print('0039')
            return (False, None)
        return (True, readdata)

    def flash_read_sha_main_process(self, start_addr, flash_data_len, shakehand=0, file=None, callback=None):
        readdata = bytearray(0)
        if shakehand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        start_time = time.time() * 1000
        log = ''
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_readSha')['cmd_id'])
        data_send = int_to_4bytearray_l(start_addr) + int_to_4bytearray_l(flash_data_len)
        try_cnt = 0
        while True:
            ret, data_read = self.com_process_one_cmd('flash_readSha', cmd_id, data_send)
            if ret.startswith('OK'):
                break
            if try_cnt < self._checksum_err_retry_limit:
                printf('Retry')
                try_cnt += 1
            else:
                self.error_code_print('0038')
                return (False, None)

        log += 'Read Sha256/' + str(flash_data_len)
        if callback is not None:
            callback(flash_data_len, flash_data_len, 'APP_VR')
        readdata += data_read
        printf(log)
        printf('Flash readsha time cost(ms): ', time.time() * 1000 - start_time)
        printf('Finished')
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return (True, readdata)

    def flash_load_xz_compress(self, file):
        try:
            xz_filters = [
             {'id':lzma.FILTER_LZMA2, 
              'dict_size':32768}]
            fp = open_file(file, 'rb')
            data = bytearray(fp.read())
            fp.close()
            flash_data = lzma.compress(data, check=(lzma.CHECK_CRC32), filters=xz_filters)
            flash_data_len = len(flash_data)
        except Exception as e:
            try:
                printf(e)
                return (False, None, None)
            finally:
                e = None
                del e

        return (
         True, flash_data, flash_data_len)

    def flash_load_tips(self):
        printf('########################################################################')
        printf('请按照以下描述排查问题：')
        printf('是否降低烧录波特率到500K测试过')
        printf('烧写文件的大小是否超过Flash所能存储的最大空间')
        printf('Flash是否被写保护')
        printf('########################################################################')

    def flash_erase_main_process(self, start_addr, end_addr, shakehand=0):
        printf('========= flash erase =========')
        printf('Erase flash  from ', hex(start_addr), ' to ', hex(end_addr))
        if shakehand != 0:
            printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                printf('Shake hand fail')
                return False
        start_time = time.time() * 1000
        self.set_temp_timeout()
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_erase')['cmd_id'])
        data_send = int_to_4bytearray_l(start_addr) + int_to_4bytearray_l(end_addr)
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd('flash_erase', cmd_id, data_send)
            if ret.startswith('OK'):
                break
            else:
                if ret.startswith('PD'):
                    printf('erase pending')
                    while True:
                        ret = self.bflb_serial_object.deal_ack()
                        if ret.startswith('PD'):
                            printf('erase pending')
                        else:
                            self.bflb_serial_object.set_timeout(0.02)
                            self.bflb_serial_object.read(1000)
                            break
                        if time.time() * 1000 - start_time > self._erase_time_out:
                            printf('erase timeout')
                            break

                    if ret.startswith('OK'):
                        break
                    if try_cnt < self._checksum_err_retry_limit:
                        printf('Retry')
                        try_cnt += 1
                    else:
                        printf('Erase Fail')
                        self.bflb_serial_object.set_timeout(self._default_time_out)
                        self.error_code_print('0034')
                        return False

        printf('Erase time cost(ms): ', time.time() * 1000 - start_time)
        self.bflb_serial_object.set_timeout(self._default_time_out)
        return True

    def flash_read_main_process(self, start_addr, flash_data_len, shakehand=0, file=None, callback=None):
        printf('========= flash read =========')
        i = 0
        cur_len = 0
        readdata = bytearray(0)
        if shakehand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        start_time = time.time() * 1000
        log = ''
        while i < flash_data_len:
            cur_len = flash_data_len - i
            if cur_len > self._bflb_com_tx_size - 8:
                cur_len = self._bflb_com_tx_size - 8
            else:
                cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_read')['cmd_id'])
                data_send = int_to_4bytearray_l(i + start_addr) + int_to_4bytearray_l(cur_len)
                try_cnt = 0
                while True:
                    ret, data_read = self.com_process_one_cmd('flash_read', cmd_id, data_send)
                    if ret.startswith('OK'):
                        break
                    if try_cnt < self._checksum_err_retry_limit:
                        printf('Retry')
                        try_cnt += 1
                    else:
                        self.error_code_print('0035')
                        return (False, None)

                i += cur_len
                log += 'Read ' + str(i) + '/' + str(flash_data_len)
                if len(log) > 50:
                    printf(log)
                    log = ''
                else:
                    log += '\n'
                if callback is not None:
                    callback(i, flash_data_len, 'APP_VR')
                readdata += data_read

        printf(log)
        printf('Flash read time cost(ms): ', time.time() * 1000 - start_time)
        printf('Finished')
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return (True, readdata)

    def flash_write_check_main_process(self, shakehand=0):
        printf('Write check')
        if shakehand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_write_check')['cmd_id'])
        try_cnt = 0
        while True:
            retry = 0
            if self.decompress_write:
                retry = 10
            ret, dmy = self.com_process_one_cmd('flash_write_check', cmd_id, bytearray(0))
            if ret.startswith('OK'):
                break
            if try_cnt < self._checksum_err_retry_limit + retry:
                printf('Retry')
                try_cnt += 1
            else:
                self.error_code_print('0037')
                return False

        return True

    def efuse_load_specified(self, file, maskfile, efusedata, efusedatamask, verify=0, security_write=False):
        printf('========= efuse load =========')
        if self._need_shake_hand != 0:
            printf('Efuse load shake hand')
            ret = self.img_load_shake_hand()
            if ret is False:
                return False
        ret = self.efuse_load_main_process(file, maskfile, efusedata, efusedatamask, verify, security_write)
        return ret

    def efuse_load_main_process(self, file, maskfile, efusedata, efusedatamask, verify=0, security_write=False):
        if efusedata != bytearray(0):
            printf('Load data')
            efuse_data = efusedata
            mask_data = efusedatamask
        else:
            if file is not None:
                printf('Load file: ', file)
                fp = open_file(file, 'rb')
                efuse_data = bytearray(fp.read()) + bytearray(0)
                fp.close()
                if verify:
                    fp = open_file(maskfile, 'rb')
                    mask_data = bytearray(fp.read()) + bytearray(0)
                    fp.close()
                else:
                    mask_data = bytearray(0)
                if len(efuse_data) > 4096:
                    printf('Decrypt efuse data')
                    efuse_data = efuse_data[4096:]
                    security_key, security_iv = get_security_key()
                    efuse_data = aes_decrypt_data(efuse_data, security_key, security_iv, 0)
            else:
                efuse_data = self._efuse_data
                if verify:
                    mask_data = self._efuse_mask_data
                else:
                    mask_data = bytearray(0)
        if security_write:
            if self.get_ecdh_shared_key() is not True:
                return False
        printf('Load efuse 0')
        if security_write:
            cmd_name = 'efuse_security_write'
        else:
            cmd_name = 'efuse_write'
        cmd_id = hexstr_to_bytearray(self._com_cmds.get(cmd_name)['cmd_id'])
        data_send = efuse_data[0:124] + bytearray(4)
        if security_write:
            data_send = self.ecdh_encrypt_data(data_send)
        data_send = int_to_4bytearray_l(0) + data_send
        ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        if ret.startswith('OK') is False:
            printf('Write Fail')
            self.error_code_print('0021')
            return False
        if verify >= 1:
            ret, read_data = self.efuse_read_main_process(0, 128, shakehand=0, file=None, security_read=security_write)
            if ret is True and self.efuse_compare(read_data, mask_data[0:124] + bytearray(4), efuse_data[0:124] + bytearray(4)):
                printf('Verify success')
            else:
                printf('Read: ')
                printf(binascii.hexlify(read_data[0:124]).decode('utf-8'))
                printf('Expected: ')
                printf(binascii.hexlify(efuse_data[0:124]).decode('utf-8'))
                printf('Verify fail')
                self.error_code_print('0022')
                return False
        data_send = bytearray(12) + efuse_data[124:128]
        if security_write:
            data_send = self.ecdh_encrypt_data(data_send)
        data_send = int_to_4bytearray_l(112) + data_send
        ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        if ret.startswith('OK') is False:
            printf('Write Fail')
            self.error_code_print('0021')
            return False
        if verify >= 1:
            ret, read_data = self.efuse_read_main_process(112, 16, shakehand=0, file=None, security_read=security_write)
            if ret is True and self.efuse_compare(read_data, bytearray(12) + mask_data[124:128], bytearray(12) + efuse_data[124:128]):
                printf('Verify success')
            else:
                printf('Read: ')
                printf(binascii.hexlify(read_data[12:16]))
                printf('Expected: ')
                printf(binascii.hexlify(efuse_data[124:128]))
                printf('Verify fail')
                self.error_code_print('0022')
                return False
        if len(efuse_data) > 128:
            printf('Load efuse 1')
            if security_write:
                cmd_name = 'efuse_security_write'
            else:
                cmd_name = 'efuse_write'
            cmd_id = hexstr_to_bytearray(self._com_cmds.get(cmd_name)['cmd_id'])
            data_send = efuse_data[128:252] + bytearray(4)
            if security_write:
                data_send = self.ecdh_encrypt_data(data_send)
            data_send = int_to_4bytearray_l(128) + data_send
            ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
            if ret.startswith('OK') is False:
                printf('Write Fail')
                self.error_code_print('0021')
                return False
            if verify >= 1:
                ret, read_data = self.efuse_read_main_process(128, 128, shakehand=0, file=None, security_read=security_write)
                if ret is True and self.efuse_compare(read_data, mask_data[128:252] + bytearray(4), efuse_data[128:252] + bytearray(4)):
                    printf('Verify success')
                else:
                    printf('Verify fail')
                    self.error_code_print('0022')
                    return False
            data_send = bytearray(12) + efuse_data[252:256]
            if security_write:
                data_send = self.ecdh_encrypt_data(data_send)
            data_send = int_to_4bytearray_l(240) + data_send
            ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
            if ret.startswith('OK') is False:
                printf('Write Fail')
                self.error_code_print('0021')
                return False
            if verify >= 1:
                ret, read_data = self.efuse_read_main_process(240, 16, shakehand=0, file=None, security_read=security_write)
                if ret is True and self.efuse_compare(read_data, bytearray(12) + mask_data[252:256], bytearray(12) + efuse_data[252:256]):
                    printf('Verify success')
                else:
                    printf('Verify fail')
                    self.error_code_print('0022')
        printf('Finished')
        return True

    def efuse_read_main_process(self, start_addr, data_len, shakehand=0, file=None, security_read=False):
        readdata = bytearray(0)
        if shakehand != 0:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        if security_read:
            cmd_name = 'efuse_security_read'
        else:
            cmd_name = 'efuse_read'
        cmd_id = hexstr_to_bytearray(self._com_cmds.get(cmd_name)['cmd_id'])
        data_send = int_to_4bytearray_l(start_addr) + int_to_4bytearray_l(data_len)
        ret, data_read = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        printf('Read efuse ')
        if ret.startswith('OK') is False:
            self.error_code_print('0020')
            return (False, None)
        readdata += data_read
        if security_read:
            readdata = self.ecdh_decrypt_data(readdata)
        printf('Finished')
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return (True, readdata)

    def efuse_compare(self, read_data, maskdata, write_data):
        i = 0
        for i in range(len(read_data)):
            compare_data = read_data[i] & maskdata[i]
            if compare_data & write_data[i] != write_data[i]:
                printf('compare fail: ', i)
                printf(read_data[i], write_data[i])
                return False

        return True

    def img_load_shake_hand(self):
        isp_sh_time = self.get_isp_sh_time()
        if self.interface.lower() == 'uart':
            self.bflb_serial_object.repeat_init(self.device, self.speed, self.chip_type, self.chip_name)
            if self._bflb_com_img_loader.toggle_boot_or_shake_hand(2, do_reset=False,
              reset_hold_time=100,
              shake_hand_delay=100,
              reset_revert=True,
              cutoff_time=0,
              isp_mode_sign=(self.isp_mode_sign),
              isp_timeout=isp_sh_time,
              boot_load=False,
              shake_hand_retry=2) != 'OK':
                self.error_code_print('0001')
                return False
        else:
            self.bflb_serial_object.if_init(self.device, self.speed, self.chip_type, self.chip_name)
            if self.bflb_serial_object.if_shakehand(do_reset=False, reset_hold_time=100,
              shake_hand_delay=100,
              reset_revert=True,
              cutoff_time=0,
              shake_hand_retry=2,
              isp_timeout=isp_sh_time,
              boot_load=False) != 'OK':
                self.error_code_print('0001')
                return False
        self._need_shake_hand = False
        return True

    def com_process_one_cmd(self, section, cmd_id, data_send):
        data_read = bytearray(0)
        data_len = int_to_2bytearray_l(len(data_send))
        checksum = 0
        checksum += bytearray_to_int(data_len[0:1]) + bytearray_to_int(data_len[1:2])
        for char in data_send:
            checksum += char

        data = cmd_id + int_to_2bytearray_l(checksum & 255)[0:1] + data_len + data_send
        if self.interface.lower() == 'uart':
            self.bflb_serial_object.write(data)
            if section in self._resp_cmds:
                res, data_read = self.bflb_serial_object.deal_response()
            else:
                res = self.bflb_serial_object.deal_ack()
        else:
            self.bflb_serial_object.if_write(data)
            if section in self._resp_cmds:
                res, data_read = self.bflb_serial_object.if_deal_response()
            else:
                res = self.bflb_serial_object.if_deal_ack()
        return (
         res, data_read)

    def get_suitable_conf_name(self, cfg_dir, flash_id):
        conf_files = []
        for home, dirs, files in os.walk(cfg_dir):
            for filename in files:
                if filename.split('_')[-1] == flash_id + '.conf':
                    conf_files.append(filename)

        if len(conf_files) > 1:
            printf('Flash id duplicate and alternative is:')
            for i in range(len(conf_files)):
                tmp = conf_files[i].split('.')[0]
                printf('%d:%s' % (i + 1, tmp))

            return conf_files[i]
        if len(conf_files) == 1:
            return conf_files[0]
        return ''

    def get_ecdh_shared_key(self, shakehand=0):
        printf('========= get ecdh shared key =========')
        publickey_file = 'utils/pem/publickey_uecc.pem'
        if shakehand != 0:
            printf('Shake hand')
            ret = self.img_load_shake_hand()
            if ret is False:
                return
        tmp_ecdh = bflb_ecdh.BflbEcdh()
        self._ecdh_public_key = tmp_ecdh.create_public_key()
        self._ecdh_private_key = binascii.hexlify(tmp_ecdh.ecdh.private_key.to_string()).decode('utf-8')
        printf('ecdh public key')
        printf(self._ecdh_public_key)
        printf('ecdh private key')
        printf(self._ecdh_private_key)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('ecdh_get_pk')['cmd_id'])
        data_send = bytearray.fromhex(self._ecdh_public_key)
        ret, data_read = self.com_process_one_cmd('ecdh_get_pk', cmd_id, data_send)
        if ret.startswith('OK') is True:
            self._ecdh_peer_public_key = binascii.hexlify(data_read).decode('utf-8')
            printf('ecdh peer key')
            printf(self._ecdh_peer_public_key)
            self._ecdh_shared_key = tmp_ecdh.create_shared_key(self._ecdh_peer_public_key[0:128])
            printf('ecdh shared key')
            printf(self._ecdh_shared_key)
            cmd_id = hexstr_to_bytearray(self._com_cmds.get('ecdh_chanllenge')['cmd_id'])
            data_send = bytearray(0)
            ret, data_read = self.com_process_one_cmd('ecdh_chanllenge', cmd_id, data_send)
            if ret.startswith('OK') is True:
                printf('challenge data')
                printf(binascii.hexlify(data_read).decode('utf-8'))
                encrypted_data = data_read[0:32]
                signature = data_read[32:96]
                signature_r = data_read[32:64]
                signature_s = data_read[64:96]
                vk = ecdsa.VerifyingKey.from_pem(open_file('utils\\pem\\room_root_publickey_ecc.pem').read())
                try:
                    ret = vk.verify(signature, (self.ecdh_decrypt_data(encrypted_data)),
                      hashfunc=(hashlib.sha256),
                      sigdecode=(ecdsa.util.sigdecode_string))
                except Exception as err:
                    try:
                        printf(err)
                    finally:
                        err = None
                        del err

                if ret is True:
                    return True
                printf('Challenge verify fail')
                return False
            else:
                printf('Challenge ack fail')
                return False
        else:
            printf('Get shared key fail')
            return False

    def ecdh_encrypt_data(self, data):
        cryptor = AES.new(bytearray.fromhex(self._ecdh_shared_key[0:32]), AES.MODE_CBC, bytearray(16))
        ciphertext = cryptor.encrypt(data)
        return ciphertext

    def ecdh_decrypt_data(self, data):
        cryptor = AES.new(bytearray.fromhex(self._ecdh_shared_key[0:32]), AES.MODE_CBC, bytearray(16))
        plaintext = cryptor.decrypt(data)
        return plaintext

    def close_serial(self):
        if self.bflb_serial_object:
            try:
                self.bflb_serial_object.close()
            except Exception as e:
                try:
                    printf(e)
                finally:
                    e = None
                    del e

    def clear_all_data(self):
        if self.bflb_serial_object:
            try:
                self.bflb_serial_object.clear_buf()
            except Exception as e:
                try:
                    printf(e)
                finally:
                    e = None
                    del e

    def base_reset_cpu(self):
        if self.bflb_serial_object:
            self.bflb_serial_object.reset_cpu()

    def object_status_clear(self):
        self.bootinfo = None
        self._macaddr_check = bytearray(0)
        self._macaddr_check_status = False

    def flash_read_status_reg_process(self, cmd, len, callback=None):
        printf('========= flash read status register =========')
        readdata = bytearray(0)
        if self._need_shake_hand is not False:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, None)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_read_status_reg')['cmd_id'])
        data_send = int_to_4bytearray_l(int(cmd, 16)) + int_to_4bytearray_l(len)
        ret, data_read = self.com_process_one_cmd('flash_read_status_reg', cmd_id, data_send)
        printf('Read flash status register ')
        if ret.startswith('OK') is False:
            self.error_code_print('0031')
            return (False, None)
        readdata += data_read
        printf('readdata: ')
        printf(binascii.hexlify(readdata))
        printf('Finished')
        return (
         True, readdata)

    def flash_write_status_reg_process(self, cmd, len, write_data, callback=None):
        printf('========= flash write status register =========')
        if self._need_shake_hand is not False:
            printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return (False, 'Flash load shake hand fail')
        printf('write_data ', write_data)
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('flash_write_status_reg')['cmd_id'])
        data_send = int_to_4bytearray_l(int(cmd, 16)) + int_to_4bytearray_l(len) + int_to_4bytearray_l(int(write_data, 16))
        ret, data_read = self.com_process_one_cmd('flash_write_status_reg', cmd_id, data_send)
        printf('Write flash status register ')
        if ret.startswith('OK') is False:
            self.error_code_print('0032')
            return (False, 'Write fail')
        printf('Finished')
        return (True, None)

    def bl_get_largest_addr(self, addrs, files):
        maxlen = 0
        datalen = 0
        for i in range(len(addrs)):
            if int(addrs[i], 16) > maxlen:
                maxlen = int(addrs[i], 16)
                if os.path.exists(files[i]):
                    datalen = os.path.getsize(files[i])
                else:
                    datalen = os.path.getsize(os.path.join(app_path, files[i]))

        return maxlen + datalen

    def bl_get_file_data(self, files):
        datas = []
        for file in files:
            if os.path.exists(file):
                temp_path = file
            else:
                temp_path = os.path.join(app_path, file)
            with open(temp_path, 'rb') as fp:
                data = fp.read()
            datas.append(data)

        return datas

    def bl_create_flash_default_data(self, length):
        datas = bytearray(length)
        for i in range(length):
            datas[i] = 255

        return datas

    def bl_write_flash_img(self, d_addrs, d_files, flash_size='1M'):
        whole_img_len = self.bl_get_largest_addr(d_addrs, d_files)
        whole_img_data = self.bl_create_flash_default_data(whole_img_len)
        whole_img_file = os.path.join(chip_path, self.chip_name, 'img_create', 'whole_flash_data.bin')
        if os.path.exists(whole_img_file):
            os.remove(whole_img_file)
        filedatas = self.bl_get_file_data(d_files)
        for i in range(len(d_addrs)):
            start_addr = int(d_addrs[i], 16)
            whole_img_data[start_addr:start_addr + len(filedatas[i])] = filedatas[i]

        if not os.path.exists(os.path.dirname(whole_img_file)):
            os.makedirs(os.path.dirname(whole_img_file))
        fp = open(whole_img_file, 'wb+')
        fp.write(whole_img_data)
        fp.close()

    def get_flash_pin_from_bootinfo(self, chiptype, bootinfo):
        return 128
# okay decompiling ./libs/base/bflb_base_eflash_loader.pyc
