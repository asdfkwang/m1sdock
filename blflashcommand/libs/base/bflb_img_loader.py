import os
import sys
import time
import hashlib
import binascii
import traceback
import threading
from Crypto.Cipher import AES
from libs import bflb_utils
from libs.base import bflb_img_create
from libs.base import bflb_serial
import config as gol
from libs.bflb_utils import app_path

class BflbImgLoader(object):

    def __init__(self, device, speed, boot_speed, interface='uart', chip_type='bl602', chip_name='bl602', eflash_loader_file1='', eflash_loader_file2='', callback=None, do_reset=False, reset_hold_time=100, shake_hand_delay=100, reset_revert=True, cutoff_time=0, shake_hand_retry=2, isp_mode_sign=False, isp_timeout=0, encrypt_key=None, encrypt_iv=None, public_key=None, private_key=None):
        self._device = device
        self._speed = speed
        self._interface = interface.lower()
        self._chip_type = chip_type
        self._chip_name = chip_name
        self._eflash_loader_file1 = eflash_loader_file1
        self._eflash_loader_file2 = eflash_loader_file2
        self._callback = callback
        self._do_reset = do_reset
        self._reset_hold_time = reset_hold_time
        self._shake_hand_delay = shake_hand_delay
        self._reset_revert = reset_revert
        self._cutoff_time = cutoff_time
        self._shake_hand_retry = shake_hand_retry
        self._isp_mode_sign = isp_mode_sign
        self._isp_timeout = isp_timeout
        self._boot_speed = boot_speed
        self.encrypt_key = encrypt_key
        self.encrypt_iv = encrypt_iv
        self.public_key = public_key
        self.private_key = private_key
        self._boot_load = True
        self._record_bootinfo = None
        self.bflb_serial_object = None
        self._imge_fp = None
        self._segcnt = 0
        self._602a0_dln_fix = False
        self.isp_baudrate = 2000000
        if interface == 'uart':
            self.bflb_serial_object = bflb_serial.BLSerialUart(rts_state=True, dtr_state=True)
        self._bootrom_cmds = {'get_chip_id': {'cmd_id': '05', 'data_len': '0000', 'callback': None}, 'get_boot_info': {'cmd_id': '10', 'data_len': '0000', 'callback': None}, 'load_boot_header': {'cmd_id': '11', 'data_len': '00b0', 'callback': None}, '808_load_boot_header': {'cmd_id': '11', 'data_len': '0160', 'callback': None}, '628_load_boot_header': {'cmd_id': '11', 'data_len': '0100', 'callback': None}, '616_load_boot_header': {'cmd_id': '11', 'data_len': '0100', 'callback': None}, '702l_load_boot_header': {'cmd_id': '11', 'data_len': '00F0', 'callback': None}, 'load_publick_key': {'cmd_id': '12', 'data_len': '0044', 'callback': None}, 'load_publick_key2': {'cmd_id': '13', 'data_len': '0044', 'callback': None}, 'load_signature': {'cmd_id': '14', 'data_len': '0004', 'callback': None}, 'load_signature2': {'cmd_id': '15', 'data_len': '0004', 'callback': None}, 'load_aes_iv': {'cmd_id': '16', 'data_len': '0014', 'callback': None}, 'load_seg_header': {'cmd_id': '17', 'data_len': '0010', 'callback': None}, 'load_seg_data': {'cmd_id': '18', 'data_len': '0100', 'callback': None}, 'check_image': {'cmd_id': '19', 'data_len': '0000', 'callback': None}, 'run_image': {'cmd_id': '1a', 'data_len': '0000', 'callback': None}, 'change_rate': {'cmd_id': '20', 'data_len': '0008', 'callback': None}, 'reset': {'cmd_id': '21', 'data_len': '0000', 'callback': None}, 'flash_erase': {'cmd_id': '30', 'data_len': '0000', 'callback': None}, 'flash_write': {'cmd_id': '31', 'data_len': '0100', 'callback': None}, 'flash_read': {'cmd_id': '32', 'data_len': '0100', 'callback': None}, 'flash_boot': {'cmd_id': '33', 'data_len': '0000', 'callback': None}, 'efuse_write': {'cmd_id': '40', 'data_len': '0080', 'callback': None}, 'efuse_read': {'cmd_id': '41', 'data_len': '0000', 'callback': None}}

    def close_port(self):
        if self.bflb_serial_object is not None:
            self.bflb_serial_object.close()

    def boot_process_load_cmd(self, section, read_len):
        read_data = bytearray(0)
        if read_len != 0:
            read_data = bytearray(self._imge_fp.read(read_len))
            if len(read_data) != read_len:
                bflb_utils.printf('read error,expected len=', read_len, 'read len=', len(read_data))
                return bytearray(0)
            if section == 'load_boot_header':
                tmp = bflb_utils.bytearray_reverse(read_data[120:124])
                self._segcnt = bflb_utils.bytearray_to_int(tmp)
                bflb_utils.printf('segcnt is ', self._segcnt)
            elif section == '808_load_boot_header':
                tmp = bflb_utils.bytearray_reverse(read_data[140:144])
                self._segcnt = bflb_utils.bytearray_to_int(tmp)
                bflb_utils.printf('segcnt is ', self._segcnt)
            elif section == '628_load_boot_header':
                tmp = bflb_utils.bytearray_reverse(read_data[136:140])
                self._segcnt = bflb_utils.bytearray_to_int(tmp)
                bflb_utils.printf('segcnt is ', self._segcnt)
            elif section == '616_load_boot_header':
                tmp = bflb_utils.bytearray_reverse(read_data[132:136])
                self._segcnt = bflb_utils.bytearray_to_int(tmp)
                bflb_utils.printf('segcnt is ', self._segcnt)
            elif section == '702l_load_boot_header':
                tmp = bflb_utils.bytearray_reverse(read_data[120:124])
                self._segcnt = bflb_utils.bytearray_to_int(tmp)
                bflb_utils.printf('segcnt is ', self._segcnt)
            if section == 'load_signature' or section == 'load_signature2':
                tmp = bflb_utils.bytearray_reverse(read_data[0:4])
                sig_len = bflb_utils.bytearray_to_int(tmp)
                read_data = read_data + bytearray(self._imge_fp.read(sig_len + 4))
                if len(read_data) != sig_len + 8:
                    bflb_utils.printf('read signature error,expected len=', sig_len + 4, 'read len=', len(read_data))
        return read_data

    def boot_process_one_cmd(self, section, cmd_id, cmd_len):
        read_len = bflb_utils.bytearray_to_int(cmd_len)
        read_data = self._bootrom_cmds.get(section)['callback'](section, read_len)
        tmp = bytearray(2)
        tmp[0] = cmd_len[1]
        tmp[1] = cmd_len[0]
        data_read = bytearray(0)
        tmp = bflb_utils.int_to_2bytearray_l(len(read_data))
        data = cmd_id + bytearray(1) + tmp + read_data
        if self._chip_type == 'bl702' and section == 'run_image':
            sub_module = __import__('libs.base.' + self._chip_type, fromlist=[self._chip_type])
            data = sub_module.chiptype_patch.img_load_create_predata_before_run_img()
        self.bflb_serial_object.write(data)
        if section == 'get_boot_info' or section == 'load_seg_header' or section == 'get_chip_id':
            (res, data_read) = self.bflb_serial_object.deal_response()
        else:
            res = self.bflb_serial_object.deal_ack()
        if res.startswith('OK') is True:
            pass
        else:
            try:
                bflb_utils.printf('result: ', res)
            except IOError:
                bflb_utils.printf('python IO error')
        return (res, data_read)

    def boot_process_one_section(self, section, data_len):
        cmd_id = bflb_utils.hexstr_to_bytearray(self._bootrom_cmds.get(section)['cmd_id'])
        if data_len == 0:
            length = bflb_utils.hexstr_to_bytearray(self._bootrom_cmds.get(section)['data_len'])
        else:
            length = bflb_utils.int_to_2bytearray_b(data_len)
        return self.boot_process_one_cmd(section, cmd_id, length)

    def boot_inf_change_rate(self, comnum, section, newrate):
        cmd_id = bflb_utils.hexstr_to_bytearray(self._bootrom_cmds.get(section)['cmd_id'])
        cmd_len = bflb_utils.hexstr_to_bytearray(self._bootrom_cmds.get(section)['data_len'])
        bflb_utils.printf('process', section, ',cmd=', binascii.hexlify(cmd_id), ',data len=', binascii.hexlify(cmd_len))
        baudrate = self.bflb_serial_object.if_get_rate()
        oldv = bflb_utils.int_to_4bytearray_l(baudrate)
        newv = bflb_utils.int_to_4bytearray_l(newrate)
        tmp = bytearray(3)
        tmp[1] = cmd_len[1]
        tmp[2] = cmd_len[0]
        data = cmd_id + tmp + oldv + newv
        self.bflb_serial_object.if_write(data)
        bflb_utils.printf()
        stime = 110/float(baudrate)*2
        if stime < 0.003:
            stime = 0.003
        time.sleep(stime)
        self.bflb_serial_object.if_close()
        self.bflb_serial_object.if_init(comnum, newrate, self._chip_type, self._chip_name)
        return self.bflb_serial_object.if_deal_ack(dmy_data=False)

    def boot_install_cmds_callback(self):
        self._bootrom_cmds.get('get_chip_id')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('get_boot_info')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_boot_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('808_load_boot_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('628_load_boot_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('616_load_boot_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('702l_load_boot_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_publick_key')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_publick_key2')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_signature')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_signature2')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_aes_iv')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_seg_header')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('load_seg_data')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('check_image')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('run_image')['callback'] = self.boot_process_load_cmd
        self._bootrom_cmds.get('reset')['callback'] = self.boot_process_load_cmd

    def issue_log_print(self):
        bflb_utils.printf('########################################################################')
        bflb_utils.printf('请按照以下描述排查问题：')
        if self._chip_type == 'bl60x':
            bflb_utils.printf('GPIO24是否上拉到板子自身的3.3V，而不是外部的3.3V')
            bflb_utils.printf('GPIO7(RX)是否连接到USB转串口的TX引脚')
            bflb_utils.printf('GPIO14(TX)是否连接到USB转串口的RX引脚')
            bflb_utils.printf('在使用烧录软件进行烧录前，是否在GPIO24拉高的情况下，使用Reset/Chip_En复位了芯片')
        elif self._chip_type == 'bl602':
            bflb_utils.printf('GPIO8是否上拉到板子自身的3.3V，而不是外部的3.3V')
            bflb_utils.printf('GPIO7(RX)是否连接到USB转串口的TX引脚')
            bflb_utils.printf('GPIO16(TX)是否连接到USB转串口的RX引脚')
            bflb_utils.printf('在使用烧录软件进行烧录前，是否在GPIO8拉高的情况下，使用Reset/Chip_En复位了芯片')
        elif self._chip_type == 'bl702':
            bflb_utils.printf('GPIO28是否上拉到板子自身的3.3V，而不是外部的3.3V')
            bflb_utils.printf('GPIO15(RX)是否连接到USB转串口的TX引脚')
            bflb_utils.printf('GPIO14(TX)是否连接到USB转串口的RX引脚')
            bflb_utils.printf('在使用烧录软件进行烧录前，是否在GPIO28拉高的情况下，使用Reset/Chip_En复位了芯片')
        else:
            bflb_utils.printf('Boot pin是否上拉到板子自身的3.3V，而不是外部的3.3V')
            bflb_utils.printf('UART RX是否连接到USB转串口的TX引脚')
            bflb_utils.printf('UART TX是否连接到USB转串口的RX引脚')
            bflb_utils.printf('在使用烧录软件进行烧录前，是否在Boot pin拉高的情况下，使用Reset/Chip_En复位了芯片')
        bflb_utils.printf('烧录软件所选择的COM口，是否是连接芯片的串口')
        bflb_utils.printf('烧录软件上选择的波特率是否是USB转串口支持的波特率')
        bflb_utils.printf('3.3V供电是否正常')
        bflb_utils.printf('板子供电电流是否正常(烧录模式下，芯片耗电电流5-7mA)')
        bflb_utils.printf('########################################################################')

    def send_55_command(self, speed):
        try:
            while True:
                if self._shakehand_flag is True:
                    break
                if self._chip_type == 'bl702' or self._chip_type == 'bl702l':
                    self.bflb_serial_object.write(self.get_sync_bytes(int(0.003*speed/10)))
                else:
                    self.bflb_serial_object.write(self.get_sync_bytes(int(0.006*speed/10)))
        except Exception as e:
            bflb_utils.printf('Error: %s' % e)

    def get_sync_bytes(self, length):
        try:
            data = bytearray(length)
            i = 0
            while i < length:
                data[i] = 85
                i += 1
            return data
        except Exception as e:
            bflb_utils.printf('Error: %s' % e)

    def set_isp_baudrate(self, isp_baudrate):
        bflb_utils.printf('isp mode speed: ', isp_baudrate)
        self.isp_baudrate = isp_baudrate

    def toggle_boot_or_shake_hand(self, run_sign, do_reset=False, reset_hold_time=100, shake_hand_delay=100, reset_revert=True, cutoff_time=0, isp_mode_sign=False, isp_timeout=0, boot_load=False, shake_hand_retry=2):
        '''
        When run_sign is 2, it run shakehand.
        '''
        device = self._device
        speed = self._speed
        if run_sign == 2:
            shake_hand_retry = shake_hand_retry
        elif run_sign == 1:
            shake_hand_retry = 1
        if self.bflb_serial_object:
            try:
                timeout = self.bflb_serial_object.get_timeout()
                blusbserialwriteflag = False
                if isp_mode_sign and isp_timeout > 0:
                    wait_timeout = isp_timeout
                    self.bflb_serial_object.set_timeout(0.1)
                    self._shakehand_flag = False
                    cutoff_time = 0
                    do_reset = False
                    self.bflb_serial_object.repeat_init(device, self.isp_baudrate, self._chip_type, self._chip_name)
                    self.bflb_serial_object.write(b'\r\nispboot if\r\nreboot\r\n')
                    fl_thrx = None
                    fl_thrx = threading.Thread(target=self.send_55_command, args=(speed,))
                    fl_thrx.setDaemon(True)
                    fl_thrx.start()
                    bflb_utils.printf('Please Press Reset Key!')
                    self.bflb_serial_object.setRTS(1)
                    time.sleep(0.2)
                    self.bflb_serial_object.setRTS(0)
                    time_stamp = time.time()
                    while time.time() - time_stamp < wait_timeout:
                        if self._chip_type == 'bl602' or self._chip_type == 'bl702':
                            self.bflb_serial_object.set_timeout(0.01)
                            (success, ack) = self.bflb_serial_object.read(3000)
                            if ack.find(b'Boot2 ISP Shakehand Suss') != -1:
                                self._shakehand_flag = True
                                if ack.find(b'Boot2 ISP Ready') != -1:
                                    bflb_utils.printf('isp ready')
                                    self.bflb_serial_object.write(bytearray.fromhex('a0000000'))
                                    self.bflb_serial_object.set_timeout(timeout)
                                    return 'OK'
                        else:
                            (success, ack) = self.bflb_serial_object.read(3000)
                            if ack.find(b'Boot2 ISP Ready') != -1:
                                bflb_utils.printf('isp ready')
                                self._shakehand_flag = True
                        if self._shakehand_flag is True:
                            self.bflb_serial_object.set_timeout(timeout)
                            tmp_timeout = self.bflb_serial_object.get_timeout()
                            self.bflb_serial_object.set_timeout(0.1)
                            if self._chip_type == 'bl602' or self._chip_type == 'bl702':
                                self.bflb_serial_object.set_timeout(0.5)
                                (success, ack) = self.bflb_serial_object.read(15)
                                self.bflb_serial_object.set_timeout(0.005)
                                ack += self.bflb_serial_object.read(15)[1]
                                self.bflb_serial_object.set_timeout(tmp_timeout)
                                bflb_utils.printf('read ready')
                                if ack.find(b'Boot2 ISP Ready') == -1:
                                    bflb_utils.printf('Boot2 isp is not ready')
                                    return 'FL'
                                self.bflb_serial_object.write(bytearray.fromhex('a0000000'))
                                return 'OK'
                            else:
                                while shake_hand_retry > 0:
                                    if cutoff_time != 0 and blusbserialwriteflag is not True:
                                        cutoff_revert = False
                                        if cutoff_time > 1000:
                                            cutoff_revert = True
                                            cutoff_time = cutoff_time - 1000
                                        self.bflb_serial_object.setRTS(1)
                                        time.sleep(0.2)
                                        self.bflb_serial_object.setRTS(0)
                                        time.sleep(0.05)
                                        self.bflb_serial_object.setRTS(1)
                                        if cutoff_revert:
                                            self.bflb_serial_object.setDTR(0)
                                        else:
                                            self.bflb_serial_object.setDTR(1)
                                        bflb_utils.printf('tx rx and power off, press the machine!')
                                        bflb_utils.printf('cutoff time is ', cutoff_time/1000.0)
                                        time.sleep(cutoff_time/1000.0)
                                        if cutoff_revert:
                                            self.bflb_serial_object.setDTR(1)
                                        else:
                                            self.bflb_serial_object.setDTR(0)
                                        bflb_utils.printf('power on tx and rx ')
                                        time.sleep(0.1)
                                    elif run_sign == 2:
                                        self.bflb_serial_object.setDTR(0)
                                        bflb_utils.printf('default set DTR high ')
                                        time.sleep(0.1)
                                    if do_reset is True and blusbserialwriteflag is not True:
                                        self.bflb_serial_object.setRTS(0)
                                        time.sleep(0.2)
                                        if reset_revert:
                                            self.bflb_serial_object.setRTS(1)
                                            time.sleep(0.001)
                                        reset_cnt = 2
                                        if reset_hold_time > 1000:
                                            reset_cnt = int(reset_hold_time//1000)
                                            reset_hold_time = reset_hold_time % 1000
                                        while reset_cnt > 0:
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(0)
                                            else:
                                                self.bflb_serial_object.setRTS(1)
                                            time.sleep(reset_hold_time/1000.0)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(1)
                                            else:
                                                self.bflb_serial_object.setRTS(0)
                                            if shake_hand_delay > 0:
                                                time.sleep(shake_hand_delay/1000.0)
                                            else:
                                                time.sleep(0.005)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(0)
                                            else:
                                                self.bflb_serial_object.setRTS(1)
                                            time.sleep(reset_hold_time/1000.0)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(1)
                                            else:
                                                self.bflb_serial_object.setRTS(0)
                                            if shake_hand_delay > 0:
                                                time.sleep(shake_hand_delay/1000.0)
                                            else:
                                                time.sleep(0.005)
                                            reset_cnt -= 1
                                        bflb_utils.printf('reset cnt: ' + str(reset_cnt) + ', reset hold: ' + str(reset_hold_time/1000.0) + ', shake hand delay: ' + str(shake_hand_delay/1000.0))
                                    if blusbserialwriteflag:
                                        self.bflb_serial_object.bl_usb_serial_write(cutoff_time, reset_revert)
                                    bflb_utils.printf('clean buf')
                                    self.bflb_serial_object.set_timeout(0.1)
                                    self.bflb_serial_object.clear_buf()
                                    if run_sign == 1:
                                        self.bflb_serial_object.set_timeout(timeout)
                                        return 'OK'
                                    if self._602a0_dln_fix:
                                        self.bflb_serial_object.set_timeout(0.5)
                                    else:
                                        self.bflb_serial_object.set_timeout(0.1)
                                    bflb_utils.printf('send sync')
                                    if self._chip_type == 'bl702' or self._chip_type == 'bl702l':
                                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.003*speed/10)))
                                    else:
                                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.006*speed/10)))
                                    if self._chip_type == 'bl808':
                                        time.sleep(0.3)
                                        self.bflb_serial_object.write(bflb_utils.hexstr_to_bytearray('5000080038F0002000000018'))
                                    if self._602a0_dln_fix:
                                        time.sleep(4)
                                    (success, ack) = self.bflb_serial_object.read(1000)
                                    bflb_utils.printf('ack is ', binascii.hexlify(ack))
                                    if ack.find(b'O') != -1 or ack.find(b'K') != -1:
                                        self.bflb_serial_object.set_timeout(timeout)
                                        if self._602a0_dln_fix:
                                            self.bflb_serial_object.write(bytearray(2))
                                        time.sleep(0.03)
                                        return 'OK'
                                    if len(ack) != 0:
                                        bflb_utils.printf('reshake')
                                        if do_reset is False:
                                            bflb_utils.printf('sleep')
                                            time.sleep(3)
                                    else:
                                        bflb_utils.printf('retry')
                                    shake_hand_retry -= 1
                                time.sleep(0.1)
                                while shake_hand_retry > 0:
                                    if cutoff_time != 0 and blusbserialwriteflag is not True:
                                        cutoff_revert = False
                                        if cutoff_time > 1000:
                                            cutoff_revert = True
                                            cutoff_time = cutoff_time - 1000
                                        self.bflb_serial_object.setRTS(1)
                                        time.sleep(0.2)
                                        self.bflb_serial_object.setRTS(0)
                                        time.sleep(0.05)
                                        self.bflb_serial_object.setRTS(1)
                                        if cutoff_revert:
                                            self.bflb_serial_object.setDTR(0)
                                        else:
                                            self.bflb_serial_object.setDTR(1)
                                        bflb_utils.printf('tx rx and power off, press the machine!')
                                        bflb_utils.printf('cutoff time is ', cutoff_time/1000.0)
                                        time.sleep(cutoff_time/1000.0)
                                        if cutoff_revert:
                                            self.bflb_serial_object.setDTR(1)
                                        else:
                                            self.bflb_serial_object.setDTR(0)
                                        bflb_utils.printf('power on tx and rx ')
                                        time.sleep(0.1)
                                    elif run_sign == 2:
                                        self.bflb_serial_object.setDTR(0)
                                        bflb_utils.printf('default set DTR high ')
                                        time.sleep(0.1)
                                    if do_reset is True and blusbserialwriteflag is not True:
                                        self.bflb_serial_object.setRTS(0)
                                        time.sleep(0.2)
                                        if reset_revert:
                                            self.bflb_serial_object.setRTS(1)
                                            time.sleep(0.001)
                                        reset_cnt = 2
                                        if reset_hold_time > 1000:
                                            reset_cnt = int(reset_hold_time//1000)
                                            reset_hold_time = reset_hold_time % 1000
                                        while reset_cnt > 0:
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(0)
                                            else:
                                                self.bflb_serial_object.setRTS(1)
                                            time.sleep(reset_hold_time/1000.0)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(1)
                                            else:
                                                self.bflb_serial_object.setRTS(0)
                                            if shake_hand_delay > 0:
                                                time.sleep(shake_hand_delay/1000.0)
                                            else:
                                                time.sleep(0.005)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(0)
                                            else:
                                                self.bflb_serial_object.setRTS(1)
                                            time.sleep(reset_hold_time/1000.0)
                                            if reset_revert:
                                                self.bflb_serial_object.setRTS(1)
                                            else:
                                                self.bflb_serial_object.setRTS(0)
                                            if shake_hand_delay > 0:
                                                time.sleep(shake_hand_delay/1000.0)
                                            else:
                                                time.sleep(0.005)
                                            reset_cnt -= 1
                                        bflb_utils.printf('reset cnt: ' + str(reset_cnt) + ', reset hold: ' + str(reset_hold_time/1000.0) + ', shake hand delay: ' + str(shake_hand_delay/1000.0))
                                    if blusbserialwriteflag:
                                        self.bflb_serial_object.bl_usb_serial_write(cutoff_time, reset_revert)
                                    bflb_utils.printf('clean buf')
                                    self.bflb_serial_object.set_timeout(0.1)
                                    self.bflb_serial_object.clear_buf()
                                    if run_sign == 1:
                                        self.bflb_serial_object.set_timeout(timeout)
                                        return 'OK'
                                    if self._602a0_dln_fix:
                                        self.bflb_serial_object.set_timeout(0.5)
                                    else:
                                        self.bflb_serial_object.set_timeout(0.1)
                                    bflb_utils.printf('send sync')
                                    if self._chip_type == 'bl702' or self._chip_type == 'bl702l':
                                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.003*speed/10)))
                                    else:
                                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.006*speed/10)))
                                    if self._chip_type == 'bl808':
                                        time.sleep(0.3)
                                        self.bflb_serial_object.write(bflb_utils.hexstr_to_bytearray('5000080038F0002000000018'))
                                    if self._602a0_dln_fix:
                                        time.sleep(4)
                                    (success, ack) = self.bflb_serial_object.read(1000)
                                    bflb_utils.printf('ack is ', binascii.hexlify(ack))
                                    if ack.find(b'O') != -1 or ack.find(b'K') != -1:
                                        self.bflb_serial_object.set_timeout(timeout)
                                        if self._602a0_dln_fix:
                                            self.bflb_serial_object.write(bytearray(2))
                                        time.sleep(0.03)
                                        return 'OK'
                                    if len(ack) != 0:
                                        bflb_utils.printf('reshake')
                                        if do_reset is False:
                                            bflb_utils.printf('sleep')
                                            time.sleep(3)
                                    else:
                                        bflb_utils.printf('retry')
                                    shake_hand_retry -= 1
                            self.bflb_serial_object.set_timeout(tmp_timeout)
                            break
                    self._shakehand_flag = True
                    self.bflb_serial_object.set_timeout(timeout)
                    self.bflb_serial_object.repeat_init(device, speed, self._chip_type, self._chip_name)
                    time.sleep(2.2)
                if self.bflb_serial_object._is_bouffalo_chip() and boot_load:
                    blusbserialwriteflag = True
                while shake_hand_retry > 0:
                    if cutoff_time != 0 and blusbserialwriteflag is not True:
                        cutoff_revert = False
                        if cutoff_time > 1000:
                            cutoff_revert = True
                            cutoff_time = cutoff_time - 1000
                        self.bflb_serial_object.setRTS(1)
                        time.sleep(0.2)
                        self.bflb_serial_object.setRTS(0)
                        time.sleep(0.05)
                        self.bflb_serial_object.setRTS(1)
                        if cutoff_revert:
                            self.bflb_serial_object.setDTR(0)
                        else:
                            self.bflb_serial_object.setDTR(1)
                        bflb_utils.printf('tx rx and power off, press the machine!')
                        bflb_utils.printf('cutoff time is ', cutoff_time/1000.0)
                        time.sleep(cutoff_time/1000.0)
                        if cutoff_revert:
                            self.bflb_serial_object.setDTR(1)
                        else:
                            self.bflb_serial_object.setDTR(0)
                        bflb_utils.printf('power on tx and rx ')
                        time.sleep(0.1)
                    elif run_sign == 2:
                        self.bflb_serial_object.setDTR(0)
                        bflb_utils.printf('default set DTR high ')
                        time.sleep(0.1)
                    if do_reset is True and blusbserialwriteflag is not True:
                        self.bflb_serial_object.setRTS(0)
                        time.sleep(0.2)
                        if reset_revert:
                            self.bflb_serial_object.setRTS(1)
                            time.sleep(0.001)
                        reset_cnt = 2
                        if reset_hold_time > 1000:
                            reset_cnt = int(reset_hold_time//1000)
                            reset_hold_time = reset_hold_time % 1000
                        while reset_cnt > 0:
                            if reset_revert:
                                self.bflb_serial_object.setRTS(0)
                            else:
                                self.bflb_serial_object.setRTS(1)
                            time.sleep(reset_hold_time/1000.0)
                            if reset_revert:
                                self.bflb_serial_object.setRTS(1)
                            else:
                                self.bflb_serial_object.setRTS(0)
                            if shake_hand_delay > 0:
                                time.sleep(shake_hand_delay/1000.0)
                            else:
                                time.sleep(0.005)
                            if reset_revert:
                                self.bflb_serial_object.setRTS(0)
                            else:
                                self.bflb_serial_object.setRTS(1)
                            time.sleep(reset_hold_time/1000.0)
                            if reset_revert:
                                self.bflb_serial_object.setRTS(1)
                            else:
                                self.bflb_serial_object.setRTS(0)
                            if shake_hand_delay > 0:
                                time.sleep(shake_hand_delay/1000.0)
                            else:
                                time.sleep(0.005)
                            reset_cnt -= 1
                        bflb_utils.printf('reset cnt: ' + str(reset_cnt) + ', reset hold: ' + str(reset_hold_time/1000.0) + ', shake hand delay: ' + str(shake_hand_delay/1000.0))
                    if blusbserialwriteflag:
                        self.bflb_serial_object.bl_usb_serial_write(cutoff_time, reset_revert)
                    bflb_utils.printf('clean buf')
                    self.bflb_serial_object.set_timeout(0.1)
                    self.bflb_serial_object.clear_buf()
                    if run_sign == 1:
                        self.bflb_serial_object.set_timeout(timeout)
                        return 'OK'
                    if self._602a0_dln_fix:
                        self.bflb_serial_object.set_timeout(0.5)
                    else:
                        self.bflb_serial_object.set_timeout(0.1)
                    bflb_utils.printf('send sync')
                    if self._chip_type == 'bl702' or self._chip_type == 'bl702l':
                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.003*speed/10)))
                    else:
                        self.bflb_serial_object.write(self.get_sync_bytes(int(0.006*speed/10)))
                    if self._chip_type == 'bl808':
                        time.sleep(0.3)
                        self.bflb_serial_object.write(bflb_utils.hexstr_to_bytearray('5000080038F0002000000018'))
                    if self._602a0_dln_fix:
                        time.sleep(4)
                    (success, ack) = self.bflb_serial_object.read(1000)
                    bflb_utils.printf('ack is ', binascii.hexlify(ack))
                    if ack.find(b'O') != -1 or ack.find(b'K') != -1:
                        self.bflb_serial_object.set_timeout(timeout)
                        if self._602a0_dln_fix:
                            self.bflb_serial_object.write(bytearray(2))
                        time.sleep(0.03)
                        return 'OK'
                    if len(ack) != 0:
                        bflb_utils.printf('reshake')
                        if do_reset is False:
                            bflb_utils.printf('sleep')
                            time.sleep(3)
                    else:
                        bflb_utils.printf('retry')
                    shake_hand_retry -= 1
                self.bflb_serial_object.set_timeout(timeout)
                return 'FL'
            except Exception as e:
                bflb_utils.printf('Error: %s' % e)
        else:
            return 'FL'

    def img_load_shake_hand(self, sh_baudrate, wk_baudrate, do_reset=False, reset_hold_time=100, shake_hand_delay=100, reset_revert=True, cutoff_time=0, shake_hand_retry=2, isp_mode_sign=False, isp_timeout=0, boot_load=True):
        self.bflb_serial_object.repeat_init(self._device, sh_baudrate, self._chip_type, self._chip_name)
        self.boot_install_cmds_callback()
        if self._chip_type == 'wb03':
            self.toggle_boot_or_shake_hand(1, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time, isp_mode_sign, isp_timeout, boot_load)
            bflb_utils.printf('get_chip_id')
            (ret, data_read) = self.boot_process_one_section('get_chip_id', 0)
            if ret.startswith('OK') is False:
                bflb_utils.printf('fail')
                return (ret, None)
            data_read = binascii.hexlify(data_read)
            bflb_utils.printf('data read is ', data_read)
            chip_id = data_read.decode('utf-8')
            if chip_id != '43484950574230334130305f424c0000' and chip_id != '43484950574230334130305F424C0000':
                return 'shake hand fail'
        else:
            if self._chip_type == 'bl602':
                self._602a0_dln_fix = False
            ret = self.toggle_boot_or_shake_hand(2, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time, isp_mode_sign, isp_timeout, boot_load, shake_hand_retry)
            if self._chip_type == 'bl602':
                self._602a0_dln_fix = False
            if ret != 'OK':
                bflb_utils.printf('shake hand fail')
                self.issue_log_print()
                bflb_utils.set_error_code('0050')
                return 'shake hand fail'
            if sh_baudrate != wk_baudrate and self.boot_inf_change_rate(self._device, 'change_rate', wk_baudrate) != 'OK':
                bflb_utils.printf('change rate fail')
                return 'change rate fail'
        bflb_utils.printf('shake hand success')
        return ret

    def img_load_main_process(self, file, group, record_bootinfo=None):
        encrypt_blk_size = 16
        bflb_utils.printf('get_boot_info')
        (ret, data_read) = self.boot_process_one_section('get_boot_info', 0)
        if ret.startswith('OK') is False:
            bflb_utils.printf('fail')
            return (ret, None)
        data_read = binascii.hexlify(data_read)
        bflb_utils.printf('data read is ', data_read)
        bootinfo = data_read.decode('utf-8')
        chipid = ''
        if self._chip_type == 'bl702' or self._chip_type == 'bl702l':
            chipid = bootinfo[32:34] + bootinfo[34:36] + bootinfo[36:38] + bootinfo[38:40] + bootinfo[40:42] + bootinfo[42:44] + bootinfo[44:46] + bootinfo[46:48]
        else:
            chipid = bootinfo[34:36] + bootinfo[32:34] + bootinfo[30:32] + bootinfo[28:30] + bootinfo[26:28] + bootinfo[24:26]
        bflb_utils.printf('========= ChipID: ', chipid, ' =========')
        bflb_utils.printf('last boot info: ', record_bootinfo)
        if record_bootinfo != None and bootinfo[8:] == record_bootinfo[8:]:
            bflb_utils.printf('repeated chip')
            return ('repeat_burn', bootinfo)
        if bootinfo[:8] == 'FFFFFFFF' or bootinfo[:8] == 'ffffffff':
            bflb_utils.printf('eflash loader present')
            return ('error_shakehand', bootinfo)
        sign = 0
        encrypt = 0
        if self._chip_type == 'bl60x':
            sign = int(data_read[8:10], 16) & 3
            encrypt = (int(data_read[8:10], 16) & 12) >> 2
        elif self._chip_type == 'bl602' or self._chip_type == 'bl702' or self._chip_type == 'bl702l':
            sign = int(data_read[8:10], 16)
            encrypt = int(data_read[10:12], 16)
        elif self._chip_type == 'bl808' or self._chip_type == 'bl628':
            if group == 0:
                sign = int(data_read[8:10], 16)
                encrypt = int(data_read[12:14], 16)
            else:
                sign = int(data_read[10:12], 16)
                encrypt = int(data_read[14:16], 16)
        else:
            sign = int(data_read[8:10], 16)
            encrypt = int(data_read[10:12], 16)
        bflb_utils.printf('sign is ', sign, ' encrypt is ', encrypt)
        if encrypt == 1 or sign == 1:
            if encrypt == 1 and self.encrypt_key != None and self.encrypt_iv != None and sign == 1 and self.public_key != None and self.private_key != None:
                (ret, encrypted_data) = bflb_img_create.encrypt_loader_bin(self._chip_type, file, sign, encrypt, self.encrypt_key, self.encrypt_iv, self.public_key, self.private_key)
            elif encrypt == 1 and self.encrypt_key != None and self.encrypt_iv != None and sign == 0:
                (ret, encrypted_data) = bflb_img_create.encrypt_loader_bin(self._chip_type, file, sign, encrypt, self.encrypt_key, self.encrypt_iv, self.public_key, self.private_key)
            elif encrypt == 0 and sign == 1 and self.public_key != None and self.private_key != None:
                (ret, encrypted_data) = bflb_img_create.encrypt_loader_bin(self._chip_type, file, sign, encrypt, self.encrypt_key, self.encrypt_iv, self.public_key, self.private_key)
            else:
                if encrypt == 1 and sign == 1:
                    bflb_utils.printf('Error: Aes-encrypt and ecc-signature is None!')
                elif encrypt == 1 and sign == 0:
                    bflb_utils.printf('Error: Aes-encrypt is None!')
                elif encrypt == 0 and sign == 1:
                    bflb_utils.printf('Error: Ecc-signature is None!')
                return ('', bootinfo)
            if ret == True:
                (filename, ext) = os.path.splitext(file)
                file_encrypt = filename + '_encrypt' + ext
                fp = open(file_encrypt, 'wb')
                fp.write(encrypted_data)
                fp.close()
                self._imge_fp = open(file_encrypt, 'rb')
            else:
                file = os.path.join(bflb_utils.app_path, file)
                self._imge_fp = open(file, 'rb')
        else:
            file = os.path.join(bflb_utils.app_path, file)
            self._imge_fp = open(file, 'rb')
        if self._chip_type == 'wb03':
            self._imge_fp.read(208)
        if self._chip_type == 'bl808':
            (ret, dmy) = self.boot_process_one_section('808_load_boot_header', 0)
        elif self._chip_type == 'bl628':
            (ret, dmy) = self.boot_process_one_section('628_load_boot_header', 0)
        elif self._chip_type == 'bl616' or self._chip_type == 'wb03':
            (ret, dmy) = self.boot_process_one_section('616_load_boot_header', 0)
        elif self._chip_type == 'bl702l':
            (ret, dmy) = self.boot_process_one_section('702l_load_boot_header', 0)
        else:
            (ret, dmy) = self.boot_process_one_section('load_boot_header', 0)
        if ret.startswith('OK') is False:
            return (ret, bootinfo)
        if sign != 0:
            (ret, dmy) = self.boot_process_one_section('load_publick_key', 0)
            if ret.startswith('OK') is False:
                return (ret, bootinfo)
            if self._chip_type == 'bl60x' or self._chip_type == 'bl808' or self._chip_type == 'bl628':
                (ret, dmy) = self.boot_process_one_section('load_publick_key2', 0)
                if ret.startswith('OK') is False:
                    return (ret, bootinfo)
            (ret, dmy) = self.boot_process_one_section('load_signature', 0)
            if ret.startswith('OK') is False:
                return (ret, bootinfo)
            if self._chip_type == 'bl60x' or self._chip_type == 'bl808' or self._chip_type == 'bl628':
                (ret, dmy) = self.boot_process_one_section('load_signature2', 0)
                if ret.startswith('OK') is False:
                    return (ret, bootinfo)
        if encrypt != 0:
            (ret, dmy) = self.boot_process_one_section('load_aes_iv', 0)
            if ret.startswith('OK') is False:
                return (ret, bootinfo)
        segs = 0
        while segs < self._segcnt:
            send_len = 0
            segdata_len = 0
            (ret, data_read) = self.boot_process_one_section('load_seg_header', 0)
            if ret.startswith('OK') is False:
                return (ret, bootinfo)
            tmp = bflb_utils.bytearray_reverse(data_read[4:8])
            segdata_len = bflb_utils.bytearray_to_int(tmp)
            bflb_utils.printf('segdata_len is ', segdata_len)
            if encrypt == 1 and segdata_len % encrypt_blk_size != 0:
                segdata_len = segdata_len + encrypt_blk_size - segdata_len % encrypt_blk_size
            while send_len < segdata_len:
                left = segdata_len - send_len
                if left > 4080:
                    left = 4080
                (ret, dmy) = self.boot_process_one_section('load_seg_data', left)
                if ret.startswith('OK') is False:
                    return (ret, bootinfo)
                send_len = send_len + left
                bflb_utils.printf(send_len, '/', segdata_len)
                if self._callback is not None:
                    self._callback(send_len, segdata_len, sys._getframe().f_code.co_name)
            segs = segs + 1
        (ret, dmy) = self.boot_process_one_section('check_image', 0)
        return (ret, bootinfo)

    def img_get_bootinfo(self, sh_baudrate, wk_baudrate, callback=None, do_reset=False, reset_hold_time=100, shake_hand_delay=100, reset_revert=True, cutoff_time=0, shake_hand_retry=2, isp_mode_sign=False, isp_timeout=0, boot_load=True):
        bflb_utils.printf('========= image get bootinfo =========')
        ret = self.img_load_shake_hand(sh_baudrate, wk_baudrate, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time, shake_hand_retry, isp_mode_sign, isp_timeout, boot_load)
        if ret == 'shake hand fail' or ret == 'change rate fail':
            bflb_utils.printf('shake hand fail')
            self.bflb_serial_object.close()
            return (False, b'')
        time.sleep(0.5)
        (ret, data_read) = self.boot_process_one_section('get_boot_info', 0)
        if ret.startswith('OK') is False:
            bflb_utils.printf('get_boot_info no ok')
            return (ret, b'')
        data_read = binascii.hexlify(data_read)
        bflb_utils.printf('data read is ', data_read)
        return (True, data_read)

    def img_loader_reset_cpu(self):
        bflb_utils.printf('========= reset cpu =========')
        (ret, data_read) = self.boot_process_one_section('reset', 0)
        if ret.startswith('OK') is False:
            bflb_utils.printf('reset cpu fail')
            return False
        return True

    def img_load_process(self, sh_baudrate, wk_baudrate, callback=None, do_reset=False, reset_hold_time=100, shake_hand_delay=100, reset_revert=True, cutoff_time=0, shake_hand_retry=2, isp_mode_sign=False, isp_timeout=0, boot_load=True, record_bootinfo=None):
        bflb_utils.printf('========= image load =========')
        success = True
        bootinfo = None
        try:
            ret = self.img_load_shake_hand(sh_baudrate, wk_baudrate, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time, shake_hand_retry, isp_mode_sign, isp_timeout, boot_load)
            if ret == 'shake hand fail' or ret == 'change rate fail':
                bflb_utils.printf('shake hand fail')
                self.bflb_serial_object.close()
                return (False, bootinfo, ret)
            time.sleep(0.01)
            if self._eflash_loader_file1 is not None and self._eflash_loader_file1 != '':
                (res, bootinfo) = self.img_load_main_process(self._eflash_loader_file1, 0, record_bootinfo)
                if res.startswith('OK') is False:
                    if res.startswith('repeat_burn') is True:
                        return (False, bootinfo, res)
                    bflb_utils.printf('Img load fail')
                    if res.startswith('error_shakehand') is True:
                        bflb_utils.printf('shakehand with eflash loader found')
                    return (False, bootinfo, res)
            if self._eflash_loader_file2 is not None and self._eflash_loader_file2 != '':
                (res, bootinfo) = self.img_load_main_process(self._eflash_loader_file2, 1, record_bootinfo)
                if res.startswith('OK') is False:
                    if res.startswith('repeat_burn') is True:
                        return (False, bootinfo, res)
                    bflb_utils.printf('Img load fail')
                    if res.startswith('error_shakehand') is True:
                        bflb_utils.printf('shakehand with eflash loader found')
                    return (False, bootinfo, res)
            bflb_utils.printf('Run img')
            self._imge_fp.close()
            (res, dmy) = self.boot_process_one_section('run_image', 0)
            if res.startswith('OK') is False:
                bflb_utils.printf('Img run fail')
                success = False
            time.sleep(0.1)
        except Exception as e:
            bflb_utils.printf(e)
            traceback.print_exc(limit=5, file=sys.stdout)
            return (False, bootinfo, '')
        return (success, bootinfo, '')

if __name__ == '__main__':
    img_load_t = BflbImgLoader()
    if len(sys.argv) == 3:
        img_load_t.img_load_process(sys.argv[1], 115200, 115200, sys.argv[2], '')
    elif len(sys.argv) == 4:
        img_load_t.img_load_process(sys.argv[1], 115200, 115200, sys.argv[2], sys.argv[3])
