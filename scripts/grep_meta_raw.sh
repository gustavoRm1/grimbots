#!/usr/bin/env bash
set -euo pipefail

# Uso: ./scripts/grep_meta_raw.sh <event_id_ou_payment_id> [LOG_PATH]
# Exemplos:
#   ./scripts/grep_meta_raw.sh 2749720
#   ./scripts/grep_meta_raw.sh evt_xxx_purchase_2749720 /var/log/celery/worker.log

TARGET=${1:-}
LOG_PATH=${2:-"logs/celery.log"}

if [ -z "$TARGET" ]; then
  echo "Uso: $0 <event_id_ou_payment_id> [LOG_PATH]" >&2
  exit 1
fi

if [ ! -f "$LOG_PATH" ]; then
  echo "Aviso: log não encontrado em $LOG_PATH" >&2
  echo "Se usar systemd/journald, rode:" >&2
  echo "  journalctl -u celery -n 5000 --no-pager | grep '[META RAW RESPONSE]' | grep "$TARGET"" >&2
  exit 2
fi

grep -F "[META RAW RESPONSE]" "$LOG_PATH" | grep "$TARGET"
