#!/bin/bash

echo "🔄 Atualizando Paradise Payment Checker..."
echo "=========================================="

# Remover entrada antiga
crontab -l 2>/dev/null | grep -v "paradise_payment_checker.py" | crontab -

# Adicionar nova entrada (a cada 2 minutos)
(crontab -l 2>/dev/null; echo "*/2 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python paradise_payment_checker.py >> /root/grimbots/logs/paradise_checker.log 2>&1") | crontab -

echo "✅ Cron job atualizado!"
echo ""
echo "📋 Nova configuração:"
crontab -l | grep paradise_payment_checker.py
echo ""
echo "🎯 Agora executa a cada 2 minutos com retry automático"
echo "🔍 Para ver os logs: tail -f /root/grimbots/logs/paradise_checker.log"
