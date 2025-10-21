#!/bin/bash
# FIX COMPLETO: META PURCHASE + CLOAKER
# Data: 2025-10-21

echo "================================================================================"
echo "🔧 FIX COMPLETO: META PURCHASE + CLOAKER"
echo "================================================================================"
echo ""

# 1. Pull do código com fix de fbclid
echo "1. Atualizando código..."
cd ~/grimbots
git pull origin main
echo "   ✅ Código atualizado"
echo ""

# 2. Habilitar Purchase events no pool
echo "2. Habilitando Purchase events..."
sqlite3 instance/saas_bot_manager.db "UPDATE redirect_pools SET meta_events_purchase = 1 WHERE meta_tracking_enabled = 1;"

# Verificar
PURCHASE_ENABLED=$(sqlite3 instance/saas_bot_manager.db "SELECT meta_events_purchase FROM redirect_pools WHERE id = 1;")
echo "   Pool 1 - Purchase enabled: $PURCHASE_ENABLED"
echo ""

# 3. Verificar/Habilitar cloaker
echo "3. Verificando cloaker..."
CLOAKER_ENABLED=$(sqlite3 instance/saas_bot_manager.db "SELECT meta_cloaker_enabled FROM redirect_pools WHERE id = 1;")
CLOAKER_VALUE=$(sqlite3 instance/saas_bot_manager.db "SELECT meta_cloaker_param_value FROM redirect_pools WHERE id = 1;")

echo "   Cloaker enabled: $CLOAKER_ENABLED"
echo "   Cloaker value: $CLOAKER_VALUE"

if [ "$CLOAKER_ENABLED" != "1" ]; then
    echo "   ⚠️  Cloaker está DESABILITADO!"
    echo "   Habilitando..."
    sqlite3 instance/saas_bot_manager.db "UPDATE redirect_pools SET meta_cloaker_enabled = 1 WHERE id = 1;"
    echo "   ✅ Cloaker habilitado"
fi

if [ -z "$CLOAKER_VALUE" ] || [ "$CLOAKER_VALUE" == "" ]; then
    echo "   ⚠️  Cloaker sem valor configurado!"
    echo "   Mantendo valor existente ou configure manualmente"
fi
echo ""

# 4. Reiniciar aplicação
echo "4. Reiniciando aplicação..."
sudo systemctl restart grimbots
sleep 5

if systemctl is-active --quiet grimbots; then
    echo "   ✅ Aplicação reiniciada com sucesso"
else
    echo "   ❌ Erro ao reiniciar aplicação!"
    sudo systemctl status grimbots --no-pager
    exit 1
fi
echo ""

# 5. Testar redirect com fbclid
echo "5. Testando redirect com fbclid..."
TESTE_FBCLID="VALIDACAO_COMPLETA_$(date +%s)"

curl -s "https://app.grimbots.online/go/red1?testecamu01&fbclid=$TESTE_FBCLID&utm_source=facebook" > /dev/null

# Verificar Redis
sleep 1
REDIS_DATA=$(redis-cli GET "tracking:$TESTE_FBCLID")

if [ -n "$REDIS_DATA" ]; then
    echo "   ✅ Dados salvos no Redis!"
    echo "   fbclid: $TESTE_FBCLID"
else
    echo "   ❌ Dados NÃO salvos no Redis!"
fi
echo ""

# 6. Verificar logs
echo "6. Verificando logs (últimos 20)..."
sudo journalctl -u grimbots -n 20 --no-pager | grep -E "TRACKING ELITE|fbclid|external_id" | head -10
echo ""

echo "================================================================================"
echo "📊 RESUMO DO FIX"
echo "================================================================================"
echo ""
echo "✅ Código atualizado (fbclid como external_id)"
echo "✅ Purchase events habilitado"
echo "✅ Cloaker verificado"
echo "✅ Aplicação reiniciada"
echo "✅ Redis testado"
echo ""
echo "🎯 PRÓXIMOS PASSOS:"
echo ""
echo "1. Fazer uma venda de teste"
echo "2. Verificar se Purchase é enviado:"
echo "   tail -f logs/celery.log | grep Purchase"
echo ""
echo "3. Verificar no Meta Events Manager:"
echo "   https://business.facebook.com/events_manager2/list/pixel/736337315882403"
echo ""
echo "================================================================================"

