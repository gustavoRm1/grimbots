#!/bin/bash

echo "🔍 VERIFICANDO - Se link de delivery está sendo enviado via Telegram"
echo "===================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se entregável está sendo enviado
echo "1️⃣ ENTREGÁVEL ESTÁ SENDO ENVIADO VIA TELEGRAM?"
echo "=============================================="
echo ""
ENTREGAVEL_ENVIADO=$(tail -2000 logs/gunicorn.log | grep -i "Entregável enviado\|delivery_token\|delivery_url" | wc -l)
echo "   Logs de entregável enviado: $ENTREGAVEL_ENVIADO"
echo ""

# 2. Verificar logs de entregável
echo "2️⃣ LOGS DE ENTREGÁVEL (últimas 30 linhas):"
echo "==========================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Entregável enviado|delivery_token|delivery_url|send_payment_delivery" | tail -30
echo ""

# 3. Verificar se delivery_token foi gerado
echo "3️⃣ delivery_token FOI GERADO?"
echo "=============================="
echo ""
DELIVERY_TOKEN=$(psql -U postgres -d grimbots -t -c "
SELECT COUNT(*) 
FROM payments 
WHERE status = 'paid' 
AND delivery_token IS NOT NULL 
AND created_at >= NOW() - INTERVAL '24 hours';
" 2>/dev/null | xargs)
echo "   Vendas com delivery_token: $DELIVERY_TOKEN"
echo ""

# 4. Verificar formato do link de delivery
echo "4️⃣ FORMATO DO LINK DE DELIVERY:"
echo "==============================="
echo ""
# Buscar uma venda recente com delivery_token
LAST_DELIVERY_TOKEN=$(psql -U postgres -d grimbots -t -c "
SELECT delivery_token 
FROM payments 
WHERE status = 'paid' 
AND delivery_token IS NOT NULL 
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_DELIVERY_TOKEN" ]; then
    echo "   delivery_token exemplo: $LAST_DELIVERY_TOKEN"
    echo "   Link de delivery seria: https://app.grimbots.online/delivery/$LAST_DELIVERY_TOKEN"
else
    echo "   ❌ Nenhum delivery_token encontrado"
fi
echo ""

# 5. Verificar logs de send_payment_delivery
echo "5️⃣ LOGS DE send_payment_delivery:"
echo "=================================="
echo ""
tail -2000 logs/gunicorn.log | grep -i "send_payment_delivery\|payment_delivery" | tail -20
echo ""

# 6. Verificar erros ao enviar entregável
echo "6️⃣ ERROS AO ENVIAR ENTREGÁVEL:"
echo "==============================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Erro ao enviar entregável|Erro.*delivery|delivery.*erro|delivery.*error" | tail -20
echo ""

# 7. Verificar se mensagem está sendo enviada via Telegram
echo "7️⃣ MENSAGEM ESTÁ SENDO ENVIADA VIA TELEGRAM?"
echo "============================================="
echo ""
TELEGRAM_SENT=$(tail -2000 logs/gunicorn.log | grep -iE "send_telegram_message|Telegram.*enviado|mensagem.*Telegram" | wc -l)
echo "   Mensagens enviadas via Telegram: $TELEGRAM_SENT"
echo ""

# 8. Verificar vendas sem delivery_token
echo "8️⃣ VENDAS SEM delivery_token:"
echo "=============================="
echo ""
NO_DELIVERY_TOKEN=$(psql -U postgres -d grimbots -t -c "
SELECT COUNT(*) 
FROM payments 
WHERE status = 'paid' 
AND delivery_token IS NULL 
AND created_at >= NOW() - INTERVAL '24 hours';
" 2>/dev/null | xargs)
echo "   Vendas sem delivery_token: $NO_DELIVERY_TOKEN"
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'entregável está sendo enviado' = 0:"
echo "      ❌ PROBLEMA: Link de delivery NÃO está sendo enviado via Telegram"
echo "      ✅ SOLUÇÃO: Verificar se send_payment_delivery() está sendo chamado (seção 5)"
echo ""
echo "   Se 'delivery_token foi gerado' = 0:"
echo "      ❌ PROBLEMA: delivery_token não está sendo gerado"
echo "      ✅ SOLUÇÃO: Verificar se send_payment_delivery() está gerando delivery_token"
echo ""
echo "   Se 'entregável está sendo enviado' > 0 mas 'acessos à página de delivery' = 0:"
echo "      ❌ PROBLEMA: Link está sendo enviado mas usuários não estão acessando"
echo "      ✅ SOLUÇÃO: Verificar formato do link (seção 4), verificar se link está correto no Telegram"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Verifique se link de delivery está sendo enviado (seção 1)"
echo "   2. Verifique formato do link (seção 4)"
echo "   3. Verifique se há erros ao enviar entregável (seção 6)"
echo "   4. Teste manualmente acessando um link de delivery de uma venda recente"
echo ""

