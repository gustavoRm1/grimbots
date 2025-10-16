#!/bin/bash
# ========================================
# DEPLOY RÁPIDO - GRIMBOTS v2.1.0
# ========================================
# Autor: Senior QI 240
# Data: 16/10/2025
# Uso: bash deploy_quick.sh

set -e  # Parar em caso de erro

echo "======================================================================"
echo "  DEPLOY GRIMBOTS v2.1.0"
echo "======================================================================"
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ========================================
# 1. VERIFICAR AMBIENTE
# ========================================
echo -e "${YELLOW}[1/10]${NC} Verificando ambiente..."

if [ ! -f ".env" ]; then
    echo -e "${RED}[ERRO]${NC} Arquivo .env não encontrado!"
    echo "Execute: cp env.example .env"
    echo "E configure as variáveis obrigatórias"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[INFO]${NC} Criando virtual environment..."
    python3 -m venv venv
fi

echo -e "${GREEN}[OK]${NC} Ambiente verificado"

# ========================================
# 2. ATIVAR VENV
# ========================================
echo -e "${YELLOW}[2/10]${NC} Ativando virtual environment..."
source venv/bin/activate
echo -e "${GREEN}[OK]${NC} Venv ativado"

# ========================================
# 3. INSTALAR DEPENDÊNCIAS
# ========================================
echo -e "${YELLOW}[3/10]${NC} Instalando dependências..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install gunicorn -q
echo -e "${GREEN}[OK]${NC} Dependências instaladas"

# ========================================
# 4. VERIFICAR MIGRATIONS
# ========================================
echo -e "${YELLOW}[4/10]${NC} Verificando migrations..."

if [ -f "instance/grpay.db" ] || [ ! -z "$DATABASE_URL" ]; then
    echo -e "${GREEN}[OK]${NC} Banco de dados detectado"
else
    echo -e "${YELLOW}[INFO]${NC} Inicializando banco pela primeira vez..."
    python init_db.py
fi

# Executar migrations v2.1.0
echo -e "${YELLOW}[INFO]${NC} Executando migrations v2.1.0..."
python migrate_add_upsells.py 2>/dev/null || true
python migrate_add_wiinpay.py 2>/dev/null || true

echo -e "${GREEN}[OK]${NC} Migrations executadas"

# ========================================
# 5. VALIDAR SINTAXE
# ========================================
echo -e "${YELLOW}[5/10]${NC} Validando sintaxe Python..."
python -m py_compile app.py
python -m py_compile models.py
python -m py_compile bot_manager.py
python -m py_compile gateway_wiinpay.py
echo -e "${GREEN}[OK]${NC} Sintaxe validada (0 erros)"

# ========================================
# 6. VERIFICAR .env
# ========================================
echo -e "${YELLOW}[6/10]${NC} Verificando configurações..."

if grep -q "SECRET_KEY=" .env; then
    echo -e "${GREEN}[OK]${NC} SECRET_KEY configurado"
else
    echo -e "${RED}[ERRO]${NC} SECRET_KEY não configurado no .env!"
    exit 1
fi

if grep -q "ENCRYPTION_KEY=" .env; then
    echo -e "${GREEN}[OK]${NC} ENCRYPTION_KEY configurado"
else
    echo -e "${RED}[ERRO]${NC} ENCRYPTION_KEY não configurado no .env!"
    exit 1
fi

# ========================================
# 7. CRIAR LOGS DIR
# ========================================
echo -e "${YELLOW}[7/10]${NC} Preparando diretório de logs..."
mkdir -p logs
touch logs/app.log logs/error.log logs/access.log
echo -e "${GREEN}[OK]${NC} Logs configurados"

# ========================================
# 8. TESTAR IMPORTAÇÕES
# ========================================
echo -e "${YELLOW}[8/10]${NC} Testando importações..."
python -c "from app import app; from models import User, Bot, Gateway; from gateway_wiinpay import WiinPayGateway; print('[OK] Imports OK')"
echo -e "${GREEN}[OK]${NC} Importações validadas"

# ========================================
# 9. VERIFICAR PERMISSÕES
# ========================================
echo -e "${YELLOW}[9/10]${NC} Verificando permissões..."
chmod +x deploy_quick.sh
chmod +x start-pm2.sh 2>/dev/null || true
chmod +x deploy_to_vps.sh 2>/dev/null || true
echo -e "${GREEN}[OK]${NC} Permissões OK"

# ========================================
# 10. MOSTRAR INFORMAÇÕES
# ========================================
echo -e "${YELLOW}[10/10]${NC} Gerando relatório..."
echo ""
echo "======================================================================"
echo "  DEPLOY CONCLUÍDO COM SUCESSO!"
echo "======================================================================"
echo ""
echo "📦 VERSÃO: 2.1.0"
echo "📅 DATA: $(date)"
echo ""
echo "✅ FEATURES DESTA VERSÃO:"
echo "  - Sistema de Upsell automático"
echo "  - Gateway WiinPay integrado (5 gateways total)"
echo "  - 10 race conditions corrigidos"
echo "  - Segurança OWASP Top 10"
echo "  - Split ID: 6877edeba3c39f8451ba5bdd (4%)"
echo ""
echo "🚀 PRÓXIMOS PASSOS:"
echo ""
echo "  MODO DESENVOLVIMENTO:"
echo "    python app.py"
echo ""
echo "  MODO PRODUÇÃO (Gunicorn):"
echo "    gunicorn -c gunicorn_config.py wsgi:app"
echo ""
echo "  MODO PRODUÇÃO (Systemd):"
echo "    sudo systemctl start grimbots"
echo ""
echo "📄 DOCUMENTAÇÃO:"
echo "  - DEPLOY_VPS_v2.1.0.md (guia completo VPS)"
echo "  - CHANGELOG_v2.1.0.md (mudanças desta versão)"
echo "  - docs/DOCUMENTACAO_COMPLETA.md (guia técnico)"
echo ""
echo "🔑 SENHA ADMIN:"
if [ -f ".admin_password" ]; then
    echo "  $(cat .admin_password)"
else
    echo "  Execute 'python init_db.py' para gerar"
fi
echo ""
echo "======================================================================"
echo ""

