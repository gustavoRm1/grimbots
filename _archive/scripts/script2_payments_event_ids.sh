#!/bin/bash

echo "=============================================="
echo " PAYMENTS × EVENT_ID (META TRACKING)"
echo "=============================================="
echo ""

# Detecta DB/USER a partir de variáveis ou defaults
DB_NAME="${DB_NAME:-grimbots}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

echo "Usando conexão: user=$DB_USER db=$DB_NAME host=$DB_HOST port=$DB_PORT"
echo ""

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<'EOF'
SELECT
  id,
  created_at,
  meta_event_id,
  pageview_event_id,
  utm_source,
  campaign_code
FROM payments
ORDER BY created_at DESC
LIMIT 15;
EOF
