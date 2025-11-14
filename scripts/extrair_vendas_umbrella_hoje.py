#!/usr/bin/env python3
"""
Script para extrair todas as vendas do UmbrellaPay de hoje e exportar para CSV
Data: 2025-11-13
"""

import os
import sys
import csv
from datetime import datetime, date, timedelta
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app import app, db
    from models import Payment
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("Certifique-se de estar executando do diretório raiz do projeto")
    sys.exit(1)

def extrair_vendas_umbrella_hoje():
    """Extrai todas as vendas do UmbrellaPay de hoje"""
    with app.app_context():
        # Data de hoje (início do dia)
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        amanha = hoje + timedelta(days=1)
        
        # 1. TODAS AS VENDAS DO UMBRELLAPAY HOJE
        hoje_date = hoje.date()
        
        todas_vendas = Payment.query.filter(
            Payment.gateway_type == 'umbrellapag',
            Payment.created_at >= hoje,
            Payment.created_at < amanha
        ).order_by(Payment.created_at.desc()).all()
        
        print(f"==========================================")
        print(f"  EXTRAÇÃO - VENDAS UMBRELLAPAY HOJE")
        print(f"==========================================")
        print(f"Data: {hoje_date}")
        print(f"")
        
        # 2. VENDAS PAGAS DO UMBRELLAPAY HOJE
        vendas_pagas = Payment.query.filter(
            Payment.gateway_type == 'umbrellapag',
            Payment.status == 'paid',
            Payment.paid_at >= hoje,
            Payment.paid_at < amanha
        ).order_by(Payment.paid_at.desc()).all()
        
        # 3. RESUMO ESTATÍSTICO
        total_vendas = len(todas_vendas)
        total_pagas = len(vendas_pagas)
        total_pendentes = len([v for v in todas_vendas if v.status == 'pending'])
        total_falhadas = len([v for v in todas_vendas if v.status == 'failed'])
        valor_total_pago = sum([v.amount for v in vendas_pagas]) if vendas_pagas else 0
        valor_total_gerado = sum([v.amount for v in todas_vendas]) if todas_vendas else 0
        purchase_enviados = len([v for v in todas_vendas if v.meta_purchase_sent])
        com_tracking_token = len([v for v in todas_vendas if v.tracking_token])
        com_fbc = len([v for v in todas_vendas if v.fbc])
        com_pageview_event_id = len([v for v in todas_vendas if v.pageview_event_id])
        
        print(f"1. RESUMO ESTATÍSTICO:")
        print(f"---------------------------------------")
        print(f"Total de vendas: {total_vendas}")
        print(f"Vendas pagas: {total_pagas}")
        print(f"Vendas pendentes: {total_pendentes}")
        print(f"Vendas falhadas: {total_falhadas}")
        print(f"Valor total pago: R$ {valor_total_pago:.2f}")
        print(f"Valor total gerado: R$ {valor_total_gerado:.2f}")
        print(f"Purchase enviados: {purchase_enviados}")
        print(f"Com tracking_token: {com_tracking_token}")
        print(f"Com fbc: {com_fbc}")
        print(f"Com pageview_event_id: {com_pageview_event_id}")
        print(f"")
        
        # 4. EXPORTAR PARA CSV
        output_dir = Path("./exports")
        output_dir.mkdir(exist_ok=True)
        
        # 4.1. TODAS AS VENDAS
        data_str = hoje_date.isoformat()
        csv_file_todas = output_dir / f"vendas_umbrella_todas_{data_str}.csv"
        with open(csv_file_todas, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'id', 'payment_id', 'status', 'gateway_type', 'gateway_transaction_id',
                'gateway_transaction_hash', 'amount', 'net_amount', 'customer_name',
                'customer_username', 'customer_user_id', 'product_name', 'product_description',
                'tracking_token', 'pageview_event_id', 'fbp', 'fbc', 'fbclid',
                'utm_source', 'utm_campaign', 'utm_medium', 'utm_content', 'utm_term',
                'campaign_code', 'meta_purchase_sent', 'meta_event_id', 'meta_purchase_sent_at',
                'created_at', 'paid_at', 'updated_at'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for venda in todas_vendas:
                writer.writerow({
                    'id': venda.id,
                    'payment_id': venda.payment_id,
                    'status': venda.status,
                    'gateway_type': venda.gateway_type,
                    'gateway_transaction_id': venda.gateway_transaction_id,
                    'gateway_transaction_hash': venda.gateway_transaction_hash,
                    'amount': venda.amount,
                    'net_amount': venda.net_amount,
                    'customer_name': venda.customer_name,
                    'customer_username': venda.customer_username,
                    'customer_user_id': venda.customer_user_id,
                    'product_name': venda.product_name,
                    'product_description': venda.product_description,
                    'tracking_token': venda.tracking_token,
                    'pageview_event_id': venda.pageview_event_id,
                    'fbp': venda.fbp,
                    'fbc': venda.fbc,
                    'fbclid': venda.fbclid,
                    'utm_source': venda.utm_source,
                    'utm_campaign': venda.utm_campaign,
                    'utm_medium': venda.utm_medium,
                    'utm_content': venda.utm_content,
                    'utm_term': venda.utm_term,
                    'campaign_code': venda.campaign_code,
                    'meta_purchase_sent': venda.meta_purchase_sent,
                    'meta_event_id': venda.meta_event_id,
                    'meta_purchase_sent_at': venda.meta_purchase_sent_at.isoformat() if venda.meta_purchase_sent_at else None,
                    'created_at': venda.created_at.isoformat() if venda.created_at else None,
                    'paid_at': venda.paid_at.isoformat() if venda.paid_at else None,
                    'updated_at': venda.updated_at.isoformat() if hasattr(venda, 'updated_at') and venda.updated_at else None
                })
        
        print(f"✅ Arquivo criado: {csv_file_todas}")
        print(f"   Total de vendas: {total_vendas}")
        print(f"")
        
        # 4.2. VENDAS PAGAS
        csv_file_pagas = output_dir / f"vendas_umbrella_pagas_{data_str}.csv"
        with open(csv_file_pagas, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for venda in vendas_pagas:
                writer.writerow({
                    'id': venda.id,
                    'payment_id': venda.payment_id,
                    'status': venda.status,
                    'gateway_type': venda.gateway_type,
                    'gateway_transaction_id': venda.gateway_transaction_id,
                    'gateway_transaction_hash': venda.gateway_transaction_hash,
                    'amount': venda.amount,
                    'net_amount': venda.net_amount,
                    'customer_name': venda.customer_name,
                    'customer_username': venda.customer_username,
                    'customer_user_id': venda.customer_user_id,
                    'product_name': venda.product_name,
                    'product_description': venda.product_description,
                    'tracking_token': venda.tracking_token,
                    'pageview_event_id': venda.pageview_event_id,
                    'fbp': venda.fbp,
                    'fbc': venda.fbc,
                    'fbclid': venda.fbclid,
                    'utm_source': venda.utm_source,
                    'utm_campaign': venda.utm_campaign,
                    'utm_medium': venda.utm_medium,
                    'utm_content': venda.utm_content,
                    'utm_term': venda.utm_term,
                    'campaign_code': venda.campaign_code,
                    'meta_purchase_sent': venda.meta_purchase_sent,
                    'meta_event_id': venda.meta_event_id,
                    'meta_purchase_sent_at': venda.meta_purchase_sent_at.isoformat() if venda.meta_purchase_sent_at else None,
                    'created_at': venda.created_at.isoformat() if venda.created_at else None,
                    'paid_at': venda.paid_at.isoformat() if venda.paid_at else None,
                    'updated_at': venda.updated_at.isoformat() if hasattr(venda, 'updated_at') and venda.updated_at else None
                })
        
        print(f"✅ Arquivo criado: {csv_file_pagas}")
        print(f"   Total de vendas pagas: {total_pagas}")
        print(f"")
        
        # 5. DETALHES DAS VENDAS PAGAS
        print(f"2. DETALHES DAS VENDAS PAGAS:")
        print(f"---------------------------------------")
        for venda in vendas_pagas:
            print(f"Payment ID: {venda.payment_id}")
            print(f"  Status: {venda.status}")
            print(f"  Valor: R$ {venda.amount:.2f}")
            print(f"  Cliente: {venda.customer_name} ({venda.customer_user_id})")
            print(f"  Produto: {venda.product_name}")
            print(f"  Tracking Token: {venda.tracking_token}")
            print(f"  PageView Event ID: {venda.pageview_event_id}")
            print(f"  FBP: {'✅' if venda.fbp else '❌'}")
            print(f"  FBC: {'✅' if venda.fbc else '❌'}")
            print(f"  FBClid: {venda.fbclid[:50] if venda.fbclid else 'N/A'}...")
            print(f"  Meta Purchase: {'✅' if venda.meta_purchase_sent else '❌'}")
            print(f"  Meta Event ID: {venda.meta_event_id}")
            print(f"  Criado em: {venda.created_at}")
            print(f"  Pago em: {venda.paid_at}")
            print(f"")
        
        print(f"==========================================")
        print(f"  EXTRAÇÃO CONCLUÍDA")
        print(f"==========================================")
        print(f"Arquivos salvos em: {output_dir}")
        print(f"")

if __name__ == '__main__':
    try:
        extrair_vendas_umbrella_hoje()
    except Exception as e:
        print(f"❌ Erro ao extrair vendas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

