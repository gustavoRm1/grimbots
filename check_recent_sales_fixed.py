#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar as últimas vendas do sistema - VERSÃO CORRIGIDA
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
        
        # 1. VENDAS RECENTES (tabela payments)
        print("\nULTIMAS 10 VENDAS (payments):")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.gateway_type,
                p.amount,
                p.status,
                p.created_at,
                p.paid_at,
                p.customer_name,
                p.customer_username,
                p.product_name,
                b.name as bot_name,
                u.username as owner
            FROM payments p
            JOIN bots b ON p.bot_id = b.id
            JOIN users u ON b.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 10
        """)
        
        recent_payments = cursor.fetchall()
        if recent_payments:
            for row in recent_payments:
                status_icon = "[PAGO]" if row['status'] == 'paid' else "[PEND]" if row['status'] == 'pending' else "[ERRO]"
                print(f"  {status_icon} {row['created_at'][:10]} | {row['gateway_type']:<12} | R$ {row['amount']:>8.2f} | {row['status']:<8} | {row['owner']:<15} | {row['bot_name']}")
        else:
            print("  Nenhuma venda encontrada")
        
        # 2. VENDAS HOJE
        print("\nVENDAS DE HOJE:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                p.gateway_type,
                COUNT(*) as vendas_hoje,
                SUM(p.amount) as receita_hoje,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga
            FROM payments p
            WHERE DATE(p.created_at) = DATE('now')
            GROUP BY p.gateway_type
        """)
        
        today_sales = cursor.fetchall()
        if today_sales:
            total_today = 0
            total_paid_today = 0
            for row in today_sales:
                print(f"  {row['gateway_type']:<15} | {row['vendas_hoje']:>3} vendas | R$ {row['receita_hoje']:>8.2f} | Pago: R$ {row['receita_paga']:>8.2f}")
                total_today += row['receita_hoje']
                total_paid_today += row['receita_paga']
            print(f"  {'TOTAL HOJE':<15} | {'':>3} vendas | R$ {total_today:>8.2f} | Pago: R$ {total_paid_today:>8.2f}")
        else:
            print("  Nenhuma venda hoje")
        
        # 3. VENDAS ULTIMOS 7 DIAS
        print("\nVENDAS ULTIMOS 7 DIAS:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                p.gateway_type,
                COUNT(*) as vendas_7d,
                SUM(p.amount) as receita_7d,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga_7d
            FROM payments p
            WHERE p.created_at >= date('now', '-7 days')
            GROUP BY p.gateway_type
            ORDER BY receita_7d DESC
        """)
        
        week_sales = cursor.fetchall()
        if week_sales:
            total_week = 0
            total_paid_week = 0
            for row in week_sales:
                print(f"  {row['gateway_type']:<15} | {row['vendas_7d']:>3} vendas | R$ {row['receita_7d']:>8.2f} | Pago: R$ {row['receita_paga_7d']:>8.2f}")
                total_week += row['receita_7d']
                total_paid_week += row['receita_paga_7d']
            print(f"  {'TOTAL 7 DIAS':<15} | {'':>3} vendas | R$ {total_week:>8.2f} | Pago: R$ {total_paid_week:>8.2f}")
        else:
            print("  Nenhuma venda nos últimos 7 dias")
        
        # 4. TOP USUARIOS (por receita)
        print("\nTOP 5 USUARIOS (por receita total):")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                u.username,
                u.total_revenue as receita_total,
                u.total_sales as vendas_total,
                u.last_sale_date,
                COUNT(b.id) as bots_count
            FROM users u
            LEFT JOIN bots b ON u.id = b.user_id
            WHERE u.total_revenue > 0
            GROUP BY u.id
            ORDER BY u.total_revenue DESC
            LIMIT 5
        """)
        
        top_users = cursor.fetchall()
        if top_users:
            for i, row in enumerate(top_users, 1):
                print(f"  {i}º {row['username']:<20} | R$ {row['receita_total']:>8.2f} | {row['vendas_total']:>3} vendas | {row['bots_count']:>2} bots | Ultima: {row['last_sale_date'] or 'N/A'}")
        else:
            print("  Nenhum usuario com vendas")
        
        # 5. RESUMO GERAL
        print("\nRESUMO GERAL:")
        print("-" * 40)
        
        cursor.execute("SELECT COUNT(*) as total_usuarios FROM users")
        total_users = cursor.fetchone()['total_usuarios']
        
        cursor.execute("SELECT COUNT(*) as total_bots FROM bots")
        total_bots = cursor.fetchone()['total_bots']
        
        cursor.execute("SELECT COUNT(*) as bots_ativos FROM bots WHERE is_active = 1")
        active_bots = cursor.fetchone()['bots_ativos']
        
        cursor.execute("SELECT SUM(total_revenue) as receita_total FROM users")
        total_revenue = cursor.fetchone()['receita_total'] or 0
        
        cursor.execute("SELECT SUM(total_sales) as vendas_total FROM users")
        total_sales = cursor.fetchone()['vendas_total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total_payments FROM payments")
        total_payments = cursor.fetchone()['total_payments']
        
        cursor.execute("SELECT SUM(amount) as receita_payments FROM payments")
        revenue_payments = cursor.fetchone()['receita_payments'] or 0
        
        cursor.execute("SELECT SUM(amount) as receita_paga FROM payments WHERE status = 'paid'")
        revenue_paid = cursor.fetchone()['receita_paga'] or 0
        
        print(f"  Usuarios cadastrados: {total_users}")
        print(f"  Total de bots: {total_bots}")
        print(f"  Bots ativos: {active_bots}")
        print(f"  Total pagamentos: {total_payments}")
        print(f"  Receita total (users): R$ {total_revenue:,.2f}")
        print(f"  Receita total (payments): R$ {revenue_payments:,.2f}")
        print(f"  Receita paga: R$ {revenue_paid:,.2f}")
        print(f"  Vendas totais: {total_sales}")
        print(f"  Ticket medio: R$ {(revenue_payments/total_payments if total_payments > 0 else 0):,.2f}")
        
        # 6. STATUS DOS PAGAMENTOS
        print("\nSTATUS DOS PAGAMENTOS:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as quantidade,
                SUM(amount) as valor_total
            FROM payments
            GROUP BY status
            ORDER BY quantidade DESC
        """)
        
        payment_status = cursor.fetchall()
        if payment_status:
            for row in payment_status:
                status_icon = "[PAGO]" if row['status'] == 'paid' else "[PEND]" if row['status'] == 'pending' else "[ERRO]"
                print(f"  {status_icon} {row['status']:<10} | {row['quantidade']:>3} pagamentos | R$ {row['valor_total']:>8.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERRO ao acessar banco: {e}")

if __name__ == "__main__":
    get_recent_sales()
