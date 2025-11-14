#!/usr/bin/env python3
"""
Script de Validação - Venda Recente
Verifica se a correção V4.1 (fbc REAL) está funcionando corretamente
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}")

from models import db, Payment, BotUser
from app import app

def extract_timestamp_from_fbc(fbc_value):
    """Extrai timestamp do fbc no formato: fb.1.<timestamp>.<payload>"""
    import re
    if not fbc_value or not isinstance(fbc_value, str):
        return None
    match = re.match(r'^fb\.1\.(\d+)\.', fbc_value)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, AttributeError):
            return None
    return None

def is_synthetic_fbc(fbc_value, current_timestamp=None):
    """Determina se fbc é sintético baseado no timestamp"""
    import time
    if not fbc_value:
        return False
    timestamp = extract_timestamp_from_fbc(fbc_value)
    if not timestamp:
        return False
    current_timestamp = current_timestamp or int(time.time())
    time_diff = current_timestamp - timestamp
    # fbc sintético: timestamp dentro de 1 hora
    if time_diff < 3600:
        return True
    return False

def validar_venda_recente():
    """Valida a venda mais recente"""
    
    print("=" * 80)
    print("🔍 VALIDAÇÃO DA VENDA MAIS RECENTE - PATCH V4.1")
    print("=" * 80)
    print()
    
    with app.app_context():
        # Buscar vendas recentes (últimas 24 horas)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        payments = Payment.query.filter(
            Payment.created_at >= cutoff
        ).order_by(Payment.created_at.desc()).limit(10).all()
        
        if not payments:
            print("❌ Nenhuma venda encontrada nas últimas 24 horas")
            print("   Tente fazer uma nova venda")
            return 1
        
        # Se houver múltiplas vendas, mostrar lista
        if len(payments) > 1:
            print(f"✅ Encontradas {len(payments)} vendas nas últimas 24 horas:")
            print()
            for i, p in enumerate(payments, 1):
                print(f"   {i}. Payment ID: {p.payment_id} | Status: {p.status} | Valor: R$ {p.amount:.2f} | Criado: {p.created_at}")
            print()
            print("   Validando a venda MAIS RECENTE...")
            print()
        
        payment = payments[0]
        
        print(f"✅ Venda encontrada:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Valor: R$ {payment.amount:.2f}")
        print(f"   Criado em: {payment.created_at}")
        print()
        
        # Buscar BotUser
        bot_user = None
        if payment.telegram_user_id:
            bot_user = BotUser.query.filter_by(
                bot_id=payment.bot_id,
                telegram_user_id=payment.telegram_user_id
            ).first()
        
        print("=" * 80)
        print("1️⃣ VALIDAÇÃO: FBC (Facebook Click ID)")
        print("=" * 80)
        
        # Verificar fbc no Payment
        payment_fbc = getattr(payment, 'fbc', None)
        if payment_fbc:
            import time
            current_ts = int(time.time())
            fbc_ts = extract_timestamp_from_fbc(payment_fbc)
            is_synthetic = is_synthetic_fbc(payment_fbc, current_ts)
            
            print(f"   Payment.fbc: {payment_fbc[:50]}...")
            if fbc_ts:
                print(f"   Timestamp do fbc: {fbc_ts}")
                print(f"   Diferença: {current_ts - fbc_ts} segundos ({((current_ts - fbc_ts) / 86400):.1f} dias)")
                if is_synthetic:
                    print(f"   ❌ FBC SINTÉTICO DETECTADO! (timestamp muito recente)")
                else:
                    print(f"   ✅ FBC REAL (timestamp antigo - do clique original)")
            else:
                print(f"   ⚠️  Não foi possível extrair timestamp do fbc")
        else:
            print(f"   ⚠️  Payment.fbc: ausente")
        
        # Verificar fbc no BotUser
        if bot_user:
            bot_user_fbc = getattr(bot_user, 'fbc', None)
            if bot_user_fbc:
                import time
                current_ts = int(time.time())
                is_synthetic = is_synthetic_fbc(bot_user_fbc, current_ts)
                print(f"   BotUser.fbc: {bot_user_fbc[:50]}...")
                if is_synthetic:
                    print(f"   ❌ FBC SINTÉTICO DETECTADO!")
                else:
                    print(f"   ✅ FBC REAL")
            else:
                print(f"   ⚠️  BotUser.fbc: ausente")
        
        print()
        
        print("=" * 80)
        print("2️⃣ VALIDAÇÃO: EXTERNAL_ID (fbclid)")
        print("=" * 80)
        
        # Verificar tracking_token
        tracking_token = getattr(payment, 'tracking_token', None)
        if tracking_token:
            print(f"   ✅ tracking_token presente: {tracking_token[:30]}...")
            
            # Tentar recuperar do Redis
            try:
                from redis_manager import get_redis_connection
                redis_conn = get_redis_connection()
                
                # Buscar no Redis
                key = f"tracking:token:{tracking_token}"
                value = redis_conn.get(key)
                
                if value:
                    import json
                    tracking_data = json.loads(value)
                    external_id = tracking_data.get('fbclid')
                    fbc_redis = tracking_data.get('fbc')
                    fbc_origin = tracking_data.get('fbc_origin')
                    
                    if external_id:
                        print(f"   ✅ fbclid no Redis: {external_id[:30]}...")
                    else:
                        print(f"   ⚠️  fbclid ausente no Redis")
                    
                    if fbc_redis:
                        import time
                        current_ts = int(time.time())
                        is_synthetic = is_synthetic_fbc(fbc_redis, current_ts)
                        print(f"   Redis.fbc: {fbc_redis[:50]}...")
                        print(f"   Redis.fbc_origin: {fbc_origin or 'ausente'}")
                        if is_synthetic:
                            print(f"   ❌ FBC SINTÉTICO no Redis!")
                        else:
                            print(f"   ✅ FBC REAL no Redis")
                    else:
                        print(f"   ⚠️  fbc ausente no Redis")
                else:
                    print(f"   ⚠️  tracking_token não encontrado no Redis (pode ter expirado)")
            except Exception as e:
                print(f"   ⚠️  Erro ao buscar no Redis: {e}")
        else:
            print(f"   ❌ tracking_token ausente no Payment")
        
        print()
        
        print("=" * 80)
        print("3️⃣ VALIDAÇÃO: META PIXEL PURCHASE EVENT")
        print("=" * 80)
        
        meta_purchase_sent = getattr(payment, 'meta_purchase_sent', False)
        meta_purchase_sent_at = getattr(payment, 'meta_purchase_sent_at', None)
        
        if meta_purchase_sent:
            print(f"   ✅ Purchase event enviado: {meta_purchase_sent_at}")
        else:
            print(f"   ❌ Purchase event NÃO foi enviado ainda")
            if payment.status != 'paid':
                print(f"   ⚠️  Motivo: Payment.status = '{payment.status}' (Purchase só envia quando 'paid')")
        
        print()
        
        print("=" * 80)
        print("4️⃣ VALIDAÇÃO: LOGS DO GUNICORN")
        print("=" * 80)
        print()
        print("   Execute os seguintes comandos para verificar os logs:")
        print()
        print(f"   # Buscar logs do redirect (PageView):")
        print(f"   grep -iE '\\[META REDIRECT\\].*{tracking_token[:20]}' logs/gunicorn.log | tail -5")
        print()
        print(f"   # Buscar logs do Purchase:")
        print(f"   grep -iE '\\[META PURCHASE\\].*{payment.payment_id}' logs/gunicorn.log | tail -10")
        print()
        print(f"   # Verificar se fbc foi capturado como REAL:")
        print(f"   grep -iE 'fbc.*ORIGEM REAL|fbc REAL' logs/gunicorn.log | tail -5")
        print()
        print(f"   # Verificar se fbc sintético foi gerado (NÃO DEVE APARECER):")
        print(f"   grep -iE 'fbc.*gerado.*fbclid|fbc sintético' logs/gunicorn.log | tail -5")
        print()
        
        print("=" * 80)
        print("📊 RESUMO DA VALIDAÇÃO")
        print("=" * 80)
        print()
        
        # Resumo
        issues = []
        successes = []
        
        if payment_fbc:
            if is_synthetic_fbc(payment_fbc):
                issues.append("❌ Payment.fbc é SINTÉTICO")
            else:
                successes.append("✅ Payment.fbc é REAL")
        else:
            issues.append("⚠️  Payment.fbc ausente (OK se não tiver cookie)")
        
        if tracking_token:
            successes.append("✅ tracking_token presente")
        else:
            issues.append("❌ tracking_token ausente")
        
        if meta_purchase_sent:
            successes.append("✅ Purchase event enviado")
        else:
            if payment.status == 'paid':
                issues.append("❌ Purchase event NÃO foi enviado (mesmo com status=paid)")
            else:
                issues.append("⚠️  Purchase event não enviado (status != paid)")
        
        print("✅ SUCESSOS:")
        for s in successes:
            print(f"   {s}")
        
        if issues:
            print()
            print("⚠️  PROBLEMAS ENCONTRADOS:")
            for i in issues:
                print(f"   {i}")
        
        print()
        print("=" * 80)
        
        return 0

if __name__ == '__main__':
    exit(validar_venda_recente())

