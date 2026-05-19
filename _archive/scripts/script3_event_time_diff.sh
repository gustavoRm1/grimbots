#!/bin/bash

if [ $# -ne 2 ]; then
  echo "Uso:"
  echo "./script3_event_time_diff.sh <event_time_unix> '<created_at>'"
  echo "Exemplo:"
  echo "./script3_event_time_diff.sh 1736172000 '2025-12-31 23:59:00'"
  exit 1
fi

EVENT_TIME="$1"
CREATED_AT="$2"

CREATED_EPOCH=$(date -d "$CREATED_AT" +%s 2>/dev/null)
if [ -z "$CREATED_EPOCH" ]; then
  echo "Erro: formato inválido de created_at"
  exit 1
fi

DIFF=$((EVENT_TIME - CREATED_EPOCH))

echo "event_time (unix):           $EVENT_TIME"
echo "payment.created_at (epoch): $CREATED_EPOCH"
echo "Diferença (segundos):       $DIFF"
