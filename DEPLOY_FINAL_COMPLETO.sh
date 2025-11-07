#!/bin/bash
# DEPLOY FINAL COMPLETO
# Resolve Git + Migra PostgreSQL + Corrige DNS + Inicia Sistema

set -e

echo "=========================================="
echo "  DEPLOY FINAL COMPLETO - QI 500"
echo "=========================================="
echo ""
echo "Este script vai:"
echo "  1. Resolver Git"
echo "  2. Migrar para PostgreSQL"
echo "  3. Corrigir DNS"
echo "  4. Iniciar sistema"
echo ""

read -p "Continuar? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Cancelado"
    exit 0
fi

# ==========================================
# FASE 1: RESOLVER GIT
# ==========================================
echo ""
echo "📋 FASE 1: Resolvendo Git..."
git add -A 2>/dev/null || true
git commit -m "Pre-migration state $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
git pull origin main || {
    echo "⚠️  Pull falhou, tentando com stash..."
    git stash
    git pull origin main
}
echo "✅ Git atualizado"

# ==========================================
# FASE 2: CORRIGIR DNS
# ==========================================
echo ""
echo "📋 FASE 2: Corrigindo DNS..."
if [ -f "FIX_DNS_TELEGRAM.sh" ]; then
    chmod +x FIX_DNS_TELEGRAM.sh
    ./FIX_DNS_TELEGRAM.sh
else
    # Configurar DNS diretamente
    sudo cp /etc/resolv.conf /etc/resolv.conf.backup 2>/dev/null || true
    echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
    echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf > /dev/null
    echo "✅ DNS configurado"
fi

# ==========================================
# FASE 3: MIGRAR POSTGRESQL
# ==========================================
echo ""
echo "📋 FASE 3: Migrando para PostgreSQL..."
if [ -f "MIGRACAO_POSTGRESQL_AGORA.sh" ]; then
    chmod +x MIGRACAO_POSTGRESQL_AGORA.sh
    ./MIGRACAO_POSTGRESQL_AGORA.sh
else
    echo "❌ Script de migração não encontrado"
    echo "Execute manualmente os comandos de migração"
    exit 1
fi

# ==========================================
# FASE 4: VALIDAR
# ==========================================
echo ""
echo "📋 FASE 4: Validando sistema..."

# Health check
sleep 10
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")

if [ "$HEALTH" = "200" ]; then
    echo "✅ Health check: OK"
else
    echo "⚠️  Health check: HTTP $HEALTH"
fi

# ==========================================
# RESUMO FINAL
# ==========================================
echo ""
echo "=========================================="
echo "  ✅ DEPLOY FINAL CONCLUÍDO"
echo "=========================================="
echo ""
echo "Verifique:"
echo "  sudo systemctl status grimbots"
echo "  curl http://localhost:5000/health"
echo "  tail -f logs/error.log"
echo ""
echo "Teste o bot (enviar /start) e verifique se:"
echo "  - Texto aparece APENAS 1 VEZ (não 2)"
echo "  - Sem erros 'database is locked'"
echo "  - Sem erros de DNS Telegram"
echo ""

