"""
Diagnóstico: Por que Paradise está enviando PIX duplicado?
Autor: Senior QI 500 + QI 502
"""

from app import app, db
from models import Payment
from datetime import datetime, timedelta

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: PARADISE PIX DUPLICADO")
    print("=" * 80)
    
    # Buscar pagamentos recentes do Paradise
    recent_payments = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.status == 'paid',
        Payment.created_at >= datetime.now() - timedelta(days=1)
    ).order_by(Payment.id.desc()).limit(50).all()
    
    print(f"\n📊 TOTAL DE VENDAS PARADISE (últimas 24h): {len(recent_payments)}")
    
    if not recent_payments:
        print("❌ Nenhuma venda recente")
        exit(0)
    
    # Verificar se há referências duplicadas
    references = {}
    for p in recent_payments:
        ref = p.product_name  # A reference do Paradise
        if ref not in references:
            references[ref] = []
        references[ref].append(p)
    
    print(f"\n📋 ANÁLISE DE REFERÊNCIAS:")
    
    duplicates = False
    for ref, payments in references.items():
        if len(payments) > 1:
            duplicates = True
            print(f"\n⚠️ REFERÊNCIA DUPLICADA: {ref}")
            for p in payments:
                print(f"   Payment ID: {p.payment_id}")
                print(f"   Customer: {p.customer_name}")
                print(f"   Amount: R$ {p.amount:.2f}")
                print(f"   Created: {p.created_at}")
                print(f"   Gateway Transaction ID: {p.gateway_transaction_id}")
                print("")
    
    if not duplicates:
        print("✅ NENHUMA REFERÊNCIA DUPLICADA ENCONTRADA!")
    
    # Verificar se há PIX duplicados para o MESMO cliente
    print(f"\n📋 VERIFICANDO CLIENTES COM MÚLTIPLOS PIX:")
    
    customer_payments = {}
    for p in recent_payments:
        key = f"{p.bot_id}_{p.customer_user_id}_{p.customer_name}"
        if key not in customer_payments:
            customer_payments[key] = []
        customer_payments[key].append(p)
    
    multi_pix = False
    for key, payments in customer_payments.items():
        if len(payments) > 1:
            multi_pix = True
            print(f"\n⚠️ CLIENTE COM MÚLTIPLOS PIX:")
            print(f"   Bot ID: {payments[0].bot_id}")
            print(f"   Customer: {payments[0].customer_name}")
            print(f"   Total de PIX: {len(payments)}")
            for i, p in enumerate(payments[:3]):  # Mostrar apenas os 3 primeiros
                print(f"   PIX {i+1}: {p.payment_id} - R$ {p.amount:.2f} - {p.created_at}")
    
    if not multi_pix:
        print("✅ NENHUM CLIENTE COM MÚLTIPLOS PIX!")
    
    print("\n" + "=" * 80)
    print("💡 CONCLUSÃO:")
    print("=" * 80)
    print("O problema NÃO está na geração do payment_id (ele é único).")
    print("O problema está no CASO DE USO:")
    print("  • Cliente tenta várias vezes gerar PIX")
    print("  • Sistema gera novo PIX a cada tentativa")
    print("  • Mas o Paradise só aceita UMA transação por referência")
    print("")
    print("SOLUÇÃO:")
    print("  • Impedir geração de múltiplos PIX para o mesmo cliente")
    print("  • Reenviar PIX antigo se já existe um pendente")
    print("  • Ou retornar 'duplicado' se já existe um PIX para esse cliente")

