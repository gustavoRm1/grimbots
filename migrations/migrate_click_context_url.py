"""Idempotente: cria coluna click_context_url em payments/payment se não existir.
Execute: python migrations/migrate_click_context_url.py
"""
import sys
from pathlib import Path

from sqlalchemy import inspect, text

# Garantir import de app/db mesmo fora do PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app, db  # noqa: E402


def run():
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)

        tables = insp.get_table_names()
        if "payments" in tables:
            table = "payments"
        elif "payment" in tables:
            table = "payment"
        else:
            raise RuntimeError("❌ Nenhuma tabela payment(s) encontrada")

        cols = [c["name"] for c in insp.get_columns(table)]
        if "click_context_url" in cols:
            print(f"✅ {table}.click_context_url já existe — nada a fazer")
            return

        print(f"➕ Criando coluna click_context_url em {table}...")
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN click_context_url TEXT"))
        db.session.commit()
        print("✅ Migração concluída com sucesso")


if __name__ == "__main__":
    run()
