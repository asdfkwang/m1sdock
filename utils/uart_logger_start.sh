#!/bin/bash
# UART Logger start script
# c0: /dev/ttyUSB0 (AI reads console log) -> logs/c0.log
# c1: /dev/ttyUSB1 (flash/control) -> logs/c1.log
#
# Usage: bash utils/uart_logger_start.sh

set -euo pipefail

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"
TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"
BAUD=2000000

mkdir -p "$LOGDIR"

echo "[uart_logger] =========================================="
echo "[uart_logger] Start: UART logger (c0 / c1)"
echo "[uart_logger] Working directory: $BASEDIR"
echo "[uart_logger] Log directory: $LOGDIR"
echo "[uart_logger] Baudrate: $BAUD"
echo "[uart_logger] =========================================="

# Stop existing sessions if running
if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[uart_logger] Stopping existing session '$TMUX_SESSION_C0'..."
    tmux kill-session -t "$TMUX_SESSION_C0" 2>/dev/null || true
    sleep 0.5
fi
if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[uart_logger] Stopping existing session '$TMUX_SESSION_C1'..."
    tmux kill-session -t "$TMUX_SESSION_C1" 2>/dev/null || true
    sleep 0.5
fi

# Write session start markers to log files (trace source/time of log output)
echo "" >> "$LOGDIR/c0.log"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') UART LOGGER START c0 (/dev/ttyUSB0, ${BAUD} baud) =====" >> "$LOGDIR/c0.log"
echo "" >> "$LOGDIR/c0.log"

echo "" >> "$LOGDIR/c1.log"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') UART LOGGER START c1 (/dev/ttyUSB1, ${BAUD} baud) =====" >> "$LOGDIR/c1.log"
echo "" >> "$LOGDIR/c1.log"

# c0: /dev/ttyUSB0 -> logs/c0.log (console log read by AI)
echo "[uart_logger] c0 (/dev/ttyUSB0 -> logs/c0.log) start..."
tmux new-session -d -s "$TMUX_SESSION_C0" \
    "tio -b $BAUD -L --log-file '$LOGDIR/c0.log' --log-append --log-strip /dev/ttyUSB0"
sleep 1

# c1: /dev/ttyUSB1 -> logs/c1.log (flash/control)
echo "[uart_logger] c1 (/dev/ttyUSB1 -> logs/c1.log) start..."
tmux new-session -d -s "$TMUX_SESSION_C1" \
    "tio -b $BAUD -L --log-file '$LOGDIR/c1.log' --log-append --log-strip /dev/ttyUSB1"
sleep 1

echo "[uart_logger] Session status:"
tmux list-sessions | grep -E "uart-c0|uart-c1" || true

echo "[uart_logger] Done. Check logs with:"
echo "  tail -n 100 logs/c0.log"
echo "  tail -n 100 logs/c1.log"
