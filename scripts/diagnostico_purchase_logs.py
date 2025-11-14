#!/usr/bin/env python3
"""
Script de diagnóstico para verificar por que Purchase não aparece nos logs
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ CRÍTICO: Carregar .env ANTES de importar app (para ENCRYPTION_KEY)
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)  # ✅ split('=', 1) preserva '=' no valor
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}")

from app import app, db
from models import Payment, PoolBot, Pool
from datetime import datetime, timedelta
import json

def diagnosticar_purchase():
    """Diagnostica por que Purchase não aparece nos logs"""
    
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: Por que Purchase não aparece nos logs?")
    print("=" * 80)
    print()
    
    with app.app_context():
        # 1. Buscar última venda (últimas 24h)
        print("1️⃣ ÚLTIMA VENDA (últimas 24h):")
        print("-" * 80)
        
        uma_hora_atras = datetime.utcnow() - timedelta(hours=24)
        ultimo_payment = Payment.query.filter(
            Payment.created_at >= uma_hora_atras
        ).order_by(Payment.created_at.desc()).first()
        
        if not ultimo_payment:
            print("❌ Nenhuma venda encontrada nas últimas 24h")
            return
        
        print(f"✅ Última venda encontrada:")
        print(f"   Payment ID: {ultimo_payment.payment_id}")
        print(f"   Status: {ultimo_payment.status}")
        print(f"   Bot ID: {ultimo_payment.bot_id}")
        print(f"   Valor: R$ {ultimo_payment.amount}")
        print(f"   Criado em: {ultimo_payment.created_at}")
        print(f"   meta_purchase_sent: {ultimo_payment.meta_purchase_sent}")
        print(f"   meta_purchase_sent_at: {ultimo_payment.meta_purchase_sent_at}")
        print()
        
        # 2. Verificar se bot está associado a um pool
        print("2️⃣ VERIFICAÇÃO: Bot → Pool")
        print("-" * 80)
        
        pool_bot = PoolBot.query.filter_by(bot_id=ultimo_payment.bot_id).first()
        if not pool_bot:
            print("❌ PROBLEMA RAIZ: Bot não está associado a nenhum pool!")
            print(f"   Bot ID: {ultimo_payment.bot_id}")
            print("   SOLUÇÃO: Associe o bot a um pool no dashboard")
            return
        
        pool = pool_bot.pool
        print(f"✅ Bot associado ao pool:")
        print(f"   Pool ID: {pool.id}")
        print(f"   Pool Nome: {pool.name}")
        print()
        
        # 3. Verificar configuração do Meta Pixel no pool
        print("3️⃣ VERIFICAÇÃO: Configuração Meta Pixel")
        print("-" * 80)
        
        print(f"   meta_tracking_enabled: {pool.meta_tracking_enabled}")
        print(f"   meta_pixel_id: {'✅ Configurado' if pool.meta_pixel_id else '❌ NÃO CONFIGURADO'}")
        print(f"   meta_access_token: {'✅ Configurado' if pool.meta_access_token else '❌ NÃO CONFIGURADO'}")
        print(f"   meta_events_purchase: {pool.meta_events_purchase}")
        print()
        
        if not pool.meta_tracking_enabled:
            print("❌ PROBLEMA: Meta tracking DESABILITADO para este pool")
            print("   SOLUÇÃO: Ative 'Meta Tracking' nas configurações do pool")
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            print("❌ PROBLEMA: Pool tem tracking ativo mas SEM pixel_id ou access_token")
            print("   SOLUÇÃO: Configure Meta Pixel ID e Access Token nas configurações do pool")
            return
        
        if not pool.meta_events_purchase:
            print("❌ PROBLEMA: Evento Purchase DESABILITADO para este pool")
            print("   SOLUÇÃO: Ative 'Purchase Event' nas configurações do pool")
            return
        
        print("✅ Configuração Meta Pixel OK")
        print()
        
        # 4. Verificar se Purchase já foi enviado
        print("4️⃣ VERIFICAÇÃO: Status do Purchase")
        print("-" * 80)
        
        if ultimo_payment.meta_purchase_sent:
            print(f"✅ Purchase JÁ FOI ENVIADO")
            print(f"   Enviado em: {ultimo_payment.meta_purchase_sent_at}")
            print(f"   Event ID: {ultimo_payment.meta_event_id}")
            print()
            print("💡 Se não apareceu nos logs, pode ser que:")
            print("   - Logs foram rotacionados")
            print("   - Logs estão em outro arquivo (celery.log)")
            print("   - Logs foram enviados antes do monitoramento")
        else:
            print("❌ Purchase NÃO FOI ENVIADO AINDA")
            print()
            print("💡 Possíveis causas:")
            print("   1. Payment.status != 'paid' (Purchase só envia quando pago)")
            print("   2. Função send_meta_pixel_purchase_event não foi chamada")
            print("   3. Função foi chamada mas retornou antes de enfileirar")
            print("   4. Exceção silenciosa antes dos logs")
            print()
            
            # Verificar onde Purchase deveria ser chamado
            print("5️⃣ VERIFICAÇÃO: Onde Purchase deveria ser chamado?")
            print("-" * 80)
            
            if ultimo_payment.status == 'paid':
                print("✅ Payment.status = 'paid' → Purchase DEVERIA ter sido enviado")
                print()
                print("📍 Locais onde Purchase é chamado:")
                print("   - tasks_async.py: process_webhook_async (quando webhook marca como paid)")
                print("   - bot_manager.py: _handle_verify_payment (quando botão 'Verificar Pagamento' confirma paid)")
                print("   - app.py: reconcile_paradise_payments (reconciliação Paradise)")
                print("   - app.py: reconcile_pushynpay_payments (reconciliação PushynPay)")
                print("   - jobs/sync_umbrellapay.py: sync_umbrellapay_payments (sincronização UmbrellaPay)")
                print()
                print("🔍 Verifique os logs destes locais para ver se houve erro silencioso")
            else:
                print(f"⚠️ Payment.status = '{ultimo_payment.status}' → Purchase NÃO será enviado até status='paid'")
                print()
                print("💡 Purchase só é enviado quando payment.status == 'paid'")
        
        # 6. Verificar tracking_token
        print()
        print("6️⃣ VERIFICAÇÃO: Tracking Token")
        print("-" * 80)
        
        tracking_token = getattr(ultimo_payment, 'tracking_token', None)
        if tracking_token:
            print(f"✅ tracking_token presente: {tracking_token[:30]}...")
        else:
            print("⚠️ tracking_token AUSENTE")
            print("   Isso pode causar problemas na recuperação de fbp/fbc")
        
        print()
        print("=" * 80)
        print("📋 RESUMO DO DIAGNÓSTICO")
        print("=" * 80)
        print()
        print("Para verificar logs completos, execute:")
        print()
        print("# Ver logs do Gunicorn:")
        print("sudo journalctl -u grimbots -n 500 | grep -i purchase")
        print()
        print("# Ver logs do Celery:")
        print("sudo journalctl -u celery-worker -n 500 | grep -i purchase")
        print("OU")
        print("tail -n 500 /root/grimbots/logs/celery.log | grep -i purchase")
        print()
        print("# Ver TODOS os logs relacionados ao payment:")
        print(f"sudo journalctl -u grimbots -n 1000 | grep {ultimo_payment.payment_id}")
        print()
        print("# Ver logs em tempo real:")
        print("sudo journalctl -u grimbots -f | grep --line-buffered -E '(Purchase|DEBUG Meta Pixel)'")
        print()

if __name__ == '__main__':
    diagnosticar_purchase()

