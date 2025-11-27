#!/bin/bash
# Script para verificar se os jobs de assinaturas foram registrados nos logs

echo "======================================================================"
echo "📋 VERIFICAÇÃO DE JOBS DE ASSINATURAS (via logs)"
echo "======================================================================"
echo ""

# Tentar encontrar o arquivo de log correto
LOG_FILE=""

# Possíveis locais de logs
POSSIBLE_LOGS=(
    "${1:-}"  # Passado como parâmetro
    "logs/gunicorn.log"
    "logs/error.log"
    "logs/app.log"
    "logs/access.log"
)

# Procurar o primeiro arquivo que exista
for log in "${POSSIBLE_LOGS[@]}"; do
    if [ -n "$log" ] && [ -f "$log" ]; then
        LOG_FILE="$log"
        break
    fi
done

if [ -z "$LOG_FILE" ]; then
    echo "❌ Nenhum arquivo de log encontrado!"
    echo ""
    echo "📁 Procurado em:"
    for log in "${POSSIBLE_LOGS[@]}"; do
        [ -n "$log" ] && echo "   - $log"
    done
    echo ""
    echo "💡 Dica: Especifique o arquivo de log como parâmetro:"
    echo "   $0 logs/gunicorn.log"
    exit 1
fi

echo "✅ Usando log: $LOG_FILE"
echo ""

echo "🔍 Verificando logs: $LOG_FILE"
echo ""

# Jobs esperados
EXPECTED_JOBS=(
    "check_expired_subscriptions"
    "check_pending_subscriptions_in_groups"
    "retry_failed_subscription_removals"
)

ALL_FOUND=true

for job in "${EXPECTED_JOBS[@]}"; do
    if grep -q "✅ Job $job registrado" "$LOG_FILE"; then
        # Buscar linha completa do log
        LOG_LINE=$(grep "✅ Job $job registrado" "$LOG_FILE" | tail -1)
        echo "✅ $job: Encontrado"
        echo "   $LOG_LINE"
    else
        echo "❌ $job: NÃO ENCONTRADO"
        ALL_FOUND=false
    fi
    echo ""
done

echo "======================================================================"
if [ "$ALL_FOUND" = true ]; then
    echo "✅ TODOS OS JOBS FORAM REGISTRADOS COM SUCESSO!"
    exit 0
else
    echo "⚠️ ALGUNS JOBS NÃO FORAM ENCONTRADOS NOS LOGS!"
    echo ""
    echo "💡 Verifique se houve erros durante o registro:"
    echo "   grep -i 'erro.*job.*subscription' $LOG_FILE | tail -10"
    exit 1
fi

