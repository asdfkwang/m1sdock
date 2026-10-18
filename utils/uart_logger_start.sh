#!/bin/bash
# UART Logger 시작 스크립트
# c0: /dev/ttyUSB0 (AI가 읽는 콘솔 로그) -> logs/c0.log
# c1: /dev/ttyUSB1 (플래싱/제어용) -> logs/c1.log
#
# 실행: bash utils/uart_logger_start.sh

set -euo pipefail

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"
TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"
BAUD=2000000

mkdir -p "$LOGDIR"

echo "[uart_logger] =========================================="
echo "[uart_logger] 시작: UART 로거 (c0 / c1)"
echo "[uart_logger] 작업 디렉터리: $BASEDIR"
echo "[uart_logger] 로그 디렉터리: $LOGDIR"
echo "[uart_logger] 보드레이트: $BAUD"
echo "[uart_logger] =========================================="

# 이미 실행 중이면 중지
if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[uart_logger] 기존 세션 '$TMUX_SESSION_C0' 종료 중..."
    tmux kill-session -t "$TMUX_SESSION_C0" 2>/dev/null || true
    sleep 0.5
fi
if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[uart_logger] 기존 세션 '$TMUX_SESSION_C1' 종료 중..."
    tmux kill-session -t "$TMUX_SESSION_C1" 2>/dev/null || true
    sleep 0.5
fi

# c0: /dev/ttyUSB0 -> logs/c0.log (AI 읽기 대상, 콘솔)
echo "[uart_logger] c0 (/dev/ttyUSB0 -> logs/c0.log) 시작..."
tmux new-session -d -s "$TMUX_SESSION_C0" \
    "tio -b $BAUD -L --log-file '$LOGDIR/c0.log' --log-append --log-strip /dev/ttyUSB0"
sleep 1

# c1: /dev/ttyUSB1 -> logs/c1.log (플래싱/제어용)
echo "[uart_logger] c1 (/dev/ttyUSB1 -> logs/c1.log) 시작..."
tmux new-session -d -s "$TMUX_SESSION_C1" \
    "tio -b $BAUD -L --log-file '$LOGDIR/c1.log' --log-append --log-strip /dev/ttyUSB1"
sleep 1

echo "[uart_logger] 세션 상태:"
tmux list-sessions | grep -E "uart-c0|uart-c1" || true

echo "[uart_logger] 완료. 아래 명령으로 로그 확인:"
echo "  tail -n 100 logs/c0.log"
echo "  tail -n 100 logs/c1.log"
