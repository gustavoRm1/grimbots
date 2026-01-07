#!/usr/bin/env bash
set -euo pipefail

# Caminho do banco SQLite. Ajuste se estiver em outro local.
DB_PATH=${DB_PATH:-"instance/saas_bot_manager.db"}

PAYMENT_ID=${1:-2749720}

QUERY="""
SELECT 
  id,
  status,
  created_at,
  tracking_token,
  pageview_event_id,
  meta_event_id,
  meta_purchase_sent,
  meta_purchase_sent_at,
  fbclid,
  fbc,
  fbp
FROM payments
WHERE id = ${PAYMENT_ID};
"""

if [ ! -f "$DB_PATH" ]; then
  echo "Erro: banco não encontrado em $DB_PATH" >&2
  exit 1
fi

sqlite3 -header -column "$DB_PATH" "$QUERY"
