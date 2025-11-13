#!/bin/bash
# Verificar logs de redirect em todos os arquivos

echo "=========================================="
echo "  VERIFICAÇÃO COMPLETA - LOGS REDIRECT"
echo "=========================================="
echo ""

echo "1. Verificar se há logs de redirect em error.log (últimas 1000 linhas):"
echo "----------------------------------------"
tail -n 1000 logs/error.log | grep -iE "redirect|/go/" | tail -10
echo ""

echo "2. Verificar se há logs em access.log (se existir):"
echo "----------------------------------------"
if [ -f logs/access.log ]; then
    tail -n 100 logs/access.log | grep -E "/go/" | tail -10
else
    echo "❌ Arquivo logs/access.log não existe"
fi
echo ""

echo "3. Verificar se há logs em access_redirect.log (se existir):"
echo "----------------------------------------"
if [ -f logs/access_redirect.log ]; then
    tail -n 100 logs/access_redirect.log | tail -10
else
    echo "❌ Arquivo logs/access_redirect.log não existe"
fi
echo ""

echo "4. Verificar últimos logs em error.log (últimas 50 linhas):"
echo "----------------------------------------"
tail -n 50 logs/error.log
echo ""

echo "5. Verificar se o Gunicorn está rodando:"
echo "----------------------------------------"
ps aux | grep -E "gunicorn|grimbots" | grep -v grep | head -5
echo ""

echo "6. Verificar se há erros no Gunicorn:"
echo "----------------------------------------"
journalctl -u grimbots.service -n 20 --no-pager 2>/dev/null || echo "Serviço systemd não encontrado"
echo ""

echo "=========================================="
echo "  TESTE MANUAL"
echo "=========================================="
echo ""
echo "1. Acesse: https://app.grimbots.online/go/red1?fbclid=TEST123"
echo "2. Execute imediatamente:"
echo "   tail -n 100 logs/error.log | grep -E 'Redirect|fbclid|fbc'"
echo ""

