#!/usr/bin/env bash
#
# setup_cron.sh - Instala crontab para jobs periódicos do GrimBots
# Substitui o APScheduler removido
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"

# Criar diretório de logs se não existir
mkdir -p "$LOG_DIR"

# Detectar usuário atual
CURRENT_USER=$(whoami)
echo "📝 Configurando crontab para usuário: $CURRENT_USER"
echo "📁 Diretório do projeto: $PROJECT_ROOT"

# Arquivo temporário para novo crontab
TEMP_CRON=$(mktemp)
trap "rm -f $TEMP_CRON" EXIT

# Ler crontab existente (se houver) e remover entradas antigas do GrimBots
crontab -l 2>/dev/null | grep -v '# GRIMBOTS-SRE-AUTO' | grep -v 'cron_jobs.py' > "$TEMP_CRON" || true

# Adicionar header
cat >> "$TEMP_CRON" << 'EOF'

# ============================================================
# GRIMBOTS-SRE-AUTO: Jobs Periódicos (Substitui APScheduler)
# Gerenciado por: setup_cron.sh
# NÃO EDITE MANUALMENTE - Use setup_cron.sh para regenerar
# ============================================================

# Variáveis de ambiente
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PYTHONPATH=
EOF

echo "PROJECT_ROOT=$PROJECT_ROOT" >> "$TEMP_CRON"
echo "LOG_DIR=$LOG_DIR" >> "$TEMP_CRON"
echo "" >> "$TEMP_CRON"

# ============================================================
# DEFINIÇÃO DOS JOBS
# ============================================================

# Reconciliadores de Gateway (a cada 1 minuto - alta frequência)
cat >> "$TEMP_CRON" << EOF
# --- RECONCILIADORES DE GATEWAY (1 minuto) ---
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reconcile_pushynpay >> $LOG_DIR/cron_reconcile_pushynpay.log 2>&1
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reconcile_atomopay >> $LOG_DIR/cron_reconcile_atomopay.log 2>&1
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reconcile_aguia >> $LOG_DIR/cron_reconcile_aguia.log 2>&1
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reconcile_bolt >> $LOG_DIR/cron_reconcile_bolt.log 2>&1
EOF

# Reconciliador Paradise (a cada 5 minutos - menos crítico)
cat >> "$TEMP_CRON" << EOF

# --- RECONCILIADOR PARADISE (5 minutos) ---
*/5 * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reconcile_paradise >> $LOG_DIR/cron_reconcile_paradise.log 2>&1
EOF

# Sistema de Assinaturas (a cada 5 minutos)
cat >> "$TEMP_CRON" << EOF

# --- SISTEMA DE ASSINATURAS (5 minutos) ---
*/5 * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py check_expired_subscriptions >> $LOG_DIR/cron_subscriptions.log 2>&1
EOF

# Remarketing (a cada 1 minuto)
cat >> "$TEMP_CRON" << EOF

# --- REMARKETING (1 minuto) ---
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py remarketing_campaigns >> $LOG_DIR/cron_remarketing.log 2>&1
EOF

# Health Check de Pools (a cada 1 minuto - antes era 15s, agora via cron)
cat >> "$TEMP_CRON" << EOF

# --- HEALTH CHECK DE POOLS (1 minuto) ---
* * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py health_check_pools >> $LOG_DIR/cron_healthcheck.log 2>&1
EOF

# Jobs Diários (ranking e reset)
cat >> "$TEMP_CRON" << EOF

# --- JOBS DIÁRIOS ---
# Reset error_count (3:00 AM)
0 3 * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py reset_error_count >> $LOG_DIR/cron_reset_error.log 2>&1

# Update ranking premium (a cada hora)
0 * * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python scripts/cron_jobs.py update_ranking >> $LOG_DIR/cron_ranking.log 2>&1
EOF

# Footer
cat >> "$TEMP_CRON" << 'EOF'

# ============================================================
# FIM GRIMBOTS-SRE-AUTO
# ============================================================
EOF

# Instalar novo crontab
echo ""
echo "📋 Instalando crontab..."
crontab "$TEMP_CRON"

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
echo "📁 Logs dos jobs: $LOG_DIR/cron_*.log"
echo ""
echo "🔧 Comandos úteis:"
echo "   crontab -l                    # Ver crontab atual"
echo "   sudo tail -f $LOG_DIR/cron_*.log  # Ver logs em tempo real"
echo "   sudo systemctl restart cron   # Reiniciar serviço cron"
echo ""

# Verificar se serviço cron está rodando
if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
    echo "✅ Serviço cron está ativo"
else
    echo "⚠️  ATENÇÃO: Serviço cron não está rodando!"
    echo "   Execute: sudo systemctl start cron"
fi
