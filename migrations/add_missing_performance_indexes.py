#!/usr/bin/env python3
"""
Migration: Adicionar índices de performance faltantes
======================================================
Cria 3 índices em bot_users e 1 composto em bot_messages.

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


INDEXES = [
    # (nome, tabela, colunas, razão)
    ("idx_bot_users_last_interaction", "bot_users", "last_interaction",
     "ALTA: dashboard ordena leads recentes por last_interaction sem índice"),
    ("idx_bot_users_archived", "bot_users", "archived",
     "ALTA: toda query de leads filtra archived=False, sem índice causa seq scan"),
    ("idx_bot_messages_bot_user_created", "bot_messages", "bot_id, bot_user_id, created_at",
     "ALTA: queries de histórico de mensagens filtram por bot_id+bot_user_id+order by created_at"),
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
