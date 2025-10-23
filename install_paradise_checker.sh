#!/bin/bash

echo "🚀 Instalando Paradise Payment Checker..."
echo "=========================================="

# 1. Tornar o script executável
chmod +x paradise_payment_checker.py

# 2. Criar diretório de logs se não existir
mkdir -p logs

# 3. Testar o script
echo "🔍 Testando o script..."
/root/grimbots/venv/bin/python paradise_payment_checker.py

# 4. Adicionar ao crontab (executar a cada 1 minuto)
echo "⏰ Configurando cron job..."

# Remover entrada antiga se existir
crontab -l 2>/dev/null | grep -v "paradise_payment_checker.py" | crontab -

# Adicionar nova entrada
(crontab -l 2>/dev/null; echo "* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python paradise_payment_checker.py >> /root/grimbots/logs/paradise_checker.log 2>&1") | crontab -

echo ""
echo "✅ Paradise Payment Checker instalado com sucesso!"
echo ""
echo "📋 Cron job configurado:"
crontab -l | grep paradise_payment_checker.py
echo ""
echo "🔍 Para ver os logs:"
echo "tail -f /root/grimbots/logs/paradise_checker.log"
echo ""
echo "🎯 O checker irá:"
echo "- Verificar pagamentos Paradise pendentes a cada 1 minuto"
echo "- Atualizar status automaticamente quando aprovados"
echo "- Disparar Meta Pixel Purchase"
echo "- Notificar clientes via Telegram"

