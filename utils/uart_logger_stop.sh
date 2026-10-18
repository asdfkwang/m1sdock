#!/bin/bash
# UART Logger 중지 스크립트
# 플래싱 전 실행하여 포트 점유 해제
#
# 실행: bash utils/uart_logger_stop.sh

set -euo pipefail

TMUX_SESSION_C0="uart-c0"
TMUX_SESSION_C1="uart-c1"

echo "[uart_logger] =========================================="
echo "[uart_logger] 중지: UART 로거 (c0 / c1)"
echo "[uart_logger] =========================================="

if tmux has-session -t "$TMUX_SESSION_C0" 2>/dev/null; then
    echo "[uart_logger] 세션 '$TMUX_SESSION_C0' 종료..."
    tmux kill-session -t "$TMUX_SESSION_C0" 2>/dev/null || true
else
    echo "[uart_logger] 세션 '$TMUX_SESSION_C0' 실행 중이 아님"
fi

if tmux has-session -t "$TMUX_SESSION_C1" 2>/dev/null; then
    echo "[uart_logger] 세션 '$TMUX_SESSION_C1' 종료..."
    tmux kill-session -t "$TMUX_SESSION_C1" 2>/dev/null || true
else
    echo "[uart_logger] 세션 '$TMUX_SESSION_C1' 실행 중이 아님"
fi

echo "[uart_logger] 완료. 포트 점유 해제됨."
