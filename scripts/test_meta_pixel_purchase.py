#!/usr/bin/env python3
"""
Script de teste para re-enviar Meta Pixel Purchase
Útil para validar se o evento está sendo enviado corretamente
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_resend_purchase():
    """Testa re-envio de Purchase para um payment específico"""
    from app import app, db, send_meta_pixel_purchase_event
    from models import Payment
    
    with app.app_context():
        # Ajustar payment_id aqui
        payment_id = input("Digite o payment_id para testar (ex: BOT47_1763013893_cd76f3af): ").strip()
        
        if not payment_id:
            print("❌ Payment ID não fornecido")
            return
        
        p = Payment.query.filter_by(payment_id=payment_id).first()
        
        if not p:
            print(f"❌ Payment {payment_id} não encontrado")
            return
        
        print(f"\n📊 Payment encontrado:")
        print(f"   ID: {p.payment_id}")
        print(f"   Status: {p.status}")
        print(f"   Valor: R$ {p.amount:.2f}")
        print(f"   Tracking Token: {p.tracking_token}")
        print(f"   fbclid: {p.fbclid[:50] if p.fbclid else 'None'}...")
        print(f"   Meta Purchase Sent: {p.meta_purchase_sent}")
        print(f"   Meta Event ID: {p.meta_event_id}")
        print(f"   Criado em: {p.created_at}")
        
        if p.status != 'paid':
            print(f"\n⚠️  Payment está com status '{p.status}', não 'paid'")
            resposta = input("Deseja continuar mesmo assim? (s/N): ").strip().lower()
            if resposta != 's':
                return
        
        print(f"\n📤 Antes do envio:")
        print(f"   meta_purchase_sent: {p.meta_purchase_sent}")
        print(f"   meta_event_id: {p.meta_event_id}")
        
        # Resetar flag para testar (OPCIONAL)
        if p.meta_purchase_sent:
            resposta = input("\n⚠️  Meta Purchase já foi enviado. Deseja resetar flag e reenviar? (s/N): ").strip().lower()
            if resposta == 's':
                p.meta_purchase_sent = False
                p.meta_event_id = None
                p.meta_purchase_sent_at = None
                db.session.commit()
                print("✅ Flag resetada")
            else:
                print("ℹ️  Mantendo flag - função deve pular envio")
        
        print(f"\n🚀 Enviando Meta Pixel Purchase...")
        try:
            send_meta_pixel_purchase_event(p)
            db.session.commit()
            
            # Recarregar
            db.session.refresh(p)
            
            print(f"\n✅ Após o envio:")
            print(f"   meta_purchase_sent: {p.meta_purchase_sent}")
            print(f"   meta_event_id: {p.meta_event_id}")
            print(f"   meta_purchase_sent_at: {p.meta_purchase_sent_at}")
            
            if p.meta_purchase_sent:
                print(f"\n✅ Purchase enviado com sucesso!")
            else:
                print(f"\n⚠️  Purchase NÃO foi enviado (verificar logs)")
                
        except Exception as e:
            print(f"\n❌ Erro ao enviar Purchase: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_resend_purchase()

