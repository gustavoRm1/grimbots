#!/usr/bin/env python3
"""
TESTE ORDER BUMP - VERIFICAR IMPLEMENTAÇÃO
==========================================
Testa se order bump está funcionando corretamente
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Bot, BotConfig, Payment
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_order_bump_implementation():
    """Testa se order bump está implementado corretamente"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE ORDER BUMP - VERIFICAR IMPLEMENTAÇÃO")
        print("=" * 80)
        
        # 1. Verificar bots com configuração
        bots = Bot.query.filter(Bot.config.has()).all()
        
        print(f"\n📊 BOTS COM CONFIGURAÇÃO: {len(bots)}")
        
        for bot in bots:
            print(f"\n🤖 BOT: {bot.name} (@{bot.username})")
            
            config = bot.config.to_dict()
            main_buttons = config.get('main_buttons', [])
            
            print(f"   📋 Botões principais: {len(main_buttons)}")
            
            # Verificar cada botão
            for i, button in enumerate(main_buttons):
                print(f"\n   🔘 BOTÃO {i+1}:")
                print(f"      Texto: {button.get('text', 'N/A')}")
                price = button.get('price', 0)
                try:
                    price_float = float(price) if price else 0
                    print(f"      Preço: R$ {price_float:.2f}")
                except (ValueError, TypeError):
                    print(f"      Preço: {price} (formato inválido)")
                print(f"      Descrição: {button.get('description', 'N/A')}")
                
                # Verificar order bump
                order_bump = button.get('order_bump', {})
                if order_bump.get('enabled'):
                    print(f"      🎁 ORDER BUMP ATIVO:")
                    print(f"         Mensagem: {order_bump.get('message', 'N/A')[:50]}...")
                    bump_price = order_bump.get('price', 0)
                    try:
                        bump_price_float = float(bump_price) if bump_price else 0
                        print(f"         Preço adicional: R$ {bump_price_float:.2f}")
                    except (ValueError, TypeError):
                        print(f"         Preço adicional: {bump_price} (formato inválido)")
                    print(f"         Descrição: {order_bump.get('description', 'N/A')}")
                    print(f"         Mídia: {order_bump.get('media_url', 'N/A')}")
                    print(f"         Tipo: {order_bump.get('media_type', 'N/A')}")
                    print(f"         Áudio: {'Sim' if order_bump.get('audio_enabled') else 'Não'}")
                    print(f"         Aceitar: {order_bump.get('accept_text', 'Padrão')}")
                    print(f"         Recusar: {order_bump.get('decline_text', 'Padrão')}")
                else:
                    print(f"      ❌ Order bump desabilitado")
        
        # 2. Verificar pagamentos com order bump
        print(f"\n📊 PAGAMENTOS COM ORDER BUMP:")
        
        payments_with_bump = Payment.query.filter(
            Payment.order_bump_shown == True
        ).order_by(Payment.created_at.desc()).limit(10).all()
        
        if payments_with_bump:
            print(f"   📈 Total encontrados: {len(payments_with_bump)}")
            for payment in payments_with_bump:
                print(f"\n   💳 PAGAMENTO: {payment.payment_id}")
                print(f"      Status: {payment.status}")
                print(f"      Valor: R$ {payment.amount:.2f}")
                print(f"      Order bump aceito: {'Sim' if payment.order_bump_accepted else 'Não'}")
                print(f"      Valor bump: R$ {payment.order_bump_value:.2f}")
                print(f"      Criado: {payment.created_at}")
        else:
            print(f"   ❌ Nenhum pagamento com order bump encontrado")
        
        # 3. Verificar estrutura do banco
        print(f"\n📊 ESTRUTURA DO BANCO:")
        
        # Verificar se campos existem
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = inspector.get_columns('payments')
        
        order_bump_fields = ['order_bump_shown', 'order_bump_accepted', 'order_bump_value']
        
        for field in order_bump_fields:
            field_exists = any(col['name'] == field for col in columns)
            status = "✅" if field_exists else "❌"
            print(f"   {status} Campo '{field}': {'Existe' if field_exists else 'NÃO EXISTE'}")
        
        print(f"\n" + "=" * 80)
        print("TESTE FINALIZADO")
        print("=" * 80)
        
        # 4. Recomendações
        print(f"\n💡 RECOMENDAÇÕES:")
        print(f"   1. Configure order bump em um bot para teste")
        print(f"   2. Teste o fluxo completo de compra")
        print(f"   3. Verifique se analytics estão sendo salvos")
        print(f"   4. Teste com diferentes configurações de mídia")

if __name__ == '__main__':
    test_order_bump_implementation()
