"""
Extrair Vendas Paradise (21-27 de Outubro) - CONFIRMADAS E PAGAS
Autor: Senior QI 500 + QI 502 (André - Especialista QI 505)
"""

from app import app, db
from models import Payment, Bot, User
from datetime import datetime, timedelta
import csv

def extrair_vendas_paradise():
    """
    Extrai vendas confirmadas e pagas do Paradise entre 21-27 de Outubro
    
    ANÁLISE SENIOR QI 500 + QI 505:
    - Período crítico: 21/10 a 27/10 (problema no gateway)
    - Foco: Apenas vendas PAID (confirmadas)
    - Gateway: Paradise apenas
    """
    
    with app.app_context():
        print("=" * 80)
        print("📊 EXTRAÇÃO - VENDAS PARADISE (21-27 OUTUBRO)")
        print("=" * 80)
        
        # Definir período
        start_date = datetime(2025, 10, 21, 0, 0, 0)
        end_date = datetime(2025, 10, 27, 23, 59, 59)
        
        print(f"\n📅 Período: {start_date.date()} até {end_date.date()}")
        print(f"🟣 Gateway: Paradise")
        print(f"✅ Status: PAID (Confirmadas e Pagas)")
        
        # Buscar vendas
        vendas = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'paid',
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).order_by(Payment.created_at).all()
        
        print(f"\n📊 TOTAL DE VENDAS ENCONTRADAS: {len(vendas)}")
        
        if not vendas:
            print("❌ Nenhuma venda encontrada no período!")
            return
        
        # Preparar dados para CSV
        csv_data = []
        total_revenue = 0
        
        for venda in vendas:
            # Buscar dados do bot e owner
            bot = Bot.query.get(venda.bot_id)
            owner = None
            bot_name = "N/A"
            owner_email = "N/A"
            
            if bot:
                bot_name = bot.name
                owner = User.query.get(bot.user_id)
                if owner:
                    owner_email = owner.email
            
            # Formatar dados
            row = {
                'ID': venda.id,
                'Payment_ID': venda.payment_id,
                'Gateway_Transaction_ID': venda.gateway_transaction_id,
                'Data': venda.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Valor': f"R$ {venda.amount:.2f}",
                'Status': venda.status,
                'Cliente': venda.customer_name or "N/A",
                'Username': venda.customer_username or "N/A",
                'Produto': venda.product_name or "N/A",
                'Bot_ID': venda.bot_id,
                'Bot_Name': bot_name,
                'Owner_Email': owner_email,
                'Gateway': venda.gateway_type,
                'Is_Downsell': venda.is_downsell,
                'Downsell_Index': venda.downsell_index or "N/A",
                'Order_Bump': venda.order_bump_accepted,
                'Paid_At': venda.paid_at.strftime('%Y-%m-%d %H:%M:%S') if venda.paid_at else "N/A",
                'PIX_Code': venda.product_description[:100] if venda.product_description else "N/A"
            }
            
            csv_data.append(row)
            total_revenue += venda.amount
        
        # Gerar CSV
        filename = f'vendas_paradise_{start_date.date()}_to_{end_date.date()}.csv'
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if csv_data:
                fieldnames = csv_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in csv_data:
                    writer.writerow(row)
        
        print(f"\n✅ CSV GERADO: {filename}")
        print(f"📊 Total de linhas: {len(csv_data)}")
        print(f"💰 Receita Total: R$ {total_revenue:.2f}")
        
        # Resumo por dia
        print("\n" + "=" * 80)
        print("📅 RESUMO POR DIA:")
        print("=" * 80)
        
        vendas_por_dia = {}
        for venda in vendas:
            dia = venda.created_at.date()
            if dia not in vendas_por_dia:
                vendas_por_dia[dia] = {'count': 0, 'revenue': 0}
            vendas_por_dia[dia]['count'] += 1
            vendas_por_dia[dia]['revenue'] += venda.amount
        
        for dia in sorted(vendas_por_dia.keys()):
            print(f"{dia.strftime('%d/%m/%Y')}: {vendas_por_dia[dia]['count']} vendas - R$ {vendas_por_dia[dia]['revenue']:.2f}")
        
        print("\n" + "=" * 80)
        print("💡 ANÁLISE SENIOR QI 505 (André):")
        print("=" * 80)
        print(f"Total de vendas: {len(vendas)}")
        print(f"Receita total: R$ {total_revenue:.2f}")
        print(f"Ticket médio: R$ {total_revenue / len(vendas):.2f}")
        print(f"\n📁 Arquivo gerado: {filename}")
        print(f"💾 Você pode baixar o CSV e enviar para análise!")

if __name__ == '__main__':
    extrair_vendas_paradise()

