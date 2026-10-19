# Troubleshooting

## Symptom matrix

| Symptom | Root cause | Fix |
|---|---|---|
| `ttyUSB1` shows full banner, `ttyUSB0` empty | d0 bootinfo bad or `img_len_cnt` stale | Re-write factory BFNP+BFAP (`bootinfo_group0/1.bin`) |
| DevCube prints erase/write ok, nothing changes on flash | USB port was opened/closed repeatedly by previous sessions | Unplug/replug USB, kill `tio`, stop loggers, re-enter flash mode |
| Flasher reports `0036` / timeout at a write | Same USB state corruption | Same as above |
| Only m0 boots; d0 throws nothing | BFAP missing/zeroed | Flash `bootinfo_group1.bin` @0x1000 |
| `bootinfo @0x8C` zeroed) | Same | See below |
| Linux mounts without `rootfs` | whole-img at wrong offset, or DTB stale | Re-write `whole_img` @0x0D2000 |

## The one fix that restored a dead board (2026-10-18, 22:04)

A d0-silent state existed since 18:07 after the first `bflb_mcu_tool`
invocation over a polluted USB line. Restoring the **factory bootinfo
pair** at `0x0` and `0x1000` from the 19:08 read-back (`rd_boot_area.bin`)
with a *single region* iot-tool write brought d0 back:

```bash
dd if=rd_boot_area.bin of=factory_bootinfo.bin bs=1 count=8192 status=none
cd tools/bflb_iot_tool && \
PYTHONPATH=$PWD python3 core/bflb_iot_tool.py --chipname bl808 \
    --port /dev/ttyUSB1 --baudrate 2000000 \
    --firmware /tmp/opencode/factory_bootinfo.bin --addr 0x0 --single
```

Then **RST** (no BOOT held). Board booted full Linux again.

## Rule of thumb

* Any change to the m0 or d0 body length ⇒ regenerate every `bootinfo_groupN.bin`
  (the 16-aligned `img_len_cnt` must follow).
* Any flasher tool invocation after a USB error ⇒ unplug/replug, `fuser -k /dev/ttyUSB*`,
  stop loggers, re-enter flash mode.
* Read-back verify after every write (`read_flash.py` regions).
