#!/usr/bin/env python3
"""
Migration v2: Índices de performance para queries críticas
==========================================================
Cria índices ausentes + remove duplicados.
Tudo com CONCURRENTLY — ZERO downtime, ZERO blocking.

ÍNDICES NOVOS:
  idx_payments_customer_user_id         — payments(customer_user_id)
  idx_payments_gateway_txn_hash         — payments(gateway_transaction_hash)
  idx_bot_messages_dir_created          — bot_messages(bot_id, direction, created_at DESC)
  idx_payments_monthly_revenue          — payments(bot_id, status, created_at)
  idx_bot_users_campaign_code           — bot_users(campaign_code)

ÍNDICES DUPLICADOS (remove se existirem):
  idx_bot_users_last_interaction        — duplicado do __table_args__
  idx_bot_users_archived                 — duplicado do __table_args__
  idx_bot_messages_bot_user_created     — duplicado do __table_args__
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from internal_logic.core.extensions import db
from sqlalchemy import inspect, text


CREATE_INDEXES = [
    ("idx_payments_customer_user_id", "payments", "customer_user_id",
     "CRÍTICO: TODAS as queries do chat e remarketing filtram por customer_user_id (SEM ÍNDICE)"),
    ("idx_payments_gateway_txn_hash", "payments", "gateway_transaction_hash",
     "ALTO: webhook matching usa gateway_transaction_hash sozinho (só existe composto)"),
    ("idx_payments_monthly_revenue", "payments", "bot_id, status, created_at",
     "ALTO: dashboard analytics filtra por bot_id + status + período (GROUP BY date)"),
    ("idx_bot_messages_dir_created", "bot_messages", "bot_id, direction, created_at DESC",
     "MÉDIO: contagem de mensagens não lidas por bot (badge do sidebar)"),
    ("idx_bot_users_campaign_code", "bot_users", "campaign_code",
     "BAIXO: corrige bug do model que anulou index=True (campaign_code sem índice hoje)"),
]

DROP_INDEXES = [
    ("idx_bot_users_last_interaction", "bot_users",
     "DUPLICADO: já existe via __table_args__ (idx_bot_users_last_interaction)"),
    ("idx_bot_users_archived", "bot_users",
     "DUPLICADO: já existe via __table_args__ (idx_bot_users_archived)"),
    ("idx_bot_messages_bot_user_created", "bot_messages",
     "DUPLICADO: já existe via __table_args__ (idx_bot_messages_bot_user_created)"),
]


def _index_exists(inspector, table: str, index_name: str) -> bool:
    for index in inspector.get_indexes(table):
        if index['name'] == index_name:
            return True
    return False


def migrate():
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)

        # ── 1. DROP índices duplicados ──
        print(f"\n{'='*60}")
        print("🗑️  REMOVENDO ÍNDICES DUPLICADOS")
        print(f"{'='*60}")
        dropped = 0
        for idx_name, table, reason in DROP_INDEXES:
            if not _index_exists(inspector, table, idx_name):
                print(f"⏭️  {idx_name} — não existe (nada a fazer)")
                continue
            print(f"🔄 {idx_name} — removendo de {table}... ({reason})")
            try:
                with engine.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as conn:
                    conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {idx_name}"))
                print(f"✅ {idx_name} — removido")
                dropped += 1
            except Exception as e:
                print(f"⚠️  {idx_name} — erro ao remover: {e} (pulando)")

        # ── 2. CREATE índices novos ──
        print(f"\n{'='*60}")
        print("🆕  CRIANDO ÍNDICES NOVOS")
        print(f"{'='*60}")
        criados = 0
        ja_existiam = 0
        erros = []

        for idx_name, table, columns, reason in CREATE_INDEXES:
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
                    conn.execute(text(sql_str))
                print(f"✅ {idx_name} — criado com sucesso!")
                criados += 1
            except Exception as e:
                erro_msg = f"❌ {idx_name} — ERRO: {e}"
                print(erro_msg)
                erros.append(erro_msg)

        # ── 3. Resumo ──
        print(f"\n{'='*60}")
        print(f"📊 RESUMO")
        print(f"{'='*60}")
        print(f"   Índices removidos: {dropped}")
        print(f"   Índices criados:   {criados}")
        print(f"   Já existiam:       {ja_existiam}")
        print(f"   Erros:             {len(erros)}")
        if erros:
            print(f"\n⚠️  Erros:")
            for e in erros:
                print(f"   {e}")
            return False

        print(f"\n✅ Migration concluída com sucesso!")
        return True


if __name__ == '__main__':
    migrate()
