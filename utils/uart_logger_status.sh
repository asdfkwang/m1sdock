#!/bin/bash
# UART Logger 상태 확인 스크립트
#
# 실행: bash utils/uart_logger_status.sh

set -euo pipefail

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"
TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"

echo "[uart_logger] =========================================="
echo "[uart_logger] 상태: UART 로거"
echo "[uart_logger] =========================================="
echo ""

echo "--- tmux 세션 ---"
if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[c0] /dev/ttyUSB0 -> logs/c0.log      : 실행 중"
else
    echo "[c0] /dev/ttyUSB0 -> logs/c0.log      : 중지됨"
fi
if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[c1] /dev/ttyUSB1 -> logs/c1.log      : 실행 중"
else
    echo "[c1] /dev/ttyUSB1 -> logs/c1.log      : 중지됨"
fi

echo ""
echo "--- 로그 파일 ---"
if [ -f "$LOGDIR/c0.log" ]; then
    LINES_C0=$(wc -l < "$LOGDIR/c0.log" 2>/dev/null || echo 0)
    SIZE_C0=$(du -h "$LOGDIR/c0.log" 2>/dev/null | cut -f1)
    echo "[c0.log] 존재함  라인: $LINES_C0  크기: $SIZE_C0"
    echo "  마지막 5줄:"
    tail -n 5 "$LOGDIR/c0.log" 2>/dev/null | sed 's/^/    /'
else
    echo "[c0.log] 존재하지 않음"
fi

if [ -f "$LOGDIR/c1.log" ]; then
    LINES_C1=$(wc -l < "$LOGDIR/c1.log" 2>/dev/null || echo 0)
    SIZE_C1=$(du -h "$LOGDIR/c1.log" 2>/dev/null | cut -f1)
    echo "[c1.log] 존재함  라인: $LINES_C1  크기: $SIZE_C1"
    echo "  마지막 5줄:"
    tail -n 5 "$LOGDIR/c1.log" 2>/dev/null | sed 's/^/    /'
else
    echo "[c1.log] 존재하지 않음"
fi

echo ""
echo "[uart_logger] 상태 확인 완료."
