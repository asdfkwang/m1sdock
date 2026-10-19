# decompyle3 version 3.9.0
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.7.16 (default, Mar 30 2023, 01:25:49) 
# [GCC 12.2.1 20220924]
# Embedded file name: libs/bflb_eflash_loader.py
from libs.bflb_utils import *
from libs.bflb_configobj import BFConfigParser
from libs.base.bflb_base_eflash_loader import BaseEflashLoader
FLASH_ERASE_SHAKE_HAND = 'Flash erase shake hand'
FLASH_LOAD_SHAKE_HAND = 'Flash load shake hand'

class BL602EflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl602, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def set_load_function(self):
        self.load_function = 1

    def get_flash_pin(self):
        return 255

    def show_identify_fail(self):
        printf('eflash loader identify flash fail!')
        self.error_code_print('0043')
        return False

    def set_temp_timeout(self):
        self.bflb_serial_object.set_timeout(self._default_time_out)

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class BL616EflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl616, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def run_flash2(self):
        """
        If chip is bl616 or wb03, it will run this function.
        """
        if self.cfg.has_option('FLASH2_CFG', 'flash2_en'):
            self._flash2_en = self.cfg.get('FLASH2_CFG', 'flash2_en') == 'true'
            if self._flash2_en is True:
                self._flash1_size = int(self.cfg.get('FLASH2_CFG', 'flash1_size')) * 1024 * 1024
                self._flash2_size = int(self.cfg.get('FLASH2_CFG', 'flash2_size')) * 1024 * 1024
                printf('flash2 set para')
                flash2_pin = 0
                flash2_clock_cfg = 0
                flash2_io_mode = 0
                flash2_clk_delay = 0
                if self.cfg.get('FLASH2_CFG', 'flash2_pin'):
                    flash_pin_cfg = self.cfg.get('FLASH2_CFG', 'flash2_pin')
                    if flash_pin_cfg.startswith('0x'):
                        flash2_pin = int(flash_pin_cfg, 16)
                    else:
                        flash2_pin = int(flash_pin_cfg, 10)
                if self.cfg.has_option('FLASH2_CFG', 'flash2_clock_cfg'):
                    clock_div_cfg = self.cfg.get('FLASH2_CFG', 'flash2_clock_cfg')
                    if clock_div_cfg.startswith('0x'):
                        flash2_clock_cfg = int(clock_div_cfg, 16)
                    else:
                        flash2_clock_cfg = int(clock_div_cfg, 10)
                if self.cfg.has_option('FLASH2_CFG', 'flash2_io_mode'):
                    io_mode_cfg = self.cfg.get('FLASH2_CFG', 'flash2_io_mode')
                    if io_mode_cfg.startswith('0x'):
                        flash2_io_mode = int(io_mode_cfg, 16)
                    else:
                        flash2_io_mode = int(io_mode_cfg, 10)
                if self.cfg.has_option('FLASH2_CFG', 'flash2_clock_delay'):
                    clk_delay_cfg = self.cfg.get('FLASH2_CFG', 'flash2_clock_delay')
                    if clk_delay_cfg.startswith('0x'):
                        flash2_clk_delay = int(clk_delay_cfg, 16)
                    else:
                        flash2_clk_delay = int(clk_delay_cfg, 10)
                self.flash2_set = (flash2_pin << 0) + (flash2_clock_cfg << 8) + (flash2_io_mode << 16) + (flash2_clk_delay << 24)
                if self.load_function == 2:
                    printf('set flash2 cfg: %X' % self.flash2_set)
                    ret = self.flash_set_para_main_process(self.flash2_set, bytearray(0))
                    self._need_shake_hand = False
                    if ret is False:
                        return (False, self.flash_burn_retry)
                ret = self.flash_switch_bank_process(1)
                self._need_shake_hand = False
                if ret is False:
                    return (False, self.flash_burn_retry)
                ret, data = self.flash_read_jedec_id_process()
                if ret:
                    self._need_shake_hand = False
                    data = binascii.hexlify(data).decode('utf-8')
                    self.id2_valid_flag = data[6:]
                    read_id2 = data[0:6]
                    self.read_flash2_id = read_id2
                    if self.cfg.has_option('FLASH2_CFG', 'flash2_para'):
                        flash2_para_file = os.path.join(app_path, self.cfg.get('FLASH2_CFG', 'flash2_para'))
                        self.flash_para_update(flash2_para_file, read_id2)
                        fp = open_file(flash2_para_file, 'rb')
                        para_data = bytearray(fp.read())
                        fp.close()
                        para_data[0:1] = b'\x11'
                        fp = open_file(flash2_para_file, 'wb+')
                        fp.write(para_data)
                        fp.close()
                else:
                    self.error_code_print('0030')
                    return (
                     False, self.flash_burn_retry)
                ret = self.flash_switch_bank_process(0)
                self._need_shake_hand = False
                if ret is False:
                    return (False, self.flash_burn_retry)
        return (True, 'continue')

    def get_flash1_and_flash2(self, flash_file, address, size_current, i):
        if self._flash1_size != 0:
            if self._flash1_size < int(address[i], 16) + size_current:
                if self._flash1_size > int(address[i], 16):
                    if self._flash2_select is False:
                        printf('%s file is overflow with flash1' % flash_file[i])
                        flash1_bin, flash1_bin_len, flash2_bin, flash2_bin_len = self.flash_loader_cut_flash_bin(flash_file[i], int(address[i], 16), self._flash1_size)
                        return (
                         flash1_bin, flash1_bin_len, flash2_bin, flash2_bin_len)
        return ('', 0, '', 0)

    def set_clear_boot_status(self, shakehand=0):
        self.clear_boot_status(shakehand)

    def get_new_bh_data(self, section, bh_data, fp):
        if section == 'BOOTHEADER_GROUP0_CFG':
            fp.write(bh_data[100:120])

    def write_flash_data(self, file, start_addr, callback):
        pass

    def get_flash_pin_from_bootinfo(self, chiptype, bootinfo):
        sw_usage_data = bootinfo[22:24] + bootinfo[20:22] + bootinfo[18:20] + bootinfo[16:18]
        sw_usage_data = int(sw_usage_data, 16)
        return sw_usage_data >> 14 & 63

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class BL628EflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl628, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def set_clear_boot_status(self, shakehand=0):
        self.clear_boot_status(shakehand)

    def get_new_bh_data(self, section, bh_data, fp):
        if section == 'BOOTHEADER_GROUP0_CFG':
            fp.write(bh_data[100:124])

    def write_flash_data(self, file, start_addr, callback):
        pass

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class BL702EflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl702, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def set_load_function(self):
        if self.chip_type == 'bl702':
            self.load_function = 0

    def set_decompress_write(self):
        self.decompress_write = False

    def get_flash_pin(self):
        return 255

    def show_identify_fail(self):
        printf('eflash loader identify flash fail!')
        self.error_code_print('0043')
        return False

    def reset_cpu(self, shakehand=0):
        printf('CPU Reset')
        if shakehand != 0:
            printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('reset')['cmd_id'])
        ret, dmy = self.com_process_one_cmd('reset', cmd_id, bytearray(0))
        if ret.startswith('OK'):
            return True
        self.error_code_print('0004')
        return False

    def run_reset_cpu(self):
        if self.isp_mode_sign is True:
            self.reset_cpu()

    def get_chip_id(self, bootinfo):
        chip_id = bootinfo[32:34] + bootinfo[34:36] + bootinfo[36:38] + bootinfo[38:40] + bootinfo[40:42] + bootinfo[42:44] + bootinfo[44:46] + bootinfo[46:48]
        return chip_id

    def get_mac_len(self):
        return 8

    def set_temp_timeout(self):
        self.bflb_serial_object.set_timeout(self._default_time_out)

    def get_isp_sh_time(self):
        return self._isp_shakehand_timeout

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class BL702LEflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl702l, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def reset_cpu(self, shakehand=0):
        printf('CPU Reset')
        if shakehand != 0:
            printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        cmd_id = hexstr_to_bytearray(self._com_cmds.get('reset')['cmd_id'])
        ret, dmy = self.com_process_one_cmd('reset', cmd_id, bytearray(0))
        if ret.startswith('OK'):
            return True
        self.error_code_print('0004')
        return False

    def run_reset_cpu(self):
        if self.isp_mode_sign is True:
            self.reset_cpu()

    def get_chip_id(self, bootinfo):
        chip_id = bootinfo[32:34] + bootinfo[34:36] + bootinfo[36:38] + bootinfo[38:40] + bootinfo[40:42] + bootinfo[42:44] + bootinfo[44:46] + bootinfo[46:48]
        return chip_id

    def get_new_bh_data(self, section, bh_data, fp):
        if section == 'BOOTHEADER_CFG':
            fp.write(bh_data[100:116])

    def get_mac_len(self):
        return 8

    def set_temp_timeout(self):
        self.bflb_serial_object.set_timeout(self._default_time_out)

    def get_isp_sh_time(self):
        return self._isp_shakehand_timeout

    def get_flash_pin_from_bootinfo(self, chiptype, bootinfo):
        dev_info_data = bootinfo[30:32] + bootinfo[28:30] + bootinfo[26:28] + bootinfo[24:26]
        dev_info_data = int(dev_info_data, 16)
        flash_cfg = dev_info_data >> 26 & 7
        sf_reverse = dev_info_data >> 29 & 1
        sf_swap_cfg = dev_info_data >> 22 & 3
        if flash_cfg == 0:
            return 0
        if sf_reverse == 0:
            return sf_swap_cfg + 1
        return sf_swap_cfg + 5

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class BL808EflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is bl808, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def set_clear_boot_status(self, shakehand=0):
        self.clear_boot_status(shakehand)

    def get_new_bh_data(self, section, bh_data, fp):
        if section == 'BOOTHEADER_GROUP0_CFG':
            fp.write(bh_data[100:128])

    def write_flash_data(self, file, start_addr, callback):
        fp = open_file(file, 'rb')
        flash_data = bytearray(fp.read())
        fp.close()
        flash_data_len = len(flash_data)
        end_addr = start_addr + flash_data_len - 1
        if start_addr <= 4096:
            if end_addr > 4096:
                ret, flash_read_data = self.flash_read_main_process(4096, 4096, 0, None, callback)
                if flash_read_data[0:4] == int_to_4bytearray_b(1112298054):
                    printf('RF para already write at flash 0x1000 addr, replace it.')
                    flash_data[4096:8192] = flash_read_data[0:4096]
                    fp = open_file(file, 'wb')
                    fp.write(flash_data)
                    fp.close()

    def is_conf_exist(self, flash_id):
        cfg_dir = app_path + '/utils/flash/bl808/'
        conf_name = self.get_suitable_conf_name(cfg_dir, flash_id)
        if os.path.isfile(cfg_dir + conf_name) is False:
            return False
        return True

    def get_flash_pin_from_bootinfo(self, chiptype, bootinfo):
        sw_usage_data = bootinfo[22:24] + bootinfo[20:22] + bootinfo[18:20] + bootinfo[16:18]
        sw_usage_data = int(sw_usage_data, 16)
        return sw_usage_data >> 14 & 31

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)


class OtherEflashLoader(BaseEflashLoader):
    __doc__ = '\n    When chip is not bl602,bl702,bl702l,bl808,bl616.wb03, eflash Loader\n    '

    def __init__(self, chip_type, args, config, callback=None, macaddr_callback=None, create_simple_callback=None, create_img_callback=None, task_num=None):
        super().__init__(chip_type, args, config, callback, macaddr_callback, create_simple_callback, create_img_callback, task_num)
        self.chip_type = chip_type

    def run_step(self):
        result, content = self.first_run_step_load_parameter()
        if not result or content != 'continue':
            return (result, content)
        if self.isp_mode_sign is True:
            self.load_function = 1
        result, content = self.second_run_step_shake_hand()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.third_run_step_read_mac_address()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fourth_run_step_interact_chip()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.fifth_run_step_write_flash_and_check()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.sixth_run_step_write_efuse()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.seventh_run_step_erase()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.eighth_run_step_read()
        if not result or content != 'continue':
            return (result, content)
        result, content = self.ninth_run_step_end()
        return (
         result, content)
# okay decompiling ./libs/bflb_eflash_loader.pyc
