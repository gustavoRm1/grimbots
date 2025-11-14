#!/usr/bin/env python3
"""
Script para analisar a SEQUÊNCIA de webhooks recebidos
Identifica se houve webhook com PAID antes do WAITING_PAYMENT
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

load_dotenv()

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

def analisar_sequencia_webhooks():
    with app.app_context():
        print("=" * 100)
        print("  🔍 ANÁLISE DE SEQUÊNCIA DE WEBHOOKS")
        print("  Objetivo: Verificar se houve webhook PAID antes de WAITING_PAYMENT")
        print("=" * 100)
        print()
        
        # Lista de gateway IDs dos pagamentos desincronizados
        gateway_ids = [
            "bfc9a555-113b-432f-8c1b-f7963308d325",
            "4ee2b3c0-0910-41aa-9aa4-64af9b387028",
            "b4eba878-a6a5-472e-9feb-ad3e4f434513",
            "d5b97666-9eaf-442e-aaba-eee53e96cad8",
            "61e95772-4cd5-48bd-a3de-4176e29a2569",
            "283f2b4b-f0f4-4460-a405-259443a5cb1f",
            "425a5f31-7733-4682-a07c-4152e2945182",
            "6330117a-cda7-4da7-a65e-82d7d086d95e",
            "8c15646f-3b76-49ea-8dd9-00339536099c",
            "27deeea7-7f4a-4a1b-9145-9a9d558eeacb",
            "feac4996-713b-48ad-929d-2d0c30f856f7"
        ]
        
        resultados = {}
        
        for gateway_id in gateway_ids:
            print("-" * 100)
            print(f"🔍 Gateway ID: {gateway_id}")
            print()
            
            # Buscar TODOS os webhooks para este transaction_id (ordenados por data)
            webhooks = WebhookEvent.query.filter(
                WebhookEvent.gateway_type == 'umbrellapag',
                WebhookEvent.transaction_id == gateway_id
            ).order_by(WebhookEvent.received_at.asc()).all()
            
            if not webhooks:
                print(f"   ❌ Nenhum webhook encontrado")
                print()
                continue
            
            print(f"   📥 Total de webhooks recebidos: {len(webhooks)}")
            print()
            
            sequencia = []
            
            for i, webhook in enumerate(webhooks, 1):
                payload = webhook.payload
                status_no_payload = None
                
                if isinstance(payload, dict):
                    # Extrair status do payload
                    if 'data' in payload and isinstance(payload['data'], dict):
                        status_no_payload = payload['data'].get('status')
                    else:
                        status_no_payload = payload.get('status')
                
                status_salvo = webhook.status
                
                print(f"   📨 Webhook {i} (recebido em {webhook.received_at}):")
                print(f"      Status no payload: {status_no_payload}")
                print(f"      Status salvo no DB: {status_salvo}")
                print(f"      Dedup Key: {webhook.dedup_key}")
                print()
                
                sequencia.append({
                    "received_at": webhook.received_at.isoformat() if webhook.received_at else None,
                    "status_payload": status_no_payload,
                    "status_salvo": status_salvo,
                    "dedup_key": webhook.dedup_key
                })
                
                # Verificar se há contradição
                if status_no_payload and status_salvo:
                    status_payload_upper = str(status_no_payload).upper()
                    status_salvo_upper = str(status_salvo).upper()
                    
                    if status_payload_upper == 'WAITING_PAYMENT' and status_salvo_upper == 'PAID':
                        print(f"      ⚠️  CONTRADIÇÃO DETECTADA!")
                        print(f"         Payload diz: {status_no_payload}")
                        print(f"         DB diz: {status_salvo}")
                        print(f"         🚨 Webhook WAITING_PAYMENT foi salvo com status PAID!")
                        print()
            
            # Verificar se houve webhook PAID antes
            teve_paid = False
            teve_waiting = False
            
            for item in sequencia:
                status_p = str(item['status_payload']).upper() if item['status_payload'] else ''
                status_s = str(item['status_salvo']).upper() if item['status_salvo'] else ''
                
                if 'PAID' in status_p or 'PAID' in status_s:
                    teve_paid = True
                if 'WAITING' in status_p or 'WAITING' in status_s:
                    teve_waiting = True
            
            print(f"   📊 Análise:")
            print(f"      Teve webhook PAID: {'✅ SIM' if teve_paid else '❌ NÃO'}")
            print(f"      Teve webhook WAITING_PAYMENT: {'✅ SIM' if teve_waiting else '❌ NÃO'}")
            
            if teve_paid and teve_waiting:
                print(f"      ⚠️  ATENÇÃO: Houve webhook PAID e depois WAITING_PAYMENT!")
                print(f"         Isso pode indicar que o gateway enviou PAID e depois reverteu para WAITING")
            elif teve_paid and not teve_waiting:
                print(f"      ✅ Webhook PAID foi recebido (pagamento confirmado)")
            elif not teve_paid and teve_waiting:
                print(f"      ⚠️  Apenas webhook WAITING_PAYMENT foi recebido")
                print(f"         Mas o sistema marcou como PAID - possível uso do botão 'Verificar Pagamento'")
            
            print()
            
            resultados[gateway_id] = {
                "total_webhooks": len(webhooks),
                "sequencia": sequencia,
                "teve_paid": teve_paid,
                "teve_waiting": teve_waiting
            }
        
        # Resumo final
        print("=" * 100)
        print("  📊 RESUMO FINAL")
        print("=" * 100)
        print()
        
        com_paid = sum(1 for r in resultados.values() if r['teve_paid'])
        com_waiting = sum(1 for r in resultados.values() if r['teve_waiting'])
        com_ambos = sum(1 for r in resultados.values() if r['teve_paid'] and r['teve_waiting'])
        
        print(f"✅ Webhooks com PAID: {com_paid}/{len(resultados)}")
        print(f"⏳ Webhooks com WAITING_PAYMENT: {com_waiting}/{len(resultados)}")
        print(f"⚠️  Webhooks com AMBOS (PAID + WAITING): {com_ambos}/{len(resultados)}")
        print()
        
        if com_ambos > 0:
            print("🚨 CONCLUSÃO CRÍTICA:")
            print("   Alguns pagamentos receberam webhook PAID e depois WAITING_PAYMENT.")
            print("   Isso indica que o gateway:")
            print("   1. Enviou webhook PAID (pagamento confirmado)")
            print("   2. Depois enviou webhook WAITING_PAYMENT (reversão?)")
            print("   3. O sistema processou o PAID e marcou como pago")
            print("   4. O painel do gateway pode estar mostrando o status mais recente (WAITING)")
            print()
            print("💡 AÇÃO: Verificar com o gateway se houve reversão ou se é apenas delay no painel")
        
        # Exportar para JSON
        output_file = project_root / "exports" / f"sequencia_webhooks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Dados exportados para: {output_file}")
        print()

if __name__ == "__main__":
    analisar_sequencia_webhooks()

