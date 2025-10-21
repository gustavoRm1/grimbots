#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar as últimas vendas do sistema
"""

import sqlite3
import json
from datetime import datetime, timedelta
import sys
import os

def get_recent_sales():
    """Busca as últimas vendas do sistema"""
    
    # Caminho do banco
    db_path = "instance/saas_bot_manager.db"
    
    if not os.path.exists(db_path):
        print(f"BANCO NAO ENCONTRADO: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("BUSCANDO ULTIMAS VENDAS...")
        print("=" * 60)
        
        # 1. VENDAS POR GATEWAY (ultimos 7 dias)
        print("\nVENDAS POR GATEWAY (ultimos 7 dias):")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                g.gateway_type,
                COUNT(*) as total_vendas,
                SUM(g.total_sales) as receita_total,
                AVG(g.total_sales) as ticket_medio
            FROM gateways g
            WHERE g.last_sale_date >= date('now', '-7 days')
            GROUP BY g.gateway_type
            ORDER BY receita_total DESC
        """)
        
        gateway_sales = cursor.fetchall()
        if gateway_sales:
            for row in gateway_sales:
                print(f"  {row['gateway_type']:<15} | {row['total_vendas']:>3} vendas | R$ {row['receita_total']:>8.2f} | Ticket: R$ {row['ticket_medio']:>6.2f}")
        else:
            print("  Nenhuma venda nos ultimos 7 dias")
        
        # 2. ULTIMAS VENDAS DETALHADAS
        print("\nULTIMAS 10 VENDAS:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                g.gateway_type,
                g.total_sales as valor,
                g.last_sale_date as data_venda,
                g.total_sales_count as total_vendas,
                u.username,
                b.name as bot_name
            FROM gateways g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN bots b ON g.user_id = b.user_id
            WHERE g.last_sale_date IS NOT NULL
            ORDER BY g.last_sale_date DESC
            LIMIT 10
        """)
        
        recent_sales = cursor.fetchall()
        if recent_sales:
            for row in recent_sales:
                print(f"  {row['data_venda']:<10} | {row['gateway_type']:<12} | R$ {row['valor']:>8.2f} | {row['username']:<15} | {row['bot_name'] or 'N/A'}")
        else:
            print("  Nenhuma venda encontrada")
        
        # 3. VENDAS HOJE
        print("\nVENDAS DE HOJE:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                g.gateway_type,
                COUNT(*) as vendas_hoje,
                SUM(g.total_sales) as receita_hoje
            FROM gateways g
            WHERE g.last_sale_date = date('now')
            GROUP BY g.gateway_type
        """)
        
        today_sales = cursor.fetchall()
        if today_sales:
            total_today = 0
            for row in today_sales:
                print(f"  {row['gateway_type']:<15} | {row['vendas_hoje']:>3} vendas | R$ {row['receita_hoje']:>8.2f}")
                total_today += row['receita_hoje']
            print(f"  {'TOTAL HOJE':<15} | {'':>3} vendas | R$ {total_today:>8.2f}")
        else:
            print("  Nenhuma venda hoje")
        
        # 4. TOP USUARIOS (vendas)
        print("\nTOP 5 USUARIOS (por receita):")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                u.username,
                u.total_revenue as receita_total,
                u.total_sales as vendas_total,
                u.last_sale_date
            FROM users u
            WHERE u.total_revenue > 0
            ORDER BY u.total_revenue DESC
            LIMIT 5
        """)
        
        top_users = cursor.fetchall()
        if top_users:
            for i, row in enumerate(top_users, 1):
                print(f"  {i}º {row['username']:<20} | R$ {row['receita_total']:>8.2f} | {row['vendas_total']:>3} vendas | Ultima: {row['last_sale_date'] or 'N/A'}")
        else:
            print("  Nenhum usuario com vendas")
        
        # 5. RESUMO GERAL
        print("\nRESUMO GERAL:")
        print("-" * 40)
        
        cursor.execute("SELECT COUNT(*) as total_usuarios FROM users")
        total_users = cursor.fetchone()['total_usuarios']
        
        cursor.execute("SELECT SUM(total_revenue) as receita_total FROM users")
        total_revenue = cursor.fetchone()['receita_total'] or 0
        
        cursor.execute("SELECT SUM(total_sales) as vendas_total FROM users")
        total_sales = cursor.fetchone()['vendas_total'] or 0
        
        cursor.execute("SELECT COUNT(*) as bots_ativos FROM bots WHERE is_active = 1")
        active_bots = cursor.fetchone()['bots_ativos']
        
        print(f"  Usuarios cadastrados: {total_users}")
        print(f"  Bots ativos: {active_bots}")
        print(f"  Receita total: R$ {total_revenue:,.2f}")
        print(f"  Vendas totais: {total_sales}")
        print(f"  Ticket medio: R$ {(total_revenue/total_sales if total_sales > 0 else 0):,.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERRO ao acessar banco: {e}")

if __name__ == "__main__":
    get_recent_sales()
