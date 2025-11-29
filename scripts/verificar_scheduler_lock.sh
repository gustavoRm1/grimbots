#!/bin/bash

echo "🔍 DIAGNÓSTICO: SCHEDULER LOCK"
echo "==============================="
echo ""

LOCK_FILE="/tmp/grimbots_scheduler.lock"

# 1. Verificar se lock existe
echo "📋 1. VERIFICANDO LOCK FILE:"
echo "-----------------------------------"
if [ -f "$LOCK_FILE" ]; then
    echo "✅ Lock file existe: $LOCK_FILE"
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    echo "   PID no lock: $PID"
    
    # Verificar se processo existe
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "   ✅ Processo $PID está rodando"
        echo "   Comando do processo:"
        ps -p "$PID" -o pid,cmd | tail -1
    else
        echo "   ❌ Processo $PID NÃO está rodando (LOCK STALE!)"
        echo "   🔧 Removendo lock stale..."
        rm -f "$LOCK_FILE"
        echo "   ✅ Lock removido!"
    fi
else
    echo "❌ Lock file não existe: $LOCK_FILE"
fi
echo ""

# 2. Verificar processos Python/Gunicorn
echo "📋 2. PROCESSOS PYTHON/GUNICORN:"
echo "-----------------------------------"
ps aux | grep -E "(gunicorn|python.*app|python.*wsgi)" | grep -v grep
echo ""

# 3. Verificar scheduler no processo principal
echo "📋 3. VERIFICANDO SCHEDULER NO PROCESSO PRINCIPAL:"
echo "-----------------------------------"
python3 << 'EOF'
from app import app, bot_manager
with app.app_context():
    print(f"Scheduler disponível: {bot_manager.scheduler is not None}")
    if bot_manager.scheduler:
        print(f"Scheduler rodando: {bot_manager.scheduler.running}")
        if bot_manager.scheduler.running:
            jobs = bot_manager.scheduler.get_jobs()
            print(f"Total jobs: {len(jobs)}")
            upsell_jobs = [j for j in jobs if 'upsell' in j.id.lower()]
            print(f"Jobs upsell: {len(upsell_jobs)}")
        else:
            print("❌ PROBLEMA: Scheduler existe mas NÃO está rodando!")
            print("   AÇÃO: Verificar se há lock stale ou problema na inicialização")
    else:
        print("❌ PROBLEMA: Scheduler NÃO está disponível!")
EOF
echo ""

# 4. Verificar lock alternativo
echo "📋 4. BUSCANDO OUTROS LOCK FILES:"
echo "-----------------------------------"
find /tmp -name "*scheduler*.lock" -o -name "*grimbots*.lock" 2>/dev/null
echo ""

echo "✅ Diagnóstico completo!"
echo ""
echo "💡 AÇÃO NECESSÁRIA:"
echo "   1. Se lock está stale (processo não existe), removê-lo"
echo "   2. Reiniciar aplicação para scheduler iniciar corretamente"
echo "   3. Verificar se 'Scheduler rodando: True' após restart"

