#!/bin/bash

echo "🔍 DIAGNÓSTICO: WEBHOOKS E UPSELLS"
echo "=================================="
echo ""

# 1. Verificar jobs falhados
echo "📋 1. JOBS FALHADOS NA FILA WEBHOOK:"
echo "-----------------------------------"
rq failed --queue webhook 2>/dev/null | head -20
echo ""

# 2. Verificar jobs recentes
echo "📋 2. ÚLTIMOS 10 JOBS PROCESSADOS:"
echo "-----------------------------------"
rq info webhook 2>/dev/null
echo ""

# 3. Verificar logs da aplicação
echo "📋 3. LOGS DE WEBHOOK (últimas 50 linhas):"
echo "-----------------------------------"
if [ -f "logs/error.log" ]; then
    echo "✅ Arquivo: logs/error.log"
    grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid|WEBHOOK.*pushynpay)" logs/error.log | tail -50
elif [ -f "logs/app.log" ]; then
    echo "✅ Arquivo: logs/app.log"
    grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid|WEBHOOK.*pushynpay)" logs/app.log | tail -50
elif [ -f "gunicorn.log" ]; then
    echo "✅ Arquivo: gunicorn.log"
    grep -E "(process_webhook_async|UPSELLS|WEBHOOK.*paid|WEBHOOK.*pushynpay)" gunicorn.log | tail -50
else
    echo "❌ Nenhum arquivo de log encontrado. Verificando diretório logs/..."
    if [ -d "logs" ]; then
        echo "Arquivos em logs/:"
        ls -lh logs/ | head -10
        echo ""
        echo "Buscando em todos os arquivos .log:"
        find logs -name "*.log" -type f -exec grep -l "process_webhook_async\|UPSELLS\|WEBHOOK" {} \; 2>/dev/null
    fi
fi
echo ""

# 4. Verificar workers RQ
echo "📋 4. WORKERS RQ ATIVOS:"
echo "-----------------------------------"
rq info webhook 2>/dev/null | grep -A 20 "workers"
echo ""

# 5. Verificar scheduler
echo "📋 5. VERIFICANDO SCHEDULER (Python):"
echo "-----------------------------------"
python3 << EOF
from app import app, bot_manager
with app.app_context():
    print(f"✅ Scheduler disponível: {bot_manager.scheduler is not None}")
    if bot_manager.scheduler:
        print(f"✅ Scheduler rodando: {bot_manager.scheduler.running}")
        jobs = bot_manager.scheduler.get_jobs()
        upsell_jobs = [j for j in jobs if 'upsell' in j.id.lower()]
        print(f"✅ Total de jobs: {len(jobs)}")
        print(f"✅ Jobs de upsell: {len(upsell_jobs)}")
        if upsell_jobs:
            print("\n📅 Próximos 5 jobs de upsell:")
            for job in upsell_jobs[:5]:
                print(f"   - {job.id}: próximo execução: {job.next_run_time}")
    else:
        print("❌ Scheduler NÃO está disponível!")
EOF
echo ""

# 6. Verificar último pagamento PushynPay
echo "📋 6. ÚLTIMO PAGAMENTO PUSHYNPAY NO BANCO:"
echo "-----------------------------------"
python3 << EOF
from app import app, db
from models import Payment
with app.app_context():
    last_payment = Payment.query.filter_by(gateway_type='pushynpay').order_by(Payment.created_at.desc()).first()
    if last_payment:
        print(f"✅ Payment ID: {last_payment.payment_id}")
        print(f"   Status: {last_payment.status}")
        print(f"   Criado em: {last_payment.created_at}")
        print(f"   Pago em: {last_payment.paid_at}")
        print(f"   Bot ID: {last_payment.bot_id}")
        if last_payment.bot and last_payment.bot.config:
            print(f"   Upsells habilitados: {last_payment.bot.config.upsells_enabled}")
            if last_payment.bot.config.upsells_enabled:
                from models import BotConfig
                upsells = last_payment.bot.config.get_upsells()
                print(f"   Quantidade de upsells: {len(upsells) if upsells else 0}")
    else:
        print("❌ Nenhum pagamento PushynPay encontrado")
EOF
echo ""

echo "✅ Diagnóstico completo!"
echo ""
echo "💡 DICA: Se não encontrar logs, verifique:"
echo "   - journalctl -u grimbots -n 100 (se usar systemd)"
echo "   - pm2 logs (se usar PM2)"
echo "   - docker logs <container> (se usar Docker)"

