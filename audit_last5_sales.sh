#!/usr/bin/env bash
set -euo pipefail

# Config DB/Redis (ajuste conforme seu ambiente)
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=grimbots}"
: "${REDIS_URL:=redis://localhost:6379/0}"

# Filtros opcionais
PAY_ID="${PAY_ID:-}"            # id (pk)
PAYMENT_ID="${PAYMENT_ID:-}"    # payment_id string
GATEWAY_ID="${GATEWAY_ID:-}"    # gateway_transaction_id

WHERE_CLAUSE="status = 'paid'"
if [[ -n "$PAY_ID" ]]; then
  WHERE_CLAUSE="id = ${PAY_ID}"
elif [[ -n "$PAYMENT_ID" ]]; then
  WHERE_CLAUSE="payment_id = '${PAYMENT_ID}'"
elif [[ -n "$GATEWAY_ID" ]]; then
  WHERE_CLAUSE="gateway_transaction_id = '${GATEWAY_ID}'"
fi

LIMIT_CLAUSE="LIMIT 5"
if [[ -n "$PAY_ID" || -n "$PAYMENT_ID" || -n "$GATEWAY_ID" ]]; then
  LIMIT_CLAUSE="LIMIT 20"
fi

# Lista pagamentos conforme filtro (default: últimos 5 pagos)
TMP_JSON=$(mktemp)
psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -At -c "
  SELECT json_agg(row_to_json(t)) FROM (
    SELECT id, payment_id, gateway_transaction_id, bot_id, amount, status,
           tracking_token, pageview_event_id, fbp, fbc, fbclid,
           created_at, paid_at
    FROM payments
    WHERE ${WHERE_CLAUSE}
    ORDER BY paid_at DESC NULLS LAST, created_at DESC
    ${LIMIT_CLAUSE}
  ) t;
" > "$TMP_JSON"

RESULT=$(cat "$TMP_JSON")
if [[ "$RESULT" == "null" || -z "$RESULT" ]]; then
  echo "Nenhuma venda encontrada."
  exit 0
fi

# Função para ler Redis via redis-cli usando redis:// URL
redis_get() {
  local key="$1"
  redis-cli -u "$REDIS_URL" GET "$key"
}

# Iterate and enrich with Redis pixel info
python3 - <<'PY'
import json, os, subprocess, sys
RAW = os.environ.get('RESULT')
if not RAW or RAW == 'null':
    print('Nenhuma venda encontrada.')
    sys.exit(0)
try:
    data = json.loads(RAW)
except Exception as e:
    print(f"Erro ao decodificar JSON de payments: {e}")
    sys.exit(1)

def fetch_redis(token: str):
    try:
        out = subprocess.check_output([
            'redis-cli','-u', os.environ.get('REDIS_URL','redis://localhost:6379/0'),
            'GET', f'tracking:{token}'
        ], text=True).strip()
        if not out:
            return None
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}

enriched = []
for p in data:
    token = p.get('tracking_token')
    redis_payload = fetch_redis(token) if token else None
    enriched.append({
        "payment_id": p.get('payment_id'),
        "db_id": p.get('id'),
        "gateway_transaction_id": p.get('gateway_transaction_id'),
        "bot_id": p.get('bot_id'),
        "amount": p.get('amount'),
        "status": p.get('status'),
        "paid_at": p.get('paid_at'),
        "tracking_token": token,
        "pixel_delivery_fallback": None,  # Payment não guarda meta_pixel_id
        "pixel_redirect_from_redis": (redis_payload or {}).get('pixel_id') or (redis_payload or {}).get('meta_pixel_id'),
        "redirect_id": (redis_payload or {}).get('redirect_id'),
        "fbp": p.get('fbp') or (redis_payload or {}).get('fbp'),
        "fbc": p.get('fbc') or (redis_payload or {}).get('fbc'),
        "fbclid": p.get('fbclid') or (redis_payload or {}).get('fbclid'),
        "utm_source": (redis_payload or {}).get('utm_source'),
        "utm_campaign": (redis_payload or {}).get('utm_campaign'),
        "event_source_url": (redis_payload or {}).get('event_source_url'),
        "redis_raw": redis_payload,
    })

print(json.dumps(enriched, ensure_ascii=False, indent=2))
PY
PY_RESULT=$?
exit $PY_RESULT
