#!/usr/bin/env bash
set -euo pipefail

# Corrige permissões da tabela meta_tracking_sessions e da sequência associada (PostgreSQL)
# Uso: ./scripts/grant_meta_tracking_sessions.sh "postgres://USER:PASSWORD@HOST:5432/DBNAME" APP_USER
# Exemplo: ./scripts/grant_meta_tracking_sessions.sh "postgres://postgres:123@localhost:5432/grimbots" grimbots

DB_URL="${1:-}"
APP_USER="${2:-}"

if [[ -z "$DB_URL" || -z "$APP_USER" ]]; then
  echo "Uso: $0 \"postgres://USER:PASSWORD@HOST:5432/DBNAME\" APP_USER" >&2
  exit 1
fi

SQL=$(cat <<EOF
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE meta_tracking_sessions TO "$APP_USER";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE meta_tracking_sessions_id_seq TO "$APP_USER";
EOF
)

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "$SQL"

echo "Permissões aplicadas para o usuário $APP_USER na tabela meta_tracking_sessions."
