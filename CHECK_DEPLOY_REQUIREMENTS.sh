#!/bin/bash
# CHECK DEPLOY REQUIREMENTS - TRACKING ELITE
# Verifica se tudo está pronto para o deploy

echo "========================================================================"
echo "VERIFICANDO PRÉ-REQUISITOS TRACKING ELITE"
echo "========================================================================"
echo ""

# 1. Redis
echo "1. Verificando Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "   ✅ Redis instalado e rodando"
else
    echo "   ❌ Redis NÃO instalado ou não está rodando"
    echo "   📝 Comando para instalar:"
    echo "      sudo apt-get update && sudo apt-get install redis-server -y"
    echo "      sudo systemctl start redis"
    echo "      sudo systemctl enable redis"
fi
echo ""

# 2. Python Redis library
echo "2. Verificando biblioteca Redis Python..."
if python -c "import redis" > /dev/null 2>&1; then
    echo "   ✅ Biblioteca redis instalada"
else
    echo "   ❌ Biblioteca redis NÃO instalada"
    echo "   📝 Comando para instalar:"
    echo "      pip install redis"
fi
echo ""

# 3. Banco de dados
echo "3. Verificando campos no banco..."
if sqlite3 instance/saas_bot_manager.db "PRAGMA table_info(bot_users);" | grep -q "ip_address"; then
    echo "   ✅ Campo ip_address existe"
else
    echo "   ❌ Campo ip_address NÃO existe"
    echo "   📝 Comando para criar:"
    echo "      python migrate_add_tracking_fields.py"
fi
echo ""

# 4. Gunicorn
echo "4. Verificando Gunicorn..."
if [ -f "venv/bin/gunicorn" ]; then
    echo "   ✅ Gunicorn instalado no venv"
else
    echo "   ❌ Gunicorn NÃO encontrado"
    echo "   📝 Comando para instalar:"
    echo "      pip install gunicorn"
fi
echo ""

# 5. Systemd service
echo "5. Verificando systemd service..."
if systemctl is-active --quiet grimbots; then
    echo "   ✅ Serviço grimbots está rodando"
    echo "   📊 Status:"
    systemctl status grimbots --no-pager | grep -E "Active|Main PID"
else
    echo "   ❌ Serviço grimbots NÃO está rodando"
    echo "   📝 Comando para iniciar:"
    echo "      sudo systemctl start grimbots"
fi
echo ""

# 6. Git status
echo "6. Verificando Git..."
cd /root/grimbots 2>/dev/null || cd ~/grimbots
git_status=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$git_status" -eq 0 ]; then
    echo "   ✅ Git clean (nenhuma alteração local)"
else
    echo "   ⚠️ $git_status arquivo(s) modificado(s) localmente"
    echo "   📝 Considere commit ou stash antes do pull"
fi
echo ""

echo "========================================================================"
echo "RESUMO"
echo "========================================================================"

# Contagem
total=0
passed=0

# Redis
if redis-cli ping > /dev/null 2>&1; then ((passed++)); fi
((total++))

# Python Redis
if python -c "import redis" > /dev/null 2>&1; then ((passed++)); fi
((total++))

# Migration
if sqlite3 instance/saas_bot_manager.db "PRAGMA table_info(bot_users);" 2>/dev/null | grep -q "ip_address"; then ((passed++)); fi
((total++))

# Gunicorn
if [ -f "venv/bin/gunicorn" ]; then ((passed++)); fi
((total++))

# Systemd
if systemctl is-active --quiet grimbots; then ((passed++)); fi
((total++))

echo "Checklist: $passed/$total itens OK"
echo ""

if [ "$passed" -eq "$total" ]; then
    echo "✅ TODOS OS PRÉ-REQUISITOS ATENDIDOS!"
    echo "🚀 Pronto para deploy do Tracking Elite"
else
    echo "⚠️ Alguns pré-requisitos faltando"
    echo "📝 Revise os comandos acima"
fi

echo "========================================================================"

