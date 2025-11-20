#!/bin/bash

echo "🔍 MONITORAMENTO EM TEMPO REAL - Purchase Events"
echo "================================================"
echo ""
echo "Monitorando logs em tempo real..."
echo ""
echo "📋 O que será monitorado:"
echo "   1. Acessos à página /delivery (Purchase disparado)"
echo "   2. Purchase client-side disparado"
echo "   3. Purchase server-side disparado"
echo "   4. Deduplicação (meta_purchase_sent)"
echo "   5. Event ID usado (para verificar matching)"
echo ""
echo "⏹️  Para parar, pressione Ctrl+C"
echo ""
echo "================================================"
echo ""

# Filtrar logs relevantes em tempo real
tail -f logs/gunicorn.log | grep --line-buffered -iE \
  "DELIVERY|Purchase|meta_purchase_sent|event_id|eventID|META DELIVERY|pixel_config" | \
  grep --line-buffered -vE "INFO -.*Estrutura recebida" | \
  while IFS= read -r line; do
    # Colorir por tipo
    if echo "$line" | grep -qiE "Purchase disparado|Purchase via Server|Purchase via Server enfileirado"; then
      echo -e "\033[32m✅ $line\033[0m"
    elif echo "$line" | grep -qiE "meta_purchase_sent.*True|Purchase já foi enviado|pulando client-side"; then
      echo -e "\033[33m⚠️  $line\033[0m"
    elif echo "$line" | grep -qiE "event_id|eventID"; then
      echo -e "\033[36m🔑 $line\033[0m"
    elif echo "$line" | grep -qiE "Delivery.*Renderizando|Delivery.*recuperado"; then
      echo -e "\033[34m📄 $line\033[0m"
    elif echo "$line" | grep -qiE "Erro|ERROR|❌"; then
      echo -e "\033[31m❌ $line\033[0m"
    else
      echo "$line"
    fi
  done
