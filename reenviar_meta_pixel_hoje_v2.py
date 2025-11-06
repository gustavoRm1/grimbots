"""
🔄 REENVIAR META PIXEL - VENDAS DE HOJE (V2 - COM fbp/fbc)

Este script:
1. Busca todas as vendas de HOJE (status='paid')
2. Reseta flag meta_purchase_sent para permitir reenvio
3. Reenvia eventos Purchase com TODOS os dados corretos:
   - external_id (fbclid hashado)
   - fbp e fbc (recuperados do Redis)
   - IP e User Agent (mesmos do PageView)
   - campaign_code (grim)
   - UTMs

A função send_meta_pixel_purchase_event já faz:
- Busca tracking data do Redis usando fbclid
- Recupera fbp, fbc, IP, User Agent
- Constrói user_data completo
- Envia com Match Quality 7-9/10

Autor: QI 600 + QI 602
"""

from app import app, db, send_meta_pixel_purchase_event
from models import Payment, get_brazil_time
from datetime import datetime
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

with app.app_context():
    print("\n" + "=" * 80)
    print("🔄 REENVIAR META PIXEL - VENDAS DE HOJE (V2 - COM fbp/fbc)")
    print("=" * 80)
    
    # ✅ CRÍTICO: Usar horário do Brasil (UTC-3), não UTC da VPS
    # Buscar vendas de HOJE (00:00 até agora) no horário do Brasil
    now_brazil = get_brazil_time()
    today_start = now_brazil.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f"\n📅 Período: {today_start.strftime('%d/%m/%Y %H:%M')} até {now_brazil.strftime('%d/%m/%Y %H:%M')} (Horário do Brasil - UTC-3)")
    
    # Buscar TODAS as vendas pagas de hoje
    # ✅ Payment.created_at já está em horário do Brasil (usando get_brazil_time())
    payments_today = Payment.query.filter(
        Payment.status == 'paid',
        Payment.created_at >= today_start,
        Payment.created_at <= now_brazil
    ).order_by(Payment.created_at.desc()).all()
    
    print(f"\n📊 TOTAL DE VENDAS DE HOJE: {len(payments_today)}")
    
    if not payments_today:
        print("\n⚠️ Nenhuma venda encontrada para hoje!")
        exit(0)
    
    # Verificar quantas já foram enviadas
    sent_count = sum(1 for p in payments_today if p.meta_purchase_sent)
    not_sent_count = len(payments_today) - sent_count
    
    print(f"  ✅ Já enviadas: {sent_count}")
    print(f"  ❌ Não enviadas: {not_sent_count}")
    
    # ✅ FILTRAR: Só reenviar vendas que realmente precisam
    # 1. Não foram enviadas OU
    # 2. Foram enviadas mas não têm fbclid/campaign_code (precisam correção)
    payments_to_resend = []
    for p in payments_today:
        needs_resend = False
        
        # Não foi enviada
        if not p.meta_purchase_sent:
            needs_resend = True
        # Foi enviada mas não tem dados críticos (precisa correção)
        elif not p.fbclid or not p.campaign_code:
            needs_resend = True
        
        if needs_resend:
            payments_to_resend.append(p)
    
    print(f"\n📊 VENDAS QUE PRECISAM SER REENVIADAS: {len(payments_to_resend)}")
    print(f"   - Não enviadas: {sum(1 for p in payments_to_resend if not p.meta_purchase_sent)}")
    print(f"   - Enviadas sem dados: {sum(1 for p in payments_to_resend if p.meta_purchase_sent and (not p.fbclid or not p.campaign_code))}")
    
    if not payments_to_resend:
        print("\n✅ Todas as vendas já foram enviadas corretamente!")
        print("   Não há necessidade de reenvio.")
        exit(0)
    
    # Mostrar preview
    print("\n📋 PREVIEW (primeiras 10 vendas que serão reenviadas):")
    for i, p in enumerate(payments_to_resend[:10], 1):
        reason = "Não enviada" if not p.meta_purchase_sent else "Sem dados críticos"
        print(f"  {i}. {p.payment_id} | R$ {p.amount:.2f} | "
              f"fbclid={'✅' if p.fbclid else '❌'} | "
              f"campaign_code={p.campaign_code or 'N/A'} | "
              f"Razão: {reason}")
    
    if len(payments_to_resend) > 10:
        print(f"  ... e mais {len(payments_to_resend) - 10} vendas")
    
    # Confirmar
    print("\n" + "=" * 80)
    print(f"⚠️ ATENÇÃO: Este script vai reenviar {len(payments_to_resend)} vendas de hoje.")
    print(f"   (De {len(payments_today)} vendas totais, {len(payments_today) - len(payments_to_resend)} já estão corretas)")
    print(f"\n   Os eventos serão enviados com:")
    print(f"   ✅ external_id (fbclid hashado)")
    print(f"   ✅ fbp e fbc (do Redis)")
    print(f"   ✅ IP e User Agent (mesmos do PageView)")
    print(f"   ✅ campaign_code (grim)")
    print(f"   ✅ UTMs")
    print("\n   ⚠️  NOTA: Vendas já enviadas com dados corretos NÃO serão reenviadas")
    print("=" * 80)
    response = input(f"\n⚠️ Deseja reenviar {len(payments_to_resend)} eventos Purchase? (s/N): ")
    
    if response.lower() != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        exit(0)
    
    # Reenviar
    print("\n" + "=" * 80)
    print("🔄 REENVIANDO EVENTOS...")
    print("=" * 80)
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Verificar se Redis está disponível
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        redis_available = True
        print("✅ Redis conectado - dados de tracking disponíveis")
    except Exception as e:
        redis_available = False
        print(f"⚠️ Redis não disponível: {e}")
        print("   Alguns dados (fbp, fbc, IP, UA) podem não estar disponíveis")
    
    for i, payment in enumerate(payments_to_resend, 1):
        print(f"\n[{i}/{len(payments_to_resend)}] Payment {payment.payment_id}")
        print(f"  💰 R$ {payment.amount:.2f}")
        print(f"  📅 Criado: {payment.created_at.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"  🎯 campaign_code: {payment.campaign_code or 'N/A'}")
        print(f"  📊 utm_source: {payment.utm_source or 'N/A'}")
        print(f"  📊 utm_campaign: {payment.utm_campaign or 'N/A'}")
        print(f"  🔑 fbclid: {'✅' if payment.fbclid else '❌'} {payment.fbclid[:30] + '...' if payment.fbclid else ''}")
        
        # Verificar se tem tracking data no Redis
        tracking_data_available = False
        if redis_available and payment.fbclid:
            try:
                tracking_key = f'tracking:{payment.fbclid}'
                tracking_json = r.get(tracking_key)
                if tracking_json:
                    tracking_data = json.loads(tracking_json)
                    fbp = tracking_data.get('fbp', '')
                    fbc = tracking_data.get('fbc', '')
                    tracking_data_available = True
                    print(f"  🔍 Redis: fbp={'✅' if fbp else '❌'} | fbc={'✅' if fbc else '❌'}")
                else:
                    print(f"  ⚠️ Redis: Tracking data não encontrado (pode ter expirado - TTL 180s)")
            except Exception as e:
                print(f"  ⚠️ Erro ao buscar Redis: {e}")
        
        # Resetar flag
        old_sent = payment.meta_purchase_sent
        old_event_id = payment.meta_event_id
        
        payment.meta_purchase_sent = False
        payment.meta_purchase_sent_at = None
        payment.meta_event_id = None
        db.session.commit()
        
        print(f"  🔄 Flag resetada (era: {old_sent}, event_id: {old_event_id or 'None'})")
        
        # Reenviar
        try:
            print(f"  📤 Reenviando Meta Pixel Purchase...")
            send_meta_pixel_purchase_event(payment)
            
            # Verificar se foi enviado com sucesso
            db.session.refresh(payment)
            if payment.meta_purchase_sent:
                success_count += 1
                print(f"  ✅ Purchase enviado com sucesso! Event ID: {payment.meta_event_id}")
            else:
                skipped_count += 1
                print(f"  ⚠️ Purchase não foi enviado (pode não ter pixel configurado ou tracking desabilitado)")
        except Exception as e:
            error_count += 1
            print(f"  ❌ Erro ao reenviar: {e}")
            logger.error(f"Erro ao reenviar payment {payment.payment_id}: {e}", exc_info=True)
            db.session.rollback()
    
    # Resumo
    print("\n" + "=" * 80)
    print("📊 RESUMO FINAL")
    print("=" * 80)
    print(f"  📊 Total de vendas hoje: {len(payments_today)}")
    print(f"  🔄 Vendas reenviadas: {len(payments_to_resend)}")
    print(f"  ✅ Sucesso: {success_count}/{len(payments_to_resend)}")
    print(f"  ⚠️  Ignorados: {skipped_count}/{len(payments_to_resend)}")
    print(f"  ❌ Erros: {error_count}/{len(payments_to_resend)}")
    print(f"  ✅ Já estavam corretas: {len(payments_today) - len(payments_to_resend)}")
    print("=" * 80)
    
    print("\n💡 PRÓXIMOS PASSOS:")
    print("   1. Verifique os logs do Celery para confirmar o envio:")
    print("      journalctl -u celery -f")
    print("   2. Procure por '📤 META PAYLOAD COMPLETO' nos logs")
    print("   3. Verifique se 'fbp' e 'fbc' estão presentes no user_data")
    print("   4. Os eventos aparecerão no Meta em 5-10 minutos")
    print("   5. Verifique Match Quality no Meta Ads Manager (esperado: 7-9/10)")
    print("\n✅ Script concluído!")

