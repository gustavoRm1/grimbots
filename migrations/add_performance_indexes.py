#!/usr/bin/env python3
"""
Migration: Adicionar índices de performance críticos
====================================================
Cria 8 índices para eliminar full table scans nas queries mais frequentes.

SEGURO PARA PRODUÇÃO:
- Usa CREATE INDEX CONCURRENTLY (não bloqueia tabelas)
- Cada índice em transação separada (autocommit)
- Verifica existência antes de criar (idempotente)
- Não altera dados, apenas adiciona índices
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from internal_logic.core.extensions import db
from sqlalchemy import inspect, text
from sqlalchemy import create_engine


INDEXES = [
    # (nome, tabela, colunas, razão)
    ("idx_payments_gateway_type", "payments", "gateway_type",
     "CRÍTICO: toda query de webhook filtra por gateway_type sem índice"),
    ("idx_payments_gateway_txn_id", "payments", "gateway_transaction_id",
     "CRÍTICO: webhook matching por transaction_id sem índice"),
    ("idx_payments_paid_at", "payments", "paid_at",
     "ALTA: dashboard ordena por paid_at, causando filesort"),
    ("idx_payments_gateway_type_status", "payments", "gateway_type, status",
     "CRÍTICO: padrão #1 de query — gateway_type + status"),
    ("idx_gateways_gateway_type", "gateways", "gateway_type",
     "CRÍTICO: toda busca de gateway filtra por tipo"),
    ("idx_gateways_user_gateway", "gateways", "user_id, gateway_type",
     "ALTA: 'gateway do user X do tipo Y' sem índice composto"),
    ("idx_commissions_status", "commissions", "status",
     "ALTA: toda query de comissão pendente varre tudo"),
    ("idx_bots_is_active", "bots", "is_active",
     "MÉDIA: todo 'meus bots' filtra por is_active"),
]


def _index_exists(inspector, table: str, index_name: str) -> bool:
    """Verifica se o índice já existe na tabela."""
    for index in inspector.get_indexes(table):
        if index['name'] == index_name:
            return True
    return False


def migrate():
    """Adiciona todos os índices de performance usando CONCURRENTLY."""
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)

        criados = 0
        ja_existiam = 0
        erros = []

        for idx_name, table, columns, reason in INDEXES:
            if _index_exists(inspector, table, idx_name):
                print(f"⏭️  {idx_name} — já existe ({reason})")
                ja_existiam += 1
                continue

            print(f"🔄 {idx_name} — criando em {table}({columns})...")
            print(f"   Motivo: {reason}")

            try:
                # CREATE INDEX CONCURRENTLY requer autocommit (fora de transação)
                # Usamos connection.execution_options(isolation_level="AUTOCOMMIT")
                with engine.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as conn:
                    sql = text(
                        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} "
                        f"ON {table} ({columns})"
                    )
                    conn.execute(sql)
                print(f"✅ {idx_name} — criado com sucesso!")
                criados += 1
            except Exception as e:
                erro_msg = f"❌ {idx_name} — ERRO: {e}"
                print(erro_msg)
                erros.append(erro_msg)

        print(f"\n{'='*60}")
        print(f"📊 RESUMO:")
        print(f"   Criados:     {criados}")
        print(f"   Já existiam: {ja_existiam}")
        print(f"   Erros:       {len(erros)}")
        if erros:
            print(f"\n⚠️  Erros encontrados:")
            for e in erros:
                print(f"   {e}")
            return False

        print(f"✅ Migration concluída com sucesso!")
        return True


if __name__ == '__main__':
    migrate()
