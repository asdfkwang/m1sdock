# m1sdock

M1s Dock

https://wiki.sipeed.com/hardware/en/maix/m1s/m1s_dock.html  
https://github.com/sipeed/M1s_BL808_Linux_SDK  
https://openbouffalo.org  

## Board

BL702 - Only For USB-UART Bridge  
BL808 - M0, D0, LP  

```text
BL808 c0 UART ── /dev/ttyUSB0 ──┐
                                ├── UART Logger (tio + tmux)
BL808 c1 UART ── /dev/ttyUSB1 ──┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                    logs/c0.log               logs/c1.log
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                                  AI Analysis
```

- `logs/c0.log` — UART c0 log (appended by tio)
- `logs/c1.log` — UART c1 log (appended by tio)
- `utils/uart_logger_start.sh` — Start both loggers
- `utils/uart_logger_stop.sh` — Stop both loggers (release UART ports)
- `utils/uart_logger_status.sh` — Check logger status
- `utils/uart_tail.sh` — Show tail of a log file

## AI Control Flow

1. **Start:** Run `bash utils/uart_logger_start.sh`.
2. **Monitor:** AI periodically runs `tail` on `logs/c0.log` / `logs/c1.log`.
3. **Analyze:** AI parses boot logs, errors, warnings, and status messages.
4. **User says "stop":** Run `bash utils/uart_logger_stop.sh` to release UART ports.
5. **Flash:** Perform build → flash → reset.
6. **Restart:** Run `bash utils/uart_logger_start.sh` again.
7. **Repeat:** AI analyzes the new boot log automatically.

