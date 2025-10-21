#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para investigar problema de contagem de vendas no dashboard
"""

import sqlite3
import os

def investigate_sales_counting():
    """Investiga por que vendas não estão sendo contabilizadas no dashboard"""
    
    db_path = "instance/saas_bot_manager.db"
    
    if not os.path.exists(db_path):
        print(f"BANCO NAO ENCONTRADO: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("INVESTIGANDO PROBLEMA DE CONTAGEM DE VENDAS...")
        print("=" * 70)
        
        # 1. VERIFICAR TODOS OS USUARIOS E SUAS VENDAS
        print("\n1. USUARIOS E SUAS VENDAS:")
        print("-" * 50)
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.total_sales as vendas_dashboard,
                u.total_revenue as receita_dashboard,
                u.last_sale_date,
                COUNT(p.id) as vendas_reais,
                SUM(p.amount) as receita_real,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as vendas_pagas,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga
            FROM users u
            LEFT JOIN bots b ON u.id = b.user_id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY u.id
            ORDER BY u.id
        """)
        
        users_data = cursor.fetchall()
        for row in users_data:
            print(f"  Usuario {row['id']}: {row['username']}")
            print(f"    Dashboard: {row['vendas_dashboard']} vendas | R$ {row['receita_dashboard'] or 0:,.2f}")
            print(f"    Real: {row['vendas_reais']} vendas | R$ {row['receita_real'] or 0:,.2f}")
            print(f"    Pagas: {row['vendas_pagas']} vendas | R$ {row['receita_paga'] or 0:,.2f}")
            
            # Verificar discrepancia
            if row['vendas_dashboard'] != row['vendas_pagas'] or row['receita_dashboard'] != row['receita_paga']:
                print(f"    ERRO - DISCREPANCIA ENCONTRADA!")
                print(f"    Dashboard vs Real: {row['vendas_dashboard']} vs {row['vendas_pagas']}")
                print(f"    Receita vs Real: R$ {row['receita_dashboard'] or 0:,.2f} vs R$ {row['receita_paga'] or 0:,.2f}")
            else:
                print(f"    OK - Dados consistentes")
            print()
        
        # 2. VERIFICAR GATEWAYS E SUAS VENDAS
        print("\n2. GATEWAYS E SUAS VENDAS:")
        print("-" * 50)
        
        cursor.execute("""
            SELECT 
                g.id,
                g.gateway_type,
                g.user_id,
                u.username,
                g.total_transactions as transacoes_gateway,
                g.successful_transactions as sucessos_gateway,
                COUNT(p.id) as pagamentos_reais,
                SUM(p.amount) as receita_real,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as pagamentos_pagos,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga
            FROM gateways g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN bots b ON u.id = b.user_id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY g.id
            ORDER BY g.id
        """)
        
        gateways_data = cursor.fetchall()
        for row in gateways_data:
            print(f"  Gateway {row['id']}: {row['gateway_type']} (Usuario: {row['username']})")
            print(f"    Gateway stats: {row['transacoes_gateway']} transacoes | {row['sucessos_gateway']} sucessos")
            print(f"    Real: {row['pagamentos_reais']} pagamentos | R$ {row['receita_real'] or 0:,.2f}")
            print(f"    Pagos: {row['pagamentos_pagos']} pagamentos | R$ {row['receita_paga'] or 0:,.2f}")
            
            # Verificar discrepancia
            if row['successful_transactions'] != row['pagamentos_pagos']:
                print(f"    ERRO - DISCREPANCIA NO GATEWAY!")
                print(f"    Gateway vs Real: {row['successful_transactions']} vs {row['pagamentos_pagos']}")
            else:
                print(f"    OK - Gateway consistente")
            print()
        
        # 3. VERIFICAR BOTS E SUAS VENDAS
        print("\n3. BOTS E SUAS VENDAS:")
        print("-" * 50)
        
        cursor.execute("""
            SELECT 
                b.id,
                b.name,
                b.user_id,
                u.username,
                b.total_sales as vendas_bot,
                b.total_revenue as receita_bot,
                COUNT(p.id) as pagamentos_reais,
                SUM(p.amount) as receita_real,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as pagamentos_pagos,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga
            FROM bots b
            JOIN users u ON b.user_id = u.id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY b.id
            ORDER BY b.id
        """)
        
        bots_data = cursor.fetchall()
        for row in bots_data:
            print(f"  Bot {row['id']}: {row['name']} (Usuario: {row['username']})")
            print(f"    Bot stats: {row['vendas_bot']} vendas | R$ {row['receita_bot'] or 0:,.2f}")
            print(f"    Real: {row['pagamentos_reais']} pagamentos | R$ {row['receita_real'] or 0:,.2f}")
            print(f"    Pagos: {row['pagamentos_pagos']} pagamentos | R$ {row['receita_paga'] or 0:,.2f}")
            
            # Verificar discrepancia
            if row['vendas_bot'] != row['pagamentos_pagos'] or row['receita_bot'] != row['receita_paga']:
                print(f"    ERRO - DISCREPANCIA NO BOT!")
                print(f"    Bot vs Real: {row['vendas_bot']} vs {row['pagamentos_pagos']}")
                print(f"    Receita vs Real: R$ {row['receita_bot'] or 0:,.2f} vs R$ {row['receita_paga'] or 0:,.2f}")
            else:
                print(f"    OK - Bot consistente")
            print()
        
        # 4. VERIFICAR PAGAMENTOS POR GATEWAY E DATA
        print("\n4. PAGAMENTOS POR GATEWAY E DATA:")
        print("-" * 50)
        
        cursor.execute("""
            SELECT 
                p.gateway_type,
                DATE(p.created_at) as data,
                COUNT(*) as total_pagamentos,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as pagamentos_pagos,
                SUM(p.amount) as receita_total,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_paga,
                u.username
            FROM payments p
            JOIN bots b ON p.bot_id = b.id
            JOIN users u ON b.user_id = u.id
            GROUP BY p.gateway_type, DATE(p.created_at), u.id
            ORDER BY p.gateway_type, DATE(p.created_at) DESC
        """)
        
        payments_by_gateway = cursor.fetchall()
        for row in payments_by_gateway:
            print(f"  {row['data']} | {row['gateway_type']:<12} | {row['username']:<15} | {row['total_pagamentos']} pagamentos | R$ {row['receita_total']:,.2f} | Pagos: {row['pagamentos_pagos']} | R$ {row['receita_paga']:,.2f}")
        
        # 5. VERIFICAR SE HÁ PAGAMENTOS SEM GATEWAY ASSOCIADO
        print("\n5. VERIFICAR PAGAMENTOS SEM GATEWAY:")
        print("-" * 50)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.gateway_type,
                p.amount,
                p.status,
                p.created_at,
                b.name as bot_name,
                u.username
            FROM payments p
            JOIN bots b ON p.bot_id = b.id
            JOIN users u ON b.user_id = u.id
            WHERE p.gateway_type IS NULL OR p.gateway_type = ''
            ORDER BY p.created_at DESC
        """)
        
        payments_no_gateway = cursor.fetchall()
        if payments_no_gateway:
            print("  Pagamentos sem gateway encontrados:")
            for row in payments_no_gateway:
                print(f"    ID {row['id']} | {row['created_at'][:10]} | R$ {row['amount']:,.2f} | {row['status']} | {row['username']} | {row['bot_name']}")
        else:
            print("  OK - Todos os pagamentos têm gateway associado")
        
        conn.close()
        
    except Exception as e:
        print(f"ERRO ao acessar banco: {e}")

if __name__ == "__main__":
    investigate_sales_counting()
