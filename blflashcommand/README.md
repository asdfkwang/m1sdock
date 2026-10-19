Boufallo Lab Flash Command - Open Source Version
================================================

This repo contains the completed work of "open sourcing" the Boufallo Lab
flash command. This utility is provided in binary form under Apache 2.0 License.
It is a [pyinstaller]() executable, so I have unpacked the binary, run it
through several Python 3.7 decompilers, and made a few adjustments. Primary
changes:

* The libs/bflb_configobj.py file has been completely rewritten. It appears
  to have been a handwritten recursive descent parser for ini files that
  include the ability to have complex objects. In reality, the configuration
  that seems to exist for flashing is simple key/value pairs in sections,
  so 2k+ lines of code were removed and replaced with simple shims to the
  python standard library
* Some additional logs were added to the output to let the user know what
  files were being used. This was necessary to debug the decompiler output
  and I thought they were useful

I have licensed this as Apache 2.0 to reflect the origin license. This is tested
and working with BL616 MCU. The flashing host computer was running Linux. This
is good for my needs and it should work for other MCUs/other flashing hosts.
However, I do not intend to provide support for anything beyond my own needs.
I am happy to take pull requests!

Usage
-----

```
$ git clone https://git.lerch.org/lobo/blflashcommand
$ python3 -m venv env
$ source env/bin/activate
$ pip3 install -r requirements.txt
$ # copy bin file and flash_prog_cfg.ini from their homes, or change to that directory
$ cp ~/bouffalo_sdk/examples/peripherals/usbdev/usbd_cdc_acm_bl616.bin .
$ cp ~/bouffalo_sdk/examples/peripherals/usbdev/flash_prog_cfg.ini .
$ python3 BLFlashCommand.py --interface=uart --baudrate=2000000 --port=/dev/ttyACM0 --chipname=bl616 --cpu_id= --config=$PWD/flash_prog_cfg.ini
```

Output of the final command should be similar to this:

