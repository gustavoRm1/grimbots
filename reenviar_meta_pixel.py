"""
Reenviar Meta Pixel para vendas recentes que não foram enviadas
Autor: Senior QI 500
"""

from app import app, db, send_meta_pixel_purchase_event
from models import Payment
from datetime import datetime, timedelta

with app.app_context():
    print("=" * 80)
    print("🔄 REENVIAR META PIXEL - VENDAS RECENTES")
    print("=" * 80)
    
    # Buscar vendas de HOJE (00:00 até agora) com meta_purchase_sent = True
    # mas que provavelmente não foram enviadas porque Celery estava parado
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    recent_payments = Payment.query.filter(
        Payment.status == 'paid',
        Payment.gateway_type == 'pushynpay',
        Payment.created_at >= today_start,
        Payment.meta_purchase_sent == True
    ).order_by(Payment.id.desc()).all()
    
    print(f"\n📊 VENDAS ENCONTRADAS: {len(recent_payments)}")
    
    if not recent_payments:
        print("✅ Nenhuma venda recente encontrada")
        exit(0)
    
    # Resetar flag e reenviar
    count = 0
    for p in recent_payments:
        print(f"\n{'=' * 80}")
        print(f"Payment ID: {p.payment_id}")
        print(f"Amount: R$ {p.amount:.2f}")
        print(f"Created: {p.created_at}")
        print(f"Meta Event ID antigo: {p.meta_event_id}")
        
        # Resetar flag
        p.meta_purchase_sent = False
        p.meta_purchase_sent_at = None
        p.meta_event_id = None
        db.session.commit()
        
        # Reenviar
        try:
            print("🔄 Reenviando Meta Pixel...")
            send_meta_pixel_purchase_event(p)
            count += 1
            print("✅ Meta Pixel reenviado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao reenviar: {e}")
    
    print("\n" + "=" * 80)
    print(f"✅ RESUMO: {count} de {len(recent_payments)} vendas reenviadas")
    print("=" * 80)
    print("\n💡 Verifique os logs do Celery para confirmar o envio:")
    print("   journalctl -u celery -f")
    print("\n💡 Os eventos aparecerão no Meta em 5-10 minutos")

