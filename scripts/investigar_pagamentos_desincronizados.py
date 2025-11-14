#!/usr/bin/env python3
"""
Script para investigar os 10 pagamentos desincronizados
(PAGOS no sistema, mas PENDENTES no gateway)
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Adicionar diretório raiz ao sys.path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Carregar ENCRYPTION_KEY do .env
env_path = project_root / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('ENCRYPTION_KEY='):
                key = line.split('=', 1)[1].strip()
                key = key.strip('"').strip("'")
                if key:
                    os.environ['ENCRYPTION_KEY'] = key
                    break

try:
    from app import app, db
    from models import Payment, WebhookEvent
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    sys.exit(1)

def investigar_pagamentos_desincronizados():
    with app.app_context():
        print("=" * 100)
        print("  🔍 INVESTIGAÇÃO - PAGAMENTOS DESINCRONIZADOS")
        print("  (PAGOS no sistema, mas PENDENTES no gateway)")
        print("=" * 100)
        print()
        
        # Buscar pagamentos UmbrellaPay PAGOS no sistema
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ontem = hoje - timedelta(days=1)
        
        pagamentos_pagos = Payment.query.filter(
            Payment.gateway_type == 'umbrellapag',
            Payment.status == 'paid',
            Payment.created_at >= ontem
        ).order_by(Payment.paid_at.desc()).all()
        
        print(f"📊 Total de pagamentos UmbrellaPay PAGOS no sistema: {len(pagamentos_pagos)}")
        print()
        
        # Verificar quais não estão na lista de pagos do gateway
        vendas_pagas_gateway = [
            "78366e3e-999b-4a5a-8232-3e442bd480eb",
            "5561f532-9fc2-40f9-bdd6-132be6769bbc",
            "1a71167d-62ea-4ac5-a088-925e5878d0c9",
            "f0212d7f-269e-49dd-aeea-212a521d2fe1",
            "63a02dd9-1d70-48ac-8036-4eff20350d2b"
        ]
        
        desincronizados = []
        
        for payment in pagamentos_pagos:
            gateway_id = payment.gateway_transaction_id
            
            # Verificar se está na lista de pagos do gateway
            if gateway_id not in vendas_pagas_gateway:
                # Verificar se há ID alternativo
                is_alternativo = False
                if gateway_id == "f0212d7f-269e-49dd-aeea-212a521d2e1":
                    # ID alternativo da transação crítica
                    is_alternativo = True
                
                if not is_alternativo:
                    desincronizados.append(payment)
        
        print(f"🚨 Pagamentos DESINCRONIZADOS encontrados: {len(desincronizados)}")
        print()
        
        if desincronizados:
            print("=" * 100)
            print("  DETALHES DOS PAGAMENTOS DESINCRONIZADOS")
            print("=" * 100)
            print()
            
            for i, payment in enumerate(desincronizados[:10], 1):  # Limitar a 10
                print("-" * 100)
                print(f"🔍 Pagamento {i}:")
                print(f"   Payment ID: {payment.payment_id}")
                print(f"   Gateway ID: {payment.gateway_transaction_id}")
                print(f"   Status Sistema: {payment.status}")
                print(f"   Valor: R$ {payment.amount:.2f}")
                print(f"   CPF: {payment.customer_user_id}")
                print(f"   Nome: {payment.customer_name}")
                print(f"   Criado em: {payment.created_at}")
                print(f"   Pago em: {payment.paid_at}")
                print()
                
                # Verificar webhooks recebidos
                webhooks = WebhookEvent.query.filter(
                    WebhookEvent.gateway_type == 'umbrellapag',
                    WebhookEvent.gateway_transaction_id == payment.gateway_transaction_id
                ).order_by(WebhookEvent.created_at.desc()).all()
                
                if webhooks:
                    print(f"   📥 Webhooks recebidos: {len(webhooks)}")
                    for webhook in webhooks[:3]:  # Mostrar últimos 3
                        print(f"      - {webhook.created_at}: Status={webhook.status}")
                else:
                    print(f"   ❌ NENHUM webhook recebido para este pagamento!")
                
                print()
                
                # Verificar logs (sugestão)
                print(f"   🔍 Verificar logs:")
                print(f"      grep -i \"{payment.gateway_transaction_id}\" logs/rq-webhook.log")
                print(f"      grep -i \"{payment.payment_id}\" logs/error.log | grep -i \"verificar\\|verify\"")
                print()
        
        print("=" * 100)
        print("  CONCLUSÃO")
        print("=" * 100)
        print()
        print(f"Total de pagamentos desincronizados: {len(desincronizados)}")
        print()
        print("🚨 AÇÕES RECOMENDADAS:")
        print("1. Verificar logs de webhook para cada pagamento")
        print("2. Verificar se botão 'Verificar Pagamento' foi usado")
        print("3. Consultar API do UmbrellaPay para confirmar status real")
        print("4. Implementar validação dupla no botão")
        print("5. Criar job de sincronização periódica")
        print()

if __name__ == "__main__":
    investigar_pagamentos_desincronizados()

