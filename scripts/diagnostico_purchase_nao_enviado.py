#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico completo para identificar por que Purchase não está sendo enviado
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Payment, PoolBot, BotUser
from utils.tracking_service import TrackingServiceV4
import json

def diagnostico_purchase_nao_enviado(payment_id=None):
    """
    Diagnóstico completo de por que Purchase não está sendo enviado
    """
    with app.app_context():
        print("=" * 80)
        print("🔍 DIAGNÓSTICO COMPLETO - PURCHASE NÃO ENVIADO")
        print("=" * 80)
        print()
        
        # 1. Buscar payment recente
        if payment_id:
            payment = Payment.query.filter_by(payment_id=payment_id).first()
        else:
            payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum payment encontrado")
            return
        
        print(f"📊 PAYMENT: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
        print(f"   Created At: {payment.created_at}")
        print(f"   Paid At: {payment.paid_at}")
        print(f"   Bot ID: {payment.bot_id}")
        print(f"   Customer User ID: {payment.customer_user_id}")
        print()
        
        # 2. Verificar Pool Bot
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if not pool_bot:
            print("❌ PROBLEMA 1: Pool Bot não encontrado")
            print(f"   Bot ID: {payment.bot_id}")
            print(f"   SOLUÇÃO: Associe o bot a um pool no dashboard")
            return
        else:
            print("✅ Pool Bot encontrado")
            pool = pool_bot.pool
            print(f"   Pool ID: {pool.id}")
            print(f"   Pool Name: {pool.name}")
            print()
        
        # 3. Verificar Meta Tracking
        if not pool.meta_tracking_enabled:
            print("❌ PROBLEMA 2: Meta Tracking desabilitado")
            print(f"   SOLUÇÃO: Ative 'Meta Tracking' nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Meta Tracking habilitado")
            print()
        
        # 4. Verificar Pixel ID e Access Token
        if not pool.meta_pixel_id:
            print("❌ PROBLEMA 3: Pixel ID ausente")
            print(f"   SOLUÇÃO: Configure Meta Pixel ID nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Pixel ID configurado")
            print(f"   Pixel ID: {pool.meta_pixel_id}")
        
        if not pool.meta_access_token:
            print("❌ PROBLEMA 4: Access Token ausente")
            print(f"   SOLUÇÃO: Configure Meta Access Token nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Access Token configurado")
            print()
        
        # 5. Verificar Evento Purchase
        if not pool.meta_events_purchase:
            print("❌ PROBLEMA 5: Evento Purchase desabilitado")
            print(f"   SOLUÇÃO: Ative 'Purchase Event' nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Evento Purchase habilitado")
            print()
        
        # 6. Verificar tracking_token
        tracking_token = getattr(payment, 'tracking_token', None)
        if not tracking_token:
            print("❌ PROBLEMA 6: tracking_token ausente no Payment")
            print(f"   SOLUÇÃO: Verifique se usuário veio do redirect")
            return
        else:
            print("✅ tracking_token encontrado no Payment")
            print(f"   Tracking Token: {tracking_token[:30]}... (len={len(tracking_token)})")
            print()
        
        # 7. Verificar BotUser
        telegram_user_id = str(payment.customer_user_id).replace('user_', '')
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=telegram_user_id
        ).first()
        
        if not bot_user:
            print("❌ PROBLEMA 7: BotUser não encontrado")
            print(f"   Telegram User ID: {telegram_user_id}")
            print()
        else:
            print("✅ BotUser encontrado")
            print(f"   tracking_session_id: {bot_user.tracking_session_id[:30] if bot_user.tracking_session_id else 'None'}...")
            print(f"   fbclid: {'✅' if bot_user.fbclid else '❌'}")
            print(f"   fbp: {'✅' if bot_user.fbp else '❌'}")
            print(f"   fbc: {'✅' if bot_user.fbc else '❌'}")
            print(f"   ip_address: {'✅' if bot_user.ip_address else '❌'}")
            print(f"   user_agent: {'✅' if bot_user.user_agent else '❌'}")
            print()
            
            # ✅ CRÍTICO: Verificar se tracking_session_id é diferente do payment.tracking_token
            if bot_user.tracking_session_id and bot_user.tracking_session_id != tracking_token:
                print("⚠️ PROBLEMA 8: tracking_session_id do BotUser é DIFERENTE do payment.tracking_token")
                print(f"   BotUser tracking_session_id: {bot_user.tracking_session_id[:30]}... (len={len(bot_user.tracking_session_id)})")
                print(f"   Payment tracking_token: {tracking_token[:30]}... (len={len(tracking_token)})")
                print(f"   SOLUÇÃO: Usar tracking_session_id do BotUser para recuperar tracking_data")
                print()
        
        # 8. Verificar tracking_data no Redis
        tracking_service_v4 = TrackingServiceV4()
        
        # ✅ PRIORIDADE 1: tracking_session_id do BotUser (token do redirect)
        tracking_data = {}
        tracking_token_used = None
        
        if bot_user and bot_user.tracking_session_id:
            try:
                tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
                if tracking_data:
                    tracking_token_used = bot_user.tracking_session_id
                    print("✅ tracking_data encontrado usando bot_user.tracking_session_id (PRIORIDADE 1)")
                    print(f"   Tracking Token: {bot_user.tracking_session_id[:30]}...")
                    print(f"   Campos: {list(tracking_data.keys())}")
                    print(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
                    print(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                    print(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                    print(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
                    print(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
                    print(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
                    print()
            except Exception as e:
                print(f"⚠️ Erro ao recuperar tracking_data usando bot_user.tracking_session_id: {e}")
                print()
        
        # ✅ PRIORIDADE 2: payment.tracking_token (se não encontrou no BotUser)
        if not tracking_data and tracking_token:
            try:
                tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
                if tracking_data:
                    tracking_token_used = tracking_token
                    print("✅ tracking_data encontrado usando payment.tracking_token (PRIORIDADE 2)")
                    print(f"   Tracking Token: {tracking_token[:30]}...")
                    print(f"   Campos: {list(tracking_data.keys())}")
                    print(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
                    print(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                    print(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                    print(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
                    print(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
                    print(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
                    print()
            except Exception as e:
                print(f"⚠️ Erro ao recuperar tracking_data usando payment.tracking_token: {e}")
                print()
        
        # ✅ PRIORIDADE 3: Recuperar via fbclid do Payment
        if not tracking_data and getattr(payment, 'fbclid', None):
            try:
                token = tracking_service_v4.redis.get(f"tracking:fbclid:{payment.fbclid}")
                if token:
                    tracking_data = tracking_service_v4.recover_tracking_data(token) or {}
                    if tracking_data:
                        tracking_token_used = token
                        print("✅ tracking_data encontrado via fbclid do Payment (PRIORIDADE 3)")
                        print(f"   Tracking Token: {token[:30]}...")
                        print(f"   Campos: {list(tracking_data.keys())}")
                        print(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
                        print(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                        print(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                        print(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
                        print(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
                        print(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
                        print()
            except Exception as e:
                print(f"⚠️ Erro ao recuperar tracking_data via fbclid: {e}")
                print()
        
        if not tracking_data:
            print("❌ PROBLEMA 9: tracking_data vazio no Redis")
            print(f"   Tentou usar: {tracking_token_used[:30] if tracking_token_used else 'N/A'}...")
            print(f"   SOLUÇÃO: Verifique se token existe no Redis")
            print()
        
        # 9. Verificar user_data que seria enviado
        from utils.meta_pixel import MetaPixelAPI, normalize_external_id
        
        external_id_value = tracking_data.get('fbclid') or payment.fbclid or (bot_user.fbclid if bot_user else None)
        fbp_value = tracking_data.get('fbp') or payment.fbp or (bot_user.fbp if bot_user else None)
        fbc_value = tracking_data.get('fbc') or payment.fbc or (bot_user.fbc if bot_user else None)
        ip_value = tracking_data.get('client_ip') or (bot_user.ip_address if bot_user else None)
        user_agent_value = tracking_data.get('client_user_agent') or (bot_user.user_agent if bot_user else None)
        
        # ✅ Normalizar external_id
        external_id_normalized = normalize_external_id(external_id_value) if external_id_value else None
        
        print("🔍 USER_DATA QUE SERIA ENVIADO:")
        print(f"   external_id (raw): {'✅' if external_id_value else '❌'} {external_id_value[:30] if external_id_value else 'N/A'}...")
        print(f"   external_id (normalized): {'✅' if external_id_normalized else '❌'} {external_id_normalized[:30] if external_id_normalized else 'N/A'}...")
        print(f"   fbp: {'✅' if fbp_value else '❌'} {fbp_value[:30] if fbp_value else 'N/A'}...")
        print(f"   fbc: {'✅' if fbc_value else '❌'} {fbc_value[:50] if fbc_value else 'N/A'}...")
        print(f"   client_ip_address: {'✅' if ip_value else '❌'} {ip_value if ip_value else 'N/A'}")
        print(f"   client_user_agent: {'✅' if user_agent_value else '❌'} {user_agent_value[:50] if user_agent_value else 'N/A'}...")
        print()
        
        # 10. Verificar validações que podem bloquear
        if not external_id_value and not ip_value:
            print("❌ PROBLEMA 10: user_data não tem external_id nem client_ip_address")
            print(f"   SOLUÇÃO: Meta rejeita eventos sem user_data válido")
            return
        
        if not external_id_value and not fbp_value and not fbc_value:
            print("❌ PROBLEMA 11: Nenhum identificador presente (external_id, fbp, fbc)")
            print(f"   SOLUÇÃO: Meta rejeita eventos sem identificadores")
            return
        
        # 11. Verificar Celery
        try:
            from celery_app import celery_app
            # Verificar se Celery está rodando
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            if active_workers:
                print("✅ Celery está rodando")
                print(f"   Workers ativos: {len(active_workers)}")
            else:
                print("❌ PROBLEMA 12: Celery não está rodando")
                print(f"   SOLUÇÃO: Inicie o Celery worker")
                return
        except Exception as e:
            print(f"❌ PROBLEMA 12: Erro ao verificar Celery: {e}")
            print(f"   SOLUÇÃO: Verifique se Celery está configurado corretamente")
            return
        
        print()
        print("=" * 80)
        print("✅ TODAS AS VALIDAÇÕES PASSARAM!")
        print("=" * 80)
        print("   Purchase DEVERIA estar sendo enviado")
        print("   Verifique logs do Celery para identificar problemas no processamento")
        print()
        print("📋 RESUMO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Tracking Token (Payment): {tracking_token[:30] if tracking_token else 'N/A'}...")
        print(f"   Tracking Token (BotUser): {bot_user.tracking_session_id[:30] if bot_user and bot_user.tracking_session_id else 'N/A'}...")
        print(f"   Tracking Token (Usado): {tracking_token_used[:30] if tracking_token_used else 'N/A'}...")
        print(f"   Tracking Data: {'✅ Encontrado' if tracking_data else '❌ Vazio'}")
        print(f"   User Data: external_id={'✅' if external_id_normalized else '❌'}, fbp={'✅' if fbp_value else '❌'}, fbc={'✅' if fbc_value else '❌'}, ip={'✅' if ip_value else '❌'}, ua={'✅' if user_agent_value else '❌'}")
        print()

if __name__ == '__main__':
    import sys
    payment_id = sys.argv[1] if len(sys.argv) > 1 else None
    diagnostico_purchase_nao_enviado(payment_id)

