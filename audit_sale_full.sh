#!/usr/bin/env bash
set -euo pipefail

# Config DB/Redis (ajuste se necessário)
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=grimbots}"
: "${REDIS_URL:=redis://localhost:6379/0}"

# Filtros opcionais
PAY_ID="${PAY_ID:-}"               # id (pk)
PAYMENT_ID="${PAYMENT_ID:-}"       # payment_id string
GATEWAY_ID="${GATEWAY_ID:-}"       # gateway_transaction_id
PAYMENT_ID_GW="${PAYMENT_ID_GW:-}" # campo payment_id_gw (se existir)
LIMIT_ROWS="${LIMIT_ROWS:-5}"
STATUS_FILTER="${STATUS_FILTER:-status IN ('paid','approved','APPROVED','PAGO')}"
ANY_STATUS="${ANY_STATUS:-1}"      # 1 = ignora filtro de status
EXACT_MATCH="${EXACT_MATCH:-0}"    # 1 = usa igualdade ao invés de ILIKE

build_where() {
  local where
  if [[ -n "$PAY_ID" ]]; then
    where="id = ${PAY_ID}"
  elif [[ -n "$PAYMENT_ID" ]]; then
    if [[ "$EXACT_MATCH" == "1" ]]; then
      where="payment_id = '${PAYMENT_ID}'"
    else
      where="payment_id ILIKE '%${PAYMENT_ID}%'"
    fi
  elif [[ -n "$PAYMENT_ID_GW" ]]; then
    if [[ "$EXACT_MATCH" == "1" ]]; then
      where="payment_id_gw = '${PAYMENT_ID_GW}'"
    else
      where="payment_id_gw ILIKE '%${PAYMENT_ID_GW}%'"
    fi
  elif [[ -n "$GATEWAY_ID" ]]; then
    if [[ "$EXACT_MATCH" == "1" ]]; then
      where="gateway_transaction_id = '${GATEWAY_ID}'"
    else
      where="gateway_transaction_id ILIKE '%${GATEWAY_ID}%'"
    fi
  else
    where="1=1"
  fi
  if [[ "$ANY_STATUS" != "1" ]]; then
    where="(${where}) AND (${STATUS_FILTER})"
  fi
  echo "$where"
}

WHERE_CLAUSE=$(build_where)
TMP_JSON=$(mktemp)

psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
  SELECT json_agg(row_to_json(t)) FROM (
    SELECT id, payment_id, gateway_transaction_id, bot_id, amount, status,
           payment_id_gw, tracking_token, pageview_event_id, fbp, fbc, fbclid,
           created_at, paid_at
    FROM payments
    WHERE ${WHERE_CLAUSE}
    ORDER BY COALESCE(paid_at, created_at) DESC
    LIMIT ${LIMIT_ROWS}
  ) t;" > "$TMP_JSON"

RESULT=$(cat "$TMP_JSON")
if [[ "$RESULT" == "null" || -z "$RESULT" ]]; then
  echo "Nenhum resultado. WHERE=${WHERE_CLAUSE}" >&2
  # Tentar sugerir candidatos por payment_id se PAYMENT_ID foi passado
  if [[ -n "$PAYMENT_ID" ]]; then
    psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
      SELECT payment_id FROM payments
      WHERE payment_id ILIKE '%${PAYMENT_ID}%'
      ORDER BY id DESC
      LIMIT 5;
    " >&2 || true
  fi
  if [[ -n "$PAYMENT_ID_GW" ]]; then
    psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
      SELECT payment_id_gw FROM payments
      WHERE payment_id_gw ILIKE '%${PAYMENT_ID_GW}%'
      ORDER BY id DESC
      LIMIT 5;
    " >&2 || true
  fi
  # Fallback: mostrar últimas 50 vendas (qualquer status) para inspeção manual
  echo "-- Últimas 50 vendas (qualquer status) --" >&2
  psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
    SELECT id, payment_id, gateway_transaction_id, status, amount, created_at, paid_at
    FROM payments
    ORDER BY COALESCE(paid_at, created_at) DESC
    LIMIT 50;
  " >&2 || true

  # Se houver PAYMENT_ID, fazer busca por prefixo de 12 chars (mais ampla)
  if [[ -n "$PAYMENT_ID" ]]; then
    PREFIX=${PAYMENT_ID:0:12}
    echo "-- Busca por prefixo '${PREFIX}' --" >&2
    psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
      SELECT id, payment_id, gateway_transaction_id, status, amount, created_at
      FROM payments
      WHERE payment_id ILIKE '%${PREFIX}%'
      ORDER BY id DESC
      LIMIT 20;
    " >&2 || true
  fi
  if [[ -n "$PAYMENT_ID_GW" ]]; then
    PREFIX=${PAYMENT_ID_GW:0:12}
    echo "-- Busca por prefixo payment_id_gw '${PREFIX}' --" >&2
    psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
      SELECT id, payment_id_gw, payment_id, gateway_transaction_id, status, amount, created_at
      FROM payments
      WHERE payment_id_gw ILIKE '%${PREFIX}%'
      ORDER BY id DESC
      LIMIT 20;
    " >&2 || true
  fi
  exit 0
fi

python3 - <<'PY'
import json, os, subprocess
RAW = os.environ.get('RESULT')
if not RAW or RAW == 'null':
    print('Nenhum resultado (json nulo)')
    raise SystemExit
try:
    data = json.loads(RAW)
except Exception as e:
    print(f"Erro ao decodificar JSON: {e}")
    raise SystemExit

REDIS_URL = os.environ.get('REDIS_URL','redis://localhost:6379/0')

def fetch_redis(token: str):
    if not token:
        return None
    try:
        out = subprocess.check_output(['redis-cli','-u', REDIS_URL,'GET', f'tracking:{token}'], text=True).strip()
        if not out:
            return None
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}

enriched = []
for p in data:
    token = p.get('tracking_token')
    r = fetch_redis(token)
    enriched.append({
        "db_id": p.get('id'),
        "payment_id": p.get('payment_id'),
        "gateway_transaction_id": p.get('gateway_transaction_id'),
        "bot_id": p.get('bot_id'),
        "amount": p.get('amount'),
        "status": p.get('status'),
        "created_at": p.get('created_at'),
        "paid_at": p.get('paid_at'),
        "tracking_token": token,
        "pageview_event_id": p.get('pageview_event_id'),
        "fbp": p.get('fbp'),
        "fbc": p.get('fbc'),
        "fbclid": p.get('fbclid'),
        "pixel_redirect_from_redis": (r or {}).get('pixel_id') or (r or {}).get('meta_pixel_id'),
        "redirect_id": (r or {}).get('redirect_id'),
        "utm_source": (r or {}).get('utm_source'),
        "utm_campaign": (r or {}).get('utm_campaign'),
        "event_source_url": (r or {}).get('event_source_url'),
        "redis_raw": r,
    })

print(json.dumps(enriched, ensure_ascii=False, indent=2))
PY
PY_RESULT=$?
exit $PY_RESULT
