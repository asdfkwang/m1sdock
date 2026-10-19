# Flashing

All wrappers run the vendored tools unmodified. Two paths are used in practice.

## Path A: single region (`bflb_iot_tool`)
Fast path for one binary at one address.  Erases what it needs and verifies
on-chip SHA-256 through the XIP path.

```bash
cd tools/bflb_iot_tool
PYTHONPATH=$PWD python3 core/bflb_iot_tool.py \
    --chipname bl808 --port /dev/ttyUSB1 --baudrate 2000000 \
    --firmware <file.bin> --addr <0x…> --single
```

Observed command outputs:

```
[22:04:00.064] flash write check
[22:04:00.080] sha256 caled by host: 990de790…
[22:04:00.112] flash xip readsha time cost(ms): 16.256
[22:04:00.128] sha256 caled by dev:  990de790…
[22:04:00.128] verification succeeded
[22:04:00.128] program finished
[22:04:00.229] [All Successful]
```

## Path B: full 4-file mirror of the DevCube GUI MCU page

[`/tmp/opencode/flash_low_load.py`](file:///tmp/opencode/flash_low_load.py) calls
`bflb_mcu_tool`'s library API (`get_value`, `create_img`, `program_img_thread`)
to reproduce, in one run:

| # | File | Target |
|---|---|---|
| 1 | `bootinfo_group0.bin` | `0x000000` (erase `0x0…0x663`) |
| 2 | `bootinfo_group1.bin` | `0x001000` (erase `0x1000…0x115F`) |
| 3 | `img_group0.bin` (m0, wrapped) | `0x002000` (erase `0x2000…0xB4EF`) |
| 4 | `img_group1.bin` (d0, wrapped) | `0x52000` (erase `0x52000…0x5920F`) |

Each step is followed by `xip mode verify` (SHA-256, host vs device).
Ends with `[All Successful]`.

## Flash-mode entry

1. Close all serial handles (`tio`, loggers) that hold `ttyUSB1`.
2. Hold **BOOT**, tap **RST**, release **BOOT** — `ttyUSB1` now speaks bootrom.
3. Run the flasher. When it prints `[All Successful]`, tap **RST** to reboot.

## Read-back (verification after the fact)

[`/tmp/opencode/read_flash.py`](file:///tmp/opencode/read_flash.py) reads any
region and drops `rd_<name>.bin` in `/tmp/opencode`. Requires flash mode.

```python
REGIONS = [
    ("v_g0", "0x00000000", "0x00000700"),   # bootinfo group0
    ("v_g1", "0x00001000", "0x00001200"),   # bootinfo group1
    # add more here, e.g. kernel header @0x9FFFC
]
```

## Serial logging

```bash
utils/uart_logger_start.sh     # tmux sessions uart-c0 / uart-c1
utils/uart_logger_stop.sh      # releases ttyUSB0 + ttyUSB1
utils/uart_logger_status.sh
tail -f logs/c0.log logs/c1.log
```

Loggers must be **stopped** before flashing (they hold both ports).
