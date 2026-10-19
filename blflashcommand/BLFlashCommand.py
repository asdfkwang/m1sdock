# decompyle3 version 3.9.0
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.7.16 (default, Mar 30 2023, 01:25:49) 
# [GCC 12.2.1 20220924]
# Embedded file name: BLFlashCommand.py
__doc__ = '\nCreated on 20221216\n\n@author: Dillon\n'
import os, re, sys, argparse, binascii, threading, configparser
from libs import bflb_utils
from libs.bflb_utils import get_serial_ports
from libs.bflb_interface_eflash_loader import InterfaceEflashLoader

def hex_to_dec(value):
    try:
        value = value.replace('0x', '')
        int(value, 16)
        return True
    except ValueError:
        return False


class ThreadIot(threading.Thread):

    def __init__(self, config, act='download', callback=None):
        threading.Thread.__init__(self)
        self.obj = InterfaceEflashLoader()
        self.config = config
        self.callback = callback
        self.act = act

    def stop(self):
        pass

    def run(self):
        self.obj.run(self.act, self.config, self.callback)


class MainClass:

    def __init__(self):
        self.dict_chip = {
          'BL602': ('bl602', 'bl602'),
          'BL702': ('bl702', 'bl702'),
          'BL702L': ('bl702l', 'bl702l'),
          'BL808': ('bl808', 'bl808'),
          'BL606P': ('bl606p', 'bl808'),
          'BL616': ('bl616', 'bl616')}

    def get_addr_from_partition_by_name(self, name, parition_file, index):
        try:
            with open(parition_file, 'rb') as fp:
                data = bytearray(fp.read())
                fp.close()
                start = data.find(name.encode('utf-8'))
                if start != -1:
                    addr = data[start + 9 + index * 4:start + 9 + 4 + index * 4]
                    addr.reverse()
                    addr = hex(int(binascii.hexlify(addr), 16))
                    return (
                     True, addr)
                print(data)
                print(name.encode('utf-8'))
                return (False, '0')
        except Exception as e:
            try:
                bflb_utils.printf(e)
                return (False, '0')
            finally:
                e = None
                del e

    def get_value(self, args):
        self.config = dict()
        self.config['param'] = dict()
        self.config['check_box'] = dict()
        self.config['input_path'] = dict()
        self.config['param']['interface_type'] = args.interface
        self.config['param']['comport_uart'] = args.port
        self.config['param']['chip'] = args.chipname.lower()
        if args.chipname.upper() not in self.dict_chip:
            bflb_utils.printf('Error: chipname ' + args.chipname + ' is error!')
            return
        chip = self.dict_chip[args.chipname.upper()]
        self.config['param']['chip_name'] = chip[0]
        self.config['param']['chip_type'] = chip[1]
        if args.interface.lower() == 'uart':
            self.config['param']['speed_uart'] = str(args.baudrate)
            self.config['param']['speed_jlink'] = '1000'
        else:
            self.config['param']['speed_uart'] = '2000000'
            if str(args.baudrate) == '2000000':
                self.config['param']['speed_jlink'] = '1000'
            else:
                self.config['param']['speed_jlink'] = str(args.baudrate)
        if args.efuse:
            self.config['check_box']['efuse'] = True
            self.config['input_path']['efuse'] = os.path.abspath(args.efuse)
        else:
            self.config['check_box']['efuse'] = False
            self.config['input_path']['efuse'] = ''
        self.config['input_path']['config'] = args.config
        try:
            try:
                self.erase = 1
                self.skip_mode = '0x0, 0x0'
                self.boot2_isp_mode = 0
                config = configparser.ConfigParser()
                if not os.path.exists(os.path.abspath(args.config)):
                    bflb_utils.printf('Error: Config File Not Found!')
                    return
                config.read((os.path.abspath(args.config)), encoding='utf-8')
                if config:
                    for item in config.sections():
                        if item == 'cfg':
                            self.erase = config.get('cfg', 'erase', fallback=1)
                            self.skip_mode = config.get('cfg', 'skip_mode', fallback='0x0, 0x0')
                            self.boot2_isp_mode = config.get('cfg', 'boot2_isp_mode', fallback=0)
                        else:
                            filedir = config.get(item, 'filedir')
                            address = config.get(item, 'address')
                            if not self.get_value_file(item, filedir, address, args.cpu_id):
                                return False

            except Exception as e:
                try:
                    config = None
                    print('ConfigParser Error: ' + str(e))
                finally:
                    e = None
                    del e

        finally:
            self.config['param']['erase'] = self.erase
            self.config['param']['skip_mode'] = self.skip_mode
            self.config['param']['boot2_isp_mode'] = self.boot2_isp_mode

        if args.key:
            self.config['check_box']['encrypt'] = True
            self.config['param']['aes_key'] = args.key
            self.config['param']['aes_iv'] = args.iv
        else:
            self.config['check_box']['encrypt'] = False
            self.config['param']['aes_key'] = ''
            self.config['param']['aes_iv'] = ''
        if args.pk:
            self.config['check_box']['sign'] = True
            self.config['input_path']['publickey'] = args.pk
            self.config['input_path']['privatekey'] = args.sk
        else:
            self.config['check_box']['sign'] = False
            self.config['input_path']['publickey'] = ''
            self.config['input_path']['privatekey'] = ''
        return self.config

    def get_value_file(self, name, path, addr, cpu_id=None):
        name = str(name)
        if os.path.isabs(path):
            path = os.path.abspath(path)
        else:
            config_dir = os.path.dirname(os.path.abspath(self.config['input_path']['config']))
            path = os.path.join(config_dir, path)
        if cpu_id:
            path = path.replace('$(CHIPNAME)', self.config['param']['chip_name'] + '_' + cpu_id)
        else:
            path = path.replace('$(CHIPNAME)', self.config['param']['chip_name'])
        addr = str(addr)
        self.config[name] = {}
        self.config[name]['addr'] = addr
        self.config[name]['path'] = path
        if not os.path.exists(path):
            dir_path = os.path.dirname(path)
            file_name = os.path.basename(path)
            try:
                all_file_list = os.listdir(dir_path)
            except Exception as e:
                try:
                    bflb_utils.printf(e)
                    return False
                finally:
                    e = None
                    del e

            result = []
            if '*' in file_name:
                file_name = file_name.replace('.', '\\.').replace('*', '.*[一-龥]*')
            for one_name in all_file_list:
                pattern = re.compile(file_name)
                temp_list = pattern.findall(one_name)
                if one_name in temp_list:
                    result += temp_list

            if len(result) > 1:
                bflb_utils.printf('Error: ' + name + ' multiple files were matched! ')
                return False
            if len(result) == 0:
                error = 'Error: ' + name + ':' + path + ' image file is not existed'
                bflb_utils.printf(error)
                return False
            self.config[name]['path'] = os.path.join(dir_path, result[0])
        if addr.find('@partition') != -1:
            bflb_utils.printf('{0} get address from partiton file {1}'.format(name, self.config['partition']['path']))
            success, addr_pt = self.get_addr_from_partition_by_name(name, self.config['partition']['path'], 0)
            if not success:
                bflb_utils.printf('Fail, not find ', name, ' in partition')
                return False
            self.config[name]['addr'] = addr_pt
            bflb_utils.printf('Address=', addr_pt)
            addr = addr_pt
        if not hex_to_dec(addr):
            error = 'Error: ' + addr + ' is invalid hexadecimal value'
            bflb_utils.printf(error)
            return False
        return True

    def main(self, argv):
        port = None
        ports = []
        for item in get_serial_ports():
            ports.append(item['port'])

        if ports:
            try:
                port = sorted(ports, key=(lambda x: int(re.match('COM(\\d+)', x).group(1))
))[0]
            except Exception:
                port = sorted(ports)[0]

        parser = argparse.ArgumentParser(description='flash-command')
        parser.add_argument('--interface', dest='interface', default='uart', help='interface to use')
        parser.add_argument('--port', dest='port', default=port, help='serial port to use')
        parser.add_argument('--chipname', dest='chipname', default='BL602', help='chip name')
        parser.add_argument('--baudrate', dest='baudrate', default=2000000, type=int, help='the speed at which to communicate')
        parser.add_argument('--config', dest='config', default='', help='run config')
        parser.add_argument('--cpu_id', dest='cpu_id', default='', help='cpu id')
        parser.add_argument('--efuse', dest='efuse', default='', help='efuse options')
        parser.add_argument('--key', dest='key', default='', help='aes key')
        parser.add_argument('--iv', dest='iv', default='', help='aes iv')
        parser.add_argument('--pk', dest='pk', help='ecc public key')
        parser.add_argument('--sk', dest='sk', default='', help='ecc private key')
        args = parser.parse_args(argv)
        if args.port:
            bflb_utils.printf('Serial port is ' + args.port)
        else:
            if port:
                bflb_utils.printf('Serial port is ' + port)
            else:
                bflb_utils.printf('Serial port is not found')
        bflb_utils.printf('==================================================')
        config = self.get_value(args)
        if config:
            self.obj = InterfaceEflashLoader()
            self.obj.run('download', config, None)


if __name__ == '__main__':
    print(sys.argv)
    app = MainClass()
    app.main(sys.argv[1:])
# okay decompiling BLFlashCommand.pyc
