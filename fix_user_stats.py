#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corrigir estatísticas de usuários que não estão sendo atualizadas
"""

import sqlite3
import os

def fix_user_stats():
    """Corrige estatísticas de usuários baseado nos pagamentos reais"""
    
    db_path = "instance/saas_bot_manager.db"
    
    if not os.path.exists(db_path):
        print(f"BANCO NAO ENCONTRADO: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("CORRIGINDO ESTATISTICAS DE USUARIOS...")
        print("=" * 60)
        
        # 1. BUSCAR TODOS OS USUARIOS COM DISCREPANCIA
        print("\n1. USUARIOS COM DISCREPANCIA:")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.total_sales as vendas_dashboard,
                u.total_revenue as receita_dashboard,
                COUNT(p.id) as vendas_reais,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_real,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as vendas_pagas
            FROM users u
            LEFT JOIN bots b ON u.id = b.user_id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY u.id
            HAVING u.total_sales != COUNT(CASE WHEN p.status = 'paid' THEN 1 END) 
                OR u.total_revenue != SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END)
        """)
        
        users_with_discrepancy = cursor.fetchall()
        
        if not users_with_discrepancy:
            print("  Nenhuma discrepancia encontrada!")
            conn.close()
            return
        
        for row in users_with_discrepancy:
            print(f"  Usuario {row['id']}: {row['username']}")
            print(f"    Dashboard: {row['vendas_dashboard']} vendas | R$ {row['receita_dashboard'] or 0:,.2f}")
            print(f"    Real: {row['vendas_pagas']} vendas | R$ {row['receita_real'] or 0:,.2f}")
            print()
        
        # 2. CORRIGIR ESTATISTICAS
        print("\n2. CORRIGINDO ESTATISTICAS...")
        print("-" * 40)
        
        for row in users_with_discrepancy:
            user_id = row['id']
            vendas_reais = row['vendas_pagas']
            receita_real = row['receita_real'] or 0
            
            print(f"  Corrigindo usuario {user_id} ({row['username']})...")
            print(f"    Atualizando: {row['vendas_dashboard']} -> {vendas_reais} vendas")
            print(f"    Atualizando: R$ {row['receita_dashboard'] or 0:,.2f} -> R$ {receita_real:,.2f}")
            
            # Atualizar estatísticas do usuário
            cursor.execute("""
                UPDATE users 
                SET 
                    total_sales = ?,
                    total_revenue = ?,
                    last_sale_date = (
                        SELECT MAX(DATE(p.created_at))
                        FROM payments p
                        JOIN bots b ON p.bot_id = b.id
                        WHERE b.user_id = ? AND p.status = 'paid'
                    )
                WHERE id = ?
            """, (vendas_reais, receita_real, user_id, user_id))
            
            print(f"    OK - Usuario {user_id} corrigido!")
        
        # 3. CORRIGIR ESTATISTICAS DOS BOTS
        print("\n3. CORRIGINDO ESTATISTICAS DOS BOTS...")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                b.id,
                b.name,
                b.user_id,
                u.username,
                b.total_sales as vendas_bot,
                b.total_revenue as receita_bot,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as vendas_reais,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_real
            FROM bots b
            JOIN users u ON b.user_id = u.id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY b.id
            HAVING b.total_sales != COUNT(CASE WHEN p.status = 'paid' THEN 1 END)
                OR b.total_revenue != SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END)
        """)
        
        bots_with_discrepancy = cursor.fetchall()
        
        for row in bots_with_discrepancy:
            bot_id = row['id']
            vendas_reais = row['vendas_reais']
            receita_real = row['receita_real'] or 0
            
            print(f"  Corrigindo bot {bot_id} ({row['name']})...")
            print(f"    Atualizando: {row['vendas_bot']} -> {vendas_reais} vendas")
            print(f"    Atualizando: R$ {row['receita_bot'] or 0:,.2f} -> R$ {receita_real:,.2f}")
            
            # Atualizar estatísticas do bot
            cursor.execute("""
                UPDATE bots 
                SET 
                    total_sales = ?,
                    total_revenue = ?
                WHERE id = ?
            """, (vendas_reais, receita_real, bot_id))
            
            print(f"    OK - Bot {bot_id} corrigido!")
        
        # 4. COMMIT DAS ALTERACOES
        print("\n4. SALVANDO ALTERACOES...")
        print("-" * 40)
        
        conn.commit()
        print("  OK - Alteracoes salvas no banco!")
        
        # 5. VERIFICAR RESULTADO
        print("\n5. VERIFICANDO RESULTADO...")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.total_sales,
                u.total_revenue,
                COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as vendas_reais,
                SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita_real
            FROM users u
            LEFT JOIN bots b ON u.id = b.user_id
            LEFT JOIN payments p ON b.id = p.bot_id
            GROUP BY u.id
            ORDER BY u.id
        """)
        
        users_after_fix = cursor.fetchall()
        for row in users_after_fix:
            if row['total_sales'] > 0 or row['total_revenue'] > 0:
                print(f"  Usuario {row['id']}: {row['username']}")
                print(f"    Dashboard: {row['total_sales']} vendas | R$ {row['total_revenue']:,.2f}")
                print(f"    Real: {row['vendas_reais']} vendas | R$ {row['receita_real'] or 0:,.2f}")
                
                if row['total_sales'] == row['vendas_reais'] and row['total_revenue'] == (row['receita_real'] or 0):
                    print(f"    OK - CORRIGIDO COM SUCESSO!")
                else:
                    print(f"    ERRO - AINDA HÁ DISCREPANCIA!")
                print()
        
        conn.close()
        print("\nOK - CORREÇÃO CONCLUÍDA!")
        
    except Exception as e:
        print(f"ERRO ao corrigir estatísticas: {e}")

if __name__ == "__main__":
    fix_user_stats()
