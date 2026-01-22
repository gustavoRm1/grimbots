#!/bin/bash
set -euo pipefail

REFERENCE="BOT134-1769086772-d52cd682-1769086772392-58c642af"
GATEWAY_TRANSACTION_ID="3898629"

# Database (ajuste se a VPS usar host diferente)
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="grimbots"
DB_USER="postgres"

# Redis
REDIS_DB=0
REDIS_CLI=(redis-cli -n "$REDIS_DB")

bold() {
  printf '\033[1m%s\033[0m\n' "$1"
}

info() {
  printf 'ℹ️  %s\n' "$1"
}

warn() {
  printf '⚠️  %s\n' "$1"
}

bold "=== INSPEÇÃO CIRÚRGICA – VENDA ESPECÍFICA ==="
echo

info "Reference alvo: $REFERENCE"
info "gateway_transaction_id alvo: $GATEWAY_TRANSACTION_ID"
echo

# Derivar possíveis payment_id a partir da referência real (formato BOT###-ts-hash-...)
REFERENCE_PAYMENT_ID=""
REFERENCE_HASH_SLICE=""
if [[ "$REFERENCE" =~ ^([A-Za-z0-9]+)-([0-9]+)-([A-Za-z0-9]+) ]]; then
  REF_PART1="${BASH_REMATCH[1]}"
  REF_PART2="${BASH_REMATCH[2]}"
  REF_PART3="${BASH_REMATCH[3]}"
  REFERENCE_PAYMENT_ID="${REF_PART1}_${REF_PART2}_${REF_PART3}"
  REFERENCE_HASH_SLICE="$REF_PART3"
fi

if [[ -n "$REFERENCE_PAYMENT_ID" ]]; then
  info "payment_id derivado da referência: $REFERENCE_PAYMENT_ID"
else
  warn "Não foi possível derivar payment_id da referência (usando apenas gateway_transaction_id/pattern)."
fi

WHERE_CLAUSES=("gateway_transaction_id = '$GATEWAY_TRANSACTION_ID'")

if [[ -n "$REFERENCE_PAYMENT_ID" ]]; then
  WHERE_CLAUSES+=("payment_id = '$REFERENCE_PAYMENT_ID'")
  WHERE_CLAUSES+=("payment_id LIKE '%${REFERENCE_PAYMENT_ID#*_}%'")
fi

WHERE_CLAUSES+=("payment_id = '$REFERENCE'")
WHERE_CLAUSES+=("payment_id LIKE '%$REFERENCE%'")

if [[ -n "$REFERENCE_HASH_SLICE" ]]; then
  WHERE_CLAUSES+=("payment_id LIKE '%${REFERENCE_HASH_SLICE}%'")
fi

# Construir WHERE final (ex: WHERE (cond1) OR (cond2) ...)
WHERE_SQL="WHERE "
for idx in "${!WHERE_CLAUSES[@]}"; do
  clause="(${WHERE_CLAUSES[$idx]})"
  if [[ $idx -eq 0 ]]; then
    WHERE_SQL+="$clause"
  else
    WHERE_SQL+=" OR $clause"
  fi
done

info "PASSO 1 — Consultando Payment no Postgres (cadeia raiz)"

PAYMENT_SQL=$(cat <<EOF
SELECT
  id,
  payment_id,
  gateway_transaction_id,
  status,
  created_at,
  tracking_token,
  pageview_event_id,
  meta_pixel_id,
  fbclid,
  fbc,
  fbp
FROM payments
${WHERE_SQL}
ORDER BY created_at DESC
LIMIT 1;
EOF
)

PAYMENT_ROW=$(psql \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --set=sslmode=disable \
  --no-align --tuples-only --field-separator '|' \
  -c "$PAYMENT_SQL" 2>/tmp/inspect_payment.err || true)

if [[ -z "$PAYMENT_ROW" ]]; then
  warn "Payment NÃO encontrado. Verifique reference/gateway_transaction_id ou lag de replicação."
  warn "Saída do psql:"; cat /tmp/inspect_payment.err
  exit 1
fi

