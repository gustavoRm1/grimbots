#!/usr/bin/env bash
#
# setup_cron.sh - Instala crontab para jobs periódicos do GrimBots
# Substitui o APScheduler removido
#
# ✅ SRE FAILPROOF: Caminhos absolutos hardcoded, sem variáveis no crontab
# ✅ Vixie Cron 100% compatível - sem declarações de variáveis customizadas
#
set -euo pipefail

# ✅ HARDcoded absoluto - não use dirname dinâmico que pode falhar
PROJECT_ROOT="/root/grimbots"
LOG_DIR="/root/grimbots/logs"
PYTHON_BIN="/root/grimbots/venv/bin/python"

# Validar que diretório existe
if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "❌ ERRO: Diretório $PROJECT_ROOT não existe!"
    exit 1
fi

# Criar diretório de logs
mkdir -p "$LOG_DIR"

echo "📝 Configurando crontab para GrimBots"
echo "📁 Diretório do projeto: $PROJECT_ROOT"
echo "📁 Diretório de logs: $LOG_DIR"

# Arquivo temporário para novo crontab
TEMP_CRON=$(mktemp)
trap "rm -f $TEMP_CRON" EXIT

# Ler crontab existente e remover entradas antigas do GrimBots
crontab -l 2>/dev/null | grep -v '# GRIMBOTS-SRE-AUTO' | grep -v '/cron_jobs.py' > "$TEMP_CRON" || true

# ============================================================
# CONSTRUIR CRONTAB - APENAS COMENTÁRIOS E JOBS, SEM VARIÁVEIS
# ============================================================

cat >> "$TEMP_CRON" << 'EOF'

# ============================================================
# GRIMBOTS-SRE-AUTO: Jobs Periódicos (Substitui APScheduler)
# Gerenciado por: setup_cron.sh
# NÃO EDITE MANUALMENTE - Use setup_cron.sh para regenerar
# ============================================================

# --- RECONCILIADORES DE GATEWAY (1 minuto) ---
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reconcile_pushynpay >> /root/grimbots/logs/cron_pushynpay.log 2>&1
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reconcile_atomopay >> /root/grimbots/logs/cron_atomopay.log 2>&1
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reconcile_aguia >> /root/grimbots/logs/cron_aguia.log 2>&1
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reconcile_bolt >> /root/grimbots/logs/cron_bolt.log 2>&1

# --- RECONCILIADOR PARADISE (5 minutos) ---
*/5 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reconcile_paradise >> /root/grimbots/logs/cron_paradise.log 2>&1

# --- SISTEMA DE ASSINATURAS (5 minutos) ---
*/5 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py check_expired_subscriptions >> /root/grimbots/logs/cron_subscriptions.log 2>&1

# --- REMARKETING (1 minuto) ---
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py remarketing_campaigns >> /root/grimbots/logs/cron_remarketing.log 2>&1

# --- HEALTH CHECK DE POOLS (1 minuto) ---
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py health_check_pools >> /root/grimbots/logs/cron_healthcheck.log 2>&1

# --- JOBS DIÁRIOS ---
# Reset error_count (3:00 AM)
0 3 * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py reset_error_count >> /root/grimbots/logs/cron_reset_error.log 2>&1

# Update ranking premium (a cada hora)
0 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python scripts/cron_jobs.py update_ranking >> /root/grimbots/logs/cron_ranking.log 2>&1

# ============================================================
# FIM GRIMBOTS-SRE-AUTO
# ============================================================
EOF

# ✅ CORREÇÃO CRÍTICA: Remover quebras de linha Windows (CRLF) que corrompem o cron
echo "🔧 Sanitizando arquivo crontab..."
tr -d '\r' < "$TEMP_CRON" > "${TEMP_CRON}.clean"
mv "${TEMP_CRON}.clean" "$TEMP_CRON"

# Validar sintaxe do crontab antes de instalar
echo "� Validando sintaxe do crontab..."
if ! crontab "$TEMP_CRON" 2>&1; then
    echo "❌ ERRO: Crontab tem sintaxe inválida!"
    echo "📄 Conteúdo do arquivo temporário:"
    cat -n "$TEMP_CRON" | head -30
    exit 1
fi

echo ""
echo "✅ Crontab instalado com sucesso!"
echo ""
echo "📊 Jobs configurados:"
echo "   • reconcile_pushynpay   - a cada 1 minuto"
echo "   • reconcile_atomopay    - a cada 1 minuto"
echo "   • reconcile_aguia       - a cada 1 minuto"
echo "   • reconcile_bolt        - a cada 1 minuto"
echo "   • reconcile_paradise    - a cada 5 minutos"
echo "   • check_expired_subs    - a cada 5 minutos"
echo "   • remarketing_campaigns - a cada 1 minuto"
echo "   • health_check_pools    - a cada 1 minuto"
echo "   • reset_error_count     - 3:00 AM diário"
echo "   • update_ranking        - a cada hora"
echo ""
echo "📁 Logs dos jobs: /root/grimbots/logs/cron_*.log"
echo ""
echo "🔧 Comandos úteis:"
echo "   crontab -l                              # Ver crontab atual"
echo "   sudo tail -f /root/grimbots/logs/cron_*.log  # Ver logs em tempo real"
echo "   sudo systemctl restart cron             # Reiniciar serviço cron"
echo ""

# Verificar se serviço cron está rodando
if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
    echo "✅ Serviço cron está ativo"
else
    echo "⚠️  ATENÇÃO: Serviço cron não está rodando!"
    echo "   Execute: sudo systemctl start cron"
fi

echo ""
echo "🚀 SRE Architecture: Cron Jobs ativos!"
