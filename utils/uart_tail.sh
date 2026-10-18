#!/bin/bash
# UART 로그 tail 스크립트 (AI가 로그 읽을 때 사용)
# 기본값: c0 로그의 마지막 200줄 출력
#
# 실행: bash utils/uart_tail.sh [c0|c1] [줄수]
#
# 예: bash utils/uart_tail.sh c0 200

set -euo pipefail

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$BASEDIR/logs"

TARGET="${1:-c0}"
LINES="${2:-200}"

case "$TARGET" in
    c0) LOGFILE="$LOGDIR/c0.log" ;;
    c1) LOGFILE="$LOGDIR/c1.log" ;;
    *)
        echo "사용법: $0 [c0|c1] [줄수]"
        echo "  c0: /dev/ttyUSB0 로그 (AI 읽기 대상)"
        echo "  c1: /dev/ttyUSB1 로그 (플래싱/제어용)"
        exit 1
        ;;
esac

if [ ! -f "$LOGFILE" ]; then
    echo "[uart_tail] 로그 파일이 존재하지 않음: $LOGFILE"
    echo "[uart_tail] 먼저 'bash utils/uart_logger_start.sh' 로 로거를 시작하세요."
    exit 1
fi

echo "[uart_tail] 파일: $LOGFILE  (마지막 $LINES 줄)"
echo "------------------------------------------------------------"
tail -n "$LINES" "$LOGFILE"
echo "------------------------------------------------------------"