IFS='|' read -r PAYMENT_DB_ID PAYMENT_ID PAYMENT_GATEWAY_ID PAYMENT_STATUS PAYMENT_CREATED_AT PAYMENT_TRACKING_TOKEN PAYMENT_PAGEVIEW EVENT_PIXEL_ID PAYMENT_FBCLID PAYMENT_FBC PAYMENT_FBP <<<"$PAYMENT_ROW"

bold "✅ PAYMENT ENCONTRADO"
cat <<EOF
 - id.................: $PAYMENT_DB_ID
 - payment_id.........: $PAYMENT_ID
 - gateway_tx_id......: ${PAYMENT_GATEWAY_ID:-"❌"}
 - status.............: $PAYMENT_STATUS
 - created_at.........: $PAYMENT_CREATED_AT
 - tracking_token.....: ${PAYMENT_TRACKING_TOKEN:-"❌"}
 - pageview_event_id..: ${PAYMENT_PAGEVIEW:-"❌"}
 - meta_pixel_id......: ${EVENT_PIXEL_ID:-"❌"}
 - fbclid.............: ${PAYMENT_FBCLID:-"❌"}
 - fbc................: ${PAYMENT_FBC:-"❌"}
 - fbp................: ${PAYMENT_FBP:-"❌"}
EOF

echo
info "PASSO 2 — Diagnóstico imediato"
if [[ -z "$PAYMENT_TRACKING_TOKEN" ]]; then
  warn "tracking_token ausente ⇒ Purchase não está ligado a nenhum PageView (Meta não atribui)."
else
  info "tracking_token presente ⇒ recuperar payload do Redis para confirmar cadeia."
fi

if [[ -z "$PAYMENT_PAGEVIEW" ]]; then
  warn "pageview_event_id ausente ⇒ mesmo com token, deduplicação client/server falha."
else
  info "pageview_event_id salvo ⇒ verificar se combina com delivery/event manager."
fi

if [[ -z "$EVENT_PIXEL_ID" ]]; then
  warn "meta_pixel_id ausente no Payment ⇒ Purchase seria disparado sem pixel válido."
else
  info "Pixel registrado no Payment: $EVENT_PIXEL_ID"
fi

if [[ -n "$PAYMENT_TRACKING_TOKEN" ]]; then
  echo
  info "PASSO 3 — Auditoria Redis (tracking:$PAYMENT_TRACKING_TOKEN)"
  TRACKING_KEY="tracking:$PAYMENT_TRACKING_TOKEN"
  RAW_PAYLOAD=$("${REDIS_CLI[@]}" GET "$TRACKING_KEY" || true)

  if [[ -z "$RAW_PAYLOAD" ]]; then
    warn "Payload ausente/expirado no Redis para $TRACKING_KEY"
  else
    echo "📦 Payload completo:" | tee /dev/stderr
    printf '%s' "$RAW_PAYLOAD" | jq .

    echo
    info "Campos críticos (pixel/pageview/fbclid/etc.):"
    printf '%s' "$RAW_PAYLOAD" | jq '{
      pixel_id,
      redirect_id,
      fbclid,
      fbp,
      fbc,
      pageview_event_id,
      event_source_url,
      tracking_token
    }'
  fi

  echo
  info "Passo extra — Localizando todas as chaves relacionadas"
  "${REDIS_CLI[@]}" --scan --pattern "*${PAYMENT_TRACKING_TOKEN}*"
fi

echo
info "PASSO 4 — Checklist final"
if [[ -z "$PAYMENT_TRACKING_TOKEN" ]]; then
  warn "Causa raiz provável: Purchase disparado sem tracking_token ⇒ Meta recebe evento sem PageView correspondente."
elif [[ -n "$PAYMENT_TRACKING_TOKEN" && -z "$PAYMENT_PAGEVIEW" ]]; then
  warn "Token existe mas pageview_event_id não foi persistido ⇒ deduplicação impossibilitada."
else
  info "Token + pageview_event_id presentes. Validar no Meta se event_id coincide e se pixel "$EVENT_PIXEL_ID" pertence à campanha."
fi
