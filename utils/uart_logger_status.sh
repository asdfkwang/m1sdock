#!/bin/bash
# UART Logger status script
#
# Usage: bash utils/uart_logger_status.sh

TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"

echo "[uart_logger] =========================================="
echo "[uart_logger] Status: UART logger"
echo "[uart_logger] =========================================="

if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[c0] /dev/ttyUSB0 -> logs/c0.log      : running"
else
    echo "[c0] /dev/ttyUSB0 -> logs/c0.log      : stopped"
fi

if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[c1] /dev/ttyUSB1 -> logs/c1.log      : running"
else
    echo "[c1] /dev/ttyUSB1 -> logs/c1.log      : stopped"
fi

echo ""
echo "--- log files ---"

if [ -f "$LOGDIR/c0.log" ]; then
    LINES_C0=$(wc -l < "$LOGDIR/c0.log")
    SIZE_C0=$(du -h "$LOGDIR/c0.log" | cut -f1)
    echo "[c0.log] exists  lines: $LINES_C0  size: $SIZE_C0"
    echo "  last 5 lines:"
    tail -n 5 "$LOGDIR/c0.log"
else
    echo "[c0.log] does not exist"
fi

echo ""

if [ -f "$LOGDIR/c1.log" ]; then
    LINES_C1=$(wc -l < "$LOGDIR/c1.log")
    SIZE_C1=$(du -h "$LOGDIR/c1.log" | cut -f1)
    echo "[c1.log] exists  lines: $LINES_C1  size: $SIZE_C1"
    echo "  last 5 lines:"
    tail -n 5 "$LOGDIR/c1.log"
else
    echo "[c1.log] does not exist"
fi

echo "[uart_logger] Status check done."
