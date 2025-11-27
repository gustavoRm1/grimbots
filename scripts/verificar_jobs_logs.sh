#!/bin/bash
# Script para verificar se os jobs de assinaturas foram registrados nos logs

echo "======================================================================"
echo "📋 VERIFICAÇÃO DE JOBS DE ASSINATURAS (via logs)"
echo "======================================================================"
echo ""

LOG_FILE="${1:-logs/app.log}"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Arquivo de log não encontrado: $LOG_FILE"
    exit 1
fi

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

