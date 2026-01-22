#!/bin/bash
set -euo pipefail

EMAIL="pixBOT13417692a2d25ca@bot.digital"
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

bold "=== INSPEÇÃO DE TRACKING – GRIMBOTS ==="
echo

info "Redis DB selecionado: $REDIS_DB"
info "Email alvo: $EMAIL"

echo
info "Procurando tracking_token pelo email (pode demorar)..."
TOKEN=$("${REDIS_CLI[@]}" KEYS "*${EMAIL}*" | head -n 1)

if [[ -z "$TOKEN" ]]; then
  warn "Nenhum tracking_token encontrado para este email"
  exit 0
fi

bold "✅ Tracking token encontrado"
printf '%s\n\n' "$TOKEN"

info "Carregando payload completo..."
RAW_PAYLOAD=$("${REDIS_CLI[@]}" GET "$TOKEN" || true)

if [[ -z "$RAW_PAYLOAD" ]]; then
  warn "Payload vazio ou chave expirada"
  exit 0
fi

echo "📦 Conteúdo do tracking payload:"
printf '%s' "$RAW_PAYLOAD" | jq .

echo
info "Campos críticos:" 
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

echo
info "Resumo matemático para atribuição:"
{
  echo "Token: $TOKEN"
  echo "Pixel ID:"; printf '%s' "$RAW_PAYLOAD" | jq -r '.pixel_id // "❌ ausente"'
  echo "PageView Event ID:"; printf '%s' "$RAW_PAYLOAD" | jq -r '.pageview_event_id // "❌ ausente"'
  echo "fbclid:"; printf '%s' "$RAW_PAYLOAD" | jq -r '.fbclid // "❌ ausente"'
  echo "fbp:"; printf '%s' "$RAW_PAYLOAD" | jq -r '.fbp // "❌ ausente"'
  echo "fbc:"; printf '%s' "$RAW_PAYLOAD" | jq -r '.fbc // "❌ ausente"'
} | sed 's/^/ - /'

echo
info "Para confirmar deduplicação, valide se eventID coincide com pageview_event_id informado acima."
info "Para confirmar pixel, compare pixel_id com o Pixel do anúncio/campanha no Meta Event Manager."
