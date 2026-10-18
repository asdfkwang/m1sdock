#!/bin/bash
# UART Logger stop script
# Run before flashing to release UART ports
#
# Usage: bash utils/uart_logger_stop.sh

set -euo pipefail

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"
TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"

echo "[uart_logger] =========================================="
echo "[uart_logger] Stop: UART logger (c0 / c1)"
echo "[uart_logger] =========================================="

if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[uart_logger] Stopping session '$TMUX_SESSION_C0'..."
    tmux kill-session -t "$TMUX_SESSION_C0" 2>/dev/null || true
else
    echo "[uart_logger] Session '$TMUX_SESSION_C0' is not running"
fi

if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[uart_logger] Stopping session '$TMUX_SESSION_C1'..."
    tmux kill-session -t "$TMUX_SESSION_C1" 2>/dev/null || true
else
    echo "[uart_logger] Session '$TMUX_SESSION_C1' is not running"
fi

# Write session stop markers to log files
echo "" >> "$LOGDIR/c0.log" 2>/dev/null || true
echo "===== $(date '+%Y-%m-%d %H:%M:%S') UART LOGGER STOP =====" >> "$LOGDIR/c0.log" 2>/dev/null || true
echo "" >> "$LOGDIR/c0.log" 2>/dev/null || true

echo "" >> "$LOGDIR/c1.log" 2>/dev/null || true
echo "===== $(date '+%Y-%m-%d %H:%M:%S') UART LOGGER STOP =====" >> "$LOGDIR/c1.log" 2>/dev/null || true
echo "" >> "$LOGDIR/c1.log" 2>/dev/null || true

echo "[uart_logger] Done. Ports released."
