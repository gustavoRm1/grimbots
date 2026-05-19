#!/bin/bash

echo "🔍 VERIFICANDO - Por que link não está sendo enviado via Telegram?"
echo "==================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se send_payment_delivery está sendo chamado
echo "1️⃣ send_payment_delivery ESTÁ SENDO CHAMADO?"
echo "============================================"
echo ""
SEND_DELIVERY_CALLED=$(tail -2000 logs/gunicorn.log | grep -iE "Enviando entregável|send_payment_delivery|📦 Enviando entregável" | wc -l)
echo "   Chamadas a send_payment_delivery: $SEND_DELIVERY_CALLED"
echo ""

# 2. Verificar se há erros ao enviar entregável
echo "2️⃣ ERROS AO ENVIAR ENTREGÁVEL:"
echo "==============================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Erro ao enviar entregável|Erro ao enviar mensagem Telegram|Erro.*delivery|delivery.*erro" | tail -20
echo ""

# 3. Verificar se há bloqueios em send_payment_delivery
echo "3️⃣ BLOQUEIOS EM send_payment_delivery:"
echo "======================================="
echo ""
echo "   a) Payment ou bot inválido:"
tail -2000 logs/gunicorn.log | grep -i "Payment ou bot inválido" | wc -l | xargs echo "      "
echo ""
echo "   b) Status inválido (não é 'paid'):"
tail -2000 logs/gunicorn.log | grep -i "BLOQUEADO.*status inválido\|status != 'paid'" | wc -l | xargs echo "      "
echo ""
echo "   c) Sem customer_user_id:"
tail -2000 logs/gunicorn.log | grep -i "não tem customer_user_id" | wc -l | xargs echo "      "
echo ""
echo "   d) Sem bot.token:"
tail -2000 logs/gunicorn.log | grep -i "bot.*não tem token\|token.*inválido" | wc -l | xargs echo "      "
echo ""

# 4. Verificar se delivery_token está sendo gerado
echo "4️⃣ delivery_token ESTÁ SENDO GERADO?"
echo "====================================="
echo ""
DELIVERY_TOKEN_GENERATED=$(tail -2000 logs/gunicorn.log | grep -i "delivery_token gerado" | wc -l)
echo "   delivery_token gerados: $DELIVERY_TOKEN_GENERATED"
echo ""

# 5. Verificar se mensagem está sendo enviada via Telegram
echo "5️⃣ MENSAGEM ESTÁ SENDO ENVIADA VIA TELEGRAM?"
echo "============================================="
echo ""
TELEGRAM_SENT=$(tail -2000 logs/gunicorn.log | grep -iE "Entregável enviado|send_telegram_message.*sucesso|mensagem.*Telegram.*enviada" | wc -l)
echo "   Mensagens enviadas via Telegram: $TELEGRAM_SENT"
echo ""

# 6. Verificar erros ao enviar mensagem via Telegram
echo "6️⃣ ERROS AO ENVIAR MENSAGEM VIA TELEGRAM:"
echo "=========================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Erro ao enviar mensagem Telegram|Telegram.*erro|bot bloqueado|chat_id.*inválido" | tail -20
echo ""

# 7. Verificar logs de send_payment_delivery para uma venda específica
echo "7️⃣ LOGS DE send_payment_delivery PARA VENDA ESPECÍFICA:"
echo "========================================================"
echo ""
LAST_PAYMENT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT payment_id FROM payments 
WHERE status = 'paid' 
AND delivery_token IS NOT NULL 
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_PAYMENT_ID" ]; then
    echo "   Buscando logs para payment: $LAST_PAYMENT_ID"
    tail -5000 logs/gunicorn.log | grep -i "$LAST_PAYMENT_ID" | grep -iE "delivery|entregável|send_payment_delivery|Telegram" | tail -20
else
    echo "   ❌ Nenhuma venda recente encontrada"
fi
echo ""

# 8. Verificar logs de webhook/reconciliação
echo "8️⃣ LOGS DE WEBHOOK/RECONCILIAÇÃO:"
echo "=================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "webhook|reconciliação|reconcile.*payment" | grep -iE "paid|entregável|delivery" | tail -15
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'send_payment_delivery está sendo chamado' = 0:"
echo "      ❌ PROBLEMA: send_payment_delivery NÃO está sendo chamado quando payment é confirmado"
echo "      ✅ SOLUÇÃO: Verificar se webhook/reconciliação está chamando send_payment_delivery"
echo ""
echo "   Se há bloqueios em send_payment_delivery:"
echo "      ❌ PROBLEMA: Alguma verificação está bloqueando o envio"
echo "      ✅ SOLUÇÃO: Corrigir problema identificado (status, customer_user_id, bot.token, etc)"
echo ""
echo "   Se 'delivery_token está sendo gerado' > 0 mas 'mensagem está sendo enviada' = 0:"
echo "      ❌ PROBLEMA: delivery_token está sendo gerado mas mensagem não está sendo enviada"
echo "      ✅ SOLUÇÃO: Verificar erros ao enviar mensagem via Telegram (seção 6)"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Verifique se send_payment_delivery está sendo chamado (seção 1)"
echo "   2. Verifique bloqueios em send_payment_delivery (seção 3)"
echo "   3. Verifique erros ao enviar mensagem via Telegram (seção 6)"
echo "   4. Teste com uma nova venda após corrigir o problema"
echo ""

