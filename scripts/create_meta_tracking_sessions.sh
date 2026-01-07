#!/usr/bin/env bash
set -euo pipefail

# Cria a tabela meta_tracking_sessions se ela não existir (PostgreSQL)
# Uso: ./scripts/create_meta_tracking_sessions.sh "postgres://user:pass@host:5432/dbname"

DB_URL="${1:-}"
if [[ -z "$DB_URL" ]]; then
  echo "Uso: $0 \"postgres://user:pass@host:5432/dbname\"" >&2
  exit 1
fi

SQL=$(cat <<'EOF'
CREATE TABLE IF NOT EXISTS meta_tracking_sessions (
  id SERIAL PRIMARY KEY,
  tracking_token TEXT UNIQUE NOT NULL,
  root_event_id TEXT NOT NULL,
  pageview_sent BOOLEAN DEFAULT FALSE,
  pageview_sent_at TIMESTAMPTZ,
  fbclid TEXT,
  fbc TEXT,
  fbp TEXT,
  user_external_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_meta_tracking_sessions_tracking_token
  ON meta_tracking_sessions(tracking_token);
EOF
)

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "$SQL"

echo "Tabela meta_tracking_sessions criada/garantida com sucesso."
