#!/bin/bash
# Script para monitorar logs em tempo real
# Foca em tracking, fbc, fbp e eventos Meta Pixel

echo "=========================================="
echo "  MONITORAMENTO TEMPO REAL - TRACKING"
echo "=========================================="
echo ""
echo "Monitorando logs do Celery (Meta Pixel) e error.log (tracking)"
echo "Pressione Ctrl+C para parar"
echo ""

# Função para destacar linhas importantes
highlight_line() {
    local line="$1"
    
    # Erros em vermelho
    if echo "$line" | grep -qiE "error|❌|falha|failed|exception"; then
        echo -e "\033[31m$line\033[0m"
    # Sucessos em verde
    elif echo "$line" | grep -qiE "✅|success|sucesso|enviado|received.*1"; then
        echo -e "\033[32m$line\033[0m"
    # Avisos em amarelo
    elif echo "$line" | grep -qiE "⚠️|warning|aviso|não encontrado"; then
        echo -e "\033[33m$line\033[0m"
    # fbc/fbp em ciano
    elif echo "$line" | grep -qiE "fbc|fbp|process_start_async.*fbc|Purchase.*fbc"; then
        echo -e "\033[36m$line\033[0m"
    # Purchase events em magenta
    elif echo "$line" | grep -qiE "Purchase ENVIADO|META PAYLOAD.*Purchase|META RESPONSE.*Purchase"; then
        echo -e "\033[35m$line\033[0m"
    # PageView events em azul
    elif echo "$line" | grep -qiE "PageView|META PAYLOAD.*PageView"; then
        echo -e "\033[34m$line\033[0m"
    else
        echo "$line"
    fi
}

# Monitorar múltiplos arquivos de log simultaneamente
tail -f logs/celery.log logs/error.log 2>/dev/null | while read line; do
    # Filtrar apenas linhas relevantes
    if echo "$line" | grep -qiE "fbc|fbp|Purchase|PageView|Meta|tracking|2804019|creationTime|process_start_async|send_meta_pixel"; then
        highlight_line "$line"
    fi
done

