#!/usr/bin/env python3
"""
🔍 DIAGNÓSTICO: Transações Paradise que não aparecem no painel
Verifica pagamentos com PIX gerado mas que não estão no painel Paradise
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: Transações Paradise não aparecem no painel")
    print("=" * 80)
    
    # Buscar pagamentos Paradise pendentes das últimas 24h
    desde = datetime.now() - timedelta(hours=24)
    
    pagamentos = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.status == 'pending',
        Payment.created_at >= desde
    ).order_by(Payment.created_at.desc()).all()
    
    print(f"\n📊 Pagamentos Paradise PENDENTES (últimas 24h): {len(pagamentos)}")
    
    for p in pagamentos[:10]:  # Mostrar apenas os 10 mais recentes
        print(f"\n   Payment ID: {p.id} ({p.payment_id})")
        print(f"   Valor: R$ {p.amount:.2f}")
        print(f"   Criado: {p.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Transaction ID: {p.gateway_transaction_id}")
        print(f"   Transaction Hash: {p.gateway_transaction_hash}")
        print(f"   Tem QR Code: {'✅' if p.product_description and p.product_description.startswith('000201') else '❌'}")
        
        # Tentar consultar status na Paradise
        if p.gateway_transaction_id or p.gateway_transaction_hash:
            try:
                gateway = Gateway.query.filter_by(
                    user_id=p.bot.user_id,
                    gateway_type='paradise',
                    is_active=True
                ).first()
                
                if gateway:
                    creds = {
                        'api_key': gateway.api_key,
                        'product_hash': gateway.product_hash,
                        'offer_hash': gateway.offer_hash,
                        'store_id': gateway.store_id,
                        'split_percentage': gateway.split_percentage or 2.0
                    }
                    g = GatewayFactory.create_gateway('paradise', creds)
                    
                    if g:
                        hash_or_id = p.gateway_transaction_hash or p.gateway_transaction_id
                        status = g.get_payment_status(str(hash_or_id))
                        
                        if status:
                            print(f"   Status na Paradise: {status.get('status', 'N/A')}")
                            print(f"   Transaction ID retornado: {status.get('gateway_transaction_id', 'N/A')}")
                        else:
                            print(f"   ⚠️ Não encontrado na Paradise (pode não ter sido criado)")
                else:
                    print(f"   ⚠️ Gateway não encontrado")
            except Exception as e:
                print(f"   ❌ Erro ao consultar: {e}")
    
    print("\n" + "=" * 80)
    print("💡 DICAS:")
    print("   1. Se QR Code existe mas não aparece no painel: verificar reference único")
    print("   2. Se não encontrado na Paradise: transação pode não ter sido criada")
    print("   3. Verificar logs do sistema para ver resposta completa da Paradise")
    print("=" * 80)