```
[15:27:25.931] - Serial port is /dev/ttyACM0
[15:27:25.931] - ==================================================
[15:27:25.937] - Program Start
[15:27:25.937] - ========= eflash loader cmd arguments =========
[15:27:25.937] - Reading configuration from file:
[15:27:25.937] -   /home/lobo/blflashcommand/chips/bl616/eflash_loader/eflash_loader_cfg.ini
[15:27:25.938] - serial port is /dev/ttyACM0
[15:27:25.938] - chiptype: bl616
[15:27:25.938] - cpu_reset=False
[15:27:25.939] - Reading configuration from file:
[15:27:25.939] -   /home/lobo/blflashcommand/chips/bl616/eflash_loader/eflash_loader_cfg.ini
[15:27:25.942] - ========= Interface is uart =========
[15:27:25.942] - Bootrom load
[15:27:25.942] - ========= get_boot_info =========
[15:27:25.942] - ========= image get bootinfo =========
[15:27:25.955] - default set DTR high
[15:27:26.055] - usb serial port
[15:27:26.106] - clean buf
[15:27:26.107] - send sync
[15:27:26.308] - ack is b'4f4b'
[15:27:26.339] - shake hand success
[15:27:26.841] - data read is b'010016060000010027928001319735cf0eb417000f758010'
[15:27:26.841] - ========= ChipID: b40ecf359731 =========
[15:27:26.841] - Get bootinfo time cost(ms): 899.405517578125
[15:27:26.842] - change bdrate: 2000000
[15:27:26.842] - Clock PLL set
[15:27:26.842] - Set clock time cost(ms): 0.44873046875
[15:27:26.954] - Read mac addr
[15:27:26.955] - flash set para
[15:27:26.955] - get flash pin cfg from bootinfo: 0x02
[15:27:26.955] - set flash cfg: 14102
[15:27:26.955] - Set flash config
[15:27:26.957] - Set para time cost(ms): 1.901611328125
[15:27:26.958] - ========= flash read jedec ID =========
[15:27:26.958] - Read flash jedec ID
[15:27:26.958] - readdata:
[15:27:26.958] - b'c8601600'
[15:27:26.958] - Finished
[15:27:26.960] - Reading configuration from file:
[15:27:26.960] -   /home/lobo/blflashcommand/utils/flash/bl616/GD25LQ32D_c86016.conf
[15:27:26.964] - Program operation
[15:27:26.964] - Dealing Index 0
[15:27:26.964] - ========= programming /home/lobo/blflashcommand/./usbd_cdc_acm_bl616.bin to 0x000000
[15:27:26.964] - Reading configuration from file:
[15:27:26.965] -   /home/lobo/blflashcommand/utils/flash/bl616/GD25LQ32D_c86016.conf
[15:27:26.977] - flash para file: /home/lobo/blflashcommand/chips/bl616/efuse_bootheader/flash_para.bin
[15:27:26.980] - Set para time cost(ms): 2.005859375
[15:27:26.980] - ========= flash load =========
[15:27:26.980] - ========= flash erase =========
[15:27:26.980] - Erase flash  from 0x0 to 0x9d5f
[15:27:27.088] - Erase time cost(ms): 107.818359375
[15:27:27.094] - Load 2048/40288 {"progress":5}
[15:27:27.100] - Load 4096/40288 {"progress":10}
[15:27:27.106] - Load 6144/40288 {"progress":15}
[15:27:27.111] - Load 8192/40288 {"progress":20}
[15:27:27.117] - Load 10240/40288 {"progress":25}
[15:27:27.123] - Load 12288/40288 {"progress":30}
[15:27:27.128] - Load 14336/40288 {"progress":35}
[15:27:27.134] - Load 16384/40288 {"progress":40}
[15:27:27.140] - Load 18432/40288 {"progress":45}
[15:27:27.146] - Load 20480/40288 {"progress":50}
[15:27:27.151] - Load 22528/40288 {"progress":55}
[15:27:27.157] - Load 24576/40288 {"progress":61}
[15:27:27.163] - Load 26624/40288 {"progress":66}
[15:27:27.169] - Load 28672/40288 {"progress":71}
[15:27:27.174] - Load 30720/40288 {"progress":76}
[15:27:27.180] - Load 32768/40288 {"progress":81}
[15:27:27.185] - Load 34816/40288 {"progress":86}
[15:27:27.190] - Load 36864/40288 {"progress":91}
[15:27:27.196] - Load 38912/40288 {"progress":96}
[15:27:27.200] - Load 40288/40288 {"progress":100}
[15:27:27.200] - Load 40288/40288 {"progress":100}
[15:27:27.200] - Write check
[15:27:27.201] - Flash load time cost(ms): 112.4423828125
[15:27:27.201] - Finished
[15:27:27.202] - Sha caled by host: 2c83e7a0b26c88f8ce0ca11715d56bff2eff1ca2ac8ff8a6d051d6d7ec0e0a1f
[15:27:27.202] - xip mode Verify
[15:27:27.237] - Read Sha256/40288
[15:27:27.237] - Flash xip readsha time cost(ms): 34.326416015625
[15:27:27.237] - Finished
[15:27:27.238] - Sha caled by dev: 2c83e7a0b26c88f8ce0ca11715d56bff2eff1ca2ac8ff8a6d051d6d7ec0e0a1f
[15:27:27.238] - Verify success
[15:27:27.238] - Program Finished
[15:27:27.238] - All time cost(ms): 1301.3779296875
[15:27:27.342] - close interface
[15:27:27.343] - [All Success]
```

Decompilers used
----------------

* [decompyle3](https://pypi.org/project/decompyle3/): This was the primary decompiler for the project
* [unpyc3](https://github.com/andrew-tavera/unpyc37.git): unpyc3 did a better job on 2 or 3 of the files (see logs)
* [pycdc](https://github.com/zrax/pycd): While not used on any files, it served
  as a useful comparison tool. A few miscompiles from decompyle3 were more
  obvious because both pycdc and unpyc3 disagreed with the decompyle3 output

Local M1s Dock integration
-------------------------

Vendored from https://git.lerch.org/lobo/blflashcommand at commit
`2cbf382b74e6549d8cafe0db0813db7f285ff781`. The Apache 2.0 license is
preserved in `LICENSE`.

Local fixes restore configuration-file writes, correct the flash-parameter
comparison, and include every JEDEC row in the BL808 flash configuration table
(including the M1s Dock's `ef4018`). `setuptools<81` supplies `pkg_resources`
for CryptoPlus. See `../bdb/README.md` for the dock workflow and
`../utils/prepare_blflash_low_load.py` for validated M0/Group0 and D0/Group1
image generation.

Python environments, caches, logs, generated images and runtime `.ini` files
are excluded from Git. Static upstream loader firmware is retained.
