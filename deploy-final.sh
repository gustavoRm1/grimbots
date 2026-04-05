#!/bin/bash
# =============================================================================
# DEPLOY FINAL - GrimBots Production
# =============================================================================
# Script atômico para deploy do sistema em produção
# Uso: sudo bash deploy-final.sh
# =============================================================================

set -e  # Exit on any error

APP_DIR="/root/grimbots"
LOGS_DIR="$APP_DIR/logs"
SERVICE_NAME="grimbots"
HEALTH_URL="http://localhost:5000/health"

echo "=========================================="
echo "🚀 DEPLOY FINAL - GrimBots"
echo "=========================================="
echo ""

# 1. Criar diretório de logs
echo "📁 Criando diretório de logs..."
mkdir -p "$LOGS_DIR"
chmod 755 "$LOGS_DIR"
echo "✅ Logs em: $LOGS_DIR"
echo ""

# 2. Copiar service file
echo "📋 Copiando grimbots.service..."
cp "$APP_DIR/grimbots.service" /etc/systemd/system/
echo "✅ Service file copiado"
echo ""

# 3. Recarregar systemd
echo "🔄 Recarregando systemd..."
systemctl daemon-reload
echo "✅ Systemd recarregado"
echo ""

# 4. Parar serviço existente (limpeza de zumbis)
echo "🛑 Parando serviço existente (se houver)..."
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    systemctl stop $SERVICE_NAME
    sleep 2
    # Forçar kill se necessário
    if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        echo "⚠️ Forçando parada..."
        systemctl kill -s SIGKILL $SERVICE_NAME 2>/dev/null || true
        sleep 1
    fi
    echo "✅ Serviço parado"
else
    echo "ℹ️ Serviço não estava rodando"
fi
echo ""

# 5. Limpar lock files antigos
echo "🧹 Limpando lock files..."
rm -f /tmp/grimbots_scheduler.lock
rm -f /tmp/bot_*.lock
echo "✅ Lock files limpos"
echo ""

# 6. Iniciar serviço
echo "▶️ Iniciando serviço..."
systemctl start $SERVICE_NAME
echo "✅ Serviço iniciado"
echo ""

# 7. Aguardar startup
echo "⏳ Aguardando startup (5s)..."
sleep 5
echo ""

# 8. Health check
echo "🏥 Health check..."
echo "   URL: $HEALTH_URL"
echo ""

HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" $HEALTH_URL 2>/dev/null || echo -e "\n000")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ HEALTH CHECK: OK (HTTP 200)"
    echo ""
    echo "📊 Resposta:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    echo "=========================================="
    echo "🎉 DEPLOY CONCLUÍDO COM SUCESSO!"
    echo "=========================================="
    echo ""
    echo "📋 Comandos úteis:"
    echo "   systemctl status $SERVICE_NAME    # Status do serviço"
    echo "   journalctl -u $SERVICE_NAME -f    # Logs em tempo real"
    echo "   tail -f $LOGS_DIR/error.log       # Logs de erro"
    echo "   tail -f $LOGS_DIR/access.log      # Logs de acesso"
    echo ""
    exit 0
else
    echo "❌ HEALTH CHECK FALHOU (HTTP $HTTP_CODE)"
    echo ""
    echo "📊 Resposta:"
    echo "$BODY"
    echo ""
    echo "🔧 Diagnóstico:"
    systemctl status $SERVICE_NAME --no-pager -l
    echo ""
    echo "📜 Logs recentes:"
    journalctl -u $SERVICE_NAME --no-pager -n 20
    echo ""
    exit 1
fi
