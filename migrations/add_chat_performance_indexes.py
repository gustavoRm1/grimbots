#!/usr/bin/env python3
"""
Migration: Índices de performance para o Chat do Dashboard
===========================================================
Cria 4 índices compostos para acelerar as queries do /chat.

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
    # (nome, tabela, colunas, condição, razão)
    ("idx_bot_messages_conversation", "bot_messages",
     "bot_id, telegram_user_id, created_at DESC", None,
     "CRÍTICA: query de mensagens do chat filtra por bot_id+telegram_user_id+order by created_at"),

    ("idx_bot_messages_unread", "bot_messages",
     "bot_id, telegram_user_id, direction, is_read",
     "WHERE is_read = false",
     "ALTA: contagem de não lidas filtra por bot_id+telegram_user_id+direction+is_read"),

    ("idx_payments_bot_customer", "payments",
     "bot_id, customer_user_id, status", None,
     "ALTA: filtros de conversa (paid/pix_generated) usam bot_id+customer_user_id+status"),

    ("idx_bot_users_conversations", "bot_users",
     "bot_id, archived, last_interaction DESC", None,
     "MÉDIA: listagem de conversas ordena por last_interaction com filtro bot_id+archived"),
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

        for idx_name, table, columns, condition, reason in INDEXES:
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
                    sql_str = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {table} ({columns})"
                    if condition:
                        sql_str += f" {condition}"
                    sql = text(sql_str)
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
