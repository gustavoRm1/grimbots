"""
Reenviar Meta Pixel Purchase para vendas de HOJE com parâmetros corretos
Autor: Senior QI 500

Este script:
1. Busca todas as vendas de HOJE (status='paid')
2. Resetar flag meta_purchase_sent para permitir reenvio
3. Reenvia eventos Purchase com parâmetros corretos (campaign_code, UTMs)
4. Gera event_id único para evitar duplicação no Meta

IMPORTANTE: Meta aceita eventos duplicados se forem correções (parâmetros diferentes)
"""

from app import app, db, send_meta_pixel_purchase_event
from models import Payment
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with app.app_context():
    print("\n" + "=" * 80)
    print("🔄 REENVIAR META PIXEL - VENDAS DE HOJE (COM PARÂMETROS CORRETOS)")
    print("=" * 80)
    
    # Buscar vendas de HOJE (00:00 até agora)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.now()
    
    print(f"\n📅 Período: {today_start.strftime('%d/%m/%Y %H:%M')} até {now.strftime('%d/%m/%Y %H:%M')}")
    
    # Buscar TODAS as vendas pagas de hoje
    payments_today = Payment.query.filter(
        Payment.status == 'paid',
        Payment.created_at >= today_start,
        Payment.created_at <= now
    ).order_by(Payment.created_at.desc()).all()
    
    print(f"\n📊 TOTAL DE VENDAS DE HOJE: {len(payments_today)}")
    
    if not payments_today:
        print("\n⚠️ Nenhuma venda encontrada para hoje!")
        exit(0)
    
    # Filtrar apenas vendas que têm campaign_code ou que foram enviadas sem parâmetros
    # (vamos reenviar todas para garantir que têm os parâmetros corretos)
    payments_to_resend = []
    
    for p in payments_today:
        # Verificar se tem campaign_code salvo
        has_campaign_code = bool(p.campaign_code)
        has_utm = bool(p.utm_source or p.utm_campaign)
        
        # Se não tem parâmetros OU já foi enviado (pode ter sido sem parâmetros)
        if not has_campaign_code or not has_utm or p.meta_purchase_sent:
            payments_to_resend.append(p)
    
    print(f"📊 VENDAS QUE PRECISAM SER REENVIADAS: {len(payments_to_resend)}")
    
    if not payments_to_resend:
        print("\n✅ Todas as vendas já têm parâmetros corretos!")
        exit(0)
    
    # Mostrar preview
    print("\n📋 PREVIEW (primeiras 10 vendas):")
    for i, p in enumerate(payments_to_resend[:10], 1):
        print(f"  {i}. Payment {p.payment_id} | R$ {p.amount:.2f} | "
              f"campaign_code={p.campaign_code or 'N/A'} | "
              f"utm_source={p.utm_source or 'N/A'} | "
              f"meta_sent={p.meta_purchase_sent}")
    
    if len(payments_to_resend) > 10:
        print(f"  ... e mais {len(payments_to_resend) - 10} vendas")
    
    # Confirmar
    print("\n" + "=" * 80)
    response = input(f"⚠️ Deseja reenviar {len(payments_to_resend)} eventos Purchase? (s/N): ")
    
    if response.lower() != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        exit(0)
    
    # Reenviar
    print("\n" + "=" * 80)
    print("🔄 REENVIANDO EVENTOS...")
    print("=" * 80)
    
    success_count = 0
    error_count = 0
    
    for i, payment in enumerate(payments_to_resend, 1):
        print(f"\n[{i}/{len(payments_to_resend)}] Payment {payment.payment_id}")
        print(f"  💰 R$ {payment.amount:.2f}")
        print(f"  📅 Criado: {payment.created_at.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"  🎯 campaign_code: {payment.campaign_code or 'N/A'}")
        print(f"  📊 utm_source: {payment.utm_source or 'N/A'}")
        print(f"  📊 utm_campaign: {payment.utm_campaign or 'N/A'}")
        print(f"  📤 Meta já enviado: {payment.meta_purchase_sent}")
        print(f"  🔍 DEBUG: customer_user_id={payment.customer_user_id}, bot_id={payment.bot_id}")
        
        try:
            # ✅ FUNÇÃO DEFINITIVA: Buscar BotUser por TODAS as formas possíveis
            from models import BotUser, BotMessage
            from datetime import timedelta
            
            bot_user = None
            
            # ============================================================
            # MÉTODO 1: Por customer_user_id (quando existe)
            # ============================================================
            if payment.customer_user_id:
                telegram_user_id_str = None
                if payment.customer_user_id.startswith('user_'):
                    telegram_user_id_str = payment.customer_user_id.replace('user_', '')
                elif payment.customer_user_id.isdigit():
                    telegram_user_id_str = payment.customer_user_id
                else:
                    telegram_user_id_str = str(payment.customer_user_id)
                
                if telegram_user_id_str:
                    bot_user = BotUser.query.filter_by(
                        bot_id=payment.bot_id,
                        telegram_user_id=telegram_user_id_str
                    ).first()
                    
                    if bot_user:
                        print(f"  ✅ [MÉTODO 1] BotUser encontrado por customer_user_id: external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # MÉTODO 2: Por fbclid (se payment tem fbclid)
            # ============================================================
            if not bot_user and payment.fbclid:
                bot_user = BotUser.query.filter_by(
                    bot_id=payment.bot_id,
                    fbclid=payment.fbclid
                ).order_by(BotUser.last_interaction.desc()).first()
                
                if bot_user:
                    print(f"  ✅ [MÉTODO 2] BotUser encontrado por fbclid: external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # MÉTODO 3: Por customer_name + customer_username
            # ============================================================
            if not bot_user and payment.customer_name and payment.customer_username:
                bot_user = BotUser.query.filter_by(
                    bot_id=payment.bot_id,
                    first_name=payment.customer_name,
                    username=payment.customer_username
                ).order_by(BotUser.last_interaction.desc()).first()
                
                if bot_user:
                    print(f"  ✅ [MÉTODO 3] BotUser encontrado por nome+username: external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # MÉTODO 4: Por customer_name apenas (pode ter múltiplos)
            # ============================================================
            if not bot_user and payment.customer_name:
                # Buscar pelo nome e pegar o mais recente que interagiu no mesmo período
                payment_time = payment.created_at
                time_window_start = payment_time - timedelta(minutes=30)
                time_window_end = payment_time + timedelta(minutes=30)
                
                bot_user = BotUser.query.filter(
                    BotUser.bot_id == payment.bot_id,
                    BotUser.first_name == payment.customer_name,
                    BotUser.last_interaction >= time_window_start,
                    BotUser.last_interaction <= time_window_end
                ).order_by(BotUser.last_interaction.desc()).first()
                
                if bot_user:
                    print(f"  ✅ [MÉTODO 4] BotUser encontrado por nome (período): external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # MÉTODO 5: Por BotMessage relacionado (mensagens que mencionam o payment_id)
            # ============================================================
            if not bot_user:
                # Buscar mensagens que contêm o payment_id no texto ou callback_data
                payment_time = payment.created_at
                time_window_start = payment_time - timedelta(minutes=10)
                time_window_end = payment_time + timedelta(minutes=10)
                
                messages = BotMessage.query.filter(
                    BotMessage.bot_id == payment.bot_id,
                    BotMessage.created_at >= time_window_start,
                    BotMessage.created_at <= time_window_end,
                    BotMessage.message_text.contains(payment.payment_id)
                ).order_by(BotMessage.created_at.desc()).limit(1).all()
                
                if messages:
                    msg = messages[0]
                    bot_user = BotUser.query.filter_by(
                        bot_id=payment.bot_id,
                        telegram_user_id=msg.telegram_user_id
                    ).first()
                    
                    if bot_user:
                        print(f"  ✅ [MÉTODO 5] BotUser encontrado por BotMessage: external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # MÉTODO 6: Últimos BotUser que interagiram com o bot no período
            # ============================================================
            if not bot_user:
                # Buscar últimos BotUser que interagiram no mesmo período (último recurso)
                payment_time = payment.created_at
                time_window_start = payment_time - timedelta(minutes=60)
                time_window_end = payment_time + timedelta(minutes=10)
                
                # Buscar o BotUser mais recente que interagiu no período
                bot_user = BotUser.query.filter(
                    BotUser.bot_id == payment.bot_id,
                    BotUser.last_interaction >= time_window_start,
                    BotUser.last_interaction <= time_window_end
                ).order_by(BotUser.last_interaction.desc()).first()
                
                if bot_user:
                    print(f"  ⚠️ [MÉTODO 6] BotUser encontrado por último recurso (pode não ser o correto): external_id={bot_user.external_id or 'N/A'}")
            
            # ============================================================
            # RESULTADO FINAL
            # ============================================================
            if not bot_user:
                print(f"  ❌ BotUser NÃO encontrado por nenhum método!")
                print(f"     payment_id={payment.payment_id}, bot_id={payment.bot_id}")
                print(f"     customer_name={payment.customer_name}, customer_username={payment.customer_username}")
                print(f"     customer_user_id={payment.customer_user_id}, fbclid={payment.fbclid or 'N/A'}")
            
            # ✅ CORREÇÃO CRÍTICA: Se não tem campaign_code, buscar do bot_user
            if not payment.campaign_code and bot_user:
                if bot_user.external_id:  # grim está salvo aqui
                    payment.campaign_code = bot_user.external_id
                    print(f"  ✅ campaign_code atualizado do bot_user.external_id: {bot_user.external_id}")
                elif bot_user.campaign_code:
                    payment.campaign_code = bot_user.campaign_code
                    print(f"  ✅ campaign_code atualizado do bot_user.campaign_code: {bot_user.campaign_code}")
            
            # ✅ CORREÇÃO: Se não tem UTMs, buscar do bot_user
            if not payment.utm_source and bot_user and bot_user.utm_source:
                payment.utm_source = bot_user.utm_source
                print(f"  ✅ utm_source atualizado: {bot_user.utm_source}")
            if not payment.utm_campaign and bot_user and bot_user.utm_campaign:
                payment.utm_campaign = bot_user.utm_campaign
                print(f"  ✅ utm_campaign atualizado: {bot_user.utm_campaign}")
            if not payment.utm_content and bot_user and bot_user.utm_content:
                payment.utm_content = bot_user.utm_content
            if not payment.utm_medium and bot_user and bot_user.utm_medium:
                payment.utm_medium = bot_user.utm_medium
            if not payment.utm_term and bot_user and bot_user.utm_term:
                payment.utm_term = bot_user.utm_term
            if not payment.fbclid and bot_user and bot_user.fbclid:
                payment.fbclid = bot_user.fbclid
            
            # Se ainda não tem campaign_code, tentar buscar do Redis (pode ter sido perdido)
            if not payment.campaign_code:
                print(f"  ⚠️ campaign_code ainda vazio após buscar bot_user. Tentando buscar do Redis...")
                try:
                    import redis
                    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                    # Tentar buscar por fbclid ou external_id
                    if payment.fbclid:
                        redis_key = f"tracking_elite:{payment.fbclid}"
                        tracking_data = redis_client.hgetall(redis_key)
                        if tracking_data and tracking_data.get('grim'):
                            payment.campaign_code = tracking_data.get('grim')
                            print(f"  ✅ campaign_code encontrado no Redis (via fbclid): {payment.campaign_code}")
                except Exception as redis_error:
                    print(f"  ⚠️ Erro ao buscar Redis: {redis_error}")
            
            # ✅ CRÍTICO: Resetar flag para permitir reenvio
            # Isso permite que send_meta_pixel_purchase_event processe novamente
            old_meta_sent = payment.meta_purchase_sent
            old_event_id = payment.meta_event_id
            
            payment.meta_purchase_sent = False
            payment.meta_purchase_sent_at = None
            payment.meta_event_id = None
            
            # Commit imediato para salvar parâmetros E resetar flag
            db.session.commit()
            
            print(f"  🔄 Flag resetada (era: {old_meta_sent}, event_id: {old_event_id})")
            print(f"  📊 Parâmetros finais: campaign_code={payment.campaign_code or 'N/A'}, utm_source={payment.utm_source or 'N/A'}")
            
            # Reenviar evento
            print(f"  📤 Reenviando Meta Pixel Purchase...")
            send_meta_pixel_purchase_event(payment)
            
            # Verificar se foi enviado com sucesso
            db.session.refresh(payment)
            if payment.meta_purchase_sent:
                success_count += 1
                print(f"  ✅ Reenviado com sucesso! (novo event_id: {payment.meta_event_id})")
            else:
                # Pode não ter sido enviado se não tem pool configurado
                print(f"  ⚠️ Evento não foi enviado (verifique logs - pode ser pool não configurado)")
                error_count += 1
                
        except Exception as e:
            error_count += 1
            print(f"  ❌ ERRO ao reenviar: {e}")
            logger.error(f"Erro ao reenviar payment {payment.payment_id}: {e}", exc_info=True)
            db.session.rollback()
            
            # Tentar restaurar flag se falhou
            try:
                payment.meta_purchase_sent = old_meta_sent
                payment.meta_event_id = old_event_id
                db.session.commit()
            except:
                pass
    
    # Resumo
    print("\n" + "=" * 80)
    print("📊 RESUMO")
    print("=" * 80)
    print(f"✅ Sucesso: {success_count} eventos")
    print(f"❌ Erros: {error_count} eventos")
    print(f"📊 Total processado: {len(payments_to_resend)}")
    print("\n💡 Os eventos aparecerão no Meta Ads Manager em 5-10 minutos")
    print("💡 Verifique os logs do Celery para detalhes: journalctl -u celery -f")
    print("=" * 80 + "\n")

