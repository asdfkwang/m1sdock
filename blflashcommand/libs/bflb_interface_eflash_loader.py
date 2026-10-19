# decompyle3 version 3.9.0
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.7.16 (default, Mar 30 2023, 01:25:49) 
# [GCC 12.2.1 20220924]
# Embedded file name: libs/bflb_interface_eflash_loader.py
__doc__ = '\nCreated on 20220909\n\n@author: Dillon\n'
import os, sys, time, traceback, binascii
from libs.base import bflb_img_loader
from libs.bflb_utils import *
from libs.bflb_eflash_loader import *

class InterfaceEflashLoader(object):

    def __init__(self):
        self._temp_task_num = None

    def error_code_print(self, code):
        set_error_code(code, self._temp_task_num)
        printf('{"ErrorCode": "' + code + '","ErrorMsg":"' + eflash_loader_error_code[code] + '"}')

    def get_chip_type(self, interface, device, chip_type, callback):
        if interface.lower() == 'uart' or interface == 'sdio':
            boot_speed = 500000
        else:
            if chip_type == 'bl606p':
                return 'bl808'
            return chip_type
        _bflb_com_img_loader = bflb_img_loader.BflbImgLoader(device, boot_speed, boot_speed, (interface.lower()), callback=callback)
        bflb_serial_object = _bflb_com_img_loader.bflb_serial_object
        try:
            ret, bootinfo = _bflb_com_img_loader.img_get_bootinfo(boot_speed, boot_speed,
              callback=callback,
              do_reset=True,
              reset_hold_time=5,
              shake_hand_delay=100,
              reset_revert=False,
              cutoff_time=100,
              shake_hand_retry=2,
              isp_mode_sign=False,
              isp_timeout=0,
              boot_load=True)
            bootinfo = bootinfo.decode('utf-8')
            bflb_serial_object.close()
            if ret is False:
                _bflb_com_img_loader = bflb_img_loader.BflbImgLoader(device, boot_speed, boot_speed, (interface.lower()), 'bl808', callback=callback)
                bflb_serial_object = _bflb_com_img_loader.bflb_serial_object
                ret, bootinfo = _bflb_com_img_loader.img_get_bootinfo(boot_speed, boot_speed,
                  callback=callback,
                  do_reset=True,
                  reset_hold_time=5,
                  shake_hand_delay=100,
                  reset_revert=False,
                  cutoff_time=100,
                  shake_hand_retry=2,
                  isp_mode_sign=False,
                  isp_timeout=0,
                  boot_load=True)
                bootinfo = bootinfo.decode('utf-8')
                bflb_serial_object.close()
                if ret is False:
                    self.error_code_print('0003')
                    return 'Error: Can not get chip type!!'
            if '01000000' in bootinfo:
                return 'bl602'
            if '01000207' in bootinfo:
                return 'bl702'
            if '01001606' in bootinfo:
                return 'bl616'
            if '01000808' in bootinfo:
                return 'bl808'
            return 'Error: Can not get chip type!!'
        except Exception as e:
            try:
                self.error_code_print('0003')
                return 'Error: Can not get chip type!!'
            finally:
                e = None
                del e

    def judge_result(self, temp_eflash_obj, result, args, start_time):
        do_reset = True
        reset_hold_time = 100
        shake_hand_delay = 100
        reset_revert = True
        cutoff_time = 0
        shake_hand_retry = 2
        if result == 'repeat_burn':
            temp_eflash_obj.close_serial()
            return 'repeat_burn'
        if temp_eflash_obj.cpu_reset is True:
            printf('Reset cpu')
            temp_eflash_obj.base_reset_cpu()
        if temp_eflash_obj.retry_delay_after_cpu_reset > 0:
            printf('delay for uart timeout: ', temp_eflash_obj.retry_delay_after_cpu_reset)
            time.sleep(temp_eflash_obj.retry_delay_after_cpu_reset)
        if result is True:
            printf('All time cost(ms): ', time.time() * 1000 - start_time)
            time.sleep(0.1)
            if not args.none:
                if temp_eflash_obj.bflb_serial_object is not None:
                    temp_eflash_obj.close_serial()
            printf('close interface')
            printf('[All Success]')
            local_log_save('log', temp_eflash_obj.input_macaddr)
            if temp_eflash_obj.bflb_serial_object is not None:
                temp_eflash_obj.close_serial()
            return True
        if temp_eflash_obj.bflb_serial_object is not None:
            temp_eflash_obj.close_serial()
        return False

    def run(self, act, config, callback=None):
        interface = config['param']['interface_type'].lower()
        error = None
        flash_burn_retry = 1
        clear_global()
        try:
            try:
                device = config['param']['comport_uart']
                if interface.lower() == 'uart':
                    speed = config['param']['speed_uart']
                else:
                    speed = config['param']['speed_jlink']
                if not speed.isdigit():
                    error = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                    printf(error)
                    return error
                chip_type = config['param']['chip_type']
                if act == 'download':
                    options = [
                     '--write', '--flash']
                    try:
                        if config['check_box']['efuse']:
                            options.extend(['--efuse'])
                    except:
                        pass

                    parser = eflash_loader_parser_init()
                    args = parser.parse_args(options)
                    start_time = time.time() * 1000
                    if 'Error' in chip_type:
                        error = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB CAN NOT GET CHIP TYPE"}'
                        printf(error)
                        return error
                    config['param']['chip_xtal'] = 'auto'
                    if chip_type == 'bl602':
                        config['param']['chip_xtal'] = '40m'
                        temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl702':
                            config['param']['chip_xtal'] = '32m'
                            temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl702l':
                                config['param']['chip_xtal'] = '32m'
                                temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl808' or chip_type == 'bl606p':
                                    temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                                else:
                                    if chip_type == 'bl616' or chip_type == 'wb03':
                                        temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                                    else:
                                        if chip_type == 'bl628':
                                            temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                        else:
                                            temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
                    while flash_burn_retry:
                        retry = -1
                        if temp_eflash_obj.bflb_serial_object is not None:
                            temp_eflash_obj.close_serial()
                        else:
                            printf('Program Start')
                            result, content = temp_eflash_obj.run_step()
                            self._temp_task_num = temp_eflash_obj.task_num
                            temp_result = self.judge_result(temp_eflash_obj, result, args, start_time)
                            if temp_result:
                                return True
                            printf('Burn Retry')
                            flash_burn_retry -= 1

                    printf('Burn return with retry fail')
                    local_log_save('log', temp_eflash_obj.input_macaddr)
                    error = errorcode_msg(self._temp_task_num)
            except Exception as e:
                try:
                    traceback.print_exc(limit=10, file=(sys.stdout))
                    error = str(e)
                finally:
                    e = None
                    del e

        finally:
            return error

    def program_read_id(self, config, callback=None):
        flash_burn_retry = 1
        interface = config['param']['interface_type']
        device = config['param']['comport_uart']
        if interface.lower() == 'uart':
            speed = config['param']['speed_uart']
        else:
            speed = config['param']['speed_jlink']
        chip_type = config['param']['chip_type']
        try:
            if not (config['param']['speed_uart'].isdigit() and config['param']['speed_jlink'].isdigit()):
                ret = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                printf(ret)
                return (
                 False, ret)
            set_error_code('FFFF')
            start_time = time.time() * 1000
            eflash_loader_cfg_tmp = os.path.join(chip_path, chip_type, 'eflash_loader/eflash_loader_cfg.ini')
            options = ['--none', '--flash', '-c', eflash_loader_cfg_tmp]
            parser_eflash = eflash_loader_parser_init()
            args = parser_eflash.parse_args(options)
            config['param']['chip_xtal'] = 'auto'
            if chip_type == 'bl602':
                config['param']['chip_xtal'] = '40m'
                temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
            else:
                if chip_type == 'bl702':
                    config['param']['chip_xtal'] = '32m'
                    temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                else:
                    if chip_type == 'bl702l':
                        config['param']['chip_xtal'] = '32m'
                        temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl808' or chip_type == 'bl606p':
                            temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl616' or chip_type == 'wb03':
                                temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl628':
                                    temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                else:
                                    temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
            result, content = temp_eflash_obj.run_step()
            ret, data = temp_eflash_obj.flash_read_jedec_id_process()
            temp_eflash_obj.object_status_clear()
            self._temp_task_num = temp_eflash_obj.task_num
            if ret:
                data = binascii.hexlify(data).decode('utf-8')
            if temp_eflash_obj.bflb_serial_object is not None:
                temp_eflash_obj.close_serial()
            return (ret, data)
        except Exception as e:
            try:
                ret = str(e)
                printf('error:' + ret)
                return (
                 False, ret)
            finally:
                e = None
                del e

    def program_read_reg(self, config, callback=None):
        flash_burn_retry = 1
        interface = config['param']['interface_type']
        device = config['param']['comport_uart']
        if interface.lower() == 'uart':
            speed = config['param']['speed_uart']
        else:
            speed = config['param']['speed_jlink']
        chip_type = config['param']['chip_type']
        try:
            if not (config['param']['speed_uart'].isdigit() and config['param']['speed_jlink'].isdigit()):
                ret = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                printf(ret)
                return (
                 False, ret)
            set_error_code('FFFF')
            start_time = time.time() * 1000
            eflash_loader_cfg_tmp = os.path.join(chip_path, chip_type, 'eflash_loader/eflash_loader_cfg.ini')
            options = ['--none', '--flash', '-c', eflash_loader_cfg_tmp]
            parser_eflash = eflash_loader_parser_init()
            args = parser_eflash.parse_args(options)
            config['param']['chip_xtal'] = 'auto'
            if chip_type == 'bl602':
                config['param']['chip_xtal'] = '40m'
                temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
            else:
                if chip_type == 'bl702':
                    config['param']['chip_xtal'] = '32m'
                    temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                else:
                    if chip_type == 'bl702l':
                        config['param']['chip_xtal'] = '32m'
                        temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl808' or chip_type == 'bl606p':
                            temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl616' or chip_type == 'wb03':
                                temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl628':
                                    temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                else:
                                    temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
            result, content = temp_eflash_obj.run_step()
            temp_eflash_obj.object_status_clear()
            cmd = config['cmd']
            length = int(config['len'])
            cmd_value = int(cmd, 16)
            if cmd_value != 5:
                if cmd_value != 53:
                    if cmd_value != 21:
                        temp_eflash_obj.close_serial()
                        ret = 'read register command value not recognize'
                        printf(ret)
                        return (
                         False, ret)
            if length > 3:
                temp_eflash_obj.close_serial()
                ret = 'read register len is too long'
                printf(ret)
                return (
                 False, ret)
            ret, data = temp_eflash_obj.flash_read_status_reg_process(cmd, length)
            if ret:
                data = binascii.hexlify(data).decode('utf-8')
            if temp_eflash_obj.bflb_serial_object is not None:
                temp_eflash_obj.close_serial()
            self._temp_task_num = temp_eflash_obj.task_num
            return (
             ret, data)
        except Exception as e:
            try:
                ret = str(e)
                printf('error:' + ret)
                return (
                 False, ret)
            finally:
                e = None
                del e

    def program_write_reg(self, config, callback=None):
        ret = None
        flash_burn_retry = 1
        interface = config['param']['interface_type']
        device = config['param']['comport_uart']
        if interface.lower() == 'uart':
            speed = config['param']['speed_uart']
        else:
            speed = config['param']['speed_jlink']
        chip_type = config['param']['chip_type']
        try:
            if not device:
                if interface.lower() == 'uart':
                    ret = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB INTERFACE HAS NO COM PORT"}'
                    printf(ret)
                    return (
                     False, ret)
            if not (config['param']['speed_uart'].isdigit() and config['param']['speed_jlink'].isdigit()):
                ret = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                printf(ret)
                return (
                 False, ret)
            set_error_code('FFFF')
            start_time = time.time() * 1000
            eflash_loader_cfg_tmp = os.path.join(chip_path, chip_type, 'eflash_loader/eflash_loader_cfg.ini')
            options = ['--none', '--flash', '-c', eflash_loader_cfg_tmp]
            parser_eflash = eflash_loader_parser_init()
            args = parser_eflash.parse_args(options)
            config['param']['chip_xtal'] = 'auto'
            if chip_type == 'bl602':
                config['param']['chip_xtal'] = '40m'
                temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
            else:
                if chip_type == 'bl702':
                    config['param']['chip_xtal'] = '32m'
                    temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                else:
                    if chip_type == 'bl702l':
                        config['param']['chip_xtal'] = '32m'
                        temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl808' or chip_type == 'bl606p':
                            temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl616' or chip_type == 'wb03':
                                temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl628':
                                    temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                else:
                                    temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
            result, content = temp_eflash_obj.run_step()
            temp_eflash_obj.object_status_clear()
            cmd = config['cmd']
            length = int(config['len'])
            val = config['val']
            cmd_value = int(cmd, 16)
            if cmd_value != 1:
                if cmd_value != 49:
                    if cmd_value != 17:
                        temp_eflash_obj.close_serial()
                        ret = 'write register command value not recognize'
                        printf(ret)
                        return (
                         False, ret)
            if length > 3:
                temp_eflash_obj.close_serial()
                ret = 'write register len is too long'
                printf(ret)
                return (
                 False, ret)
            ret, data = temp_eflash_obj.flash_write_status_reg_process(cmd, length, val)
            temp_eflash_obj.close_serial()
            self._temp_task_num = temp_eflash_obj.task_num
            return (
             ret, data)
        except Exception as e:
            try:
                ret = str(e)
                printf('error:' + ret)
                return (
                 False, ret)
            finally:
                e = None
                del e

    def read_flash_thread(self, config, callback=None):
        ret = None
        flash_burn_retry = 1
        interface = config['param']['interface_type']
        device = config['param']['comport_uart']
        if interface.lower() == 'uart':
            speed = config['param']['speed_uart']
        else:
            speed = config['param']['speed_jlink']
        chip_type = config['param']['chip_type']
        try:
            try:
                if not device:
                    if interface.lower() == 'uart':
                        ret = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB INTERFACE HAS NO COM PORT"}'
                        printf(ret)
                        return (
                         False, ret)
                if not (config['param']['speed_uart'].isdigit() and config['param']['speed_jlink'].isdigit()):
                    ret = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                    printf(ret)
                    return (
                     False, ret)
                set_error_code('FFFF')
                start_time = time.time() * 1000
                eflash_loader_cfg_tmp = os.path.join(chip_path, chip_type, 'eflash_loader/eflash_loader_cfg.ini')
                if verify_hex_num(config['start_addr'][2:]) is True:
                    if config['start_addr'][0:2] == '0x':
                        start = config['start_addr'][2:]
                    else:
                        printf('Error, start_addr is HEX data, must begin with 0x')
                        ret = 'start_addr is HEX data, must begin with 0x'
                else:
                    printf('Error, Please check start_addr hex data')
                    ret = 'Please check start_addr hex data'
                if verify_hex_num(config['end_addr'][2:]) is True:
                    if config['end_addr'][0:2] == '0x':
                        end = config['end_addr'][2:]
                    else:
                        printf('Error, end_addr is HEX data, must begin with 0x')
                        ret = 'end_addr is HEX data, must begin with 0x'
                else:
                    printf('Error, Please check end_addr hex data')
                    ret = 'Please check end_addr hex data'
                if int(start, 16) >= int(end, 16):
                    printf('Error, Start addr must less than end addr')
                    ret = 'Start addr must less than end addr'
                if ret is not None:
                    return ret
                printf('Save as flash.bin')
                options = ['--read', '--flash', '--start=' + start, '--end=' + end, '--file=flash.bin', '-c', eflash_loader_cfg_tmp]
                parser_eflash = eflash_loader_parser_init()
                args = parser_eflash.parse_args(options)
                config['param']['chip_xtal'] = 'auto'
                if chip_type == 'bl602':
                    config['param']['chip_xtal'] = '40m'
                    temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
                else:
                    if chip_type == 'bl702':
                        config['param']['chip_xtal'] = '32m'
                        temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl702l':
                            config['param']['chip_xtal'] = '32m'
                            temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl808' or chip_type == 'bl606p':
                                temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl616' or chip_type == 'wb03':
                                    temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                                else:
                                    if chip_type == 'bl628':
                                        temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                    else:
                                        temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
                result, content = temp_eflash_obj.run_step()
                temp_eflash_obj.object_status_clear()
                self._temp_task_num = temp_eflash_obj.task_num
                temp_result = self.judge_result(temp_eflash_obj, result, args, start_time)
                if temp_result:
                    return True
                printf('Burn Retry')
                flash_burn_retry -= 1
                printf('Burn return with retry fail')
                local_log_save('log', temp_eflash_obj.input_macaddr)
                ret = errorcode_msg(self._temp_task_num)
            except Exception as e:
                try:
                    ret = str(e)
                finally:
                    e = None
                    del e

        finally:
            return ret

    def erase_flash_thread(self, config, callback=None):
        options = ''
        start = ''
        end = ''
        ret = None
        flash_burn_retry = 1
        interface = config['param']['interface_type']
        device = config['param']['comport_uart']
        if interface.lower() == 'uart':
            speed = config['param']['speed_uart']
        else:
            speed = config['param']['speed_jlink']
        chip_type = config['param']['chip_type']
        start_time = time.time() * 1000
        try:
            try:
                if verify_hex_num(config['start_addr'][2:]) is True:
                    if config['start_addr'][0:2] == '0x':
                        start = config['start_addr'][2:]
                    else:
                        printf('Error, start_addr is HEX data, must begin with 0x')
                        ret = 'start_addr is HEX data, must begin with 0x'
                else:
                    if config['whole_chip'] is False:
                        printf('Error, Please check start_addr hex data')
                        ret = 'Please check start_addr hex data'
                if verify_hex_num(config['end_addr'][2:]) is True:
                    if config['end_addr'][0:2] == '0x':
                        end = config['end_addr'][2:]
                    else:
                        printf('Error, end_addr is HEX data, must begin with 0x')
                        ret = 'end_addr is HEX data, must begin with 0x'
                else:
                    if config['whole_chip'] is False:
                        printf('Error, Please check end_addr hex data')
                        ret = 'Please check end_addr hex data'
                if config['whole_chip'] is False:
                    if int(start, 16) >= int(end, 16):
                        printf('Error, Start addr must less than end addr')
                        ret = 'Start addr must less than end addr'
                if ret is not None:
                    return ret
                eflash_loader_cfg_tmp = os.path.join(chip_path, chip_type, 'eflash_loader/eflash_loader_cfg.ini')
                if config['whole_chip'] is True:
                    options = [
                     '--erase','--flash','--end=0','-c',eflash_loader_cfg_tmp]
                else:
                    options = [
                     '--erase', '--flash', '--start=' + start, '--end=' + end, '-c', eflash_loader_cfg_tmp]
                parser_eflash = eflash_loader_parser_init()
                args = parser_eflash.parse_args(options)
                config['param']['chip_xtal'] = 'auto'
                if chip_type == 'bl602':
                    config['param']['chip_xtal'] = '40m'
                    temp_eflash_obj = BL602EflashLoader(chip_type, args, config, callback)
                else:
                    if chip_type == 'bl702':
                        config['param']['chip_xtal'] = '32m'
                        temp_eflash_obj = BL702EflashLoader(chip_type, args, config, callback)
                    else:
                        if chip_type == 'bl702l':
                            config['param']['chip_xtal'] = '32m'
                            temp_eflash_obj = BL702LEflashLoader(chip_type, args, config, callback)
                        else:
                            if chip_type == 'bl808' or chip_type == 'bl606p':
                                temp_eflash_obj = BL808EflashLoader(chip_type, args, config, callback)
                            else:
                                if chip_type == 'bl616' or chip_type == 'wb03':
                                    temp_eflash_obj = BL616EflashLoader(chip_type, args, config, callback)
                                else:
                                    if chip_type == 'bl628':
                                        temp_eflash_obj = BL628EflashLoader(chip_type, args, config, callback)
                                    else:
                                        temp_eflash_obj = OtherEflashLoader(chip_type, args, config, callback)
                result, content = temp_eflash_obj.run_step()
                temp_eflash_obj.object_status_clear()
                self._temp_task_num = temp_eflash_obj.task_num
                temp_result = self.judge_result(temp_eflash_obj, result, args, start_time)
                if temp_result:
                    return True
                printf('Burn Retry')
                flash_burn_retry -= 1
                printf('Burn return with retry fail')
                local_log_save('log', temp_eflash_obj.input_macaddr)
                ret = errorcode_msg(self._temp_task_num)
            except Exception as e:
                try:
                    ret = str(e)
                finally:
                    e = None
                    del e

        finally:
            return ret


if __name__ == '__main__':
    act = 'download'
    config_value_dict = {
      'interface_type': 'uart',
      'comport_uart': 'COM28',
      'speed_uart': '2000000',
      'chip_xtal': '40M',
      'verify': 'False',
      'ckb_erase_all': 'False'}
    config = {'param': config_value_dict}
    iel = InterfaceEflashLoader()
    iel.run(act, config)
# okay decompiling ./libs/bflb_interface_eflash_loader.pyc
