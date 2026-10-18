#!/bin/bash
# UART log tail script (used by AI to read logs)
# Default: print last 200 lines of c0 log
#
# Usage: bash utils/uart_tail.sh [c0|c1] [line count]
# Example: bash utils/uart_tail.sh c0 200

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"

CH="${1:-c0}"
LINES="${2:-200}"

case "$CH" in
    c0) LOGFILE="$LOGDIR/c0.log"
        PORT_DESC="/dev/ttyUSB0 log (AI read target)"
        ;;
    c1) LOGFILE="$LOGDIR/c1.log"
        PORT_DESC="/dev/ttyUSB1 log (flash/control)"
        ;;
    *)
        echo "Usage: $0 [c0|c1] [line count]"
        echo "  c0: /dev/ttyUSB0 log (AI read target)"
        echo "  c1: /dev/ttyUSB1 log (flash/control)"
        exit 1
        ;;
esac

if [ ! -f "$LOGFILE" ]; then
    echo "[uart_tail] log file does not exist: $LOGFILE"
    echo "[uart_tail] start logger first with 'bash utils/uart_logger_start.sh'"
    exit 1
fi

echo "[uart_tail] file: $LOGFILE  (last $LINES lines)"
tail -n "$LINES" "$LOGFILE"
