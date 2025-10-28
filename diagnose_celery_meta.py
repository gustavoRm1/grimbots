"""
Diagnóstico: Verificar se Celery está processando eventos Meta Pixel
Autor: Senior QI 500
"""

from app import app, db
from models import Payment
from datetime import datetime, timedelta
import requests

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO CELERY - META PIXEL")
    print("=" * 80)
    
    # Buscar última venda com meta_event_id
    latest_payment = Payment.query.filter(
        Payment.status == 'paid',
        Payment.meta_purchase_sent == True,
        Payment.gateway_type == 'pushynpay'
    ).order_by(Payment.id.desc()).first()
    
    if not latest_payment:
        print("\n❌ NENHUMA VENDA COM META PIXEL ENVIADO!")
        exit(0)
    
    print(f"\n📊 ÚLTIMA VENDA:")
    print(f"Payment ID: {latest_payment.payment_id}")
    print(f"Meta Event ID: {latest_payment.meta_event_id}")
    print(f"Created At: {latest_payment.created_at}")
    print(f"Meta Purchase Sent: {latest_payment.meta_purchase_sent}")
    print(f"Meta Purchase Sent At: {latest_payment.meta_purchase_sent_at}")
    
    # Verificar se Celery está rodando
    print("\n" + "=" * 80)
    print("🔍 VERIFICANDO CELERY:")
    print("=" * 80)
    
    try:
        import subprocess
        result = subprocess.run(['systemctl', 'is-active', 'celery'], 
                              capture_output=True, text=True)
        celery_status = result.stdout.strip()
        
        if celery_status == 'active':
            print("✅ Celery está RODANDO")
        else:
            print(f"❌ Celery NÃO está rodando! Status: {celery_status}")
    except Exception as e:
        print(f"⚠️ Erro ao verificar Celery: {e}")
    
    # Verificar logs recentes do Celery
    print("\n" + "=" * 80)
    print("🔍 ÚLTIMOS LOGS DO CELERY:")
    print("=" * 80)
    
    try:
        import subprocess
        result = subprocess.run(['journalctl', '-u', 'celery', '--since', '2 hours ago', 
                                '-n', '50', '--no-pager'], 
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"⚠️ Erro ao ler logs: {e}")
    
    # Verificar se eventos estão no Celery (via Flower ou diretamente)
    print("\n" + "=" * 80)
    print("💡 PRÓXIMOS PASSOS:")
    print("=" * 80)
    print("1. Verificar se Celery está processando tarefas:")
    print("   celery -A celery_app inspect active")
    print("   celery -A celery_app inspect scheduled")
    print("")
    print("2. Reenviar eventos manualmente se necessário:")
    print("   python reenviar_meta_pixel.py")
    print("")
    print("3. Verificar se eventos chegaram no Meta:")
    print("   - Acessar Events Manager do Facebook")
    print("   - Procurar pelo event_id: " + (latest_payment.meta_event_id or "N/A"))

