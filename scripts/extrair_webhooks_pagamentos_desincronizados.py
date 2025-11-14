#!/usr/bin/env python3
"""
Script para extrair webhooks dos 10 pagamentos desincronizados
Se o webhook retornou 'paid', então o GATEWAY confirmou o pagamento
"""
import os
import sys
import json
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

def extrair_webhooks_desincronizados():
    with app.app_context():
        print("=" * 100)
        print("  📥 EXTRAÇÃO DE WEBHOOKS - PAGAMENTOS DESINCRONIZADOS")
        print("  Objetivo: Verificar se GATEWAY retornou 'paid' no webhook")
        print("=" * 100)
        print()
        
        # Lista de vendas PAGAS no gateway (fonte da verdade)
        vendas_pagas_gateway = [
            "78366e3e-999b-4a5a-8232-3e442bd480eb",
            "5561f532-9fc2-40f9-bdd6-132be6769bbc",
            "1a71167d-62ea-4ac5-a088-925e5878d0c9",
            "f0212d7f-269e-49dd-aeea-212a521d2fe1",
            "63a02dd9-1d70-48ac-8036-4eff20350d2b"
        ]
        
        # IDs alternativos
        ids_alternativos = {
            "f0212d7f-269e-49dd-aeea-212a521d2e1": "f0212d7f-269e-49dd-aeea-212a521d2fe1"
        }
        
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
        
        # Identificar pagamentos desincronizados
        desincronizados = []
        
        for payment in pagamentos_pagos:
            gateway_id = payment.gateway_transaction_id
            
            # Verificar se está na lista de pagos do gateway
            if gateway_id not in vendas_pagas_gateway:
                # Verificar se é ID alternativo
                is_alternativo = False
                for alt_id, main_id in ids_alternativos.items():
                    if gateway_id == alt_id and main_id in vendas_pagas_gateway:
                        is_alternativo = True
                        break
                
                if not is_alternativo:
                    desincronizados.append(payment)
        
        print(f"🚨 Pagamentos DESINCRONIZADOS encontrados: {len(desincronizados)}")
        print("   (PAGOS no sistema, mas NÃO na lista de pagos do gateway)")
        print()
        
        if not desincronizados:
            print("✅ Nenhum pagamento desincronizado encontrado!")
            return
        
        print("=" * 100)
        print("  ANÁLISE DE WEBHOOKS")
        print("=" * 100)
        print()
        
        resultados = {
            "com_webhook_paid": [],
            "com_webhook_outro_status": [],
            "sem_webhook": []
        }
        
        for i, payment in enumerate(desincronizados, 1):
            print("-" * 100)
            print(f"🔍 Pagamento {i}/{len(desincronizados)}:")
            print(f"   Payment ID: {payment.payment_id}")
            print(f"   Gateway ID: {payment.gateway_transaction_id}")
            print(f"   Status Sistema: {payment.status}")
            print(f"   Valor: R$ {payment.amount:.2f}")
            print(f"   CPF: {payment.customer_user_id}")
            print(f"   Nome: {payment.customer_name}")
            print(f"   Criado em: {payment.created_at}")
            print(f"   Pago em: {payment.paid_at}")
            print()
            
            # Buscar webhooks recebidos para este pagamento
            webhooks = WebhookEvent.query.filter(
                WebhookEvent.gateway_type == 'umbrellapag',
                WebhookEvent.transaction_id == payment.gateway_transaction_id
            ).order_by(WebhookEvent.received_at.desc()).all()
            
            # Se não encontrou por transaction_id, tentar por payment_id no payload
            if not webhooks:
                # Buscar todos os webhooks UmbrellaPay recentes e verificar payload
                todos_webhooks = WebhookEvent.query.filter(
                    WebhookEvent.gateway_type == 'umbrellapag',
                    WebhookEvent.received_at >= payment.created_at
                ).order_by(WebhookEvent.received_at.desc()).all()
                
                for webhook in todos_webhooks:
                    payload = webhook.payload
                    if isinstance(payload, dict):
                        # Verificar se payment_id está no payload
                        metadata = payload.get('data', {}).get('metadata') or payload.get('metadata')
                        if isinstance(metadata, str):
                            try:
                                metadata_dict = json.loads(metadata)
                                if metadata_dict.get('payment_id') == payment.payment_id:
                                    webhooks = [webhook]
                                    break
                            except:
                                pass
                        elif isinstance(metadata, dict):
                            if metadata.get('payment_id') == payment.payment_id:
                                webhooks = [webhook]
                                break
            
            if webhooks:
                print(f"   📥 Webhooks encontrados: {len(webhooks)}")
                print()
                
                # Analisar cada webhook
                for j, webhook in enumerate(webhooks, 1):
                    print(f"   📨 Webhook {j}:")
                    print(f"      Recebido em: {webhook.received_at}")
                    print(f"      Status retornado: {webhook.status}")
                    print(f"      Transaction ID: {webhook.transaction_id}")
                    print()
                    
                    # Mostrar payload completo
                    payload = webhook.payload
                    if isinstance(payload, dict):
                        print(f"      📋 PAYLOAD COMPLETO DO WEBHOOK:")
                        print(f"      {json.dumps(payload, indent=6, ensure_ascii=False)}")
                        print()
                        
                        # Extrair status do payload
                        status_bruto = None
                        if 'data' in payload and isinstance(payload['data'], dict):
                            status_bruto = payload['data'].get('status')
                        else:
                            status_bruto = payload.get('status')
                        
                        if status_bruto:
                            print(f"      🔍 Status bruto no payload: {status_bruto}")
                        
                        # Verificar se status é 'paid'
                        if webhook.status == 'paid' or (status_bruto and str(status_bruto).upper() in ['PAID', 'APPROVED', 'CONFIRMED']):
                            print(f"      ✅ GATEWAY RETORNOU 'PAID' NO WEBHOOK!")
                            print(f"      🎯 CONCLUSÃO: Gateway CONFIRMOU o pagamento via webhook")
                            print(f"      ⚠️  Se o painel mostra 'WAITING_PAYMENT', é problema de delay/sincronização do painel")
                            print()
                            
                            resultados["com_webhook_paid"].append({
                                "payment": payment,
                                "webhook": webhook,
                                "payload": payload
                            })
                        else:
                            print(f"      ⚠️  Status do webhook: {webhook.status} (não é 'paid')")
                            print()
                            
                            resultados["com_webhook_outro_status"].append({
                                "payment": payment,
                                "webhook": webhook,
                                "payload": payload
                            })
                    else:
                        print(f"      ⚠️  Payload não é dict: {type(payload)}")
                        print()
            else:
                print(f"   ❌ NENHUM webhook encontrado para este pagamento!")
                print(f"   🚨 Isso indica que:")
                print(f"      - Webhook não foi enviado pelo gateway")
                print(f"      - OU webhook foi enviado mas não foi processado")
                print(f"      - OU pagamento foi marcado como pago via botão 'Verificar Pagamento'")
                print()
                
                resultados["sem_webhook"].append({
                    "payment": payment,
                    "webhook": None
                })
            
            print()
        
        # Resumo final
        print("=" * 100)
        print("  📊 RESUMO FINAL")
        print("=" * 100)
        print()
        
        print(f"✅ Webhooks com status 'paid': {len(resultados['com_webhook_paid'])}")
        print(f"⚠️  Webhooks com outro status: {len(resultados['com_webhook_outro_status'])}")
        print(f"❌ Sem webhook: {len(resultados['sem_webhook'])}")
        print()
        
        if resultados["com_webhook_paid"]:
            print("=" * 100)
            print("  ✅ EVIDÊNCIAS: GATEWAY CONFIRMOU PAGAMENTO VIA WEBHOOK")
            print("=" * 100)
            print()
            print("🎯 CONCLUSÃO:")
            print("   Se o webhook retornou 'paid', o GATEWAY confirmou o pagamento.")
            print("   Mesmo que o painel mostre 'WAITING_PAYMENT', o pagamento está PAGO.")
            print("   O problema é de delay/sincronização do painel do gateway.")
            print()
            print("📋 Para conversar com o gateway, use estes dados:")
            print()
            
            for item in resultados["com_webhook_paid"]:
                payment = item["payment"]
                webhook = item["webhook"]
                payload = item["payload"]
                
                print(f"   Gateway ID: {payment.gateway_transaction_id}")
                print(f"   Payment ID: {payment.payment_id}")
                print(f"   Webhook recebido em: {webhook.received_at}")
                print(f"   Status no webhook: {webhook.status}")
                print(f"   Payload completo:")
                print(f"   {json.dumps(payload, indent=4, ensure_ascii=False)}")
                print()
        
        if resultados["sem_webhook"]:
            print("=" * 100)
            print("  ⚠️  PAGAMENTOS SEM WEBHOOK")
            print("=" * 100)
            print()
            print("🚨 Estes pagamentos foram marcados como PAGOS, mas NÃO receberam webhook:")
            print()
            
            for item in resultados["sem_webhook"]:
                payment = item["payment"]
                print(f"   - Gateway ID: {payment.gateway_transaction_id}")
                print(f"     Payment ID: {payment.payment_id}")
                print(f"     Pago em: {payment.paid_at}")
                print()
            
            print("💡 Possíveis causas:")
            print("   1. Botão 'Verificar Pagamento' foi usado (consulta manual)")
            print("   2. Webhook não foi enviado pelo gateway")
            print("   3. Webhook foi enviado mas falhou ao processar")
            print()
        
        # Exportar para JSON
        output_file = project_root / "exports" / f"webhooks_desincronizados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        export_data = {
            "data_extracao": datetime.now().isoformat(),
            "total_desincronizados": len(desincronizados),
            "com_webhook_paid": [
                {
                    "payment_id": item["payment"].payment_id,
                    "gateway_transaction_id": item["payment"].gateway_transaction_id,
                    "valor": float(item["payment"].amount),
                    "cpf": item["payment"].customer_user_id,
                    "nome": item["payment"].customer_name,
                    "paid_at": item["payment"].paid_at.isoformat() if item["payment"].paid_at else None,
                    "webhook_received_at": item["webhook"].received_at.isoformat() if item["webhook"].received_at else None,
                    "webhook_status": item["webhook"].status,
                    "webhook_payload": item["payload"]
                }
                for item in resultados["com_webhook_paid"]
            ],
            "com_webhook_outro_status": [
                {
                    "payment_id": item["payment"].payment_id,
                    "gateway_transaction_id": item["payment"].gateway_transaction_id,
                    "webhook_status": item["webhook"].status,
                    "webhook_payload": item["payload"]
                }
                for item in resultados["com_webhook_outro_status"]
            ],
            "sem_webhook": [
                {
                    "payment_id": item["payment"].payment_id,
                    "gateway_transaction_id": item["payment"].gateway_transaction_id,
                    "paid_at": item["payment"].paid_at.isoformat() if item["payment"].paid_at else None
                }
                for item in resultados["sem_webhook"]
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print("=" * 100)
        print(f"  ✅ DADOS EXPORTADOS PARA: {output_file}")
        print("=" * 100)
        print()
        print("📋 Use este arquivo JSON para conversar com o gateway UmbrellaPay")
        print()

if __name__ == "__main__":
    extrair_webhooks_desincronizados()

